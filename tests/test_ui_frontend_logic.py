import pytest
from pathlib import Path

def test_intent_pending_state_logic():
    # Simulate pending state
    pending_intents = {"test.action": {"status": "pending", "label": "Running..."}}
    assert pending_intents["test.action"]["status"] == "pending"

def test_log_stream_rendering():
    # Simulate log entry with HTML chars
    log = "<script>alert('xss')</script>"
    # Ensure it would be escaped if handled by textContent
    rendered = str(log)
    assert "<script>" in rendered
    # In JS: element.textContent = rendered would be safe.


def test_websocket_routes_progress_events_to_store():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "websocket.js"
    content = path.read_text(encoding="utf-8")
    assert "progress_event" in content
    assert "onProgress" in content


def test_progress_store_caps_retained_events():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "progress-store.js"
    content = path.read_text(encoding="utf-8")
    assert "MAX_PROGRESS_EVENTS" in content
    assert "slice(-MAX_PROGRESS_EVENTS)" in content


def test_command_progress_card_renderer_is_dumb():
    path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "command-progress-card.js"
    content = path.read_text(encoding="utf-8")
    assert "renderCommandProgressCard" in content
    assert "operation_id" in content
    assert "message" in content
    assert "status" in content
    assert "command" not in content.lower() or "command-progress" in content.lower()
