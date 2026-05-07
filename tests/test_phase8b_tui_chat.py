from __future__ import annotations

from rig_tools.tui_chat import preview_intent
from rig_tools.tui_chat_rendering import redact
from rig_tools.tui_slash_commands import parse_slash_command


def test_slash_commands_map_to_canonical_actions() -> None:
    assert parse_slash_command("/status")["command"] == "status"
    assert parse_slash_command("/run").get("command") == "run"


def test_natural_language_creates_preview_not_execution() -> None:
    preview = preview_intent("Please fix the import error in the parser")
    assert preview["kind"] == "intent"
    assert "proposal" in preview["preview"].lower()


def test_chat_redacts_secrets() -> None:
    assert "sk-test" not in redact("key sk-test-123")
    assert "<redacted>" in redact("key sk-test-123")
