#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


def main() -> int:
    readme = Path("README.md").read_text(encoding="utf-8")
    required = ["rig init", "rig tui", "rig run --task", "rig debug bundle"]
    missing = [item for item in required if item not in readme]
    if missing:
        print("\n".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
