from __future__ import annotations

from rig_tools.tui_theme import status_label, status_marker


def redact(text: str) -> str:
    return text.replace("sk-", "<redacted>")


def render_chat_line(text: str, *, authoritative: bool = True) -> str:
    prefix = "CHAT" if authoritative else "CHAT DRAFT — NOT EVIDENCE"
    return f"{prefix}: {redact(text)}"
