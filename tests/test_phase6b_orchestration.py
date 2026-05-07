from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from rig_tools import schema_validation, orchestration

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = REPO_ROOT / ".build" / "venv" / "bin" / "python"
PYTHON_GE_314 = sys.version_info >= (3, 14)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(PYTHON), "-m", "rig", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def test_job_create_writes_durable_artifact() -> None:
    if not PYTHON_GE_314:
        proc = run("job", "create", "--task", "phase6-smoke", "--provider", "custom-command")
        assert proc.returncode == 1
        assert "Rig requires Python 3.14 or newer" in proc.stderr
        return
    proc = run("job", "create", "--task", "phase6-smoke", "--provider", "custom-command")
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["job_id"]
    assert (REPO_ROOT / ".build" / "rig" / "jobs" / f"{payload['job_id']}.json").exists()


def test_job_list_finds_created_jobs() -> None:
    if not PYTHON_GE_314:
        return
    create = run("job", "create", "--task", "phase6-list", "--provider", "custom-command")
    job_id = json.loads(create.stdout)["job_id"]
    listing = run("job", "list")
    assert listing.returncode == 0, listing.stderr
    assert job_id in listing.stdout


def test_job_inspect_returns_status_and_step() -> None:
    if not PYTHON_GE_314:
        return
    create = run("job", "create", "--task", "phase6-inspect", "--provider", "custom-command")
    job_id = json.loads(create.stdout)["job_id"]
    inspect = run("job", "inspect", job_id)
    payload = json.loads(inspect.stdout)
    assert payload["status"] == "queued"
    assert payload["current_step"] is None


def test_job_run_stops_at_acceptance_gate_and_no_auto_apply() -> None:
    if not PYTHON_GE_314:
        return
    create = run("job", "create", "--task", "phase6-gate", "--provider", "custom-command")
    job_id = json.loads(create.stdout)["job_id"]
    result = run("job", "run", job_id)
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["blocked_reason"] == "proposal_acceptance_required"
    assert "rig agent inspect" in "\n".join(payload["next"])
    assert not (REPO_ROOT / ".build" / "rig" / "receipts" / f"{job_id}_apply.json").exists()


def test_run_dry_run_performs_no_writes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    before = set(repo.iterdir())
    proc = subprocess.run([sys.executable, "-m", "rig", "run", "--task", "dry", "--provider", "custom-command", "--dry-run"], cwd=repo, text=True, capture_output=True, check=False)
    if not PYTHON_GE_314:
        assert proc.returncode == 1
        assert "Rig requires Python 3.14 or newer" in proc.stderr
        return
    assert proc.returncode == 0, proc.stderr
    assert set(repo.iterdir()) == before


def test_policy_defaults_are_conservative() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "allow_auto_apply = false" in lowered
    assert "allow_auto_execute = false" in lowered


def test_allow_auto_apply_does_not_enable_auto_apply(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, text=True, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, text=True, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, text=True, capture_output=True, check=False)
    (repo / ".gitignore").write_text(".build/\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        "[tool.rig]\n[tool.rig.policy]\nallow_auto_apply = true\n",
        encoding="utf-8",
    )
    (repo / "file.txt").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, text=True, capture_output=True, check=False)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, text=True, capture_output=True, check=False)
    job = orchestration.create_job(repo, task="gate", provider_id="custom-command")
    result = orchestration.run_job(repo, job["job_id"])
    assert result["status"] == "blocked"
    assert result["blocked_reason"] == "proposal_acceptance_required"
    assert not (repo / ".build" / "rig" / "receipts" / f"{job['job_id']}_apply.json").exists()


def test_cancel_prevents_further_execution(tmp_path: Path) -> None:
    if not PYTHON_GE_314:
        return
    repo = tmp_path / "repo"
    repo.mkdir()
    create = subprocess.run([str(PYTHON), "-m", "rig", "job", "create", "--task", "cancel", "--provider", "custom-command"], cwd=repo, text=True, capture_output=True, check=False)
    job_id = json.loads(create.stdout)["job_id"]
    cancel = subprocess.run([str(PYTHON), "-m", "rig", "job", "cancel", job_id], cwd=repo, text=True, capture_output=True, check=False)
    assert json.loads(cancel.stdout)["status"] == "cancelled"
    retry = subprocess.run([str(PYTHON), "-m", "rig", "job", "retry", job_id], cwd=repo, text=True, capture_output=True, check=False)
    assert json.loads(retry.stdout)["status"] == "blocked"


def test_orchestration_receipt_validates_against_schema(tmp_path: Path) -> None:
    if not PYTHON_GE_314:
        return
    repo = tmp_path / "repo"
    repo.mkdir()
    create = subprocess.run([str(PYTHON), "-m", "rig", "job", "create", "--task", "schema", "--provider", "custom-command"], cwd=repo, text=True, capture_output=True, check=False)
    job_id = json.loads(create.stdout)["job_id"]
    subprocess.run([str(PYTHON), "-m", "rig", "job", "run", job_id], cwd=repo, text=True, capture_output=True, check=False)
    result = schema_validation.validate_artifacts(repo, family="rig.orchestration_receipt.v1")
    assert result.status == "passed"
