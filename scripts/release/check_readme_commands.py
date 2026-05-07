#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


COMMAND_RE = re.compile(r"^\s*[$>]\s*(rig\s+.+)$", re.MULTILINE)


def _extract_commands(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return COMMAND_RE.findall(text)


def main() -> int:
    docs = [Path("README.md"), Path("docs/quickstart.md"), Path("docs/cli.md"), Path("docs/troubleshooting.md")]
    required = {"rig init", "rig tui", "rig run", "rig debug bundle"}
    found = set()
    for doc in docs:
        if not doc.exists():
            continue
        for cmd in _extract_commands(doc):
            found.add(" ".join(cmd.split()[:3]))
    missing = [item for item in required if not any(cmd.startswith(item) for cmd in found)]
    if missing:
        print("\n".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
