from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


def _sanitize(value: str| Optional) -> str:
    text = (value or "").replace("\n", " ").replace("\r", " ").strip()
    return text[:200]


def _escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\"", "\\\"")


@dataclass
class NotificationResult:
    requested: bool
    backend: str| Optional
    status: str
    error: str| Optional = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "notification_requested": self.requested,
            "notification_backend": self.backend,
            "notification_status": self.status,
            "notification_error": self.error,
        }


def detect_backends() -> dict[str, Any]:
    return {
        "osascript": shutil.which("osascript") is not None,
        "terminal-notifier": shutil.which("terminal-notifier") is not None,
        "none": True,
    }


def choose_backend(preferred: str| Optional = None) -> str| Optional:
    if preferred and preferred != "auto":
        return preferred
    if shutil.which("osascript"):
        return "osascript"
    if shutil.which("terminal-notifier"):
        return "terminal-notifier"
    return "none"


def build_osascript_command(*, title: str, subtitle: str| Optional, message: str| Optional) -> list[str]:
    title = _sanitize(title)
    subtitle = _sanitize(subtitle)
    message = _sanitize(message)
    parts = [f'display notification "{_escape_applescript(message)}"']
    if title:
        parts.append(f'with title "{_escape_applescript(title)}"')
    if subtitle:
        parts.append(f'subtitle "{_escape_applescript(subtitle)}"')
    return ["osascript", "-e", " ".join(parts)]


def send_notification(*, title: str, message: str, subtitle: str| Optional = None, backend: str| Optional = None) -> NotificationResult:
    backend = choose_backend(backend)
    if backend == "none":
        return NotificationResult(requested=True, backend=backend, status="skipped")
    if backend == "osascript":
        if not shutil.which("osascript"):
            return NotificationResult(requested=True, backend=backend, status="tool_missing", error="osascript not installed")
        cmd = build_osascript_command(title=title, subtitle=subtitle, message=message)
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
            if proc.returncode == 0:
                return NotificationResult(requested=True, backend=backend, status="sent")
            return NotificationResult(requested=True, backend=backend, status="failed", error=(proc.stderr or proc.stdout or "osascript failed").strip())
        except Exception as exc:
            return NotificationResult(requested=True, backend=backend, status="failed", error=str(exc))
    if backend == "terminal-notifier":
        if not shutil.which("terminal-notifier"):
            return NotificationResult(requested=True, backend=backend, status="tool_missing", error="terminal-notifier not installed")
        cmd = ["terminal-notifier", "-title", _sanitize(title), "-message", _sanitize(message)]
        if subtitle:
            cmd.extend(["-subtitle", _sanitize(subtitle)])
        try:
            proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
            if proc.returncode == 0:
                return NotificationResult(requested=True, backend=backend, status="sent")
            return NotificationResult(requested=True, backend=backend, status="failed", error=(proc.stderr or proc.stdout or "terminal-notifier failed").strip())
        except Exception as exc:
            return NotificationResult(requested=True, backend=backend, status="failed", error=str(exc))
    return NotificationResult(requested=True, backend=backend, status="tool_missing", error="unknown backend")


def should_notify(trigger: str| Optional, result_status: str| Optional) -> bool:
    if not trigger or trigger == "never":
        return False
    if trigger == "finish":
        return result_status in {"passed", "failed", "known_blocked", "blocked", "ready_to_commit"}
    if trigger == "failure":
        return result_status in {"failed"}
    if trigger == "known-blocked":
        return result_status == "known_blocked"
    if trigger == "blocked":
        return result_status == "blocked"
    if trigger == "ready":
        return result_status == "ready_to_commit"
    return False

