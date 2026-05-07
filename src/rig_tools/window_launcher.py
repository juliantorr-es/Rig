import json
import logging
import os
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from rig_tools.action_manifest import SCHEMA_VERSION

logger = logging.getLogger(__name__)

WINDOW_SESSION_SCHEMA_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def get_textual_available() -> bool:
    """Check if Textual is available as a Python package."""
    try:
        import textual  # noqa: F401
        return True
    except ImportError:
        return False


def get_textual_serve_available() -> bool:
    """Check if textual-serve is available."""
    try:
        import textual_serve  # noqa: F401
        return True
    except ImportError:
        return False


def get_pywebview() -> bool:
    try:
        import webview
        return True
    except ImportError:
        return False


def save_session(repo_root: Path, session: Dict[str, Any]) -> None:
    session_id = session["session_id"]
    base_dir = repo_root / ".build" / "rig" / "window"
    
    sessions_dir = base_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    session_path = sessions_dir / f"{session_id}.json"
    session_path.write_text(json.dumps(session, indent=2))
    
    latest_json = base_dir / "latest.json"
    latest_json.write_text(json.dumps(session, indent=2))
    
    latest_md = base_dir / "latest.md"
    latest_md.write_text(f"# Rig Window Session: {session_id}\n\nStatus: {session['status']}\nURL: {session['url']}\nMode: {session['mode']}\n")


def check_status(repo_root: Path) -> Dict[str, Any]:
    latest_json = repo_root / ".build" / "rig" / "window" / "latest.json"
    if not latest_json.exists():
        return {"status": "no_session"}
    try:
        return json.loads(latest_json.read_text())
    except Exception:
        return {"status": "invalid"}


def _create_textual_app_module(repo_root: Path, chat_enabled: bool = False, module_name: str = "rig_window_app") -> Path:
    """
    Create a temporary Python module that textual-serve can import to launch the TUI.
    The module creates a GridlineApp with the given repo_root and chat_enabled.
    Returns the path to the module file.
    """
    repo_root_str = str(repo_root.resolve())
    chat_flag = str(chat_enabled).lower()
    
    # Get the src directory path for imports
    src_path = str((Path(repo_root) / "src").resolve())
    
    module_code = f'''import sys
sys.path.insert(0, "{src_path}")
from pathlib import Path
from rig_tools.tui_grid import GridlineApp

class RigWindowApp(GridlineApp):
    def __init__(self):
        super().__init__(Path("{repo_root_str}"), chat_enabled={chat_flag})

if __name__ == "__main__":
    app = RigWindowApp()
    app.run()
'''
    
    # Create temp directory for the module
    temp_dir = Path(tempfile.mkdtemp(prefix="rig_window_"))
    module_path = temp_dir / f"{module_name}.py"
    module_path.write_text(module_code)
    
    return module_path


def _get_server_process(module_path: Path, host: str, port: int) -> subprocess.Popen:
    """Start textual-serve as a subprocess with the given module."""
    # textual-serve expects: python -m textual_serve --port PORT --host HOST MODULE:Class
    module_dir = module_path.parent
    module_name = module_path.stem
    command = [
        sys.executable, "-m", "textual_serve",
        "--port", str(port),
        "--host", host,
        f"{module_name}:RigWindowApp"
    ]
    
    # Set PYTHONPATH so textual-serve can find our temp module
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{module_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"
    
    proc = subprocess.Popen(
        command,
        cwd=module_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return proc


def open_window(repo_root: Path, dry_run: bool, host: str, port: Optional[int], browser: bool = False, allow_lan: bool = False, chat_enabled: bool = False) -> Dict[str, Any]:
    """
    Open Rig OS window using textual-serve and pywebview.
    
    For dry-run: Returns planned session info without starting anything.
    For execution: 
        1. Creates a temporary module with the TUI app
        2. Starts textual-serve on the specified port
        3. Opens the URL in pywebview (native window) or browser
    
    Args:
        repo_root: Repository root path
        dry_run: If True, only plan the session without starting
        host: Host to bind the server
        port: Port to bind (random if None)
        browser: If True, prefer browser over pywebview
        allow_lan: If True, allow binding to 0.0.0.0
        chat_enabled: If True, enable chat/slash console in Gridline
    """
    session_id = f"win-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    
    if host == "0.0.0.0" and not allow_lan:
        return {"status": "failed", "error": "Refusing to bind 0.0.0.0 without --allow-lan"}

    port = port or find_free_port()
    textual_available = get_textual_available()
    textual_serve_available = get_textual_serve_available()
    has_pywebview = get_pywebview()
    
    warnings: list[str] = []
    
    if not textual_available:
        warnings.append("Textual not installed. Install with: pip install -e .")
    
    if not textual_serve_available:
        warnings.append("textual-serve not installed. Install with: pip install textual-serve")
    
    if dry_run:
        return {
            "schema_version": WINDOW_SESSION_SCHEMA_VERSION,
            "session_id": session_id,
            "created_at": _utc_now(),
            "mode": "dry_run",
            "host": host,
            "port": port,
            "url": f"http://{host}:{port}",
            "command_argv": [sys.executable, "-m", "rig", "tui", "--window"],
            "server_pid": None,
            "token_enabled": False,
            "status": "dry_run",
            "warnings": warnings,
            "authoritative": False
        }
    
    # For execution
    if not textual_available or not textual_serve_available:
        return {
            "status": "failed", 
            "error": "Missing dependencies",
            "warnings": warnings
        }
    
    # Create temporary module for textual-serve
    temp_module_path = _create_textual_app_module(repo_root, chat_enabled=chat_enabled)
    temp_module_dir = temp_module_path.parent
    
    url = f"http://{host}:{port}"
    
    session = {
        "schema_version": WINDOW_SESSION_SCHEMA_VERSION,
        "session_id": session_id,
        "created_at": _utc_now(),
        "mode": "pywebview" if has_pywebview else "browser",
        "host": host,
        "port": port,
        "url": url,
        "command_argv": [sys.executable, "-m", "rig", "tui", "--window"],
        "server_pid": None,
        "token_enabled": False,
        "status": "planned",
        "warnings": warnings,
        "authoritative": False
    }
    
    # Start textual-serve server
    server_proc = _get_server_process(temp_module_path, host, port)
    session["server_pid"] = server_proc.pid
    session["status"] = "running"
    
    save_session(repo_root, session)
    
    # Wait for server to start (textual-serve takes a moment)
    time.sleep(2)
    
    # Try to open in pywebview first, fallback to browser
    if has_pywebview:
        try:
            import webview
            # Create window with the URL
            webview.create_window('Rig OS', url, width=1200, height=800)
            # Start monitoring server in background thread
            def monitor_server():
                try:
                    server_proc.wait()
                except:
                    pass
                finally:
                    try:
                        shutil.rmtree(temp_module_path.parent)
                    except Exception:
                        pass
            threading.Thread(target=monitor_server, daemon=True).start()
            
            # webview.start() must be called on main thread and blocks
            # The server process will be monitored in the background thread
            try:
                webview.start()
            except KeyboardInterrupt:
                server_proc.terminate()
                try:
                    shutil.rmtree(temp_module_path.parent)
                except Exception:
                    pass
            
            session["status"] = "stopped"
            save_session(repo_root, session)
            return session
            
        except Exception as e:
            warnings.append(f"pywebview failed: {e}. Falling back to browser.")
            session["warnings"] = warnings
            save_session(repo_root, session)
            server_proc.terminate()
    
    # Fallback to browser
    try:
        import webbrowser
        webbrowser.open(url)
        # Wait for server in main thread
        try:
            server_proc.wait()
        except KeyboardInterrupt:
            server_proc.terminate()
    except Exception as e:
        warnings.append(f"Browser launch failed: {e}")
        session["warnings"] = warnings
        save_session(repo_root, session)
        server_proc.terminate()
    finally:
        # Clean up temp files
        try:
            shutil.rmtree(temp_module_path.parent)
        except Exception:
            pass
    
    session["status"] = "stopped"
    save_session(repo_root, session)
    return session
