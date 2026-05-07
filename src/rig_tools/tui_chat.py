from __future__ import annotations

from rig_tools.tui_chat_state import TuiChatState
from rig_tools.tui_slash_commands import parse_slash_command


def preview_intent(text: str) -> dict[str, str]:
    parsed = parse_slash_command(text)
    if parsed.get("kind") == "slash":
        return {"kind": "slash", "command": parsed["command"], "preview": f"Run /{parsed['command']}"}
    return {"kind": "intent", "preview": "Create provider proposal?"}
