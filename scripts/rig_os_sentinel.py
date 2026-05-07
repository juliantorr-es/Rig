#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


if __name__ == "__main__":
    sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() not in {ROOT, ROOT / "Scripts"}]
    from rig_os_sentinel import main
    raise SystemExit(main())
