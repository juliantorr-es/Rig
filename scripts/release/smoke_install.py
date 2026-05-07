#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys


def _run(cmd: list[str]) -> int:
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def main() -> int:
    commands = [
        [sys.executable, "-m", "pip", "install", "-e", "."],
        [sys.executable, "-m", "rig", "--help"],
        [sys.executable, "-m", "rig", "init", "--dry-run"],
        [sys.executable, "-m", "rig", "status"],
        [sys.executable, "-m", "rig", "doctor"],
        [sys.executable, "-m", "rig", "doctor", "queue"],
        [sys.executable, "-m", "rig", "tui", "--dry-run"],
        [sys.executable, "-m", "rig", "debug", "bundle", "--dry-run"],
    ]
    for cmd in commands:
        rc = _run(cmd)
        if rc != 0:
            return rc
    if shutil.which("pipx"):
        if _run(["pipx", "install", "."]) != 0:
            return 1
    if shutil.which("uv"):
        if _run(["uv", "tool", "install", "."]) != 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
