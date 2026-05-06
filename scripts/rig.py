#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() not in {ROOT, ROOT / "scripts"}]

from rig.main import main


if __name__ == "__main__":
    raise SystemExit(main())
