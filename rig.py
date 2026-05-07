#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() not in {ROOT, ROOT / "scripts"}]
__path__ = [str(SRC / "rig")]
if __spec__ is not None:
    __spec__.submodule_search_locations = __path__


if __name__ == "__main__":
    sys.path = [str(SRC)] + [p for p in sys.path if Path(p).resolve() not in {ROOT, ROOT / "scripts"}]
    from rig.cli.main import main
    raise SystemExit(main())
