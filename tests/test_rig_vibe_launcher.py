from __future__ import annotations

import os
import stat
import sys
from pathlib import Path


def _make_executable(path: Path, contents: str) -> Path:
    path.write_text(contents, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _write_fake_vibe(tmp_path: Path, name: str, log_name: str = "vibe.log") -> Path:
    script = tmp_path / name
    _make_executable(
        script,
        """#!/bin/sh
set -eu
LOG_FILE="$RIG_FAKE_VIBE_LOG"
printf '%s\n' "$*" >> "$LOG_FILE"
printf 'FAKE_VIBE %s\n' "$*"
exit 0
""",
    )
    (tmp_path / log_name).touch()
    return script


def _run_launcher(*args: str, env: dict[str, str] | None = None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return __import__("subprocess").run(
        [sys.executable, "scripts/rig_vibe_launcher.py", *args],
        cwd=Path("/Users/user/Developer/GitHub/Rig"),
        env=full_env,
        text=True,
        capture_output=True,
    )


def _minimal_path(*entries: Path | str) -> str:
    return os.pathsep.join(str(entry) for entry in entries)


def test_doctor_reports_guard_active(tmp_path):
    fake_vibe = _write_fake_vibe(tmp_path, "vibe")
    env = {
        "PATH": _minimal_path(tmp_path, "/Users/user/Developer/GitHub/Rig/scripts"),
        "RIG_FAKE_VIBE_LOG": str(tmp_path / "vibe.log"),
        "RIG_REAL_VIBE": str(fake_vibe),
    }
    result = _run_launcher("--doctor", env=env)
    assert result.returncode == 0
    assert "guard_active: yes" in result.stdout
    assert "which_git: /Users/user/Developer/GitHub/Rig/scripts/git" in result.stdout
    assert "RIG_REAL_VIBE: set" in result.stdout


def test_launcher_fails_when_guard_inactive(tmp_path):
    fake_vibe = _write_fake_vibe(tmp_path, "vibe")
    env = {
        "PATH": str(tmp_path),
        "RIG_REAL_VIBE": str(fake_vibe),
        "RIG_GIT_GUARD_BIN": str(tmp_path / "no-guard"),
    }
    result = _run_launcher("--agent", "test", env=env)
    assert result.returncode == 126
    assert "Blocked by Rig Vibe launcher" in result.stderr


def test_launcher_honors_rig_real_vibe(tmp_path):
    fake_vibe = _write_fake_vibe(tmp_path, "custom-vibe")
    env = {
        "PATH": _minimal_path(tmp_path, "/Users/user/Developer/GitHub/Rig/scripts"),
        "RIG_FAKE_VIBE_LOG": str(tmp_path / "vibe.log"),
        "RIG_REAL_VIBE": str(fake_vibe),
    }
    result = _run_launcher("--agent", "alpha", env=env)
    assert result.returncode == 0
    assert "FAKE_VIBE --agent alpha" in result.stdout
    assert (tmp_path / "vibe.log").read_text(encoding="utf-8").strip() == "--agent alpha"


def test_launcher_discovers_vibe_on_path(tmp_path):
    fake_vibe = _write_fake_vibe(tmp_path, "vibe")
    env = {
        "PATH": _minimal_path(tmp_path, "/Users/user/Developer/GitHub/Rig/scripts"),
        "RIG_FAKE_VIBE_LOG": str(tmp_path / "vibe.log"),
    }
    result = _run_launcher("--agent", "beta", env=env)
    assert result.returncode == 0
    assert "FAKE_VIBE --agent beta" in result.stdout


def test_launcher_discovers_mistral_vibe_when_vibe_absent(tmp_path):
    fake_vibe = _write_fake_vibe(tmp_path, "mistral-vibe")
    env = {
        "PATH": _minimal_path(tmp_path, "/Users/user/Developer/GitHub/Rig/scripts"),
        "RIG_FAKE_VIBE_LOG": str(tmp_path / "vibe.log"),
    }
    result = _run_launcher("--agent", "gamma", env=env)
    assert result.returncode == 0
    assert "FAKE_VIBE --agent gamma" in result.stdout


def test_launcher_avoids_selecting_itself_recursively(tmp_path):
    env = {
        "PATH": os.pathsep.join([f"/Users/user/Developer/GitHub/Rig/scripts", str(tmp_path)]),
        "RIG_REAL_VIBE": str(tmp_path / "missing"),
    }
    result = _run_launcher("--doctor", env=env)
    assert result.returncode in (0, 1)
    assert "discovered_vibe: NOT_FOUND" in result.stdout or "discovered_vibe:" in result.stdout


def test_launcher_preserves_and_forwards_arguments(tmp_path):
    fake_vibe = _write_fake_vibe(tmp_path, "vibe")
    env = {
        "PATH": _minimal_path(tmp_path, "/Users/user/Developer/GitHub/Rig/scripts"),
        "RIG_FAKE_VIBE_LOG": str(tmp_path / "vibe.log"),
        "RIG_REAL_VIBE": str(fake_vibe),
    }
    result = _run_launcher("--agent", "delta", "--mode", "safe", env=env)
    assert result.returncode == 0
    assert "FAKE_VIBE --agent delta --mode safe" in result.stdout
    assert (tmp_path / "vibe.log").read_text(encoding="utf-8").strip() == "--agent delta --mode safe"


def test_launcher_prepends_repo_scripts_before_delegating(tmp_path):
    fake_vibe = _write_fake_vibe(tmp_path, "vibe")
    env = {
        "PATH": str(tmp_path),
        "RIG_FAKE_VIBE_LOG": str(tmp_path / "vibe.log"),
        "RIG_REAL_VIBE": str(fake_vibe),
    }
    result = _run_launcher("--doctor", env=env)
    assert result.returncode == 0
    assert "guard_path: /Users/user/Developer/GitHub/Rig/scripts/git" in result.stdout
    assert "path_head:" in result.stdout


def test_launcher_fails_when_no_vibe_found(tmp_path):
    env = {
        "PATH": _minimal_path(tmp_path, "/Users/user/Developer/GitHub/Rig/scripts"),
    }
    result = _run_launcher("--agent", "epsilon", env=env)
    assert result.returncode == 127
    assert "no Vibe executable found" in result.stderr
