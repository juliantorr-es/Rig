from __future__ import annotations

import json
import time
from typing import Any, Optional, Union
from rich.text import Text

def bauhaus_marker_for_status(status: str, risk: str = "low", artifact: bool = False) -> str:
    """Returns geometric Bauhaus markers for states."""
    if artifact: return "\u25c6" # ◆
    
    s = str(status).lower()
    r = str(risk).lower()
    
    if s in {"blocked", "failed", "critical"} or r == "high": return "\u25b2" # ▲
    if s in {"approval", "warning", "pending"} or r == "medium": return "\u25a0" # ■
    if s in {"running", "queued", "in_progress", "started"}: return "\u25cf" # ●
    if s in {"passed", "done", "complete", "review", "passed"}: return "\u25ac" # ▬
    return "\u00b7" # ·

def normalize_event_label(etype: str, status: Optional[str] = None) -> str:
    """Normalizes internal event types to human operator labels."""
    e = etype.lower()
    if e == "run_started": return "START"
    if e == "run_finished":
        if status == "passed": return "PASS"
        if status == "failed": return "FAIL"
        return "FINISH"
    if e == "artifact_written": return "ARTIFACT"
    if e == "mode_switched": return "MODE"
    if e == "monitor_snapshot": return "SYSTEM"
    if e == "command_finished":
        if status == "passed": return "PASS"
        return "FAIL"
    
    # Fallback to truncated uppercase
    return etype.upper()[:8]


def event_semantic_class(event: dict[str, Any]) -> str:
    """Maps a structured event to a stable semantic color class for the TUI."""
    etype = str(event.get("event_type") or "").lower()
    attrs = event.get("attributes") or {}
    status = str(attrs.get("status") or "").lower()
    if etype in {"run_finished", "command_finished"} and status in {"passed", "complete", "completed"}:
        return "semantic-pass"
    if etype in {"run_finished", "command_finished"} and status in {"failed", "error"}:
        return "semantic-fail"
    if etype in {"monitor_snapshot", "telemetry_sample", "artifact_written"}:
        return "semantic-info"
    if status in {"blocked", "warning", "pending", "review"}:
        return "semantic-warn"
    if status in {"failed", "error", "unsafe"}:
        return "semantic-fail"
    if status in {"passed", "ready", "safe", "allowed"}:
        return "semantic-pass"
    return "semantic-info"

def render_tui_event(event_line: str, focus_task_id: Optional[str] = None) -> Optional[Text]:
    """Renders a single JSONL event line as a Bauhaus timeline Text object."""
    try:
        ev = json.loads(event_line)
        etype = ev.get("event_type", "unknown")
        if etype == "button_pressed": return None # Skip noisy UI events
        
        attr = ev.get("attributes", {})
        task = attr.get("task") or ""
        
        # Focus filtering
        if focus_task_id:
            if task and task != focus_task_id: return None
            msg_lower = str(attr.get("message", "")).lower()
            if focus_task_id.lower() not in msg_lower and not task:
                 if etype not in {"milestone", "run_finished", "gate_decided"}: return None

        ts = (ev.get("timestamp_utc") or "")[11:19]
        raw_status = attr.get("status", "")
        label = normalize_event_label(etype, raw_status)
        marker = bauhaus_marker_for_status(raw_status or etype, risk=attr.get("risk", "low"))
        
        # Override markers for lifecycle
        if etype == "run_started": marker = "\u25cf" # ●
        elif etype == "run_finished": marker = "\u25ac" if raw_status == "passed" else "\u25b2"
        elif etype == "milestone": marker = "\u25c6" # ◆
        
        msg = attr.get("message") or attr.get("milestone") or attr.get("task") or ""
        cmd = ev.get("command_group") or ""
        
        style = ""
        if label == "FAIL" or raw_status == "failed": style = "bold error"
        elif label == "PASS" or raw_status == "passed": style = "success"
        elif label == "MODE": style = "bold white"
        elif label == "START": style = "bold cyan"
        elif etype in {"monitor_snapshot", "telemetry_sample"}: style = "dim"
        
        content = f"{ts} {marker} {label:8} \u00b7 {cmd:10} \u00b7 {msg[:100]}"
        return Text(content, style=style)
        
    except Exception as exc:
        # Return a visible error receipt instead of swallowing
        return Text(f"EVENT ERROR \u00b7 {str(exc)[:50]}", style="bold red")

def render_command_result(command_id: str, status: str, duration: float, error: Optional[str] = None) -> Text:
    """Renders a command completion summary."""
    ts = time.strftime("%H:%M:%S")
    marker = "\u25ac" if status == "passed" else "\u25b2"
    label = "PASS" if status == "passed" else "FAIL"
    style = "success" if status == "passed" else "bold error"
    
    msg = f"{command_id} in {duration:.1f}s"
    if error: msg += f" \u00b7 {error}"
    
    content = f"{ts} {marker} {label:8} \u00b7 {msg}"
    return Text(content, style=style)


def render_human_event_line(event: dict[str, Any], focus_task_id: Optional[str] = None) -> Optional[str]:
    try:
        etype = str(event.get("event_type") or "unknown")
        attrs = event.get("attributes") or {}
        if etype == "button_pressed":
            return None
        task = str(attrs.get("task") or "")
        if focus_task_id and task and task != focus_task_id:
            return None
        ts = str(event.get("timestamp_utc") or "")[11:16]
        label = normalize_event_label(etype, str(attrs.get("status") or ""))
        msg = str(attrs.get("message") or attrs.get("milestone") or attrs.get("summary") or task or "")
        if focus_task_id and focus_task_id not in msg and task != focus_task_id and etype not in {"run_finished", "artifact_written", "gate_decided"}:
            return None
        receipt = attrs.get("receipt_path") or attrs.get("result_path") or attrs.get("path")
        if receipt:
            return f"{ts} {label} · {msg[:96]} · {str(receipt)[:80]}"
        return f"{ts} {label} · {msg[:120]}"
    except Exception:
        return None
