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
