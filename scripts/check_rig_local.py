#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    venv_python = root / ".build" / "venv" / "bin" / "python"
    python = str(venv_python) if venv_python.exists() else sys.executable
    raise SystemExit(subprocess.run([python, "-m", "pytest", "-q"], check=False).returncode)
