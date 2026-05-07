from __future__ import annotations

import json
import sys
from pathlib import Path


def register(subparsers, helpers):
    parser = subparsers.add_parser(
        "tui",
        help="Launch the Rig Gridline TUI (DEPRECATED)",
        description="DEPRECATED: The Textual terminal TUI is retired. Use 'rig ui' for the windowed interface or CLI commands for terminal use."
    )
    parser.add_argument("--safe", action="store_true", help="[DEPRECATED] Launch in safe mode")
    parser.add_argument("--action", action="store_true", help="[DEPRECATED] Launch in action mode")
    parser.add_argument("--auto-approve", action="store_true", help="[DEPRECATED] Launch in auto-approve mode")
    parser.add_argument("--yolo", action="store_true", help="[DEPRECATED] Alias for --auto-approve")
    parser.add_argument(
        "--window",
        action="store_true",
        help="Open the windowed UI (compatibility alias for 'rig ui')"
    )
    parser.add_argument("--chat", action="store_true", help="[DEPRECATED] Enable chat console")
    parser.add_argument("--dry-run", action="store_true", help="Plan the launch without starting")
    parser.add_argument("--mode", choices=["safe", "action", "auto-approve"], default=None, help="[DEPRECATED] Explicitly set mode")
    parser.add_argument("--refresh", type=int, default=2)
    parser.set_defaults(handler=lambda args: _run(helpers, args))


def _emit_deprecation() -> int:
    """Emit deprecation message pointing to new UI command."""
    message = {
        "status": "deprecated",
        "message": "The Textual terminal TUI has been retired.",
        "replacement": "rig ui",
        "alternatives": {
            "windowed_ui": "rig ui [--browser] [--allow-lan] [--chat]",
            "cli_status": "rig status",
            "cli_run": "rig run --task <task-id> --provider <provider>",
            "cli_validate": "rig validate",
        },
        "help": "Use 'rig ui --help' for windowed interface options, or use CLI commands for terminal operation."
    }
    print(json.dumps(message, indent=2))
    return 0


def _run(helpers, args) -> int:
    """Handle deprecated TUI command.
    
    If --window is specified, redirect to the new windowed UI (rig ui).
    Otherwise, emit deprecation message.
    """
    # If --window flag is used, redirect to rig ui behavior
    if args.window:
        from rig_tools import window_launcher
        result = window_launcher.open_window(
            helpers.repo_root,
            dry_run=args.dry_run,
            host="127.0.0.1",
            port=None,
            browser=False,
            allow_lan=False,
            chat_enabled=getattr(args, "chat", False)
        )
        if args.dry_run:
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status") != "failed" else 1

    # Otherwise, emit deprecation message
    return _emit_deprecation()
