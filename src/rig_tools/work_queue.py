"""
Work Queue for Rig

Manages job queue and checkpoints for scheduled work.

Uses rig_tools.core.io for JSON I/O.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rig_tools import action_manifest, context_compression, events, schema_validation, supervisor_loop
from rig_tools.loop_actions import expand_command, latest_agent_plan_path
from rig_tools.core.io import read_json, write_json


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


def _repo_rel(repo_root: Path, path: Path | None) -> str | None:
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
    """Load the queue from disk."""
    path = queue_path(repo_root)
    if path.exists():
        try:
            return _normalize_queue(read_json(path))
        except Exception:
            pass
    return {"schema_version": QUEUE_SCHEMA_VERSION, "jobs": [], "warnings": []}


def save_queue(repo_root: Path, payload: dict[str, Any]) -> Path:
    """Save the queue to disk."""
    payload = dict(payload)
    payload.setdefault("schema_version", QUEUE_SCHEMA_VERSION)
    payload.setdefault("warnings", [])
    path = queue_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, payload)
    return path


def _job_id(task: str) -> str:
    return f"{task}-{uuid.uuid4().hex[:10]}"


def _checkpoint_path(repo_root: Path, job_id: str) -> Path:
    return checkpoints_dir(repo_root) / f"{job_id}.json"


def _run_dir(repo_root: Path, job_id: str) -> Path:
    out = runs_dir(repo_root) / job_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def _load_job(repo_root: Path, job_id: str) -> dict[str, Any] | None:
    queue = load_queue(repo_root)
    for job in queue.get("jobs", []):
        if isinstance(job, dict) and job.get("job_id") == job_id:
            return job
    return None
