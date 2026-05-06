from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "rig.session_review_bundle.v1"
FIXED_ZIP_DT = (1980, 1, 1, 0, 0, 0)
HARD_EXCLUDES = {".git", "__MACOSX", "__pycache__", ".pytest_cache", "DerivedData", "archives"}


@dataclass
class BundleResult:
    bundle_path: Path| Optional
    manifest_path: Path
    summary_path: Path
    manifest: dict[str, Any]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str| Optional:
    try:
        return sha256_bytes(path.read_bytes())
    except Exception:
        return None


def _repo_rel(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True, check=False)


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


def _task_slug(task: str) -> str:
    return task.replace("/", "-")


def _default_bundle_dir(repo_root: Path) -> Path:
    return repo_root / "Session-bundles"


def _read_task_context(repo_root: Path, task: str) -> dict[str, Any]:
    from rig_tools import git_manage, prompt_telemetry, result_index

    runs = result_index.build_run_rows(repo_root)
    latest_run = next((row for row in reversed(runs) if row.get("task") == task), None)
    affected_rows = result_index.build_affected_rows(repo_root)
    latest_affected = next((row for row in reversed(affected_rows) if row.get("task") == task), None)
    swift_rows = result_index.build_swift_rows(repo_root)
    latest_swift = swift_rows[-1] if swift_rows else None
    return {
        "latest_run": latest_run,
        "latest_affected": latest_affected,
        "latest_swift": latest_swift,
        "latest_registry": git_manage.latest_registry_gate(repo_root),
        "latest_schema": git_manage.latest_schema_validation(repo_root),
        "latest_result": git_manage.latest_result(repo_root),
        "latest_proof": git_manage.latest_proof(repo_root),
    }


def _git_status(repo_root: Path) -> dict[str, Any]:
    res = _git(repo_root, "status", "--porcelain=v1", "-z")
    changed: list[str] = []
    untracked: list[str] = []
    for item in res.stdout.split("\0"):
        if not item or len(item) < 4:
            continue
        path = item[3:].strip()
        if item.startswith("?? "):
            untracked.append(path)
        else:
            changed.append(path)
    return {"changed_files": sorted(set(changed + untracked)), "untracked_files": sorted(set(untracked))}


def _read_commit_plan(repo_root: Path, task: str) -> dict[str, Any]| Optional:
    path = repo_root / ".build" / "rig" / "git" / f"commit-plan-{task}.json"
    return _load_json(path, {}) if path.exists() else None


def _list_agent_plans(repo_root: Path, task: str) -> list[Path]:
    out = repo_root / ".build" / "rig" / "agents" / "plans"
    if not out.exists():
        return []
    return sorted([p for p in out.glob(f"*{task}*.json") if p.is_file()], key=lambda p: p.name)


def _list_agent_runs(repo_root: Path, task: str) -> list[Path]:
    out = repo_root / ".build" / "rig" / "agents" / "runs"
    if not out.exists():
        return []
    rows = []
    for path in out.glob("*/agent-run.json"):
        if path.is_file():
            data = _load_json(path, {})
            if task in str(data.get("task") or "") or task in path.as_posix():
                rows.append(path)
    return sorted(rows, key=lambda p: p.parent.name)


def _list_loop_plans(repo_root: Path, task: str) -> list[Path]:
    out = repo_root / ".build" / "rig" / "loop" / "plans"
    if not out.exists():
        return []
    return sorted([p for p in out.glob(f"*{task}*.json") if p.is_file()], key=lambda p: p.name)


def _list_loop_runs(repo_root: Path, task: str) -> list[Path]:
    out = repo_root / ".build" / "rig" / "loop" / "runs"
    if not out.exists():
        return []
    rows = []
    for path in out.glob("*/loop-run.json"):
        if path.is_file():
            data = _load_json(path, {})
            if task in str(data.get("task") or "") or task in path.as_posix():
                rows.append(path)
    return sorted(rows, key=lambda p: p.parent.name)


def _context_pack(repo_root: Path, task: str) -> tuple[Path| Optional, Path| Optional]:
    candidates = [
        (repo_root / ".build" / "rig" / "context" / f"{task}-context-pack.md", repo_root / ".build" / "rig" / "context" / f"{task}-context-pack.json"),
        (repo_root / ".build" / "rig" / "context" / "latest.md", repo_root / ".build" / "rig" / "context" / "latest.json"),
        (repo_root / ".build" / "rig" / "context-packs" / f"{task}-small.md", repo_root / ".build" / "rig" / "context-packs" / f"{task}-small.json"),
    ]
    for md, json_path in candidates:
        if md.exists() or json_path.exists():
            return (md if md.exists() else None, json_path if json_path.exists() else None)
    return (None, None)


def _should_exclude(path: str) -> bool:
    p = Path(path)
    if any(part in HARD_EXCLUDES for part in p.parts):
        return True
    if p.suffix == ".pyc" or p.name == ".DS_Store":
        return True
    if p.suffix == ".zip":
        return True
    return False


def _truncate_note(path: str, size: int, sha: str| Optional, reason: str) -> str:
    return f"[omitted] {path} size={size} sha256={sha or 'unknown'} reason={reason}\n"


def _safe_read(path: Path, max_bytes: int) -> tuple[bytes| Optional, str| Optional, str| Optional]:
    try:
        data = path.read_bytes()
    except Exception as exc:
        return None, None, f"read_error:{exc}"
    if len(data) > max_bytes:
        return None, sha256_bytes(data), f"too_large:{len(data)}"
    return data, sha256_bytes(data), None


def _task_scoped(path: str, task: str) -> bool:
    return task in path or path.endswith(f"{task}.md") or path.endswith(f"{task}.json")


def _zipinfo(name: str, mode: int = 0o100644) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_DT)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = mode << 16
    return info


def _rel_or_none(repo_root: Path, path: Path| Optional) -> str| Optional:
    if path is None:
        return None
    return _repo_rel(repo_root, path)


def _resolve_output_base(repo_root: Path, *, out: Path| Optional, task: str, run_id: str| Optional, latest_run: bool, overwrite: bool) -> tuple[Path, Path, Path]:
    if out is None:
        out_dir = _default_bundle_dir(repo_root)
        bundle_path = out_dir / f"{_task_slug(task)}-session-review.zip"
    else:
        out = out.expanduser()
        if out.suffix == ".zip":
            out_dir = out.parent
            bundle_path = out
        else:
            out_dir = out
            bundle_path = out_dir / f"{_task_slug(task)}-session-review.zip"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"{_task_slug(task)}-session-review.manifest.json"
    summary_path = out_dir / f"{_task_slug(task)}-session-review.summary.md"
    if bundle_path.exists() and not overwrite:
        suffix = run_id or ("latest" if latest_run else None)
        if suffix:
            bundle_path = bundle_path.with_name(f"{bundle_path.stem}-{suffix}{bundle_path.suffix}")
            manifest_path = manifest_path.with_name(f"{manifest_path.stem}-{suffix}{manifest_path.suffix}")
            summary_path = summary_path.with_name(f"{summary_path.stem}-{suffix}{summary_path.suffix}")
        else:
            idx = 2
            candidate = bundle_path
            while candidate.exists():
                candidate = bundle_path.with_name(f"{bundle_path.stem}-{idx}{bundle_path.suffix}")
                idx += 1
            bundle_path = candidate
            manifest_path = manifest_path.with_name(f"{manifest_path.stem}-{candidate.stem.split('-')[-1]}{manifest_path.suffix}")
            summary_path = summary_path.with_name(f"{summary_path.stem}-{candidate.stem.split('-')[-1]}{summary_path.suffix}")
    return out_dir, bundle_path, manifest_path, summary_path


def _list_session_bundles(repo_root: Path) -> list[Path]:
    out_dir = _default_bundle_dir(repo_root)
    if not out_dir.exists():
        return []
    return sorted([p for p in out_dir.glob("*.zip") if p.is_file()], key=lambda p: p.name)


def _patch_lines(repo_root: Path, task: str) -> tuple[str, str]:
    diff = _git(repo_root, "diff", "--no-ext-diff", "--binary")
    status = _git_status(repo_root)
    task_lines = [f"Task: {task}", "Changed files:"]
    for path in status["changed_files"]:
        if _task_scoped(path, task):
            task_lines.append(f"- {path}")
    return diff.stdout, "\n".join(task_lines) + "\n"


def _collect_candidate_paths(repo_root: Path, task: str, selected_run_id: str| Optional) -> dict[str, list[Path]]:
    task_slug = _task_slug(task)
    out = {
        "results": [],
        "events": [],
        "pipeline": [],
        "patches": [],
        "prompts": [],
        "proofs": sorted([p for p in (repo_root / "Docs" / "proofs").glob(f"*{task}*") if p.is_file()], key=lambda p: p.name),
        "briefs": sorted([p for p in (repo_root / "Docs" / "td" / "briefs").glob(f"*{task}*") if p.is_file()], key=lambda p: p.name),
        "indexes": sorted([p for p in (repo_root / "Docs" / "indexes").glob("*.json") if p.is_file()], key=lambda p: p.name),
        "llm": sorted([p for p in (repo_root / ".build" / "rig" / "llm").glob(f"*{task}*") if p.is_file()], key=lambda p: p.name),
        "embeddings": sorted([p for p in (repo_root / ".build" / "rig" / "embeddings").glob("*") if p.is_file()], key=lambda p: p.name),
        "tui": sorted([p for p in (repo_root / ".build" / "rig" / "tui").glob("*") if p.is_file()], key=lambda p: p.name),
        "actions": sorted([p for p in (repo_root / ".build" / "rig" / "actions").glob("*.json") if p.is_file()], key=lambda p: p.name),
        "policy": sorted([p for p in (repo_root / ".build" / "rig" / "policy").glob("*.json") if p.is_file()], key=lambda p: p.name),
        "agent_plans": _list_agent_plans(repo_root, task),
        "agent_runs": _list_agent_runs(repo_root, task),
        "loop_plans": _list_loop_plans(repo_root, task),
        "loop_runs": _list_loop_runs(repo_root, task),
    }
    latest_result = repo_root / ".build" / "rig" / "results" / "latest.json"
    if latest_result.exists():
        out["results"].append(latest_result)
    if selected_run_id:
        result = repo_root / ".build" / "rig" / "results" / f"{selected_run_id}.json"
        event = repo_root / ".build" / "rig" / "events" / f"{selected_run_id}.jsonl"
        if result.exists():
            out["results"].append(result)
        if event.exists():
            out["events"].append(event)
    latest_event = repo_root / ".build" / "rig" / "events" / "latest.jsonl"
    if latest_event.exists():
        out["events"].append(latest_event)
    patch_root = repo_root / ".build" / "rig" / "patches"
    if patch_root.exists():
        for path in sorted(patch_root.glob("*/patch.json"), key=lambda p: p.parent.name):
            if task in path.as_posix():
                out["patches"].append(path)
                for child in ["changes.patch", "proposal.md", "validation.json", "validation.md"]:
                    child_path = path.parent / child
                    if child_path.exists():
                        out["patches"].append(child_path)
    for path in sorted((repo_root / ".build" / "anigma-pipeline" / "runs").glob(f"{task_slug}/*")):
        if path.is_file():
            out["pipeline"].append(path)
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file():
                    out["pipeline"].append(child)
    return out


def build_manifest(repo_root: Path, *, task: str, run_id: str| Optional = None, latest_run: bool = False, include_untracked: bool = False, profile: str = "forensic") -> dict[str, Any]:
    from rig_tools import prompt_telemetry

    ctx = _read_task_context(repo_root, task)
    git_status = _git_status(repo_root)
    commit_plan = _read_commit_plan(repo_root, task)
    prompt_root = repo_root / ".build" / "rig" / "prompts"
    resolved_run_id = run_id or (ctx["latest_run"]["run_id"] if latest_run and ctx["latest_run"] else None)
    if resolved_run_id == "latest":
        resolved_run_id = ctx["latest_run"]["run_id"] if ctx["latest_run"] else None
    changed_files = sorted(set(git_status["changed_files"]))
    untracked_files = sorted(set(git_status["untracked_files"]))
    task_scoped_modified = [path for path in changed_files if _task_scoped(path, task)]
    task_scoped_untracked = [path for path in untracked_files if _task_scoped(path, task)]
    include_set = set(task_scoped_modified)
    if commit_plan and commit_plan.get("included_files"):
        include_set.update(path for path in commit_plan["included_files"] if isinstance(path, str))
    if include_untracked:
        include_set.update(task_scoped_untracked)
    warnings: list[str] = []
    omissions: list[dict[str, Any]] = []
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "task": task,
        "run_id": resolved_run_id,
        "created_by": "rig.py bundle session",
        "profile": profile,
        "source_repo_root": _repo_rel(repo_root, repo_root),
        "bundle_path": None,
        "bundle_status": "reviewable",
        "scope_status": "partial" if changed_files and not task_scoped_modified else "passed",
        "review_status": "reviewable",
        "commit_plan_status": commit_plan.get("status") if commit_plan else None,
        "registry_gate_status": ctx["latest_registry"]["status"] if ctx["latest_registry"] else None,
        "schema_status": ctx["latest_schema"]["status"] if ctx["latest_schema"] else None,
        "swift_status": ctx["latest_swift"]["status"] if ctx["latest_swift"] else None,
        "affected_targets": ctx["latest_affected"].get("directly_affected_targets", []) if ctx["latest_affected"] else [],
        "recommended_profiles": ctx["latest_affected"].get("recommended_profiles", []) if ctx["latest_affected"] else [],
        "doctor_summary": _load_json(repo_root / ".build" / "rig" / "doctor" / "latest.json", {}),
        "contract_audit_summary": _load_json(repo_root / ".build" / "rig" / "audit" / "contracts" / "latest.json", {}),
        "prompt_summary": {
            "path": _repo_rel(repo_root, prompt_root),
            "trace_count": len(list((prompt_root / "traces").glob("*/trace.json"))) if (prompt_root / "traces").exists() else 0,
            "quarantine_count": len(list((prompt_root / "quarantine").glob("*/trace.json"))) if (prompt_root / "quarantine").exists() else 0,
            "regression_case_count": len(list((prompt_root / "regression").glob("**/cases/*.json"))) if (prompt_root / "regression").exists() else 0,
            "experiment_count": len(list((prompt_root / "experiments").glob("*/latest.json"))) if (prompt_root / "experiments").exists() else 0,
            "latest_quarantined_trace": _repo_rel(repo_root, max((prompt_root / "quarantine").glob("*/trace.json"), key=lambda p: p.stat().st_mtime)) if (prompt_root / "quarantine").exists() and list((prompt_root / "quarantine").glob("*/trace.json")) else None,
            "latest_experiment": _repo_rel(repo_root, max((prompt_root / "experiments").glob("*/latest.json"), key=lambda p: p.stat().st_mtime)) if (prompt_root / "experiments").exists() and list((prompt_root / "experiments").glob("*/latest.json")) else None,
            "top_failure_types": prompt_telemetry.top_failure_types(repo_root, limit=5),
        },
        "included_files": [],
        "omitted_files": [],
        "modified_files_included": sorted(task_scoped_modified),
        "untracked_files_included": sorted(task_scoped_untracked if include_untracked else []),
        "patches": [],
        "proofs": [],
        "briefs": [],
        "indexes": [],
        "artifacts": [],
        "sha256": None,
        "size_bytes": 0,
        "warnings": warnings,
        "limitations": [],
    }
    if changed_files and not task_scoped_modified:
        warnings.append("no_task_scoped_modified_files_detected")
    if not ctx["latest_run"] and not resolved_run_id:
        warnings.append("no_selected_run")
    return manifest


def _session_summary(manifest: dict[str, Any], task: str, run_id: str| Optional) -> str:
    lines = [
        "# Session Review Bundle",
        "",
        f"- Task: `{task}`",
        f"- Run: `{run_id or 'n/a'}`",
        f"- Bundle status: `{manifest.get('bundle_status')}`",
        f"- Included files: `{len(manifest.get('included_files', []))}`",
        f"- Omitted files: `{len(manifest.get('omitted_files', []))}`",
        f"- Review status: `{manifest.get('review_status')}`",
        "",
        "## Inspect First",
        "",
        "- `summary.md`",
        "- `bundle-manifest.json`",
        "- `patches/changes.patch`",
        "- `modified-files/`",
        "- `rig/results/` and `rig/events/`",
    ]
    return "\n".join(lines) + "\n"


def _write_bundle_files(repo_root: Path, bundle_path: Path, manifest_path: Path, summary_path: Path, task: str, manifest: dict[str, Any], included: list[tuple[str, Path]], *, max_log_bytes: int, max_file_bytes: int, dry_run: bool, include_untracked: bool) -> None:
    if dry_run:
        _write_json(manifest_path, manifest)
        _write_text(summary_path, _session_summary(manifest, task, manifest.get("run_id")))
        return
    changes_patch, task_patch = _patch_lines(repo_root, task)
    status = _git_status(repo_root)
    untracked_manifest = {"task": task, "untracked_files": status.get("untracked_files", [])}
    zip_entries: list[tuple[str, bytes]] = [
        ("README.md", _session_summary(manifest, task, manifest.get("run_id")).encode("utf-8")),
        ("bundle-manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")),
        ("summary.md", _session_summary(manifest, task, manifest.get("run_id")).encode("utf-8")),
        ("patches/changes.patch", changes_patch.encode("utf-8")),
        ("patches/task-scoped-changes.patch", task_patch.encode("utf-8")),
        ("patches/untracked-files-manifest.json", (json.dumps(untracked_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")),
    ]
    for arcname, src in included:
        data, sha, reason = _safe_read(src, max_file_bytes)
        if data is None:
            note = _truncate_note(arcname, src.stat().st_size if src.exists() else 0, sha, reason or "unknown")
            zip_entries.append((f"{arcname}.stub.txt", note.encode("utf-8")))
            manifest["omitted_files"].append({"path": arcname, "reason": reason or "unknown", "sha256": sha})
            continue
        zip_entries.append((arcname, data))
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for arcname, data in sorted(zip_entries, key=lambda item: item[0]):
            zf.writestr(_zipinfo(arcname), data)
    manifest["size_bytes"] = bundle_path.stat().st_size
    manifest["sha256"] = sha256_path(bundle_path)
    manifest["bundle_path"] = _repo_rel(repo_root, bundle_path)
    _write_json(manifest_path, manifest)
    _write_text(summary_path, _session_summary(manifest, task, manifest.get("run_id")))


def write_bundle(repo_root: Path, *, task: str, run_id: str| Optional = None, latest_run: bool = False, out: Path| Optional = None, dry_run: bool = False, include_untracked: bool = False, profile: str = "forensic", max_log_bytes: int = 200000, max_file_bytes: int = 1000000, overwrite: bool = False) -> BundleResult:
    out_dir, bundle_path, manifest_path, summary_path = _resolve_output_base(repo_root, out=out, task=task, run_id=run_id, latest_run=latest_run, overwrite=overwrite)
    manifest = build_manifest(repo_root, task=task, run_id=run_id, latest_run=latest_run, include_untracked=include_untracked, profile=profile)
    ctx = _read_task_context(repo_root, task)
    selected_run_id = manifest.get("run_id") or (ctx["latest_result"].get("run_id") if ctx["latest_result"] else None)
    candidates = _collect_candidate_paths(repo_root, task, selected_run_id)
    included: list[tuple[str, Path]] = []
    omitted: list[dict[str, Any]] = []

    def add(src: Path| Optional, arcname: str| Optional = None) -> None:
        if src is None or not src.exists() or not src.is_file():
            return
        arc = arcname or _repo_rel(repo_root, src)
        if _should_exclude(arc):
            omitted.append({"path": arc, "reason": "excluded"})
            return
        included.append((arc, src))

    for src in candidates["results"]:
        add(src, f"rig/results/{src.name}")
    for src in candidates["events"]:
        add(src, f"rig/events/{src.name}")
    add(repo_root / ".build" / "rig" / "affected" / "files.json", "rig/affected/files.json")
    add(repo_root / ".build" / "rig" / "affected" / "targets.json", "rig/affected/targets.json")
    add(repo_root / ".build" / "rig" / "affected" / "risks.json", "rig/affected/risks.json")
    add(repo_root / ".build" / "rig" / "affected" / "profiles.json", "rig/affected/profiles.json")
    add(repo_root / ".build" / "rig" / "affected" / "summary.md", "rig/affected/summary.md")
    add(repo_root / ".build" / "rig" / "swift-diagnostics" / "latest.json", "rig/swift-diagnostics/latest.json")
    add(repo_root / ".build" / "rig" / "swift-diagnostics" / "latest.md", "rig/swift-diagnostics/latest.md")
    add(repo_root / ".build" / "rig" / "schema-validation" / "latest.json", "rig/schema-validation/latest.json")
    add(repo_root / ".build" / "rig" / "schema-validation" / "latest.md", "rig/schema-validation/latest.md")
    add(repo_root / ".build" / "rig" / "monitor" / "state.json", "rig/monitor/state.json")
    add(repo_root / ".build" / "rig" / "monitor" / "index.html", "rig/monitor/index.html")
    add(repo_root / ".build" / "rig" / "kanban" / "latest.json", "rig/kanban/latest.json")
    add(repo_root / ".build" / "rig" / "kanban" / "latest.md", "rig/kanban/latest.md")
    add(repo_root / ".build" / "rig" / "task-graph" / "latest.json", "rig/task-graph/latest.json")
    add(repo_root / ".build" / "rig" / "task-graph" / "latest.md", "rig/task-graph/latest.md")
    add(repo_root / ".build" / "rig" / "system-pressure" / "latest.json", "rig/system-pressure/latest.json")
    add(repo_root / ".build" / "rig" / "models" / "active-llama-cpp-model.json", "rig/models/active-llama-cpp-model.json")
    for path in sorted((repo_root / ".build" / "rig" / "models" / "downloads").glob("*.json")):
        add(path, f"rig/models/downloads/{path.name}")
    add(repo_root / ".build" / "rig" / "agents" / "discovery" / "latest.json", "rig/agents/discovery/latest.json")
    add(repo_root / ".build" / "rig" / "loop" / "latest.json", "rig/loop/latest.json")
    add(repo_root / ".build" / "rig" / "loop" / "latest.md", "rig/loop/latest.md")
    add(repo_root / ".build" / "rig" / "actions" / "latest.json", "rig/actions/latest.json")
    for path in sorted((repo_root / ".build" / "rig" / "actions").glob("*.json")):
        if path.name != "latest.json":
            add(path, f"rig/actions/{path.name}")
    add(repo_root / ".build" / "rig" / "policy" / "latest.json", "rig/policy/latest.json")
    for path in sorted((repo_root / ".build" / "rig" / "policy").glob("*.json")):
        if path.name != "latest.json":
            add(path, f"rig/policy/{path.name}")
    add(repo_root / ".build" / "rig" / "queue" / "queue.json", "rig/queue/queue.json")
    for path in sorted((repo_root / ".build" / "rig" / "queue" / "checkpoints").glob("*.json")):
        add(path, f"rig/queue/checkpoints/{path.name}")
    for path in sorted((repo_root / ".build" / "rig" / "queue" / "runs").glob("*/queue-run.json")):
        add(path, f"rig/queue/runs/{path.parent.name}/queue-run.json")
        for child_name in ["events.jsonl", "summary.md"]:
            child = path.parent / child_name
            add(child, f"rig/queue/runs/{path.parent.name}/{child_name}")
    add(repo_root / ".build" / "rig" / "projections" / "latest.json", "rig/projections/latest.json")
    add(repo_root / ".build" / "rig" / "projections" / "latest.md", "rig/projections/latest.md")
    add(repo_root / ".build" / "rig" / "llm" / "latest-summary.json", "rig/llm/latest-summary.json")
    add(repo_root / ".build" / "rig" / "llm" / "latest-summary.md", "rig/llm/latest-summary.md")
    add(repo_root / ".build" / "rig" / "llm" / f"{task}-session-summary.json", f"rig/llm/{task}-session-summary.json")
    add(repo_root / ".build" / "rig" / "llm" / f"{task}-session-summary.md", f"rig/llm/{task}-session-summary.md")
    add(repo_root / ".build" / "rig" / "tui" / "latest-state.json", "rig/tui/latest-state.json")
    add(repo_root / ".build" / "rig" / "tui" / "latest-command.json", "rig/tui/latest-command.json")
    add(repo_root / ".build" / "rig" / "tui" / "latest-command.stdout.log", "rig/tui/latest-command.stdout.log")
    add(repo_root / ".build" / "rig" / "tui" / "latest-command.stderr.log", "rig/tui/latest-command.stderr.log")
    add(repo_root / ".build" / "rig" / "embeddings" / "index.json", "rig/embeddings/index.json")
    add(repo_root / ".build" / "rig" / "embeddings" / "query-results.json", "rig/embeddings/query-results.json")
    add(repo_root / ".build" / "rig" / "embeddings" / "query-results.md", "rig/embeddings/query-results.md")
    add(repo_root / ".build" / "rig" / "embeddings" / "query-results.json", "rig/embeddings/query-results.json")
    add(repo_root / ".build" / "rig" / "embeddings" / "query-results.md", "rig/embeddings/query-results.md")
    add(repo_root / ".build" / "rig" / "embeddings" / "smoke.json", "rig/embeddings/smoke.json")
    add(repo_root / ".build" / "rig" / "embeddings" / "smoke.md", "rig/embeddings/smoke.md")
    add(repo_root / ".build" / "rig" / "prompts" / "latest.json", "rig/prompts/latest.json")
    add(repo_root / ".build" / "rig" / "prompts" / "latest.md", "rig/prompts/latest.md")
    add(repo_root / ".build" / "rig" / "doctor" / "latest.json", "rig/doctor/latest.json")
    add(repo_root / ".build" / "rig" / "doctor" / "latest.md", "rig/doctor/latest.md")
    add(repo_root / ".build" / "rig" / "audit" / "contracts" / "latest.json", "rig/audit/contracts/latest.json")
    add(repo_root / ".build" / "rig" / "audit" / "contracts" / "latest.md", "rig/audit/contracts/latest.md")
    for path in sorted((repo_root / ".build" / "rig" / "prompts" / "traces").glob("*/trace.json")):
        add(path, f"rig/prompts/traces/{path.parent.name}/trace.json")
        for child_name in ["prompt.txt", "raw-output.txt", "parsed-output.json", "validator.txt"]:
            child = path.parent / child_name
            add(child, f"rig/prompts/traces/{path.parent.name}/{child_name}")
    for path in sorted((repo_root / ".build" / "rig" / "prompts" / "quarantine").glob("*/trace.json")):
        add(path, f"rig/prompts/quarantine/{path.parent.name}/trace.json")
        for child_name in ["prompt.txt", "raw-output.txt", "parsed-output.json", "validator.txt", "summary.md"]:
            child = path.parent / child_name
            add(child, f"rig/prompts/quarantine/{path.parent.name}/{child_name}")
    for path in sorted((repo_root / ".build" / "rig" / "prompts" / "regression").glob("**/cases/*.json")):
        add(path, f"rig/prompts/regression/{path.parent.parent.name}/cases/{path.name}")
    for path in sorted((repo_root / ".build" / "rig" / "prompts" / "experiments").glob("*/latest.json")):
        add(path, f"rig/prompts/experiments/{path.parent.name}/latest.json")
        md = path.parent / "latest.md"
        add(md, f"rig/prompts/experiments/{path.parent.name}/latest.md")
    add(repo_root / ".build" / "rig" / "loop" / "latest.json", "rig/loop/latest.json")
    add(repo_root / ".build" / "rig" / "loop" / "latest.md", "rig/loop/latest.md")
    for path in candidates["loop_plans"]:
        add(path, f"rig/loop/plans/{path.name}")
    for path in candidates["loop_runs"]:
        add(path, f"rig/loop/runs/{path.parent.name}/loop-run.json")
        for child_name in ["events.jsonl", "summary.md"]:
            child = path.parent / child_name
            add(child, f"rig/loop/runs/{path.parent.name}/{child_name}")
    for path in candidates["agent_plans"]:
        add(path, f"rig/agents/plans/{path.name}")
    for path in candidates["agent_runs"]:
        add(path, f"rig/agents/runs/{path.parent.name}/agent-run.json")
        for child_name in ["prompt.md", "stdout.log", "stderr.log", "events.jsonl"]:
            child = path.parent / child_name
            add(child, f"rig/agents/runs/{path.parent.name}/{child_name}")
    for path in candidates["patches"]:
        rel = _repo_rel(repo_root, path)
        if rel.startswith(".build/rig/patches/"):
            rel = "rig/" + rel.removeprefix(".build/rig/")
        add(path, rel)
    for path in sorted((repo_root / ".build" / "rig" / "git").glob(f"commit-plan-{task}.*")):
        add(path, f"rig/git/{path.name}")
    for path in sorted((repo_root / ".build" / "rig" / "git").glob(f"task-status-{task}.*")):
        add(path, f"rig/git/{path.name}")
    ctx_md, ctx_json = _context_pack(repo_root, task)
    add(ctx_md, "context-pack.md")
    add(ctx_json, "context-pack.json")
    for path in candidates["proofs"]:
        add(path, f"proofs/{path.name}")
    for path in candidates["briefs"]:
        add(path, f"briefs/{path.name}")
    for path in candidates["indexes"][:8]:
        add(path, f"indexes/{path.name}")
    add(repo_root / "Docs" / "atlas" / "targets.json", "atlas/targets.json")
    add(repo_root / "Docs" / "atlas" / "entrypoints.json", "atlas/entrypoints.json")
    add(repo_root / "Docs" / "atlas" / "architecture-projections.json", "atlas/architecture-projections.json")
    add(repo_root / "Docs" / "atlas" / "coupling-index.json", "atlas/coupling-index.json")
    add(repo_root / "Docs" / "atlas" / "overlap-index.json", "atlas/overlap-index.json")
    add(repo_root / "Docs" / "atlas" / "desired-state-index.json", "atlas/desired-state-index.json")
    add(repo_root / "logs" / "validator-registry-check.json", "validation/logs-validator-registry-check.json")
    add(repo_root / "logs" / "validator-registry-check.log", "validation/logs-validator-registry-check.log")

    status = _git_status(repo_root)
    changed_files = status["changed_files"]
    modified_candidates = [path for path in changed_files if not _should_exclude(path)]
    included_modified = sorted(set(modified_candidates))
    for rel in included_modified:
        add(repo_root / rel, f"modified-files/{rel}")
    included_untracked = []
    if include_untracked:
        included_untracked = [path for path in status["untracked_files"] if not _should_exclude(path)]
        for rel in included_untracked:
            add(repo_root / rel, f"modified-files/{rel}")

    deduped: list[tuple[str, Path]] = []
    seen_arcs: set[str] = set()
    for arc, src in sorted(included, key=lambda item: item[0]):
        if arc in seen_arcs:
            continue
        seen_arcs.add(arc)
        deduped.append((arc, src))
    included = deduped
    manifest["included_files"] = [arc for arc, _ in included]
    manifest["omitted_files"] = sorted([{**item} for item in omitted], key=lambda item: item["path"])
    manifest["proofs"] = [arc for arc in manifest["included_files"] if arc.startswith("proofs/")]
    manifest["briefs"] = [arc for arc in manifest["included_files"] if arc.startswith("briefs/")]
    manifest["indexes"] = [arc for arc in manifest["included_files"] if arc.startswith("indexes/")]
    manifest["artifacts"] = [arc for arc in manifest["included_files"] if arc.startswith(("rig/", "context-pack", "atlas/", "validation/"))]
    manifest["artifacts"].extend([arc for arc in manifest["included_files"] if arc.startswith("rig/agents/")])
    manifest["artifacts"].extend([arc for arc in manifest["included_files"] if arc.startswith("rig/loop/")])
    manifest["artifacts"].extend([arc for arc in manifest["included_files"] if arc.startswith("rig/prompts/")])
    manifest["modified_files_included"] = [arc for arc in manifest["included_files"] if arc.startswith("modified-files/")]
    manifest["untracked_files_included"] = [arc for arc in manifest["modified_files_included"] if arc.split("modified-files/", 1)[-1] in included_untracked]
    manifest["patches"] = ["patches/changes.patch", "patches/task-scoped-changes.patch", "patches/untracked-files-manifest.json"]
    manifest["bundle_path"] = _repo_rel(repo_root, bundle_path)
    summary_text = _session_summary(manifest, task, selected_run_id)
    _write_json(manifest_path, manifest)
    _write_text(summary_path, summary_text)
    if dry_run:
        return BundleResult(None, manifest_path, summary_path, manifest)
    _write_bundle_files(repo_root, bundle_path, manifest_path, summary_path, task, manifest, included, max_log_bytes=max_log_bytes, max_file_bytes=max_file_bytes, dry_run=dry_run, include_untracked=include_untracked)
    manifest["size_bytes"] = bundle_path.stat().st_size
    manifest["sha256"] = sha256_path(bundle_path)
    manifest["bundle_path"] = _repo_rel(repo_root, bundle_path)
    _write_json(manifest_path, manifest)
    _write_text(summary_path, _session_summary(manifest, task, selected_run_id))
    return BundleResult(bundle_path, manifest_path, summary_path, manifest)
