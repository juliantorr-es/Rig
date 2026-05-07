from __future__ import annotations

from rig_tools.tui_command_registry import build_registry


def parse_slash_command(text: str) -> dict[str, str]:
    text = text.strip()
    if not text.startswith("/"):
        return {"kind": "intent"}
    command = text.split(maxsplit=1)[0][1:]
    registry = build_registry()
    spec = registry.get(command)
    if spec is None:
        return {"kind": "slash", "command": "unknown"}
    return {
        "kind": "slash",
        "command": spec.name,
        "action_type": spec.action_type,
        "usage": spec.usage,
        "description": spec.description,
    }

