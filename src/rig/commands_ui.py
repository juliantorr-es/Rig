from __future__ import annotations

import json
import sys
from pathlib import Path


def _check_ui_dependencies() -> bool:
    """Check if UI dependencies (aiohttp, pywebview) are available.
    
    Returns True if all dependencies are available, False otherwise.
    """
    try:
        import aiohttp  # noqa: F401
        import webview  # noqa: F401
        return True
    except ImportError:
        return False


def _get_missing_ui_dependencies() -> list[str]:
    """Get list of missing UI dependencies."""
    missing = []
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        missing.append("aiohttp")
    try:
        import webview  # noqa: F401
    except ImportError:
        missing.append("pywebview")
    return missing


def register(subparsers, helpers):
    parser = subparsers.add_parser(
        "ui", 
        help="Rig Windowed UI", 
        description="Open the rich, windowed control plane for interactive work and governance."
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan session without launching")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind local server")
    parser.add_argument("--port", type=int, help="Port to bind local server (random if missing)")
    parser.add_argument("--browser", action="store_true", help="Force browser mode instead of pywebview")
    parser.add_argument("--allow-lan", action="store_true", help="Allow binding to 0.0.0.0")
    parser.add_argument("--chat", action="store_true", help="Enable chat console in the windowed UI")
    parser.add_argument("--debug", action="store_true", help="Enable browser DevTools and debug logging")
    parser.set_defaults(handler=lambda args: _ui_handler(helpers.repo_root, args))


def _ui_handler(repo_root: Path, args) -> int:
    # Check for UI dependencies before importing window_launcher
    if not _check_ui_dependencies():
        missing = _get_missing_ui_dependencies()
        missing_str = ", ".join(missing)
        print(
            f"Error: UI dependencies are missing: {missing_str}\n"
            "Install them with: pip install -e \".[ui]\"",
            file=sys.stderr
        )
        return 1
    
    from rig_tools import window_launcher
    result = window_launcher.open_window(
        repo_root=repo_root,
        dry_run=args.dry_run,
        host=args.host,
        port=args.port,
        browser=args.browser,
        allow_lan=args.allow_lan,
        chat_enabled=args.chat,
        debug=args.debug
    )
    if args.dry_run:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if result.get("status") == "failed":
        error = result.get('error', '')
        if 'dependencies' in error.lower() or 'import' in error.lower():
            print(
                f"Error: {error}\n"
                "Install UI dependencies with: pip install -e \".[ui]\"",
                file=sys.stderr
            )
        else:
            print(f"Error: {result.get('error')}", file=sys.stderr)
        return 1
    return 0
