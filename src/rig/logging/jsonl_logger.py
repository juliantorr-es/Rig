from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class JsonlLogger:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def path_for_run(self, run_id: str) -> Path:
        return self.log_dir / f"run_{run_id}.jsonl"

    def write_event(self, run_id: str, *, level: str, event: str, message: str, workspace_id: str | None = None, command_id: str | None = None, metadata: dict[str, Any] | None = None) -> Path:
        payload = {
            "timestamp": utc_now(),
            "level": level,
            "event": event,
            "workspace_id": workspace_id,
            "command_id": command_id,
            "run_id": run_id,
            "message": message,
            "metadata": metadata or {},
        }
        path = self.path_for_run(run_id)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
        return path

