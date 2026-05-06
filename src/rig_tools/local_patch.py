from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rig_tools import action_manifest, context_compression, mlx_local, prompt_telemetry, schema_validation


SCHEMA_VERSION = "rig.local_patch.v1"
VALIDATION_SCHEMA_VERSION = "rig.patch_validation.v1"
DEFAULT_TIMEOUT_SECONDS = 600
PATCH_ROOT = ".build/rig/patches"
SANDBOX_ROOT = ".build/rig/sandboxes"
PATCH_PROHIBITED = {".git", ".venv-rig", "Session-bundles", "DerivedData", "__pycache__", ".pytest_cache"}


@dataclass
class PatchResult:
    patch_id: str
    task: str
    status: str
    patch_path: Path
    proposal_markdown_path: Path
    validation_path: Path | None = None
    validation_markdown_path: Path | None = None
    sandbox_path: Path | None = None


def _repo_rel(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_validation_artifacts(repo_root: Path, patch_id: str, result: dict[str, Any]) -> tuple[Path, Path]:
    patch_dir = _patch_dir(repo_root, patch_id)
    json_path = patch_dir / "validation.json"
    md_path = patch_dir / "validation.md"
    _write_json(json_path, result)
    md_path.write_text("\n".join([
        "# Rig Local Patch Validation",
        "",
        f"- Patch ID: `{patch_id}`",
        f"- Status: `{result.get('status')}`",
        f"- Git apply check: `{result.get('git_apply_check_status')}`",
        f"- Sandbox apply: `{result.get('sandbox_apply_status')}`",
    ]) + "\n", encoding="utf-8")
    return json_path, md_path


def _patch_dir(repo_root: Path, patch_id: str) -> Path:
    out = repo_root / PATCH_ROOT / patch_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def _sandbox_dir(repo_root: Path, patch_id: str) -> Path:
    out = repo_root / SANDBOX_ROOT / patch_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def _safe_path(path: str) -> bool:
    if not path or path.startswith("/") or ".." in Path(path).parts:
        return False
    if path.endswith("/") or path.startswith("\\"):
        return False
    return True


def _is_forbidden(path: str) -> bool:
    parts = Path(path).parts
    return any(part in PATCH_PROHIBITED for part in parts)


def _is_binary_patch(text: str) -> bool:
    return "\0" in text or "GIT binary patch" in text


def _has_conflict_markers(text: str) -> bool:
    return any(marker in text for marker in ("<<<<<<<", "=======", ">>>>>>>"))


def _find_diff_start(text: str) -> int:
    markers = ["diff --git ", "--- ", "+++ ", "@@ "]
    idxs = [text.find(marker) for marker in markers if text.find(marker) >= 0]
    return min(idxs) if idxs else -1


def _extract_unified_diff(text: str) -> tuple[str, dict[str, Any]]:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.strip():
        return "", {"status": "no_diff_found", "error_summary": "empty output"}
    if "```" in raw:
        fence_start = raw.find("```diff")
        if fence_start >= 0:
            fence_end = raw.find("```", fence_start + 7)
            if fence_end > fence_start:
                candidate = raw[fence_start + 7:fence_end].strip("\n")
                if candidate and not candidate.endswith("\n"):
                    candidate += "\n"
                return candidate, {"status": "parsed", "error_summary": None}
        return "", {"status": "markdown_fence_or_prose_only", "error_summary": "markdown fences detected"}
    start = _find_diff_start(raw)
    if start < 0:
        return "", {"status": "no_diff_found", "error_summary": "no unified diff marker found"}
    candidate = raw[start:].strip("\n")
    if not candidate.strip():
        return "", {"status": "no_diff_found", "error_summary": "no diff content"}
    if "diff --git " not in candidate and candidate.startswith(("--- ", "+++ ", "@@ ")):
        candidate = "diff --git a/placeholder b/placeholder\n" + candidate
    if candidate and not candidate.endswith("\n"):
        candidate += "\n"
    return candidate, {"status": "parsed", "error_summary": None}


def _parse_touched_paths(patch_text: str) -> list[str]:
    paths: list[str] = []
    for line in patch_text.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            raw = line[4:].strip()
            if raw in {"/dev/null", "a/dev/null", "b/dev/null"}:
                continue
            if raw.startswith("a/") or raw.startswith("b/"):
                raw = raw[2:]
            paths.append(raw)
    return sorted({p for p in paths if p})


def _validate_scope(allowed_paths: list[str], touched_paths: list[str], *, allow_deletions: bool = False) -> dict[str, Any]:
    violations: list[str] = []
    deletions = []
    for path in touched_paths:
        if not _safe_path(path):
            violations.append(path)
            continue
        if _is_forbidden(path):
            violations.append(path)
            continue
        if not any(Path(path).as_posix().startswith(Path(prefix).as_posix().rstrip("/") + "/") or Path(path).as_posix() == Path(prefix).as_posix().rstrip("/") for prefix in allowed_paths):
            violations.append(path)
    return {"ok": not violations, "violations": sorted(set(violations)), "deletions": deletions}


def _classify_scope_violation(path: str) -> str:
    if path.startswith("/"):
        return "absolute_path"
    if ".." in Path(path).parts:
        return "path_traversal"
    if _is_forbidden(path):
        return "forbidden_path"
    return "path_outside_allowlist"


def build_patch_prompt(*, task: str, allowed_paths: list[str], context: str) -> str:
    return "\n".join([
        "You are Rig's local patch proposer.",
        "You are not executing tools.",
        "Output a unified diff only.",
        "No prose, no markdown, no explanation.",
        "Do not mutate Git or request shell commands.",
        "Do not include binary patches or deletions.",
        "Edit only the allowed paths.",
        "Keep the patch small and task-scoped.",
        "Rig deterministic artifacts are authoritative; this patch is advisory only.",
        f"Task: {task}",
        "Allowed paths:",
        *[f"- {path}" for path in allowed_paths],
        "",
        "Context:",
        context.strip(),
        "",
        "Return only a unified diff.",
    ]) + "\n"


def status(repo_root: Path) -> dict[str, Any]:
    env = mlx_local.detect_mlx_environment()
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "available" if env.get("mlx_lm") else "tool_missing",
        "python_executable": env.get("python_executable"),
        "python_version": env.get("python_version"),
        "mlx": env.get("mlx"),
        "mlx_version": env.get("mlx_version"),
        "mlx_lm": env.get("mlx_lm"),
        "mlx_lm_version": env.get("mlx_lm_version"),
        "selected_backend": mlx_local._selected_generation_backend(),
        "patch_root": _repo_rel(repo_root, repo_root / PATCH_ROOT),
        "sandbox_root": _repo_rel(repo_root, repo_root / SANDBOX_ROOT),
        "warnings": [],
    }


def _latest_patch_dir(repo_root: Path) -> Path | None:
    root = repo_root / PATCH_ROOT
    if not root.exists():
        return None
    candidates = [p for p in root.iterdir() if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _choose_patch_id(task: str) -> str:
    return f"{task}-{uuid.uuid4().hex[:10]}"


def _context(repo_root: Path, task: str) -> dict[str, Any]:
    pack = context_compression.build_context_pack(repo_root, task=task, purpose="patch-proposer", max_chars=24000, use_llm=False)
    return {"source_artifacts": pack["selected_artifacts"] or pack["input_artifacts"], "context": pack["markdown"][:24000]}


def _repair_prompt(*, task: str, allowed_paths: list[str], forbidden_paths: list[str], failure: dict[str, Any], previous_candidate_patch: str) -> str:
    return "\n".join([
        "You are Rig's local patch proposer.",
        "Repair the previous unified diff only.",
        "Output unified diff only.",
        "No prose, no markdown fences, no explanations.",
        "Do not touch paths outside the allowlist.",
        "No deletions, no binary files, no chmod or mode changes.",
        "Keep the patch minimal.",
        f"Task: {task}",
        "Allowed paths:",
        *[f"- {path}" for path in allowed_paths],
        "Forbidden paths:",
        *[f"- {path}" for path in forbidden_paths],
        "Exact validation failure:",
        json.dumps(failure, indent=2, sort_keys=True),
        "",
        "Previous candidate patch:",
        previous_candidate_patch.strip(),
        "",
        "Return only a unified diff.",
    ]) + "\n"


def _attempt_dir(repo_root: Path, patch_id: str, attempt_index: int) -> Path:
    out = _patch_dir(repo_root, patch_id) / "attempts" / f"attempt-{attempt_index}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_attempt_artifacts(attempt_dir: Path, *, raw_output: str, candidate_patch: str, parse: dict[str, Any], safety: dict[str, Any], git_check_stdout: str = "", git_check_stderr: str = "", repair_prompt: str | None = None) -> None:
    _write_text(attempt_dir / "raw-output.txt", raw_output)
    _write_text(attempt_dir / "candidate.patch", candidate_patch)
    _write_json(attempt_dir / "parse.json", parse)
    _write_json(attempt_dir / "safety.json", safety)
    _write_text(attempt_dir / "git-apply-check.stdout.log", git_check_stdout)
    _write_text(attempt_dir / "git-apply-check.stderr.log", git_check_stderr)
    if repair_prompt is not None:
        _write_text(attempt_dir / "repair-prompt.md", repair_prompt)


def _candidate_status(parse: dict[str, Any], safety: dict[str, Any]) -> tuple[str, str]:
    if parse.get("status") != "parsed":
        return str(parse.get("status") or "parse_failed"), str(parse.get("status") or "parse_failed")
    if not safety.get("ok", False):
        return "safety_failed", "safety_failed"
    return "raw_generated", "raw_generated"


def _run_model(prompt: str, *, model: str | None, timeout_seconds: int) -> dict[str, Any]:
    return mlx_local.generate_summary(
        prompt=prompt,
        model=model or mlx_local.SUMMARY_MODEL,
        max_tokens=900,
        timeout_seconds=timeout_seconds,
        task="local_patch",
        prompt_kind="patch_propose",
        prompt_template_id="rig.local_patch.v1",
        context_pack_path=mlx_local.REPO_ROOT / ".build" / "rig" / "context" / "latest.md",
    )


def _evaluate_candidate(repo_root: Path, candidate_patch: str, *, allowed_paths: list[str], patch_id: str, task: str, attempt_index: int, max_repair_attempts: int, git_apply_check_timeout: int) -> tuple[dict[str, Any], dict[str, Any], Path]:
    attempt_dir = _attempt_dir(repo_root, patch_id, attempt_index)
    parse: dict[str, Any] = {"status": "parsed", "error_summary": None}
    if not candidate_patch.strip():
        parse = {"status": "no_diff_found", "error_summary": "empty output"}
    else:
        candidate_patch, parse = _extract_unified_diff(candidate_patch)
    touched_paths = _parse_touched_paths(candidate_patch)
    scope = _validate_scope(allowed_paths, touched_paths)
    safety = {
        "status": "passed" if scope["ok"] and not _is_binary_patch(candidate_patch) and not _has_conflict_markers(candidate_patch) else "failed",
        "ok": scope["ok"] and not _is_binary_patch(candidate_patch) and not _has_conflict_markers(candidate_patch),
        "violations": scope["violations"],
        "binary_patch_detected": _is_binary_patch(candidate_patch),
        "deletion_detected": "deleted file mode" in candidate_patch,
        "mode_change_detected": "old mode" in candidate_patch or "new mode" in candidate_patch,
        "forbidden_paths": [p for p in touched_paths if _is_forbidden(p)],
        "error_summary": None,
    }
    if not scope["ok"]:
        safety["error_summary"] = "path_outside_allowlist" if any(_classify_scope_violation(p) == "path_outside_allowlist" for p in scope["violations"]) else "forbidden_path"
    elif safety["binary_patch_detected"]:
        safety["error_summary"] = "binary_patch"
    elif safety["deletion_detected"]:
        safety["error_summary"] = "deletion_detected"
    elif safety["mode_change_detected"]:
        safety["error_summary"] = "mode_change_detected"
    elif _has_conflict_markers(candidate_patch):
        safety["error_summary"] = "conflict_marker"
        safety["ok"] = False
        safety["status"] = "failed"
    git_stdout = ""
    git_stderr = ""
    git_status = "not_run"
    if parse.get("status") == "parsed" and safety["ok"]:
        proc = subprocess.run(["git", "apply", "--check", "--verbose", str(attempt_dir / "candidate.patch")], cwd=repo_root, text=True, capture_output=True, check=False, timeout=git_apply_check_timeout)
        git_stdout = proc.stdout or ""
        git_stderr = proc.stderr or ""
        git_status = "passed" if proc.returncode == 0 else "failed"
        if proc.returncode != 0:
            safety["ok"] = False
            safety["status"] = "failed"
            safety["error_summary"] = "git_apply_check_failed"
    _write_attempt_artifacts(attempt_dir, raw_output=candidate_patch if parse.get("status") == "parsed" else "", candidate_patch=candidate_patch, parse=parse, safety=safety, git_check_stdout=git_stdout, git_check_stderr=git_stderr)
    return {"attempt_dir": attempt_dir, "parse": parse, "safety": safety, "git_status": git_status, "candidate_patch": candidate_patch}


def propose_patch(repo_root: Path, *, task: str, backend: str, model: str | None, allowed_paths: list[str], dry_run: bool = False, max_repair_attempts: int = 3, repair_timeout_seconds: int = 120, no_repair: bool = False, keep_failed_attempts: bool = True) -> dict[str, Any]:
    patch_id = _choose_patch_id(task)
    patch_dir = _patch_dir(repo_root, patch_id)
    ctx = _context(repo_root, task)
    proposal_md = patch_dir / "proposal.md"
    patch_path = patch_dir / "changes.patch"
    patch_json = patch_dir / "patch.json"
    attempts: list[dict[str, Any]] = []
    chosen_patch = ""
    successful_attempt: int | None = None
    final_failure_reason: str | None = None
    repair_loop_used = False
    current_prompt = build_patch_prompt(task=task, allowed_paths=allowed_paths, context=ctx["context"])
    current_result = _run_model(current_prompt, model=model, timeout_seconds=repair_timeout_seconds)
    last_candidate = current_result.get("output") or ""
    for attempt_index in range(1, max_repair_attempts + 1):
        if attempt_index > 1:
            repair_loop_used = True
            current_prompt = _repair_prompt(
                task=task,
                allowed_paths=allowed_paths,
                forbidden_paths=sorted(PATCH_PROHIBITED),
                failure=attempts[-1],
                previous_candidate_patch=last_candidate,
            )
            current_result = _run_model(current_prompt, model=model, timeout_seconds=repair_timeout_seconds)
            last_candidate = current_result.get("output") or ""
        raw_output = current_result.get("output") or ""
        if not raw_output.strip():
            parse = {"status": "no_diff_found", "error_summary": "empty output"}
            candidate_patch = ""
        else:
            candidate_patch, parse = _extract_unified_diff(raw_output)
        touched = _parse_touched_paths(candidate_patch)
        scope = _validate_scope(allowed_paths, touched)
        safety = {
            "status": "passed" if parse.get("status") == "parsed" and scope["ok"] and not _is_binary_patch(candidate_patch) and not _has_conflict_markers(candidate_patch) and "deleted file mode" not in candidate_patch and "old mode" not in candidate_patch and "new mode" not in candidate_patch else "failed",
            "ok": False,
            "violations": scope["violations"],
            "binary_patch_detected": _is_binary_patch(candidate_patch),
            "deletion_detected": "deleted file mode" in candidate_patch,
            "mode_change_detected": "old mode" in candidate_patch or "new mode" in candidate_patch,
            "forbidden_paths": [p for p in touched if _is_forbidden(p)],
            "error_summary": None,
        }
        status, _ = _candidate_status(parse, safety)
        error_summary = parse.get("error_summary") or safety.get("error_summary")
        if parse.get("status") == "parsed" and scope["ok"] and not safety["binary_patch_detected"] and not safety["deletion_detected"] and not safety["mode_change_detected"] and not _has_conflict_markers(candidate_patch):
            # Write the candidate before the git check so check failures can inspect it.
            _write_text(_attempt_dir(repo_root, patch_id, attempt_index) / "candidate.patch", candidate_patch)
            proc = subprocess.run(["git", "apply", "--check", "--verbose", str(_attempt_dir(repo_root, patch_id, attempt_index) / "candidate.patch")], cwd=repo_root, text=True, capture_output=True, check=False, timeout=repair_timeout_seconds)
            git_status = "passed" if proc.returncode == 0 else "failed"
            _write_attempt_artifacts(_attempt_dir(repo_root, patch_id, attempt_index), raw_output=raw_output, candidate_patch=candidate_patch, parse=parse, safety={**safety, "ok": proc.returncode == 0, "status": "passed" if proc.returncode == 0 else "failed", "error_summary": None if proc.returncode == 0 else "git_apply_check_failed"}, git_check_stdout=proc.stdout or "", git_check_stderr=proc.stderr or "")
            attempt_record = {
                "attempt_index": attempt_index,
                "status": "check_passed" if proc.returncode == 0 else "apply_check_failed",
                "parse_status": parse.get("status"),
                "safety_status": "passed" if scope["ok"] and not safety["binary_patch_detected"] and not safety["deletion_detected"] and not safety["mode_change_detected"] and not _has_conflict_markers(candidate_patch) else "failed",
                "git_apply_check_status": git_status,
                "error_summary": None if proc.returncode == 0 else (proc.stderr or proc.stdout or "git apply --check failed").strip(),
                "candidate_patch_path": _repo_rel(repo_root, _attempt_dir(repo_root, patch_id, attempt_index) / "candidate.patch"),
                "raw_output_path": _repo_rel(repo_root, _attempt_dir(repo_root, patch_id, attempt_index) / "raw-output.txt"),
                "stdout_path": _repo_rel(repo_root, _attempt_dir(repo_root, patch_id, attempt_index) / "git-apply-check.stdout.log"),
                "stderr_path": _repo_rel(repo_root, _attempt_dir(repo_root, patch_id, attempt_index) / "git-apply-check.stderr.log"),
            }
            attempts.append(attempt_record)
            if proc.returncode == 0:
                chosen_patch = candidate_patch
                successful_attempt = attempt_index
                final_failure_reason = None
                break
            final_failure_reason = "git_apply_check_failed"
            if no_repair:
                break
            continue
        _write_attempt_artifacts(_attempt_dir(repo_root, patch_id, attempt_index), raw_output=raw_output, candidate_patch=candidate_patch, parse=parse, safety=safety, git_check_stdout="", git_check_stderr="", repair_prompt=None if attempt_index == 1 else current_prompt)
        attempt_record = {
            "attempt_index": attempt_index,
            "status": parse.get("status") if parse.get("status") != "parsed" else ("safety_failed" if not scope["ok"] or safety["binary_patch_detected"] or safety["deletion_detected"] or safety["mode_change_detected"] or _has_conflict_markers(candidate_patch) else "raw_generated"),
            "parse_status": parse.get("status"),
            "safety_status": "passed" if scope["ok"] and not safety["binary_patch_detected"] and not safety["deletion_detected"] and not safety["mode_change_detected"] and not _has_conflict_markers(candidate_patch) else "failed",
            "git_apply_check_status": "not_run",
            "error_summary": parse.get("error_summary") or safety.get("error_summary") or "validation_failed",
            "candidate_patch_path": _repo_rel(repo_root, _attempt_dir(repo_root, patch_id, attempt_index) / "candidate.patch"),
            "raw_output_path": _repo_rel(repo_root, _attempt_dir(repo_root, patch_id, attempt_index) / "raw-output.txt"),
            "stdout_path": _repo_rel(repo_root, _attempt_dir(repo_root, patch_id, attempt_index) / "git-apply-check.stdout.log"),
            "stderr_path": _repo_rel(repo_root, _attempt_dir(repo_root, patch_id, attempt_index) / "git-apply-check.stderr.log"),
        }
        attempts.append(attempt_record)
        final_failure_reason = attempt_record["status"]
        if no_repair:
            break
        if attempt_index < max_repair_attempts:
            repair_loop_used = True
            continue
    if successful_attempt is None and final_failure_reason is None:
        final_failure_reason = "max_attempts_exceeded"
    if successful_attempt is None and len(attempts) >= max_repair_attempts and final_failure_reason in {None, "", "no_diff_found", "markdown_fence_or_prose_only", "path_outside_allowlist", "forbidden_path", "binary_patch", "deletion_detected", "mode_change_detected", "absolute_path", "path_traversal", "conflict_marker", "git_apply_check_failed", "model_timeout", "model_error"}:
        final_failure_reason = "max_attempts_exceeded"
    chosen_patch = chosen_patch or (attempts[-1]["candidate_patch_path"] if attempts else "")
    final_candidate = ""
    if attempts:
        last_attempt_dir = _attempt_dir(repo_root, patch_id, attempts[-1]["attempt_index"])
        final_candidate = (last_attempt_dir / "candidate.patch").read_text(encoding="utf-8") if (last_attempt_dir / "candidate.patch").exists() else ""
    if not chosen_patch and final_candidate:
        chosen_patch = final_candidate
    if chosen_patch:
        patch_path.write_text(chosen_patch, encoding="utf-8")
    proposal_md.write_text("\n".join([
        "# Rig Local Patch Proposal",
        "",
        f"- Task: `{task}`",
        f"- Patch ID: `{patch_id}`",
        f"- Backend: `{backend}`",
        f"- Model: `{model or mlx_local.SUMMARY_MODEL}`",
        f"- Status: `{('check_passed' if successful_attempt else 'rejected')}`",
        f"- Allowed paths: `{', '.join(allowed_paths)}`",
        "",
        "## Advisory",
        "",
        "Local LLM output is advisory only.",
        "",
        "## Source Context",
        "",
        *[f"- `{item}`" for item in ctx["source_artifacts"]],
        "",
        "## Attempts",
        "",
        *[f"- Attempt `{a['attempt_index']}`: `{a['status']}` / `{a['error_summary']}`" for a in attempts],
    ]) + "\n", encoding="utf-8")
    patch_payload = {
        "schema_version": SCHEMA_VERSION,
        "patch_id": patch_id,
        "task": task,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": backend,
        "model": model or mlx_local.SUMMARY_MODEL,
        "authoritative": False,
        "allowed_paths": allowed_paths,
        "forbidden_paths": sorted(PATCH_PROHIBITED),
        "intended_files": _parse_touched_paths(chosen_patch or final_candidate),
        "patch_path": _repo_rel(repo_root, patch_path),
        "proposal_markdown_path": _repo_rel(repo_root, proposal_md),
        "source_context": ctx["source_artifacts"],
        "warnings": [] if successful_attempt else [final_failure_reason or "unknown_failure"],
        "limitations": ["advisory only", "not canonical", "no main-worktree mutation"],
    }
    prompt_telemetry.record_trace(
        repo_root,
        task=task,
        prompt_kind="patch_propose",
        prompt_template_id="rig.local_patch.v1",
        backend=backend,
        model=model or mlx_local.SUMMARY_MODEL,
        runtime_settings={"max_tokens": 900, "timeout_seconds": repair_timeout_seconds},
        context_pack_path=repo_root / ".build" / "rig" / "context" / "latest.md",
        prompt_text=current_prompt,
        raw_output_text=current_result.get("output") or "",
        parsed_output_text=chosen_patch or final_candidate,
        validator_text=json.dumps({"validation": "patch"}, indent=2),
        status="valid" if successful_attempt else "invalid",
        failure_type="malformed_json" if not chosen_patch and final_failure_reason in {"no_diff_found", "markdown_fence_or_prose_only"} else (final_failure_reason or "unknown"),
        failure_summary=final_failure_reason or "",
        repair_attempted=repair_loop_used,
        repair_success=successful_attempt is not None,
        quarantined=successful_attempt is None,
    )
    _write_json(patch_json, patch_payload)
    _write_json(repo_root / PATCH_ROOT / "latest.json", patch_payload)
    (repo_root / PATCH_ROOT / "latest.md").write_text(proposal_md.read_text(encoding="utf-8"), encoding="utf-8")
    action_manifest.write_action_manifest(
        repo_root,
        task=task,
        action_kind="patch.propose",
        command_group="patch",
        command=["python", "scripts/rig.py", "patch", "propose", "--task", task, "--backend", backend],
        inputs=[{"path": str(repo_root / ".build" / "rig" / "context" / "latest.md"), "kind": "context_pack"}],
        outputs=[{"path": str(patch_json), "kind": "patch", "status": "produced"}, {"path": str(proposal_md), "kind": "patch_proposal", "status": "produced"}, {"path": str(patch_path), "kind": "patch", "status": "produced"}],
        status="passed" if successful_attempt else "failed",
        exit_code=0 if successful_attempt else 1,
        result_path=patch_json,
    )
    validation = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "patch_id": patch_id,
        "task": task,
        "status": "check_passed" if successful_attempt else "check_failed" if final_failure_reason else "proposed",
        "repair_loop_used": repair_loop_used or len(attempts) > 1,
        "repair_attempt_count": len(attempts),
        "max_repair_attempts": max_repair_attempts,
        "successful_attempt": successful_attempt,
        "attempts": attempts,
        "final_failure_reason": final_failure_reason,
        "git_apply_check_status": "passed" if successful_attempt else "failed",
        "sandbox_apply_status": "not_run",
        "scope_status": "passed" if successful_attempt else "failed",
        "forbidden_path_violations": [],
        "binary_patch_detected": any(a.get("status") == "binary_patch" for a in attempts),
        "deletion_detected": any(a.get("status") == "deletion_detected" for a in attempts),
        "validation_commands": [["git", "apply", "--check", "--verbose", _repo_rel(repo_root, patch_path)]] if successful_attempt else [],
        "artifacts": [_repo_rel(repo_root, patch_path), _repo_rel(repo_root, proposal_md)],
        "warnings": ["repair_loop_used"] if repair_loop_used else [],
        "authoritative": False,
    }
    _write_validation_artifacts(repo_root, patch_id, validation)
    return {**patch_payload, "validation": validation}


def load_patch(repo_root: Path, patch_path: Path) -> dict[str, Any]:
    patch_dir = patch_path.parent
    patch_json = patch_dir / "patch.json"
    payload = _load_json(patch_json, None)
    if isinstance(payload, dict):
        payload["patch_path"] = _repo_rel(repo_root, patch_path)
        return payload
    return {"status": "missing", "patch_path": _repo_rel(repo_root, patch_path)}


def check_patch(repo_root: Path, patch_path: Path) -> dict[str, Any]:
    text = patch_path.read_text(encoding="utf-8", errors="replace")
    patch = load_patch(repo_root, patch_path)
    touched = _parse_touched_paths(text)
    scope = _validate_scope(patch.get("allowed_paths", []), touched)
    result = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "patch_id": patch.get("patch_id"),
        "task": patch.get("task"),
        "status": "check_failed",
        "git_apply_check_status": "failed",
        "sandbox_apply_status": "not_run",
        "scope_status": "failed" if not scope["ok"] else "passed",
        "forbidden_path_violations": scope["violations"],
        "binary_patch_detected": _is_binary_patch(text),
        "deletion_detected": "deleted file mode" in text,
        "validation_commands": [],
        "artifacts": [patch.get("patch_path"), patch.get("proposal_markdown_path")],
        "warnings": [],
        "authoritative": False,
    }
    if result["binary_patch_detected"] or result["deletion_detected"] or _has_conflict_markers(text) or not scope["ok"]:
        result["warnings"].append("scope_or_patch_structure_failed")
        result["status"] = "rejected"
        _write_validation_artifacts(repo_root, str(patch.get("patch_id") or patch_path.parent.name), result)
        action_manifest.write_action_manifest(
            repo_root,
            task=str(patch.get("task") or patch_path.parent.name),
            action_kind="patch.check",
            command_group="patch",
            command=["python", "scripts/rig.py", "patch", "check", "--patch", str(patch_path)],
            inputs=[{"path": str(patch_path), "kind": "patch"}],
            outputs=[{"path": str(patch_path.parent / "validation.json"), "kind": "patch_validation", "status": "produced"}],
            status="failed",
            exit_code=1,
            result_path=patch_path.parent / "validation.json",
        )
        return result
    cmd = ["git", "apply", "--check", "--verbose", str(patch_path)]
    proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True, check=False)
    result["validation_commands"].append(cmd)
    result["git_apply_check_status"] = "passed" if proc.returncode == 0 else "failed"
    result["status"] = "check_passed" if proc.returncode == 0 else "check_failed"
    if proc.returncode != 0:
        result["warnings"].append((proc.stderr or proc.stdout or "git apply --check failed").strip())
    _write_validation_artifacts(repo_root, str(patch.get("patch_id") or patch_path.parent.name), result)
    action_manifest.write_action_manifest(
        repo_root,
        task=str(patch.get("task") or patch_path.parent.name),
        action_kind="patch.check",
        command_group="patch",
        command=["python", "scripts/rig.py", "patch", "check", "--patch", str(patch_path)],
        inputs=[{"path": str(patch_path), "kind": "patch"}],
        outputs=[{"path": str(patch_path.parent / "validation.json"), "kind": "patch_validation", "status": "produced"}],
        status="passed" if proc.returncode == 0 else "failed",
        exit_code=proc.returncode,
        result_path=patch_path.parent / "validation.json",
    )
    return result


def _sandbox_sources(repo_root: Path, patch_path: Path, patch: dict[str, Any]) -> list[Path]:
    touched = _parse_touched_paths(patch_path.read_text(encoding="utf-8", errors="replace"))
    out: list[Path] = []
    allowed = patch.get("allowed_paths", []) or []
    for rel in touched:
        if not _safe_path(rel) or _is_forbidden(rel):
            continue
        if not any(Path(rel).as_posix().startswith(Path(prefix).as_posix().rstrip("/") + "/") or Path(rel).as_posix() == Path(prefix).as_posix().rstrip("/") for prefix in allowed):
            continue
        src = repo_root / rel
        if src.exists() and src.is_file():
            out.append(src)
    return out


def _init_sandbox(repo_root: Path, patch_id: str, sources: list[Path]) -> Path:
    sandbox = _sandbox_dir(repo_root, patch_id)
    for src in sources:
        dst = sandbox / src.relative_to(repo_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    subprocess.run(["git", "init", "-q"], cwd=sandbox, check=False, capture_output=True, text=True)
    return sandbox


def apply_sandbox(repo_root: Path, patch_path: Path) -> dict[str, Any]:
    patch = load_patch(repo_root, patch_path)
    patch_id = patch.get("patch_id") or patch_path.parent.name
    sandbox = _sandbox_dir(repo_root, patch_id)
    sources = _sandbox_sources(repo_root, patch_path, patch)
    sandbox = _init_sandbox(repo_root, patch_id, sources)
    proc = subprocess.run(["git", "apply", "--verbose", str(patch_path.resolve())], cwd=sandbox, text=True, capture_output=True, check=False)
    status = "sandbox_applied" if proc.returncode == 0 else "rejected"
    result = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "patch_id": patch.get("patch_id"),
        "task": patch.get("task"),
        "status": status,
        "git_apply_check_status": "passed",
        "sandbox_apply_status": "passed" if proc.returncode == 0 else "failed",
        "scope_status": "passed",
        "forbidden_path_violations": [],
        "binary_patch_detected": False,
        "deletion_detected": False,
        "validation_commands": [["git", "apply", "--verbose", str(patch_path.resolve())]],
        "artifacts": [patch.get("patch_path"), _repo_rel(repo_root, sandbox)],
        "warnings": [] if proc.returncode == 0 else [(proc.stderr or proc.stdout or "sandbox apply failed").strip()],
        "authoritative": False,
    }
    val_json, val_md = _write_validation_artifacts(repo_root, patch_id, result)
    action_manifest.write_action_manifest(
        repo_root,
        task=str(patch.get("task") or patch_id),
        action_kind="patch.apply-sandbox",
        command_group="patch",
        command=["python", "scripts/rig.py", "patch", "apply-sandbox", "--patch", str(patch_path)],
        inputs=[{"path": str(patch_path), "kind": "patch"}],
        outputs=[{"path": str(val_json), "kind": "patch_validation", "status": "produced"}, {"path": str(val_md), "kind": "patch_validation", "status": "produced"}],
        status=status,
        exit_code=0 if proc.returncode == 0 else 1,
        result_path=val_json,
    )
    result["validation_path"] = _repo_rel(repo_root, val_json)
    result["validation_markdown_path"] = _repo_rel(repo_root, val_md)
    result["sandbox_path"] = _repo_rel(repo_root, sandbox)
    _write_json(repo_root / PATCH_ROOT / "latest.json", {**patch, "validation": result})
    (repo_root / PATCH_ROOT / "latest.md").write_text(val_md.read_text(encoding="utf-8"), encoding="utf-8")
    return result


def validate_patch(repo_root: Path, patch_path: Path) -> dict[str, Any]:
    checked = check_patch(repo_root, patch_path)
    if checked.get("status") != "check_passed":
        val_json = _patch_dir(repo_root, patch_path.parent.name) / "validation.json"
        _write_json(val_json, checked)
        return checked
    return apply_sandbox(repo_root, patch_path)


def list_patches(repo_root: Path) -> list[dict[str, Any]]:
    root = repo_root / PATCH_ROOT
    if not root.exists():
        return []
    rows = []
    for path in sorted(root.glob("*/patch.json"), key=lambda p: p.parent.name):
        item = _load_json(path, {})
        if isinstance(item, dict):
            rows.append(item)
    return rows


def show_patch(repo_root: Path, patch_id: str) -> dict[str, Any]:
    patch_dir = repo_root / PATCH_ROOT / patch_id
    patch = _load_json(patch_dir / "patch.json", {})
    validation = _load_json(patch_dir / "validation.json", {})
    return {"patch": patch, "validation": validation}
