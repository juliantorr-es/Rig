from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_GE_314 = sys.version_info >= (3, 14)


def run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "rig", *args], cwd=REPO_ROOT, text=True, input=input_text, capture_output=True, check=False)


def test_readme_leads_with_product_positioning() -> None:
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert text.lstrip().startswith("# Rig")
    assert "cryptographically governed control plane for local ai coding" in text.lower()
    assert "Anigma" in text
    assert text.index("Anigma") > text.lower().index("models propose. rig disposes.")


def test_init_dry_run_performs_no_writes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    pyproject = repo / "pyproject.toml"
    pyproject.write_text("[project]\nname = \"demo\"\nversion = \"0.1.0\"\n", encoding="utf-8")
    proc = subprocess.run([sys.executable, "-m", "rig", "init", "--dry-run"], cwd=repo, text=True, capture_output=True, check=False)
    if not PYTHON_GE_314:
        assert proc.returncode == 1
        assert "Rig requires Python 3.14 or newer" in proc.stderr
        return
    assert proc.returncode == 0, proc.stderr
    assert not (repo / ".gitignore").exists()
    assert pyproject.read_text(encoding="utf-8") == "[project]\nname = \"demo\"\nversion = \"0.1.0\"\n"


def test_init_yes_adds_gitignore_and_promptless_success(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    proc = subprocess.run([sys.executable, "-m", "rig", "init", "--yes"], cwd=repo, text=True, capture_output=True, check=False)
    if not PYTHON_GE_314:
        assert proc.returncode == 1
        assert "Rig requires Python 3.14 or newer" in proc.stderr
        return
    assert proc.returncode == 0, proc.stderr
    assert (repo / ".gitignore").exists()
    assert ".build/rig/" in (repo / ".gitignore").read_text(encoding="utf-8")
    assert "Next:" in proc.stdout


def test_scripts_directory_contains_only_wrappers_or_utilities() -> None:
    scripts = [path for path in (REPO_ROOT / "scripts").glob("*.py") if path.name not in {"check_rig_local.py"}]
    content = "\n".join(path.read_text(encoding="utf-8") for path in scripts)
    assert "workspace_governance" not in content
    assert "runtime_registry" not in content
    assert "agent_proposals" not in content
    assert "model_registry" not in content
