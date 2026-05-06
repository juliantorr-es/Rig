from __future__ import annotations

import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rig_tools import action_manifest, context_compression, events, schema_validation, supervisor_loop
from rig_tools.loop_actions import expand_command, latest_agent_plan_path


QUEUE_SCHEMA_VERSION = "rig.queue.v1"
CHECKPOINT_SCHEMA_VERSION = "rig.checkpoint.v1"
DEFAULT_MAX_STEPS = 5
DEFAULT_TIMEOUT_SECONDS = 1800
STOP_REASONS = {
    "completed",
    "max_steps_reached",
    "needs_human_approval",
    "planner_malformed_json",
    "action_validation_failed",
    "external_agent_not_available",
    "codex_quota_exhausted",
    "swift_known_blocker",
    "dirty_worktree_scope_too_broad",
    "missing_context",
    "timeout",
    "cancelled",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def queue_dir(repo_root: Path) -> Path:
    out = repo_root / ".build" / "rig" / "queue"
    out.mkdir(parents=True, exist_ok=True)
    return out


def queue_path(repo_root: Path) -> Path:
    return queue_dir(repo_root) / "queue.json"


def checkpoints_dir(repo_root: Path) -> Path:
    out = queue_dir(repo_root) / "checkpoints"
    out.mkdir(parents=True, exist_ok=True)
    return out


def runs_dir(repo_root: Path) -> Path:
    out = queue_dir(repo_root) / "runs"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _repo_rel(repo_root: Path, path: Path| Optional) -> str| Optional:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _normalize_queue(data: Any) -> dict[str, Any]:
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        return data
    return {"schema_version": QUEUE_SCHEMA_VERSION, "jobs": [], "warnings": []}


def load_queue(repo_root: Path) -> dict[str, Any]:
    return _normalize_queue(_load_json(queue_path(repo_root), {"schema_version": QUEUE_SCHEMA_VERSION, "jobs": [], "warnings": []}))


def save_queue(repo_root: Path, payload: dict[str, Any]) -> Path:
    payload = dict(payload)
    payload.setdefault("schema_version", QUEUE_SCHEMA_VERSION)
    payload.setdefault("warnings", [])
    _write_json(queue_path(repo_root), payload)
    return queue_path(repo_root)


def _job_id(task: str) -> str:
    return f"{task}-{uuid.uuid4().hex[:10]}"


def _checkpoint_path(repo_root: Path, job_id: str) -> Path:
    return checkpoints_dir(repo_root) / f"{job_id}.json"


def _run_dir(repo_root: Path, job_id: str) -> Path:
    out = runs_dir(repo_root) / job_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def _load_job(repo_root: Path, job_id: str) -> dict[str, Any]| Optional:
    queue = load_queue(repo_root)
    for job in queue.get("jobs", []):
        if isinstance(job, dict) and job.get("job_id") == job_id:
            return job
    return None


def _job_index(repo_root: Path) -> dict[str, int]:
    queue = load_queue(repo_root)
    out = {}
    for idx, job in enumerate(queue.get("jobs", [])):
        if isinstance(job, dict) and job.get("job_id"):
            out[str(job["job_id"])] = idx
    return out


def _checkpoint_payload(job: dict[str, Any], *, loop_run_id: str| Optional, step_index: int, last_action: str| Optional, last_result_path: str| Optional, next_allowed_actions: list[str], stop_reason: str| Optional, resume_policy: str = "resume_next_step", artifacts: list[str]| Optional = None, warnings: list[str]| Optional = None) -> dict[str, Any]:
    return {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "job_id": job["job_id"],
        "task": job["task"],
        "loop_run_id": loop_run_id,
        "step_index": step_index,
        "last_action": last_action,
        "last_result_path": last_result_path,
        "next_allowed_actions": next_allowed_actions,
        "stop_reason": stop_reason,
        "resume_policy": resume_policy,
        "artifacts": artifacts or [],
        "warnings": warnings or [],
        "authoritative": False,
    }


def add_job(repo_root: Path, *, task: str, mode: str, max_steps: int, notes: str| Optional = None) -> dict[str, Any]:
    queue = load_queue(repo_root)
    job = {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "job_id": _job_id(task),
        "task": task,
        "mode": mode,
        "status": "queued",
        "max_steps": int(max_steps),
        "created_at": utc_now(),
        "started_at": None,
        "finished_at": None,
        "latest_checkpoint": None,
        "stop_reason": None,
        "artifacts": [],
        "warnings": [],
        "authoritative": False,
        "notes": notes,
    }
    queue["jobs"].append(job)
    save_queue(repo_root, queue)
    action_manifest.write_action_manifest(
        repo_root,
        task=task,
        action_kind="queue.add",
        command_group="queue",
        command=["python", "scripts/rig.py", "queue", "add", "--task", task, "--mode", mode, "--max-steps", str(max_steps)],
        inputs=[],
        outputs=[{"path": str(queue_path(repo_root)), "kind": "queue", "status": "produced"}],
        status="passed",
        exit_code=0,
        result_path=queue_path(repo_root),
    )
    return job


def list_jobs(repo_root: Path) -> list[dict[str, Any]]:
    return [job for job in load_queue(repo_root).get("jobs", []) if isinstance(job, dict)]


def status(repo_root: Path) -> dict[str, Any]:
    jobs = list_jobs(repo_root)
    counts: dict[str, int] = {}
    for job in jobs:
        counts[str(job.get("status") or "unknown")] = counts.get(str(job.get("status") or "unknown"), 0) + 1
    latest_checkpoint = None
    cps = sorted(checkpoints_dir(repo_root).glob("*.json"), key=lambda p: p.stat().st_mtime)
    if cps:
        latest_checkpoint = _load_json(cps[-1], {})
    return {
        "schema_version": QUEUE_SCHEMA_VERSION,
        "queue_path": _repo_rel(repo_root, queue_path(repo_root)),
        "jobs_total": len(jobs),
        "status_counts": counts,
        "latest_checkpoint": latest_checkpoint,
        "warnings": load_queue(repo_root).get("warnings", []),
    }


def pause_job(repo_root: Path, job_id: str) -> dict[str, Any]:
    queue = load_queue(repo_root)
    for job in queue.get("jobs", []):
        if isinstance(job, dict) and job.get("job_id") == job_id:
            if job.get("status") in {"queued", "running"}:
                job["status"] = "paused"
                save_queue(repo_root, queue)
                return job
    return {"status": "missing"}


def resume_job(repo_root: Path, job_id: str) -> dict[str, Any]:
    queue = load_queue(repo_root)
    for job in queue.get("jobs", []):
        if isinstance(job, dict) and job.get("job_id") == job_id:
            if job.get("status") == "paused":
                job["status"] = "queued"
                save_queue(repo_root, queue)
                return job
    return {"status": "missing"}


def cancel_job(repo_root: Path, job_id: str) -> dict[str, Any]:
    queue = load_queue(repo_root)
    for job in queue.get("jobs", []):
        if isinstance(job, dict) and job.get("job_id") == job_id:
            job["status"] = "cancelled"
            job["stop_reason"] = "cancelled"
            job["finished_at"] = utc_now()
            save_queue(repo_root, queue)
            return job
    return {"status": "missing"}


def show_job(repo_root: Path, job_id: str) -> dict[str, Any]:
    job = _load_job(repo_root, job_id)
    checkpoint = _load_json(_checkpoint_path(repo_root, job_id), None)
    return {"job": job, "checkpoint": checkpoint}


def _update_job(repo_root: Path, job: dict[str, Any]) -> None:
    queue = load_queue(repo_root)
    for idx, existing in enumerate(queue.get("jobs", [])):
        if isinstance(existing, dict) and existing.get("job_id") == job["job_id"]:
            queue["jobs"][idx] = job
            save_queue(repo_root, queue)
            return


def _write_checkpoint(repo_root: Path, job: dict[str, Any], *, loop_run_id: str| Optional, step_index: int, last_action: str| Optional, last_result_path: str| Optional, next_allowed_actions: list[str], stop_reason: str| Optional, artifacts: list[str]| Optional = None, warnings: list[str]| Optional = None) -> dict[str, Any]:
    payload = _checkpoint_payload(job, loop_run_id=loop_run_id, step_index=step_index, last_action=last_action, last_result_path=last_result_path, next_allowed_actions=next_allowed_actions, stop_reason=stop_reason, artifacts=artifacts, warnings=warnings)
    _write_json(_checkpoint_path(repo_root, job["job_id"]), payload)
    job["latest_checkpoint"] = _repo_rel(repo_root, _checkpoint_path(repo_root, job["job_id"]))
    _update_job(repo_root, job)
    return payload


def _loop_plan_for_job(repo_root: Path, job: dict[str, Any]) -> tuple[dict[str, Any], Path| Optional]:
    pack = context_compression.write_context_pack(repo_root, task=job["task"], purpose="loop-planner", max_chars=16000, use_llm=False)
    plan, path = supervisor_loop.draft_plan(repo_root, task=job["task"], mode=job["mode"], backend="mlx", model="mlx-community/Qwen3-4B-Instruct-2507-4bit", max_steps=int(job.get("max_steps") or DEFAULT_MAX_STEPS))
    plan["context_pack"] = {"json_path": pack.get("json_path"), "md_path": pack.get("md_path")}
    return plan, path


def run_jobs(repo_root: Path, *, max_jobs: int = 1) -> dict[str, Any]:
    queue = load_queue(repo_root)
    run_ids: list[str] = []
    processed = 0
    for job in queue.get("jobs", []):
        if processed >= max_jobs:
            break
        if not isinstance(job, dict):
            continue
        if job.get("status") not in {"queued", "paused", "blocked"}:
            continue
        if job.get("status") == "paused":
            continue
        processed += 1
        job["status"] = "running"
        job["started_at"] = utc_now()
        _update_job(repo_root, job)
        run_dir = _run_dir(repo_root, job["job_id"])
        events_path = run_dir / "events.jsonl"
        summary_path = run_dir / "summary.md"
        run_id = uuid.uuid4().hex[:12]
        emitted: list[dict[str, Any]] = []

        def emit(event_type: str, **attrs: Any) -> None:
            emitted.append(events.make_event(event_type, run_id=run_id, command_group="queue", command="rig queue run", task=job["task"], attributes=attrs))

        emit("run_started", milestone="queue_started", job_id=job["job_id"])
        plan, plan_path = _loop_plan_for_job(repo_root, job)
        action_manifest.write_action_manifest(
            repo_root,
            task=job["task"],
            action_kind="queue.run",
            command_group="queue",
            command=["python", "scripts/rig.py", "queue", "run", "--max-jobs", str(max_jobs)],
            inputs=[{"path": str(queue_path(repo_root)), "kind": "queue"}],
            outputs=[{"path": str(plan_path) if plan_path else "", "kind": "loop_plan", "status": "produced"}] if plan_path else [],
            status="running",
            exit_code=0,
            result_path=run_dir / "queue-run.json",
            event_path=events_path,
            warnings=[],
        )
        validation = supervisor_loop.validate_plan(repo_root, plan)
        if validation["status"] != "passed":
            job["status"] = "blocked"
            job["stop_reason"] = "action_validation_failed"
            job["finished_at"] = utc_now()
            checkpoint = _write_checkpoint(repo_root, job, loop_run_id=None, step_index=0, last_action=None, last_result_path=None, next_allowed_actions=[], stop_reason=job["stop_reason"], warnings=validation["errors"])
            emit("error", milestone="loop_failed", reason=job["stop_reason"], job_id=job["job_id"])
            _finalize_run(repo_root, job, run_id, run_dir, events_path, summary_path, emitted, status="blocked", stop_reason=job["stop_reason"], checkpoint=checkpoint)
            continue
        steps = plan.get("sequence") if isinstance(plan.get("sequence"), list) else [plan]
        existing_checkpoint = _load_json(_checkpoint_path(repo_root, job["job_id"]), {})
        start_index = int(existing_checkpoint.get("step_index") or 0) if isinstance(existing_checkpoint, dict) else 0
        checkpoint = None
        stop_reason = None
        loop_run_id = None
        for idx, step_plan in enumerate(steps[start_index: int(job.get("max_steps") or DEFAULT_MAX_STEPS)], start=start_index + 1):
            action_id = step_plan.get("action_id") if isinstance(step_plan, dict) else plan.get("action_id")
            if action_id == "stop":
                stop_reason = step_plan.get("reason") or "completed"
                checkpoint = _write_checkpoint(repo_root, job, loop_run_id=loop_run_id, step_index=idx, last_action=action_id, last_result_path=None, next_allowed_actions=[], stop_reason=stop_reason, artifacts=[_repo_rel(repo_root, plan_path)] if plan_path else [], warnings=plan.get("warnings", []))
                emit("step_started", milestone="loop_stopped", action_id=action_id, step_index=idx)
                break
            cmd = expand_command(action_id, task=job["task"], model=plan.get("model") or "mlx-community/Qwen3-4B-Instruct-2507-4bit", agent_plan_path=latest_agent_plan_path(repo_root) or plan_path.as_posix(), query=str((step_plan.get("arguments") or {}).get("query") or "RuntimeAuthority shutdown boundary"))
            emit("step_started", milestone="action_started", action_id=action_id, step_index=idx, command=cmd)
            try:
                proc = supervisor_loop._run_command(repo_root, cmd, timeout_seconds=int(step_plan.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS))
            except subprocess.TimeoutExpired:
                stop_reason = "timeout"
                job["status"] = "blocked"
                job["stop_reason"] = stop_reason
                job["finished_at"] = utc_now()
                checkpoint = _write_checkpoint(repo_root, job, loop_run_id=loop_run_id, step_index=idx, last_action=action_id, last_result_path=None, next_allowed_actions=[], stop_reason=stop_reason, warnings=["timeout"])
                emit("error", milestone="loop_failed", reason=stop_reason, action_id=action_id)
                break
            loop_run_id = loop_run_id or uuid.uuid4().hex[:12]
            step_result = run_dir / f"step-{idx}-{action_id}.json"
            step_result.write_text(proc.stdout or "", encoding="utf-8")
            emit("artifact", milestone="artifact_written", path=_repo_rel(repo_root, step_result), artifact_type="step_result")
            emit("step_finished", milestone="action_finished", action_id=action_id, step_index=idx, exit_code=proc.returncode)
            checkpoint = _write_checkpoint(repo_root, job, loop_run_id=loop_run_id, step_index=idx, last_action=action_id, last_result_path=_repo_rel(repo_root, step_result), next_allowed_actions=[step.get("action_id") for step in steps[idx:idx+3] if isinstance(step, dict) and step.get("action_id")], stop_reason=None, artifacts=[_repo_rel(repo_root, plan_path), _repo_rel(repo_root, step_result)], warnings=[])
            if proc.returncode != 0:
                stop_reason = "external_agent_not_available" if action_id == "agent_dry_run" else "swift_known_blocker"
                job["status"] = "blocked"
                job["stop_reason"] = stop_reason
                job["finished_at"] = utc_now()
                break
            if step_plan.get("stop_after"):
                stop_reason = step_plan.get("reason") or "completed"
                break
        if not stop_reason:
            if start_index + len(steps[start_index:]) >= int(job.get("max_steps") or DEFAULT_MAX_STEPS):
                stop_reason = "max_steps_reached"
            else:
                stop_reason = "completed"
        if job.get("status") not in {"blocked"}:
            job["status"] = "completed" if stop_reason == "completed" else "blocked"
            if job["status"] == "completed":
                job["stop_reason"] = "completed"
            else:
                job["stop_reason"] = stop_reason
            job["finished_at"] = utc_now()
        _update_job(repo_root, job)
        _finalize_run(repo_root, job, run_id, run_dir, events_path, summary_path, emitted, status=job["status"], stop_reason=stop_reason, checkpoint=checkpoint)
        run_ids.append(run_id)
    return {"processed": processed, "run_ids": run_ids, "queue_path": _repo_rel(repo_root, queue_path(repo_root))}


def _finalize_run(repo_root: Path, job: dict[str, Any], run_id: str, run_dir: Path, events_path: Path, summary_path: Path, emitted: list[dict[str, Any]], *, status: str, stop_reason: str, checkpoint: dict[str, Any]| Optional) -> dict[str, Any]:
    from rig_tools.events import write_event_stream

    finished = utc_now()
    result = {
        "schema_version": "rig.queue_run.v1",
        "run_id": run_id,
        "job_id": job["job_id"],
        "task": job["task"],
        "status": status,
        "stop_reason": stop_reason,
        "event_path": _repo_rel(repo_root, events_path),
        "result_path": _repo_rel(repo_root, run_dir / "queue-run.json"),
        "artifacts": [a for a in [job.get("latest_checkpoint"), _repo_rel(repo_root, run_dir / "queue-run.json"), _repo_rel(repo_root, events_path), _repo_rel(repo_root, summary_path)] if a],
        "warnings": checkpoint.get("warnings", []) if checkpoint else [],
        "authoritative": False,
        "started_at": job.get("started_at"),
        "finished_at": finished,
    }
    result["duration_seconds"] = 0.0
    write_event_stream(events_path, emitted + [events.make_event("run_finished", run_id=run_id, command_group="queue", command="rig queue run", task=job["task"], attributes={"status": status, "stop_reason": stop_reason})])
    _write_json(run_dir / "queue-run.json", result)
    summary_path.write_text("\n".join([
        "# Rig Queue Run",
        "",
        f"- Job ID: `{job['job_id']}`",
        f"- Task: `{job['task']}`",
        f"- Status: `{status}`",
        f"- Stop reason: `{stop_reason}`",
        f"- Checkpoint: `{job.get('latest_checkpoint') or 'none'}`",
    ]) + "\n", encoding="utf-8")
    latest = repo_root / ".build" / "rig" / "queue" / "latest.json"
    latest_md = repo_root / ".build" / "rig" / "queue" / "latest.md"
    _write_json(latest, result)
    latest_md.write_text(summary_path.read_text(encoding="utf-8"), encoding="utf-8")
    return result
