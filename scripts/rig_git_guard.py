#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from shutil import which

BLOCKED_COMMANDS = {
    "restore",
    "clean",
    "stash",
    "rebase",
    "merge",
}

ALLOWED_INSPECTION_COMMANDS = {
    "status",
    "diff",
    "log",
    "rev-parse",
    "branch",
    "show",
}

KNOWN_GIT_PATHS = (
    "/opt/homebrew/bin/git",
    "/usr/bin/git",
    "/usr/local/bin/git",
)

HEX40_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _resolve_guard_path() -> Path:
    return Path(__file__).resolve()


def _is_guard_path(candidate: str) -> bool:
    try:
        return Path(candidate).resolve() == _resolve_guard_path()
    except Exception:
        return False


def _find_real_git() -> str | None:
    env_git = os.environ.get("RIG_REAL_GIT")
    if env_git:
        if _is_guard_path(env_git):
            return None
        resolved = Path(env_git).resolve()
        if resolved.exists():
            return str(resolved)
        return None

    for candidate in KNOWN_GIT_PATHS:
        if _is_guard_path(candidate):
            continue
        path = Path(candidate)
        if path.exists():
            return str(path.resolve())

    guard_dir = _script_dir()
    path_entries = []
    for item in os.environ.get("PATH", "").split(os.pathsep):
        if not item:
            continue
        try:
            if Path(item).resolve() == guard_dir:
                continue
        except Exception:
            pass
        path_entries.append(item)

    which_path = which("git", path=os.pathsep.join(path_entries))
    if which_path and not _is_guard_path(which_path):
        return str(Path(which_path).resolve())
    return None


def _blocked(message: str) -> int:
    print(f"Blocked by Rig Git guard: {message}\n"
          "Rig agent sessions must patch forward from dirty files. "
          "Do not restore, reset, checkout, stash, clean, rebase, or merge to clear user-owned dirt.",
          file=sys.stderr)
    return 126


def _matches_absolute_git_bypass(argv: list[str]) -> bool:
    return any(arg in KNOWN_GIT_PATHS for arg in argv)


def _is_hex_commitish(value: str) -> bool:
    return bool(HEX40_RE.fullmatch(value))


def _blocked_checkout(argv: list[str]) -> bool:
    if len(argv) == 1:
        return True
    if argv[1] == "--":
        return True
    if len(argv) >= 2 and _is_hex_commitish(argv[1]):
        return True
    return False


def _blocked_reset(argv: list[str]) -> bool:
    if len(argv) == 1:
        return True
    destructive_modes = {"--hard", "--merge", "--keep"}
    return any(arg in destructive_modes for arg in argv[1:4])


def _blocked_stash(argv: list[str]) -> bool:
    return True


def _blocked_branch(argv: list[str]) -> bool:
    return any(arg == "-D" or arg == "--delete" for arg in argv[1:])


def _should_block(argv: list[str]) -> tuple[bool, str]:
    if not argv:
        return False, ""
    if _matches_absolute_git_bypass(argv):
        return True, "call git through the Rig guard, not via an absolute Git path"

    command = argv[0]
    if command == "restore":
        return True, "git restore is blocked by policy"
    if command == "clean":
        return True, "git clean is blocked by policy"
    if command == "stash":
        return True, "git stash is blocked by policy"
    if command == "rebase":
        return True, "git rebase is blocked by policy"
    if command == "merge":
        return True, "git merge is blocked by policy"
    if command == "checkout":
        if _blocked_checkout(argv):
            return True, "git checkout destructive forms are blocked by policy"
    if command == "reset":
        if _blocked_reset(argv):
            return True, "git reset destructive modes are blocked by policy"
        return True, "all git reset modes are blocked by policy in agent sessions"
    if command == "branch" and _blocked_branch(argv):
        return True, "git branch -D is blocked by policy"
    return False, ""


def main(argv: list[str]) -> int:
    if not argv:
        print("Blocked by Rig Git guard: no git arguments provided", file=sys.stderr)
        return 126

    should_block, reason = _should_block(argv)
    if should_block:
        return _blocked(reason)

    real_git = _find_real_git()
    if not real_git:
        print(
            "Blocked by Rig Git guard: unable to locate a real git binary.\n"
            "Set RIG_REAL_GIT or install git in /opt/homebrew/bin, /usr/bin, or /usr/local/bin.",
            file=sys.stderr,
        )
        return 127

    proc = subprocess.run([real_git, *argv], check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
