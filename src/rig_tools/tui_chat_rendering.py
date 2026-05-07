from __future__ import annotations


def redact(text: str) -> str:
    return text.replace("sk-", "<redacted>")
