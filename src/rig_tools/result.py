from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "rig.result.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


@dataclass
class RigResult:
    command_group: str
    command: str
    status: str
    exit_code: int
    run_id: str
    task: str | None = None
    started_at: str = field(default_factory=utc_now)
    finished_at: str = field(default_factory=utc_now)
    duration_seconds: float = 0.0
    artifacts: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)
    stderr_tail: str | None = None
    notification_requested: bool = False
    notification_backend: str | None = None
    notification_status: str = "skipped"
    notification_error: str | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "command_group": self.command_group,
            "command": self.command,
            "task": self.task,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": round(self.duration_seconds, 3),
            "artifacts": self.artifacts,
            "warnings": self.warnings,
            "errors": self.errors,
            "summary": self.summary,
            "next_actions": self.next_actions,
            "stderr_tail": self.stderr_tail,
            "notification_requested": self.notification_requested,
            "notification_backend": self.notification_backend,
            "notification_status": self.notification_status,
            "notification_error": self.notification_error,
        }


def write_latest_result(repo_root: Path, payload: dict) -> Path:
    out_dir = repo_root / ".build" / "rig" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "latest.json"
    path.write_text(stable_json(payload), encoding="utf-8")
    return path


def write_run_result(repo_root: Path, run_id: str, payload: dict) -> Path:
    out_dir = repo_root / ".build" / "rig" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run_id}.json"
    path.write_text(stable_json(payload), encoding="utf-8")
    return path
