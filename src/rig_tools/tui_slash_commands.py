from __future__ import annotations


def parse_slash_command(text: str) -> dict[str, str]:
    text = text.strip()
    if not text.startswith("/"):
        return {"kind": "intent"}
    cmd = text.split(maxsplit=1)[0][1:]
    mapping = {
        "help": "help",
        "status": "status",
        "init": "init",
        "run": "run",
        "jobs": "jobs",
        "doctor": "doctor",
        "clear": "clear",
    }
    return {"kind": "slash", "command": mapping.get(cmd, "unknown")}
