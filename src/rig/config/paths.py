from __future__ import annotations

import hashlib
import os
from pathlib import Path


def _home(name: str, fallback: str) -> Path:
    return Path(os.environ.get(name, fallback)).expanduser()


def config_home() -> Path:
    return _home("RIG_CONFIG_HOME", os.environ.get("XDG_CONFIG_HOME", "~/.config"))


def state_home() -> Path:
    return _home("RIG_STATE_HOME", os.environ.get("XDG_STATE_HOME", "~/.local/state"))


def cache_home() -> Path:
    return _home("RIG_CACHE_HOME", os.environ.get("XDG_CACHE_HOME", "~/.cache"))


def repo_hash(repo_root: Path) -> str:
    return hashlib.sha256(str(repo_root).encode("utf-8")).hexdigest()[:12]


def repo_state_root(repo_root: Path) -> Path:
    return repo_root / ".build" / "rig"


def worktree_root(repo_root: Path) -> Path:
    return state_home() / "rig" / "worktrees" / repo_hash(repo_root)


def config_file() -> Path:
    return config_home() / "rig" / "config.toml"

