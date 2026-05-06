from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from rig_tools import action_manifest, agent_plan, context_compression, events, mlx_local, prompt_telemetry, result, schema_validation
from rig_tools.loop_actions import ACTION_ORDER, ACTION_COMMANDS, expand_command, latest_agent_plan_path

SCHEMA_VERSION = "rig.loop_plan.v1"
RUN_SCHEMA_VERSION = "rig.loop_run.v1"
MAX_CONTEXT_CHARS = 12000
DEFAULT_MAX_STEPS = 5
DEFAULT_TIMEOUT_SECONDS = 1800


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


def _read_text(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def _collect_context(repo_root: Path, task: str) -> dict[str, Any]:
    pack_path = repo_root / ".build" / "rig" / "context" / "latest.md"
    if pack_path.exists():
        return {
            "source_artifacts": [_repo_rel(repo_root, repo_root / ".build" / "rig" / "context" / "latest.json"), _repo_rel(repo_root, pack_path)],
            "context": _read_text(pack_path, MAX_CONTEXT_CHARS),
        }
    pack = context_compression.build_context_pack(repo_root, task=task, purpose="loop-planner", max_chars=MAX_CONTEXT_CHARS, use_llm=False)
    return {
        "source_artifacts": pack["selected_artifacts"] or pack["input_artifacts"],
        "context": pack["markdown"][:MAX_CONTEXT_CHARS],
    }


def _allowed_actions(repo_root: Path, *, allow_local_patches: bool = False) -> list[str]:
    actions = []
    for action_id in ACTION_ORDER:
        if action_id == "local_patch_propose" and not allow_local_patches:
            continue
        if action_id == "agent_dry_run" and not (repo_root / ".build" / "rig" / "agents" / "plans").exists():
            continue
        if action_id == "bundle_session" and not (repo_root / "scripts" / "rig.py").exists():
            continue
        actions.append(action_id)
    return actions


def _action_enabled(repo_root: Path, action_id: str, *, allow_local_patches: bool = False) -> bool:
    return action_id in _allowed_actions(repo_root, allow_local_patches=allow_local_patches)


def status(repo_root: Path, *, allow_local_patches: bool = False) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "actions": [
            {
                "action_id": action_id,
                "enabled": _action_enabled(repo_root, action_id, allow_local_patches=allow_local_patches),
                "command": ACTION_COMMANDS[action_id],
            }
            for action_id in ACTION_ORDER
        ],
        "warnings": [],
    }


def build_plan_prompt(*, task: str, mode: str, allowed_actions: list[str], source_artifacts: list[str], context: str, max_steps: int, model: str) -> str:
    return "\n".join([
        "You are Rig's supervisor-loop planner.",
        "You are not executing tools.",
        "Choose only from the allowed actions.",
        "Output JSON matching rig.loop_plan.v1 only.",
        "Do not include shell commands.",
        "Do not request Git mutation.",
        "Do not request source edits in read-only/review mode.",
        "Stop when enough evidence is gathered.",
        "Put uncertainty in warnings.",
        f"Task: {task}",
        f"Mode: {mode}",
        f"Model: {model}",
        f"Max steps: {max_steps}",
        "Allowed actions:",
        *[f"- {action}" for action in allowed_actions],
        "Source artifacts:",
        *[f"- {item}" for item in source_artifacts],
        "",
        "Context:",
        context[:MAX_CONTEXT_CHARS],
        "",
        "Return a JSON object with keys:",
        "schema_version, plan_id, task, mode, step_index, action_id, arguments, reason, expected_artifacts, safety_class, requires_confirm, authoritative, stop_after, warnings",
    ]) + "\n"


def _extract_json(text: str) -> dict[str, Any] | None:
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            return None
    return None


def _fallback_sequence(task: str) -> list[dict[str, Any]]:
    return [
        {"action_id": "affected_summary", "arguments": {"task": task}, "reason": "baseline scope", "expected_artifacts": [], "safety_class": "read_only", "requires_confirm": False, "authoritative": False, "stop_after": False, "warnings": []},
        {"action_id": "embeddings_query", "arguments": {"query": "RuntimeAuthority shutdown boundary"}, "reason": "retrieve related evidence", "expected_artifacts": [], "safety_class": "read_only", "requires_confirm": False, "authoritative": False, "stop_after": False, "warnings": []},
        {"action_id": "project_architecture", "arguments": {}, "reason": "projection context", "expected_artifacts": [], "safety_class": "read_only", "requires_confirm": False, "authoritative": False, "stop_after": False, "warnings": []},
        {"action_id": "stop", "arguments": {}, "reason": "deterministic fallback stop", "expected_artifacts": [], "safety_class": "read_only", "requires_confirm": False, "authoritative": False, "stop_after": True, "warnings": ["fallback_sequence"]},
    ]


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _normalize_arguments(action_id: str, arguments: Any, *, repo_root: Path, task: str, model: str) -> dict[str, Any]:
    if isinstance(arguments, dict):
        normalized = dict(arguments)
    elif isinstance(arguments, list):
        normalized = {f"arg_{idx}": value for idx, value in enumerate(arguments)}
    elif isinstance(arguments, str):
        normalized = {"value": arguments}
    else:
        normalized = {}
    if action_id == "affected_summary":
        normalized.setdefault("task", task)
    elif action_id == "embeddings_query":
        normalized.setdefault("query", "RuntimeAuthority shutdown boundary")
    elif action_id == "agent_plan":
        normalized.setdefault("task", task)
        normalized.setdefault("backend", "mlx")
        normalized.setdefault("model", model)
    elif action_id == "agent_dry_run":
        normalized.setdefault("agent_plan_path", latest_agent_plan_path(repo_root))
    return normalized


def draft_plan(repo_root: Path, *, task: str, mode: str, backend: str, model: str, max_steps: int = DEFAULT_MAX_STEPS, allow_local_patches: bool = False) -> tuple[dict[str, Any], Path | None]:
    ctx = _collect_context(repo_root, task)
    allowed_actions = _allowed_actions(repo_root, allow_local_patches=allow_local_patches)
    prompt = build_plan_prompt(task=task, mode=mode, allowed_actions=allowed_actions, source_artifacts=ctx["source_artifacts"], context=ctx["context"], max_steps=max_steps, model=model)
    result_payload = mlx_local.generate_summary(
        prompt=prompt,
        model=model,
        max_tokens=512,
        timeout_seconds=600,
        task=task,
        prompt_kind="loop_plan",
        prompt_template_id="rig.loop_plan.v1",
        context_pack_path=repo_root / ".build" / "rig" / "context" / "latest.md",
    )
    raw = result_payload.get("output") or ""
    parsed = _extract_json(raw)
    plan_id = f"{task}-loop-plan"
    out_dir = repo_root / ".build" / "rig" / "loop" / "plans"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / f"{plan_id}.raw.txt"
    if not parsed:
        raw_path.write_text(raw, encoding="utf-8")
        parsed = {"schema_version": SCHEMA_VERSION, "plan_id": plan_id, "task": task, "mode": mode, "step_index": 0, "action_id": "affected_summary", "arguments": {"task": task}, "reason": "fallback sequence", "expected_artifacts": [], "safety_class": "read_only", "requires_confirm": False, "authoritative": False, "stop_after": False, "warnings": ["llm_output_unparseable", "fallback_sequence"], "sequence": _fallback_sequence(task), "generation_status": "failed", "raw_output_path": _repo_rel(repo_root, raw_path)}
    parsed.setdefault("schema_version", SCHEMA_VERSION)
    parsed.setdefault("plan_id", plan_id)
    parsed.setdefault("task", task)
    parsed.setdefault("mode", mode)
    parsed.setdefault("step_index", 0)
    parsed.setdefault("action_id", "stop")
    parsed["arguments"] = _normalize_arguments(parsed.get("action_id", "stop"), parsed.get("arguments"), repo_root=repo_root, task=task, model=model)
    parsed.setdefault("reason", "")
    parsed.setdefault("expected_artifacts", [])
    parsed.setdefault("safety_class", "read_only")
    parsed.setdefault("requires_confirm", False if mode == "read-only" else True)
    parsed.setdefault("authoritative", False)
    parsed["requires_confirm"] = _coerce_bool(parsed.get("requires_confirm"), False if mode == "read-only" else True)
    parsed["stop_after"] = _coerce_bool(parsed.get("stop_after"), False)
    parsed.setdefault("warnings", [])
    parsed["source_artifacts"] = ctx["source_artifacts"]
    parsed["allowed_actions"] = allowed_actions
    parsed["generation_status"] = result_payload.get("status")
    parsed["backend"] = backend
    parsed["model"] = model
    parsed["max_steps"] = max_steps
    parsed["warnings"] = sorted(set(str(item) for item in parsed["warnings"]))
    if parsed.get("action_id") == "agent_dry_run" and not parsed["arguments"].get("agent_plan_path"):
        parsed["warnings"].append("agent_plan_path_missing")
    prompt_telemetry.record_trace(
        repo_root,
        task=task,
        prompt_kind="loop_plan",
        prompt_template_id="rig.loop_plan.v1",
        backend=result_payload.get("backend") or backend,
        model=result_payload.get("model") or model,
        runtime_settings={"max_tokens": 512, "timeout_seconds": 600},
        context_pack_path=repo_root / ".build" / "rig" / "context" / "latest.md",
        prompt_text=prompt,
        raw_output_text=raw,
        parsed_output_text=json.dumps(parsed, indent=2, sort_keys=True) if parsed else "",
        validator_text="",
        status="valid" if parsed and parsed.get("schema_version") == SCHEMA_VERSION else "invalid",
        failure_type="malformed_json" if not parsed else "unknown",
        failure_summary="llm output unparseable" if not parsed else "",
        repair_attempted=False,
        repair_success=bool(parsed),
        quarantined=not parsed,
    )
    json_path = out_dir / f"{plan_id}.json"
    md_path = out_dir / f"{plan_id}.md"
    json_path.write_text(json.dumps(parsed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(["# Rig Supervisor Loop Plan", "", f"- Task: `{task}`", f"- Mode: `{mode}`", f"- Action: `{parsed['action_id']}`", f"- Generation status: `{parsed.get('generation_status')}`", f"- Raw output: `{_repo_rel(repo_root, raw_path) if raw_path.exists() else 'n/a'}`"]) + "\n", encoding="utf-8")
    action_manifest.write_action_manifest(
        repo_root,
        task=task,
        action_kind="loop.plan",
        command_group="loop",
        command=["python", "scripts/rig.py", "loop", "plan", "--task", task, "--mode", mode],
        inputs=[{"path": str(repo_root / ".build" / "rig" / "context" / "latest.md"), "kind": "context_pack"}],
        outputs=[{"path": str(json_path), "kind": "loop_plan", "status": "produced"}, {"path": str(md_path), "kind": "loop_plan", "status": "produced"}],
        status="passed" if parsed.get("generation_status") != "failed" else "failed",
        exit_code=0 if parsed.get("generation_status") != "failed" else 1,
        result_path=json_path,
    )
    return parsed, json_path


def validate_plan(repo_root: Path, plan: dict[str, Any], *, allow_vibe: bool = False, experimental_implementation: bool = False, allow_local_patches: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    allowed_actions = set(_allowed_actions(repo_root))
    normalized_args = _normalize_arguments(str(plan.get("action_id") or ""), plan.get("arguments"), repo_root=repo_root, task=str(plan.get("task") or ""), model=str(plan.get("model") or ""))
    if plan.get("schema_version") != SCHEMA_VERSION:
        errors.append("bad_schema_version")
    if plan.get("authoritative") is not False:
        errors.append("must_be_non_authoritative")
    if plan.get("action_id") not in allowed_actions and not (allow_local_patches and plan.get("action_id") == "local_patch_propose"):
        errors.append("unknown_or_disabled_action")
    if plan.get("mode") not in {"read-only", "review", "implementation"}:
        errors.append("bad_mode")
    if plan.get("mode") == "implementation" and not experimental_implementation:
        errors.append("implementation_requires_experimental_flag")
    if plan.get("mode") == "read-only" and plan.get("requires_confirm") is not False:
        errors.append("read_only_requires_confirm_false")
    args = normalized_args
    raw = json.dumps(args)
    if any(tok in raw for tok in [";", "&&", "||", "|", "`", "$(", ">", "<"]):
        errors.append("raw_shell_detected")
    if any(tok in raw.lower() for tok in ["git push", "git pull", "git rebase", "git merge", "rm -rf", "sudo ", "chmod +x"]):
        errors.append("forbidden_instruction")
    if any(token in raw for token in [".git", ".venv-rig", "DerivedData", "__pycache__", ".pytest_cache"]):
        errors.append("forbidden_path")
    if plan.get("action_id") == "agent_dry_run" and plan.get("requires_confirm") is not False:
        errors.append("dry_run_requires_confirm_false")
    if not isinstance(plan.get("stop_after"), bool):
        errors.append("bad_stop_after")
    return {"status": "passed" if not errors else "failed", "errors": errors, "warnings": warnings}


def mode_for_plan(plan: dict[str, Any]) -> str:
    return str(plan.get("mode") or "read-only")


def _run_command(repo_root: Path, cmd: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True, check=False, timeout=timeout_seconds, shell=False)


def run_loop(repo_root: Path, *, task: str, mode: str, backend: str, model: str, max_steps: int = DEFAULT_MAX_STEPS, dry_run: bool = False, experimental_implementation: bool = False, allow_local_patches: bool = False) -> dict[str, Any]:
    run_id = uuid.uuid4().hex[:12]
    out_dir = repo_root / ".build" / "rig" / "loop" / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / "events.jsonl"
    result_path = out_dir / "loop-run.json"
    started = time.time()
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    emitted: list[dict[str, Any]] = []
    def emit(event_type: str, **attrs: Any) -> None:
        emitted.append(events.make_event(event_type, run_id=run_id, command_group="loop", command="rig loop", task=task, attributes=attrs))
    emit("run_started", milestone="loop_started", mode=mode)
    emit("step_started", milestone="context_loaded")
    ctx = _collect_context(repo_root, task)
    emit("artifact", milestone="context_loaded", path=_repo_rel(repo_root, repo_root / ".build" / "rig" / "context" / "latest.md"))
    plan, plan_path = draft_plan(repo_root, task=task, mode=mode, backend=backend, model=model, max_steps=max_steps, allow_local_patches=allow_local_patches)
    emit("step_started", milestone="planner_called")
    action_manifest.write_action_manifest(
        repo_root,
        task=task,
        action_kind="loop.plan",
        command_group="loop",
        command=["python", "scripts/rig.py", "loop", "plan", "--task", task, "--mode", mode],
        inputs=[{"path": str(repo_root / ".build" / "rig" / "context" / "latest.md"), "kind": "context_pack"}],
        outputs=[{"path": str(plan_path) if plan_path else "", "kind": "loop_plan", "status": "produced"}] if plan_path else [],
        status="passed" if validation["status"] == "passed" else "failed",
        exit_code=0 if validation["status"] == "passed" else 1,
        result_path=result_path if False else None,
        event_path=events_path,
        warnings=plan.get("warnings", []),
    )
    validation = validate_plan(repo_root, plan, experimental_implementation=experimental_implementation, allow_local_patches=allow_local_patches)
    emit("step_finished", milestone="plan_validated", status=validation["status"])
    if validation["status"] != "passed":
        status = "failed"
        stop_reason = "plan_invalid"
        steps = []
    else:
        steps = []
        allowed_sequence = plan.get("sequence") if isinstance(plan.get("sequence"), list) else [plan]
        if dry_run:
            status = "dry_run"
            stop_reason = "dry_run"
        else:
            status = "passed"
            stop_reason = "completed"
        for idx, step_plan in enumerate(allowed_sequence[:max_steps], start=1):
            action_id = step_plan.get("action_id") if isinstance(step_plan, dict) else plan.get("action_id")
            if action_id == "stop":
                emit("step_started", milestone="loop_stopped", action_id=action_id, step_index=idx)
                stop_reason = step_plan.get("reason") or "stop"
                steps.append({"step_index": idx, "action_id": action_id, "status": "stopped"})
                break
            step_arguments = _normalize_arguments(action_id, step_plan.get("arguments") if isinstance(step_plan, dict) else plan.get("arguments"), repo_root=repo_root, task=task, model=model)
            agent_plan_path = step_arguments.get("agent_plan_path") or latest_agent_plan_path(repo_root) or plan_path.as_posix()
            cmd = expand_command(action_id, task=task, model=model, agent_plan_path=agent_plan_path, query=str(step_arguments.get("query") or "RuntimeAuthority shutdown boundary"))
            if dry_run:
                emit("artifact", milestone="agent_dry_run", action_id=action_id, command=cmd)
                steps.append({"step_index": idx, "action_id": action_id, "status": "dry_run", "command": cmd})
                continue
            emit("step_started", milestone="action_started", action_id=action_id, step_index=idx, command=cmd)
            try:
                proc = _run_command(repo_root, cmd, timeout_seconds=int(step_plan.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS))
                step_status = "passed" if proc.returncode == 0 else "failed"
                steps.append({"step_index": idx, "action_id": action_id, "status": step_status, "exit_code": proc.returncode, "command": cmd})
                emit("step_finished", milestone="action_finished", action_id=action_id, step_index=idx, exit_code=proc.returncode)
                result_artifact = out_dir / f"step-{idx}-{action_id}.json"
                result_artifact.write_text(proc.stdout or "", encoding="utf-8")
                emit("artifact", milestone="artifact_written", path=_repo_rel(repo_root, result_artifact), artifact_type="step_result")
            except subprocess.TimeoutExpired:
                steps.append({"step_index": idx, "action_id": action_id, "status": "failed", "exit_code": 124, "command": cmd})
                emit("error", milestone="loop_failed", action_id=action_id, step_index=idx, reason="timeout")
                status = "failed"
                stop_reason = "timeout"
                break
            if step_plan.get("stop_after"):
                stop_reason = step_plan.get("reason") or "stop_after"
                emit("step_started", milestone="loop_stopped", action_id=action_id, step_index=idx)
                break
    finished = time.time()
    finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished))
    artifacts = [_repo_rel(repo_root, plan_path), _repo_rel(repo_root, result_path), _repo_rel(repo_root, events_path), _repo_rel(repo_root, out_dir / "summary.md")]
    run_payload = {
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": run_id,
        "task": task,
        "mode": mode,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(finished - started, 3),
        "max_steps": max_steps,
        "steps": steps,
        "event_path": _repo_rel(repo_root, events_path),
        "result_path": _repo_rel(repo_root, result_path),
        "artifacts": [item for item in artifacts if item],
        "stop_reason": stop_reason,
        "warnings": plan.get("warnings", []),
        "authoritative": False,
    }
    events.write_event_stream(events_path, emitted + [events.make_event("run_finished", run_id=run_id, command_group="loop", command="rig loop", task=task, attributes={"milestone": "loop_stopped", "status": status, "stop_reason": stop_reason})])
    result_path.write_text(json.dumps(run_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_md = out_dir / "summary.md"
    summary_md.write_text("\n".join(["# Rig Supervisor Loop", "", f"- Task: `{task}`", f"- Mode: `{mode}`", f"- Status: `{status}`", f"- Stop reason: `{stop_reason}`", f"- Steps: `{len(steps)}`"]) + "\n", encoding="utf-8")
    latest_json = repo_root / ".build" / "rig" / "loop" / "latest.json"
    latest_md = repo_root / ".build" / "rig" / "loop" / "latest.md"
    latest_json.write_text(json.dumps(run_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_md.write_text(summary_md.read_text(encoding="utf-8"), encoding="utf-8")
    action_manifest.write_action_manifest(
        repo_root,
        task=task,
        action_kind="loop.run",
        command_group="loop",
        command=["python", "scripts/rig.py", "loop", "run", "--task", task, "--mode", mode, "--max-steps", str(max_steps)],
        inputs=[{"path": str(repo_root / ".build" / "rig" / "context" / "latest.md"), "kind": "context_pack"}],
        outputs=[{"path": str(result_path), "kind": "loop_run", "status": "produced"}, {"path": str(events_path), "kind": "events", "status": "produced"}, {"path": str(summary_md), "kind": "summary", "status": "produced"}],
        status=status,
        exit_code=0 if status in {"passed", "dry_run"} else 1,
        result_path=result_path,
        event_path=events_path,
        warnings=plan.get("warnings", []),
    )
    return run_payload
