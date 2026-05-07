from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Any


def inspect_system() -> dict[str, Any]:
    return {
        "os": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "ram": "unknown",
        "metal": "available" if platform.system() == "Darwin" else "unavailable",
        "mlx": _has_module("mlx"),
    }


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False

