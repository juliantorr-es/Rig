from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import shutil
import socket
import subprocess
import sys
import time
import threading
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

WINDOW_SESSION_SCHEMA_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def get_textual_available() -> bool:
    try:
        import textual  # noqa: F401
        return True
    except Exception:
        return False


def get_pywebview() -> bool:
    try:
        import webview  # noqa: F401
        return True
    except Exception:
        return False


def get_aiohttp_available() -> bool:
    """Check if aiohttp is available."""
    try:
        import aiohttp  # noqa: F401
        return True
    except Exception:
        return False


def check_ui_dependencies() -> tuple[bool, list[str]]:
    """Check all UI dependencies and return (all_available, missing_list)."""
    missing = []
    if not get_aiohttp_available():
        missing.append("aiohttp")
    if not get_pywebview():
        missing.append("pywebview")
    return (len(missing) == 0, missing)


def _set_macos_app_name(name: str) -> bool:
    if sys.platform != "darwin":
        return False
    try:
        from Foundation import NSBundle, NSProcessInfo

        process_info = NSProcessInfo.processInfo()
        if hasattr(process_info, "setProcessName_"):
            process_info.setProcessName_(name)
        bundle = NSBundle.mainBundle()
        info = bundle.infoDictionary() if bundle is not None else None
        if info is not None:
            try:
                info["CFBundleName"] = name
            except Exception:
                pass
            try:
                info["CFBundleDisplayName"] = name
            except Exception:
                pass
        return True
    except Exception:
        pass
    try:
        from AppKit import NSApplication

        app = NSApplication.sharedApplication()
        if hasattr(app, "setApplicationName_"):
            app.setApplicationName_(name)
            return True
        if hasattr(app, "setTitle_"):
            app.setTitle_(name)
            return True
    except Exception:
        pass
    return False


def _wait_for_http(url: str, timeout_seconds: float = 20.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if 200 <= getattr(response, "status", 200) < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.2)
    return False


def _escape_html(text: Any) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_html_list(items: list[Any]) -> str:
    if not items:
        return "<p class='muted'>None.</p>"
    return "<ul>" + "".join(f"<li>{_escape_html(item)}</li>" for item in items) + "</ul>"


# LEGACY COMPATIBILITY: This function produces static HTML snapshots for the
# embedded native window. It is retained for compatibility with historical tests
# and tooling but is NOT used for the new WebSocket-based UI server.
# For new UI development, use UIServer in ui_server.py instead.
def _render_window_html(repo_root: Path, *, chat_enabled: bool) -> str:
    from rig_tools.tui_snapshot import load_snapshot

    snapshot = load_snapshot(repo_root)
    jobs = snapshot.get("jobs", [])
    workspaces = snapshot.get("workspaces", [])
    providers = snapshot.get("providers", [])
    queue = snapshot.get("queue", {})
    recent_logs = snapshot.get("recent_logs", [])
    next_gate = queue.get("next_gate") or queue.get("status") or "unknown"

    chat_block = ""
    if chat_enabled:
        chat_block = """
        <section class="panel chat">
          <h2>CHAT / SLASH CONSOLE</h2>
          <div class="chatbox">
            <p class="muted">Type / for commands or describe an intent…</p>
            <p class="muted">Chat is available in the terminal Gridline shell; this embedded window is a read-only dashboard.</p>
          </div>
        </section>
        """

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rig</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f7f2;
      --surface: #ffffff;
      --text: #111111;
      --border: #1a1a1a;
      --muted: #5f6368;
      --success: #1e8e3e;
      --warning: #f9ab00;
      --info: #1a73e8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .shell {{
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr auto;
      gap: 12px;
      padding: 12px;
    }}
    .topbar, .footer, .panel {{
      border: 1px solid var(--border);
      background: var(--surface);
    }}
    .topbar, .footer {{
      padding: 12px 14px;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: baseline;
    }}
    .title {{
      letter-spacing: .12em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    .body {{
      display: grid;
      grid-template-columns: 28fr minmax(0, 1fr) 38fr;
      gap: 12px;
      min-height: 0;
    }}
    .col {{
      display: grid;
      gap: 12px;
      min-height: 0;
      align-content: start;
    }}
    .panel {{
      padding: 12px;
      min-height: 0;
    }}
    .panel h2 {{
      margin: 0 0 12px 0;
      text-transform: uppercase;
      letter-spacing: .10em;
      font-size: .82rem;
    }}
    .metric {{
      display: grid;
      gap: 4px;
      padding: 10px 0;
      border-top: 1px solid rgba(26,26,26,.12);
    }}
    .metric:first-of-type {{ border-top: 0; padding-top: 0; }}
    .metric .label {{ color: var(--muted); text-transform: uppercase; letter-spacing: .08em; font-size: .75rem; }}
    .metric .value {{ font-size: 1.6rem; font-weight: 700; }}
    .metric .note, .muted {{ color: var(--muted); }}
    ul {{ margin: 0; padding-left: 18px; }}
    .footer {{ color: var(--muted); display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; }}
    .badge {{ border: 1px solid var(--border); padding: 2px 6px; text-transform: uppercase; font-size: .72rem; letter-spacing: .08em; }}
    .status-success {{ color: var(--success); }}
    .status-warning {{ color: var(--warning); }}
    .status-info {{ color: var(--info); }}
    .status-muted {{ color: var(--muted); }}
    .chatbox {{ min-height: 180px; }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div>
        <div class="title">Rig</div>
        <div class="muted">Gridline embedded native window</div>
      </div>
      <div>
        <span class="badge">Next gate: {_escape_html(next_gate)}</span>
      </div>
    </header>
    <main class="body">
      <section class="col">
        <section class="panel">
          <h2>Sidebar</h2>
          <div class="metric"><div class="label">Jobs</div><div class="value status-info">{len(jobs)}</div></div>
          <div class="metric"><div class="label">Workspaces</div><div class="value status-success">{len(workspaces)}</div></div>
          <div class="metric"><div class="label">Providers</div><div class="value status-warning">{len(providers)}</div></div>
        </section>
      </section>
      <section class="col">
        <section class="panel">
          <h2>Main</h2>
          <p class="muted">This window is the embedded native Rig dashboard. It mirrors the governed product shell without going through the Textual web bridge.</p>
          <div class="metric"><div class="label">Queue</div><div class="value">{_escape_html(queue.get('status', 'unknown'))}</div><div class="note">Read-only snapshot from the repo state.</div></div>
          <div class="metric"><div class="label">Recent logs</div>{_render_html_list(recent_logs[:5])}</div>
        </section>
      </section>
      <section class="col">
        <section class="panel">
          <h2>Evidence</h2>
          <div class="metric"><div class="label">Next gate</div><div class="value status-warning">{_escape_html(next_gate)}</div></div>
          <div class="metric"><div class="label">Recent activity</div>{_render_html_list(snapshot.get('recent_activity', []))}</div>
        </section>
        {chat_block}
      </section>
    </main>
    <footer class="footer">
      <span>Native window: pywebview</span>
      <span>Terminal Gridline shell remains available via <code>rig tui --gridline</code></span>
    </footer>
  </div>
</body>
</html>
"""


def save_session(repo_root: Path, session: Dict[str, Any]) -> None:
    base_dir = repo_root / ".build" / "rig" / "window"
    sessions_dir = base_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "logs").mkdir(parents=True, exist_ok=True)
    (sessions_dir / f"{session['session_id']}.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    (base_dir / "latest.json").write_text(json.dumps(session, indent=2), encoding="utf-8")
    (base_dir / "latest.md").write_text(
        f"# Rig Window Session: {session['session_id']}\n\nStatus: {session['status']}\nURL: {session['url']}\nMode: {session['mode']}\n",
        encoding="utf-8",
    )


def check_status(repo_root: Path) -> Dict[str, Any]:
    latest_json = repo_root / ".build" / "rig" / "window" / "latest.json"
    if not latest_json.exists():
        return {"status": "no_session"}
    try:
        return json.loads(latest_json.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "invalid"}


def _create_textual_app_module(repo_root: Path, chat_enabled: bool = False, module_name: str = "rig_window_app") -> Path:
    """Compatibility shim for legacy tests and tooling.

    The release-window path no longer uses a generated module, but some historical
    tests still import this helper. Keep it lightweight and side-effect free.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="rig_window_"))
    module_path = temp_dir / f"{module_name}.py"
    module_path.write_text(
        "from rig_tools.tui_grid import build_gridline_app\n"
        "from pathlib import Path\n\n"
        "if __name__ == '__main__':\n"
        f"    build_gridline_app(Path({str(repo_root.resolve())!r}), chat_enabled={str(chat_enabled).lower()}).run()\n",
        encoding="utf-8",
    )
    return module_path


def _create_server_script(module_dir: Path, module_name: str, src_path: str, host: str, port: int) -> Path:
    """Compatibility shim that produces a direct `textual serve` launcher script."""
    script_path = module_dir / "_serve_launch.py"
    script_path.write_text(
        "import subprocess, sys\n"
        f"subprocess.run([sys.executable, '-m', 'textual', 'serve', 'python -m {module_name}', '--host', {host!r}, '--port', {port!r}], check=True)\n",
        encoding="utf-8",
    )
    return script_path


def _get_server_command(module_dir: Path, module_name: str, src_path: str, host: str, port: int) -> list[str]:
    """Compatibility shim used by legacy tests."""
    return [sys.executable, str(_create_server_script(module_dir, module_name, src_path, host, port))]


def _serve_command(repo_root: Path, host: str, port: int) -> list[str]:
    # Textual's own serve CLI is the only web bridge used here.
    # The command is intentionally simple and avoids the extra textual-serve wrapper layer.
    return [
        sys.executable,
        "-m",
        "textual",
        "serve",
        "python -m rig tui --gridline",
        "--host",
        host,
        "--port",
        str(port),
    ]


# WebSocket UI Architecture Doctrine:
# 1. Frontend (pywebview shell) is a "dumb" renderer of backend-authored UIProjections.
# 2. Communication occurs over WebSocket via UIServer.
# 3. Backend owns all state transitions, governance, and action legality.
# 4. Projections are truth; live streams are progress narration only.
# 5. Intentions are requested by the UI and validated/dispatched by the backend.
def open_window(
    repo_root: Path,
    dry_run: bool,
    host: str,
    port: Optional[int],
    browser: bool = False,
    allow_lan: bool = False,
    chat_enabled: bool = False,
) -> Dict[str, Any]:
    # Check UI dependencies before proceeding
    deps_ok, missing_deps = check_ui_dependencies()
    if not deps_ok:
        return {
            "status": "failed",
            "error": f"Missing UI dependencies: {', '.join(missing_deps)}",
            "hint": "pip install -e \".[ui]\""
        }
    
    session_id = f"win-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    session_token = uuid.uuid4().hex
    
    if host == "0.0.0.0" and not allow_lan:
        return {"status": "failed", "error": "Refusing to bind 0.0.0.0 without --allow-lan"}

    port = port or find_free_port()
    warnings: list[str] = []

    if not get_textual_available():
        warnings.append("Textual not installed. Install Rig product dependencies with: python3.14 -m pip install -e .")

    if dry_run:
        return {
            "schema_version": WINDOW_SESSION_SCHEMA_VERSION,
            "session_id": session_id,
            "created_at": _utc_now(),
            "mode": "dry_run",
            "host": host,
            "port": port,
            "url": f"http://{host}:{port}/?rig_session={session_token}",
            "command_argv": [sys.executable, "-m", "rig", "ui"],
            "server_pid": None,
            "token_enabled": True,
            "status": "dry_run",
            "warnings": warnings,
            "authoritative": False,
        }

    from rig_tools.ui_server import UIServer
    ui_server = UIServer(repo_root, session_token)
    
    # Start server in background thread
    def run_server():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(ui_server.start(host, port))
        loop.run_forever()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    url = f"http://{host}:{port}/?rig_session={session_token}"
    
    if not _wait_for_http(url):
        return {"status": "failed", "error": "UI Server failed to start"}

    use_webview = get_pywebview() and not browser
    _set_macos_app_name("Rig")
    
    session = {
        "schema_version": WINDOW_SESSION_SCHEMA_VERSION,
        "session_id": session_id,
        "created_at": _utc_now(),
        "mode": "webview" if use_webview else "browser",
        "host": host,
        "port": port,
        "url": url,
        "command_argv": [sys.executable, "-m", "rig", "tui", "--gridline", "--window"],
        "server_pid": None,
        "token_enabled": True,
        "status": "active",
        "warnings": warnings,
        "authoritative": False,
    }
    save_session(repo_root, session)

    try:
        if use_webview:
            import webview
            webview.create_window("Rig", url=url, width=1200, height=800)
            webview.start()
        else:
            import webbrowser
            webbrowser.open(url)
    except Exception as exc:
        warnings.append(f"Window launch failed: {exc}")
        session["warnings"] = warnings
        session["status"] = "failed"
        session["error"] = str(exc)
        save_session(repo_root, session)
        return {"status": "failed", "error": str(exc), "warnings": warnings}
    
    session["status"] = "stopped"
    save_session(repo_root, session)
    return session
