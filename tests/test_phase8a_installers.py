from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
PYTHON_GE_314 = sys.version_info >= (3, 14)


def test_pyproject_requires_python_314() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.14"


def test_default_dependencies_include_runtime_surfaces() -> None:
    deps = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for name in ["textual", "pywebview", "mlx", "llama-cpp-python", "psutil", "tomli-w"]:
        assert name in deps


def test_window_command_registered_and_window_open_dry_run() -> None:
    help_proc = subprocess.run([str(PYTHON), "-m", "rig", "--help"], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    assert help_proc.returncode == 0, help_proc.stderr
    assert "ui" in help_proc.stdout.lower()
    proc = subprocess.run([str(PYTHON), "-m", "rig", "window", "open", "--dry-run"], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout or proc.stderr


def test_doctor_deps_reports_without_traceback() -> None:
    proc = subprocess.run([str(PYTHON), "-m", "rig", "doctor", "deps"], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert "python_version" in proc.stdout
    assert "Traceback" not in proc.stderr


def test_benchmark_and_model_recommend_write_artifacts_without_downloads(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    proc = subprocess.run([str(PYTHON), "-m", "rig", "benchmark", "run", "--dry-run"], cwd=repo, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert not (repo / ".build" / "rig" / "benchmarks").exists()
    rec = subprocess.run([str(PYTHON), "-m", "rig", "model", "recommend", "--dry-run"], cwd=repo, text=True, capture_output=True, check=False)
    assert rec.returncode == 0, rec.stderr


def test_packaging_docs_exist() -> None:
    for path in [
        REPO_ROOT / "docs/dev/rig/PYTHON_314_POLICY.md",
        REPO_ROOT / "docs/dev/rig/BATTERIES_INCLUDED_INSTALL_RECIPES.md",
        REPO_ROOT / "docs/dev/rig/LOCAL_RUNTIME_BENCHMARKS.md",
        REPO_ROOT / "packaging/pipx.md",
        REPO_ROOT / "packaging/uv.md",
        REPO_ROOT / "packaging/homebrew/rig.rb",
        REPO_ROOT / "packaging/npm/package.json",
        REPO_ROOT / "packaging/npm/README.md",
    ]:
        assert path.exists()
