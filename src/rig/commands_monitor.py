from __future__ import annotations

import json
import sys
from pathlib import Path

from rig_tools import monitor


def register(subparsers, helpers):
    parser = subparsers.add_parser("monitor", help="Rig monitor", description="Read-only monitor over Rig artifacts.")
    mon = parser.add_subparsers(dest="monitor_cmd", required=True)

    snap = mon.add_parser("snapshot", help="Write monitor snapshot")
    snap.add_argument("--from-db", action="store_true")
    snap.set_defaults(handler=lambda args: _snapshot(helpers, args))

    tui = mon.add_parser("tui", help="Launch monitor TUI")
    tui.add_argument("--from-db", action="store_true")
    tui.set_defaults(handler=lambda args: _tui(helpers, args))

    runs = mon.add_parser("runs", help="List runs")
    runs.set_defaults(handler=lambda args: _runs(helpers, args))

    tasks = mon.add_parser("tasks", help="List tasks")
    tasks.set_defaults(handler=lambda args: _tasks(helpers, args))

    tail = mon.add_parser("tail", help="Tail run events")
    tail.add_argument("--run-id", required=True)
    tail.add_argument("--jsonl", action="store_true")
    tail.set_defaults(handler=lambda args: _tail(helpers, args))


def _ensure_snapshot(repo_root: Path) -> dict:
    state_path = repo_root / ".build" / "rig" / "monitor" / "state.json"
    if not state_path.exists():
        monitor.write_snapshot(repo_root)
    return json.loads(state_path.read_text(encoding="utf-8"))


def _snapshot(helpers, args) -> int:
    paths = monitor.write_snapshot(helpers.repo_root, from_db=args.from_db)
    print(json.dumps({"state_path": str(paths["state"].relative_to(helpers.repo_root)), "html_path": str(paths["html"].relative_to(helpers.repo_root))}, indent=2, sort_keys=True))
    return 0


def _tui(helpers, args) -> int:
    try:
        import textual  # type: ignore
    except Exception:
        print(json.dumps({"status": "tool_missing", "step": "step_skipped", "tool": "textual", "message": "Textual not installed"}))
        return 0
    state_path = monitor.write_state(helpers.repo_root, from_db=args.from_db) if args.from_db or not (helpers.repo_root / ".build" / "rig" / "monitor" / "state.json").exists() else (helpers.repo_root / ".build" / "rig" / "monitor" / "state.json")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    from textual.app import App, ComposeResult
    from textual.widgets import DataTable, Static

    class MonitorApp(App):
        CSS = ""

        def compose(self) -> ComposeResult:
            yield Static("Rig Monitor")
            table = DataTable()
            table.add_columns("Key", "Value")
            for key in ["schema_version", "generated_at", "warnings"]:
                table.add_row(key, str(state.get(key)))
            yield table

        def on_key(self, event) -> None:
            if event.key == "q":
                self.exit()
            if event.key == "r":
                monitor.write_snapshot(helpers.repo_root, from_db=args.from_db)
                self.exit()

    MonitorApp().run()
    return 0


def _runs(helpers, args) -> int:
    state = _ensure_snapshot(helpers.repo_root)
    if helpers.output_mode == "json":
        print(json.dumps({"runs": state.get("runs", [])}, indent=2, sort_keys=True))
    else:
        for row in state.get("runs", []):
            print(f"{row.get('run_id')} {row.get('status')} {row.get('command')}")
    return 0


def _tasks(helpers, args) -> int:
    state = _ensure_snapshot(helpers.repo_root)
    if helpers.output_mode == "json":
        print(json.dumps({"tasks": state.get("tasks", [])}, indent=2, sort_keys=True))
    else:
        for row in state.get("tasks", []):
            print(f"{row.get('task_id')} {row.get('latest_run_status')} {row.get('commit_plan_status')}")
    return 0


def _tail(helpers, args) -> int:
    events = monitor.read_events(helpers.repo_root, args.run_id)
    if args.jsonl:
        for event in events:
            print(json.dumps(event, sort_keys=True))
        return 0
    for event in events:
        print(f"{event.get('timestamp_utc')} {event.get('event_type')} {event.get('attributes', {})}")
    return 0
