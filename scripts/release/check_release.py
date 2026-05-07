#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    proc = subprocess.run([sys.executable, "-m", "rig", "release", "check"], text=True, capture_output=True, check=False)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
