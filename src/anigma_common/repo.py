from __future__ import annotations
import subprocess
from functools import lru_cache
from pathlib import Path
from .ignore import should_ignore_path

@lru_cache(maxsize=1)
def _discover_repo_root() -> Path | None:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL).strip()
        if out:
            return Path(out)
    except Exception:
        return None
    return None

def repo_root() -> Path:
    root = _discover_repo_root()
    if root is not None:
        return root
    return Path(__file__).resolve().parents[2]

def repo_relative(path: Path | str) -> str:
    p = Path(path).resolve()
    try:
        return str(p.relative_to(repo_root()))
    except ValueError:
        return str(p)

def iter_repo_files():
    root = repo_root()
    for p in root.rglob("*"):
        if p.is_file() and not should_ignore_path(p):
            yield p
