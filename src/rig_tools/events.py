from __future__ import annotations

import json
from datetime import datetime, timezone

SCHEMA_VERSION = "rig.event.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_event(event_type: str, *, run_id: str, command_group: str, command: str, task: str| Optional = None, attributes: dict| Optional = None) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_type": event_type,
        "timestamp_utc": utc_now(),
        "run_id": run_id,
        "command_group": command_group,
        "command": command,
        "task": task,
        "attributes": attributes or {},
    }


def dumps(event: dict) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"))


def write_event_stream(path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(dumps(event) for event in events) + ("\n" if events else ""), encoding="utf-8")
