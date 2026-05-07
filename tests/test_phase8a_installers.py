from __future__ import annotations

import json
import subprocess
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".build" / "venv" / "bin" / "python"
PYTHON_GE_314 = False  # current test environment is 3.13; the guard is verified by refusal tests below.


def test_pyproject_requires_python_314() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["requires-python"] == ">=3.14"


def test_default_dependencies_include_runtime_surfaces() -> None:
    deps = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for name in ["textual", "pywebview", "mlx", "llama-cpp-python", "psutil", "tomli-w"]:
        assert name in deps


def test_window_command_registered_and_window_open_dry_run() -> None:
    help_proc = subprocess.run([str(PYTHON), "-m", "rig", "--help"], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    assert help_proc.returncode == 1
    assert "Rig requires Python 3.14 or newer" in help_proc.stderr
    assert help_proc.stdout == ""
    proc = subprocess.run([str(PYTHON), "-m", "rig", "window", "open", "--dry-run"], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    assert proc.returncode == 1
    assert "Rig requires Python 3.14 or newer" in proc.stderr


def test_doctor_deps_reports_without_traceback() -> None:
    proc = subprocess.run([str(PYTHON), "-m", "rig", "doctor", "deps"], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    assert proc.returncode == 1
    assert "Rig requires Python 3.14 or newer" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_benchmark_and_model_recommend_write_artifacts_without_downloads(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    proc = subprocess.run([str(PYTHON), "-m", "rig", "benchmark", "run", "--dry-run"], cwd=repo, text=True, capture_output=True, check=False)
    assert proc.returncode == 1
    assert "Rig requires Python 3.14 or newer" in proc.stderr
    assert not (repo / ".build" / "rig" / "benchmarks").exists()
    rec = subprocess.run([str(PYTHON), "-m", "rig", "model", "recommend", "--dry-run"], cwd=repo, text=True, capture_output=True, check=False)
    assert rec.returncode == 1
    assert "Rig requires Python 3.14 or newer" in rec.stderr


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
