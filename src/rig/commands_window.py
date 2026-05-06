from __future__ import annotations

import json
import sys
from pathlib import Path

from rig_tools import window_launcher

def register(subparsers, helpers):
    parser = subparsers.add_parser("window", help="Rig Window Management", description="Open Rig OS in a local desktop window or browser.")
    sub = parser.add_subparsers(dest="window_cmd", required=True)

    status_cmd = sub.add_parser("status", help="Show the current window session status")
    status_cmd.set_defaults(handler=lambda args: _emit(window_launcher.check_status(helpers.repo_root)))

    open_cmd = sub.add_parser("open", help="Open Rig OS window")
    open_cmd.add_argument("--dry-run", action="store_true", help="Plan session without launching")
    open_cmd.add_argument("--host", default="127.0.0.1", help="Host to bind local server")
    open_cmd.add_argument("--port", type=int, help="Port to bind local server (random if missing)")
    open_cmd.add_argument("--browser", action="store_true", help="Force browser mode instead of pywebview")
    open_cmd.add_argument("--allow-lan", action="store_true", help="Allow binding to 0.0.0.0")
    open_cmd.set_defaults(handler=lambda args: _emit(window_launcher.open_window(
        repo_root=helpers.repo_root,
        dry_run=args.dry_run,
        host=args.host,
        port=args.port,
        browser=args.browser,
        allow_lan=args.allow_lan
    )))

    url_cmd = sub.add_parser("url", help="Print the URL of the latest session")
    url_cmd.add_argument("--print", action="store_true", help="Print URL and exit 0 if running")
    url_cmd.set_defaults(handler=lambda args: _url_handler(helpers.repo_root, args.print))

def _emit(payload: dict) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload.get("status") in {"failed", "invalid"}:
        return 1
    return 0

def _url_handler(repo_root: Path, do_print: bool) -> int:
    status = window_launcher.check_status(repo_root)
    if status.get("status") in {"running", "dry_run"}:
        if do_print:
            print(status.get("url", ""))
        return 0
    if do_print:
        print("No running session URL")
    return 1
