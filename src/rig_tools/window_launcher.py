import json
import logging
import os
import random
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Dict
from pathlib import Path
from typing import Any

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

def get_textual_bin() -> Optional[str]:
    return shutil.which("textual") or shutil.which("textual-serve")

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

def open_window(repo_root: Path, dry_run: bool, host: str, port: Optional[int], browser: bool = False, allow_lan: bool = False) -> Dict[str, Any]:
    session_id = f"win-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    
    if host == "0.0.0.0" and not allow_lan:
        return {"status": "failed", "error": "Refusing to bind 0.0.0.0 without --allow-lan"}

    port = port or find_free_port()
    
    textual_bin = get_textual_bin()
    has_pywebview = get_pywebview()
    
    warnings = []
    
    if not textual_bin:
        if not dry_run:
            return {"status": "failed", "error": "textual or textual-serve not found. Please install the `tui` extra or textual directly."}
        textual_bin = "textual"
        warnings.append("textual not found, using placeholder for dry-run")

    mode = "browser" if browser or not has_pywebview else "pywebview"
    if dry_run:
        mode = "dry_run"

    url = f"http://{host}:{port}"
    token_enabled = False # Could add a secure token in URL later
    
    command_argv = [
        textual_bin, "serve",
        "--host", host,
        "--port", str(port),
        "--",
        sys.executable, str(repo_root / "scripts" / "rig.py"), "tui"
    ]
    
    session = {
        "schema_version": WINDOW_SESSION_SCHEMA_VERSION,
        "session_id": session_id,
        "created_at": _utc_now(),
        "mode": mode,
        "host": host,
        "port": port,
        "url": url,
        "command_argv": command_argv,
        "server_pid": None,
        "token_enabled": token_enabled,
        "status": "planned",
        "warnings": warnings,
        "authoritative": False
    }

    if dry_run:
        session["status"] = "dry_run"
        save_session(repo_root, session)
        return session

    # Logs
    logs_dir = repo_root / ".build" / "rig" / "window" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    out_log = logs_dir / f"{session_id}.out.log"
    err_log = logs_dir / f"{session_id}.err.log"

    session["status"] = "running"
    
    # Start server
    try:
        with open(out_log, "w") as stdout, open(err_log, "w") as stderr:
            proc = subprocess.Popen(
                command_argv,
                stdout=stdout,
                stderr=stderr,
                cwd=str(repo_root)
            )
        session["server_pid"] = proc.pid
    except Exception as e:
        session["status"] = "failed"
        session["error"] = str(e)
        save_session(repo_root, session)
        return session

    save_session(repo_root, session)
    time.sleep(1) # wait for server to bind

    # Launch frontend
    if mode == "pywebview":
        try:
            import webview
            # Wait a little more if needed
            webview.create_window('Rig OS', url)
            webview.start()
        except Exception as e:
            session["warnings"].append(f"pywebview failed: {e}. Falling back to browser.")
            mode = "browser"

    if mode == "browser":
        import webbrowser
        webbrowser.open(url)
        # We block here if we want, or just let the server run in background?
        # Actually MVP might just keep it running until interrupted
        try:
            proc.wait()
        except KeyboardInterrupt:
            pass

    # Server stopped
    if proc.poll() is None:
        proc.terminate()
        proc.wait()
        
    session["status"] = "stopped"
    save_session(repo_root, session)
    return session
