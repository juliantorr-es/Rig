from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
from datetime import datetime, timezone


@dataclass
class TuiSnapshot:
    repo_root: Path
    state: dict[str, Any] = field(default_factory=dict)
    board: dict[str, Any] = field(default_factory=dict)
    loop: dict[str, Any] = field(default_factory=dict)
    queue: dict[str, Any] = field(default_factory=dict)
    swarm: dict[str, Any] = field(default_factory=dict)
    doctor: dict[str, Any] = field(default_factory=dict)
    audit: dict[str, Any] = field(default_factory=dict)
    sentinel: dict[str, Any] = field(default_factory=dict)
    vault: dict[str, Any] = field(default_factory=dict)
    workspace: dict[str, Any] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    pressure: dict[str, Any] = field(default_factory=dict)
    prompt_summary: dict[str, Any] = field(default_factory=dict)
    latest_agent: dict[str, Any] | None = None
    latest_task: dict[str, Any] | None = None
    recent_events: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "repo_root": str(self.repo_root),
            "state": self.state,
            "board": self.board,
            "loop": self.loop,
            "queue": self.queue,
            "swarm": self.swarm,
            "doctor": self.doctor,
            "audit": self.audit,
            "sentinel": self.sentinel,
            "vault": self.vault,
            "workspace": self.workspace,
            "settings": self.settings,
            "pressure": self.pressure,
            "prompt_summary": self.prompt_summary,
            "latest_agent": self.latest_agent,
            "latest_task": self.latest_task,
            "recent_events": self.recent_events,
            "warnings": self.warnings,
        }


DEFAULT_TUI_MODE = "safe"
DEFAULT_TUI_SELECTION: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_tui_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "rig.tui_state.v1",
            "mode": DEFAULT_TUI_MODE,
            "selected_task_id": DEFAULT_TUI_SELECTION,
            "selected_workspace_id": None,
            "auto_approve_requested": False,
            "auto_approve_pending": False,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("schema_version", "rig.tui_state.v1")
            payload.setdefault("mode", DEFAULT_TUI_MODE)
            payload.setdefault("selected_task_id", DEFAULT_TUI_SELECTION)
            payload.setdefault("auto_approve_requested", False)
            payload.setdefault("auto_approve_pending", False)
            return payload
    except Exception:
        pass
    return {
        "schema_version": "rig.tui_state.v1",
        "mode": DEFAULT_TUI_MODE,
        "selected_task_id": DEFAULT_TUI_SELECTION,
        "auto_approve_requested": False,
        "auto_approve_pending": False,
    }


def save_tui_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["schema_version"] = "rig.tui_state.v1"
    payload["updated_at"] = _utc_now()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clamp_mode(mode: str) -> str:
    return mode if mode in {"safe", "action", "auto-approve"} else DEFAULT_TUI_MODE
