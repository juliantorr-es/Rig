from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

from .paths import config_file, worktree_root


def defaults() -> dict[str, Any]:
    return {
        "default_mode": "safe",
        "worktree_root": None,
        "log_dir": None,
    }


def load_global_config() -> dict[str, Any]:
    path = config_file()
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_repo_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "pyproject.toml"
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return ((data.get("tool") or {}).get("rig") or {})


def merge_config(repo_root: Path, cli_overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    out = copy.deepcopy(defaults())
    out.update(load_global_config())
    out.update(load_repo_config(repo_root))
    if cli_overrides:
        out.update(cli_overrides)
    out["repo_root"] = str(repo_root)
    out["config_file"] = str(config_file())
    out["state_dir"] = str(repo_root / ".build" / "rig")
    out["external_worktree_root"] = str(worktree_root(repo_root))
    out["sources"] = {
        "defaults": "built-in",
        "global_config": str(config_file()),
        "repo_config": str(repo_root / "pyproject.toml"),
        "cli": "runtime",
    }
    return out
