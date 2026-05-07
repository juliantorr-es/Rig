#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    proc = subprocess.run([sys.executable, "-m", "rig", "--help"], text=True, capture_output=True, check=False)
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
