#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=False)


def _emit(result: subprocess.CompletedProcess[str]) -> None:
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)


def _smoke(bin_cmd: list[str], *, cwd: Path) -> int:
    for cmd in [
        bin_cmd + ["--help"],
        bin_cmd + ["init", "--dry-run"],
        bin_cmd + ["status"],
        bin_cmd + ["doctor"],
        bin_cmd + ["release", "check", "--json"],
        bin_cmd + ["tui", "--dry-run"],
        bin_cmd + ["debug", "bundle", "--dry-run"],
    ]:
        result = _run(cmd, cwd=cwd)
        _emit(result)
        if result.returncode != 0:
            return result.returncode
    return 0


def _editable(repo_root: Path) -> int:
    result = _run([sys.executable, "-m", "pip", "install", "-e", "."], cwd=repo_root)
    _emit(result)
    if result.returncode != 0:
        return result.returncode
    return _smoke([sys.executable, "-m", "rig"], cwd=repo_root)


def _wheel(repo_root: Path) -> int:
    if shutil.which("build") is None:
        print("SKIP: build tool unavailable")
        return 0
    build_root = repo_root / ".build" / "rig" / "release-smoke"
    build_root.mkdir(parents=True, exist_ok=True)
    result = _run([sys.executable, "-m", "build"], cwd=repo_root)
    _emit(result)
    if result.returncode != 0:
        return result.returncode
    wheel = next((repo_root / "dist").glob("*.whl"), None)
    if wheel is None:
        print("wheel build did not produce a wheel")
        return 1
    venv_dir = build_root / "wheel-venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    python = venv_dir / "bin" / "python"
    install = _run([str(python), "-m", "pip", "install", str(wheel)], cwd=repo_root)
    _emit(install)
    if install.returncode != 0:
        return install.returncode
    return _smoke([str(python), "-m", "rig"], cwd=repo_root)


def _pipx(repo_root: Path) -> int:
    if shutil.which("pipx") is None:
        print("SKIP: pipx unavailable")
        return 0
    result = _run(["pipx", "install", "."], cwd=repo_root)
    _emit(result)
    return 0 if result.returncode == 0 else result.returncode


def _uv(repo_root: Path) -> int:
    if shutil.which("uv") is None:
        print("SKIP: uv unavailable")
        return 0
    result = _run(["uv", "tool", "install", "."], cwd=repo_root)
    _emit(result)
    return 0 if result.returncode == 0 else result.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--editable", action="store_true")
    parser.add_argument("--wheel", action="store_true")
    parser.add_argument("--pipx", action="store_true")
    parser.add_argument("--uv", action="store_true")
    args = parser.parse_args()
    repo_root = Path.cwd()
    rc = 0
    if args.editable:
        rc = _editable(repo_root)
    if rc == 0 and args.wheel:
        rc = _wheel(repo_root)
    if rc == 0 and args.pipx:
        rc = _pipx(repo_root)
    if rc == 0 and args.uv:
        rc = _uv(repo_root)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
