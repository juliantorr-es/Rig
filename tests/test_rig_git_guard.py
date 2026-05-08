from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _write_fake_git(path: Path) -> Path:
    script = path / "fake-git.py"
    script.write_text(
        """#!/usr/bin/env python3
import os
import pathlib
import sys

log = pathlib.Path(os.environ["RIG_FAKE_GIT_LOG"])
log.write_text("\\n".join(sys.argv[1:]), encoding="utf-8")
print("FAKE_GIT " + " ".join(sys.argv[1:]))
""",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _run_guard(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "scripts/rig_git_guard.py", *args],
        cwd=Path(__file__).parent.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture()
def fake_git_env(tmp_path: Path) -> dict[str, str]:
    fake_git = _write_fake_git(tmp_path)
    log = tmp_path / "git-args.txt"
    env = os.environ.copy()
    env["RIG_REAL_GIT"] = str(fake_git)
    env["RIG_FAKE_GIT_LOG"] = str(log)
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    return env


def test_status_short_branch_is_allowed_and_delegates(fake_git_env: dict[str, str]) -> None:
    log = Path(fake_git_env["RIG_FAKE_GIT_LOG"])
    proc = _run_guard(["status", "--short", "--branch"], env=fake_git_env)

    assert proc.returncode == 0
    assert "FAKE_GIT status --short --branch" in proc.stdout
    assert log.read_text(encoding="utf-8") == "status\n--short\n--branch"


@pytest.mark.parametrize(
    "args",
    [
        ["restore", "AGENTS.md"],
        ["clean", "-fd"],
        ["stash"],
        ["rebase", "main"],
        ["merge", "main"],
        ["reset", "--hard"],
        ["reset", "--merge"],
        ["checkout", "--", "AGENTS.md"],
        ["checkout", "0123456789abcdef0123456789abcdef01234567"],
        ["branch", "-D", "foo"],
    ],
)
def test_destructive_commands_are_blocked(fake_git_env: dict[str, str], args: list[str]) -> None:
    proc = _run_guard(args, env=fake_git_env)

    assert proc.returncode == 126
    assert "Blocked by Rig Git guard" in proc.stderr
    assert "patch forward" in proc.stderr.lower()


@pytest.mark.parametrize(
    "args",
    [
        ["status", "--short", "--branch"],
        ["diff"],
        ["diff", "--staged"],
        ["log", "--oneline", "-5"],
        ["rev-parse", "--short", "HEAD"],
        ["branch", "--show-current"],
    ],
)
def test_safe_commands_are_allowed(fake_git_env: dict[str, str], args: list[str]) -> None:
    proc = _run_guard(args, env=fake_git_env)

    assert proc.returncode == 0
    assert "FAKE_GIT" in proc.stdout


def test_real_git_discovery_honors_rig_real_git(tmp_path: Path) -> None:
    fake_git = _write_fake_git(tmp_path)
    env = os.environ.copy()
    env["RIG_REAL_GIT"] = str(fake_git)
    env["RIG_FAKE_GIT_LOG"] = str(tmp_path / "git-args.txt")
    proc = _run_guard(["status", "--short", "--branch"], env=env)

    assert proc.returncode == 0
    assert "FAKE_GIT status --short --branch" in proc.stdout


def test_discovery_avoids_recursively_selecting_the_guard(tmp_path: Path) -> None:
    guard = Path(__file__).parent.parent / "scripts" / "rig_git_guard.py"
    env = os.environ.copy()
    env["RIG_REAL_GIT"] = str(guard)

    proc = _run_guard(["status", "--short", "--branch"], env=env)

    assert proc.returncode == 127
    assert "unable to locate a real git binary" in proc.stderr.lower()


def test_absolute_git_path_bypass_is_blocked(fake_git_env: dict[str, str]) -> None:
    proc = _run_guard(["/usr/bin/git", "status"], env=fake_git_env)

    assert proc.returncode == 126
    assert "absolute git path" in proc.stderr.lower()
