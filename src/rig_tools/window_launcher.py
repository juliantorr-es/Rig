from __future__ import annotations

import json
import logging
import tempfile
import shutil
import socket
import subprocess
import sys
import time
import threading
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


def open_window(
    repo_root: Path,
    dry_run: bool,
    host: str,
    port: Optional[int],
    browser: bool = False,
    allow_lan: bool = False,
    chat_enabled: bool = False,
) -> Dict[str, Any]:
    session_id = f"win-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
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
            "url": f"http://{host}:{port}",
            "command_argv": _serve_command(repo_root, host, port),
            "server_pid": None,
            "token_enabled": False,
            "status": "dry_run",
            "warnings": warnings,
            "authoritative": False,
        }

    if not get_textual_available():
        return {"status": "failed", "error": "Textual is not installed.", "warnings": warnings}

    url = f"http://{host}:{port}"
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
        "command_argv": _serve_command(repo_root, host, port),
        "server_pid": None,
        "token_enabled": False,
        "status": "planned",
        "warnings": warnings,
        "authoritative": False,
    }
    save_session(repo_root, session)

    server_proc = subprocess.Popen(
        session["command_argv"],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    session["server_pid"] = server_proc.pid
    session["status"] = "running"
    save_session(repo_root, session)
    ready = _wait_for_http(url, timeout_seconds=30.0)
    if not ready:
        warnings.append("Window server did not become ready before the window opened.")

    try:
        if use_webview:
            import webview

            window = webview.create_window(
                "Rig",
                html=(
                    "<!doctype html><html><head><meta charset='utf-8'>"
                    "<style>body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;"
                    "display:grid;place-items:center;height:100vh;margin:0;background:#f7f7f2;color:#111;}"
                    ".card{border:1px solid #1a1a1a;padding:1rem 1.25rem;max-width:36rem;}"
                    "h1{margin:0 0 .5rem 0;font-size:1.1rem;letter-spacing:.08em;text-transform:uppercase;}"
                    "p{margin:0;line-height:1.5;}</style></head>"
                    "<body><div class='card'><h1>Rig loading</h1>"
                    "<p>The Gridline window is starting. If this message remains, the Textual web server did not respond.</p>"
                    "</div></body></html>"
                ),
                width=1200,
                height=800,
            )

            def _load_ready_window() -> None:
                if _wait_for_http(url, timeout_seconds=10.0):
                    window.load_url(url)
                else:
                    warnings.append("Textual web endpoint did not respond in time.")

            webview.start(_load_ready_window)
        else:
            if get_pywebview() and threading.current_thread() is not threading.main_thread():
                warnings.append("pywebview requires main thread; falling back to browser")
            import webbrowser

            webbrowser.open(url)
            server_proc.wait()
    except Exception as exc:
        warnings.append(f"Browser launch failed: {exc}")
        session["warnings"] = warnings
        session["status"] = "failed"
        session["error"] = str(exc)
        save_session(repo_root, session)
        if server_proc.poll() is None:
            server_proc.terminate()
        return {"status": "failed", "error": str(exc), "warnings": warnings}
    finally:
        try:
            if server_proc.poll() is None:
                server_proc.terminate()
                try:
                    server_proc.wait(timeout=5)
                except Exception:
                    server_proc.kill()
                    server_proc.wait()
        except Exception:
            pass

    session["status"] = "stopped"
    session["warnings"] = warnings
    save_session(repo_root, session)
    return session
