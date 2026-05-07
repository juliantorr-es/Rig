from __future__ import annotations

import json
import sys
from pathlib import Path


def register(subparsers, helpers):
    parser = subparsers.add_parser("tui", help="Launch the safe Rig Textual TUI")
    parser.add_argument("--safe", action="store_true", help="Launch in safe mode (default)")
    parser.add_argument("--action", action="store_true", help="Launch in action mode (guarded execution)")
    parser.add_argument("--auto-approve", action="store_true", help="Launch in auto-approve mode (bounded YOLO)")
    parser.add_argument("--yolo", action="store_true", help="Alias for --auto-approve")
    parser.add_argument("--window", action="store_true", help="Open the TUI in window mode")
    parser.add_argument("--dry-run", action="store_true", help="Plan the launch without starting the app")
    parser.add_argument("--mode", choices=["safe", "action", "auto-approve"], default=None, help="Explicitly set mode")
    parser.add_argument("--refresh", type=int, default=2)
    parser.set_defaults(handler=lambda args: _run(helpers, args))


def _run(helpers, args) -> int:
    mode = "safe"
    if args.mode:
        mode = args.mode
    elif args.auto_approve or args.yolo:
        mode = "auto-approve"
    elif args.action:
        mode = "action"
    elif args.safe:
        mode = "safe"

    if args.window:
        from rig_tools import window_launcher
        return 0 if window_launcher.open_window(helpers.repo_root, dry_run=args.dry_run, host="127.0.0.1", port=None, browser=True, allow_lan=False).get("status") != "failed" else 1

    if args.dry_run:
        payload = {"status": "dry_run", "mode": mode, "command": [sys.executable, "-m", "rig", "tui", "--mode", mode]}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    try:
        import textual  # noqa: F401
    except Exception as exc:
        payload = {
            "status": "tool_missing",
            "message": "Textual not installed",
            "install_hint": "python3.14 -m pip install textual",
            "error": str(exc),
        }
        out_dir = helpers.repo_root / ".build" / "rig" / "tui"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "latest-command.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (out_dir / "latest-state.json").write_text(json.dumps({"status": "tool_missing", "tool": "textual", "install_hint": payload["install_hint"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    from rig_tools import tui_app
    app = tui_app.build_app(helpers.repo_root, mode=mode, refresh_seconds=max(1, int(args.refresh)))
    app.run()
    return 0
