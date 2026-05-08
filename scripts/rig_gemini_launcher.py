#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
GUARD_GIT = SCRIPTS_DIR / "git"
COMMON_GEMINI_NAMES = ("gemini", "mistral-gemini")
GUARD_BIN_ENV = "RIG_GIT_GUARD_BIN"


def _path_entries(path: str | None) -> list[str]:
    if not path:
        return []
    return [entry for entry in path.split(os.pathsep) if entry]


def _prepend_scripts_path(env: dict[str, str]) -> dict[str, str]:
    updated = dict(env)
    guard_bin = Path(updated.get(GUARD_BIN_ENV, str(SCRIPTS_DIR))).expanduser()
    current = updated.get("PATH", "")
    updated["PATH"] = os.pathsep.join([str(guard_bin), current]) if current else str(guard_bin)
    return updated


def _guarded_git_path(env: dict[str, str]) -> str | None:
    candidate = shutil.which("git", path=env.get("PATH"))
    if candidate is None:
        return None
    resolved = Path(candidate).resolve()
    try:
        if resolved.samefile(GUARD_GIT):
            return candidate
    except FileNotFoundError:
        pass
    if candidate == str(GUARD_GIT):
        return candidate
    return None


def _discover_gemini(env: dict[str, str]) -> str | None:
    override = env.get("RIG_REAL_GEMINI")
    if override:
        candidate = Path(override)
        if candidate.exists() and candidate.is_file():
            return str(candidate)
        return None

    search_dirs = _path_entries(env.get("PATH"))
    filtered_dirs = [entry for entry in search_dirs if Path(entry).resolve() != SCRIPTS_DIR.resolve()]
    filtered_path = os.pathsep.join(filtered_dirs)

    for name in COMMON_GEMINI_NAMES:
        candidate = shutil.which(name, path=filtered_path)
        if candidate:
            resolved = Path(candidate).resolve()
            if resolved == Path(__file__).resolve() or resolved == GUARD_GIT.resolve():
                continue
            return candidate
    return None


def _doctor(env: dict[str, str]) -> int:
    launched_env = _prepend_scripts_path(env)
    git_path = _guarded_git_path(launched_env)
    gemini_path = _discover_gemini(launched_env)
    path_entries = _path_entries(launched_env.get("PATH"))
    print(f"repo_root: {REPO_ROOT}")
    print(f"guard_path: {GUARD_GIT}")
    print(f"which_git: {git_path or 'NOT_FOUND'}")
    print(f"guard_active: {'yes' if git_path else 'no'}")
    print(f"RIG_REAL_GEMINI: {'set' if env.get('RIG_REAL_GEMINI') else 'unset'}")
    print(f"discovered_gemini: {gemini_path or 'NOT_FOUND'}")
    print("path_head:")
    for entry in path_entries[:5]:
        print(f"  - {entry}")
    return 0 if git_path else 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    env = dict(os.environ)
    if "--doctor" in argv:
        return _doctor(env)

    env = _prepend_scripts_path(env)
    git_path = _guarded_git_path(env)
    if not git_path:
        print(
            "Blocked by Rig Gemini launcher: guarded git is not active.\n"
            f"Expected `which git` to resolve to {GUARD_GIT}.\n"
            "Set PATH so the Rig Git guard comes first before launching Gemini.",
            file=sys.stderr,
        )
        return 126

    gemini_path = _discover_gemini(env)
    if not gemini_path:
        print(
            "Blocked by Rig Gemini launcher: no Gemini executable found.\n"
            "Set RIG_REAL_GEMINI or install `gemini`/`mistral-gemini` on PATH.",
            file=sys.stderr,
        )
        return 127

    result = subprocess.run([gemini_path, *argv], env=env, check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
