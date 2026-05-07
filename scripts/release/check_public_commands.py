#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    contract = json.loads(Path("docs/dev/rig/public_command_contract.json").read_text(encoding="utf-8"))
    proc = subprocess.run([sys.executable, "-m", "rig", "--help"], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode
    help_text = proc.stdout
    missing = []
    for group in contract.values():
        if not isinstance(group, list):
            continue
        for entry in group:
            if not isinstance(entry, dict):
                continue
            command = entry["command"]
            if command.startswith("rig ") and command.split()[1] not in help_text:
                missing.append(command)
    if missing:
        print("\n".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
