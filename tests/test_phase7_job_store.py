from __future__ import annotations

import json
import threading
from pathlib import Path
import subprocess
import sys

from rig_tools import orchestration
from rig_tools.atomic_io import write_json_atomic

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
PYTHON_GE_314 = sys.version_info >= (3, 14)

def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".build" / "rig" / "jobs").mkdir(parents=True, exist_ok=True)
    (repo / ".build" / "rig" / "receipts").mkdir(parents=True, exist_ok=True)
    return repo


def test_hundred_job_creations_produce_hundred_job_files(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    for index in range(100):
        orchestration.create_job(repo, task=f"task-{index}", provider_id="custom-command")
    files = sorted((repo / ".build" / "rig" / "jobs").glob("*.json"))
    assert len(files) == 100
    assert len({p.stem for p in files}) == 100


def test_concurrent_job_creation_is_unique_and_not_corrupt(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    created: list[str] = []

    def worker(i: int) -> None:
        created.append(orchestration.create_job(repo, task=f"task-{i}", provider_id="custom-command")["job_id"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(24)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(created) == len(set(created)) == 24
    assert len(list((repo / ".build" / "rig" / "jobs").glob("*.json"))) == 24
    for path in (repo / ".build" / "rig" / "jobs").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["job_id"] == path.stem


def test_tmp_file_ignored_by_loader(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    job = orchestration.create_job(repo, task="tmp", provider_id="custom-command")
    tmp_file = repo / ".build" / "rig" / "jobs" / f"{job['job_id']}.json.tmp"
    tmp_file.write_text("{\"broken\":", encoding="utf-8")
    load = orchestration.load_all_jobs(repo)
    assert len(load.jobs) == 1
    assert not load.malformed


def test_malformed_job_does_not_crash_list_and_doctor_reports(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    bad = repo / ".build" / "rig" / "jobs" / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    listing = orchestration.list_jobs(repo)
    assert listing == []
    health = orchestration.queue_health(repo)
    assert health["malformed_job_count"] == 1
    assert health["malformed"][0]["path"].endswith("bad.json")


def test_doctor_repair_quarantines_malformed_job(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    bad = repo / ".build" / "rig" / "jobs" / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    health = orchestration.queue_health(repo, repair=True)
    assert health["quarantined_bad_count"] == 1 or health["quarantined"]
    assert (repo / ".build" / "rig" / "jobs" / "bad.json.bad").exists()


def test_atomic_write_failure_preserves_last_good_file(tmp_path: Path, monkeypatch) -> None:
    repo = _repo(tmp_path)
    path = repo / ".build" / "rig" / "jobs" / "job.json"
    write_json_atomic(path, {"ok": True})
    original = path.read_text(encoding="utf-8")

    import os

    def boom(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr(os, "replace", boom)
    try:
        write_json_atomic(path, {"ok": False})
    except OSError:
        pass
    assert path.read_text(encoding="utf-8") == original


def test_legacy_migration_preserves_original_and_writes_receipt(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    legacy = repo / ".build" / "rig" / "queue" / "queue.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(json.dumps({"jobs": [{"job_id": "legacy-1", "task": "legacy-task"}]}), encoding="utf-8")
    result = orchestration.migrate_legacy_queue(repo)
    assert legacy.exists()
    assert (repo / ".build" / "rig" / "jobs" / "legacy-1.json").exists()
    assert result["receipt"].endswith("_legacy_queue_migration.json")


def test_product_commands_do_not_write_legacy_queue(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    orchestration.create_job(repo, task="no-legacy", provider_id="custom-command")
    assert not (repo / ".build" / "rig" / "queue" / "queue.json").exists()


def test_init_warns_about_legacy_queue_without_migrating(tmp_path: Path) -> None:
    if not PYTHON_GE_314:
        return
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".build" / "rig" / "queue").mkdir(parents=True, exist_ok=True)
    (repo / ".build" / "rig" / "queue" / "queue.json").write_text(json.dumps({"jobs": []}), encoding="utf-8")
    proc = subprocess.run([str(PYTHON), "-m", "rig", "init", "--dry-run"], cwd=repo, text=True, capture_output=True, check=False)
    assert proc.returncode == 0
    assert "Legacy queue state detected" in proc.stdout
    assert not (repo / ".build" / "rig" / "jobs").exists() or not list((repo / ".build" / "rig" / "jobs").glob("*.json"))


def test_cli_repair_migrates_legacy_queue(tmp_path: Path) -> None:
    if not PYTHON_GE_314:
        return
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".build" / "rig" / "queue").mkdir(parents=True, exist_ok=True)
    (repo / ".build" / "rig" / "queue" / "queue.json").write_text(json.dumps({"jobs": [{"job_id": "legacy-2", "task": "legacy"}]}), encoding="utf-8")
    proc = subprocess.run([str(PYTHON), "-m", "rig", "doctor", "repair", "--migrate-legacy-queue"], cwd=repo, text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert (repo / ".build" / "rig" / "jobs" / "legacy-2.json").exists()
