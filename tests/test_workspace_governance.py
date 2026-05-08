from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rig.domain.workspace import WorkspaceDomain


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test User")
    (path / "pyproject.toml").write_text(
        "[tool.rig]\n[[tool.rig.validators]]\nid = \"ok\"\nargv = [\"python\", \"-c\", \"print('ok')\"]\nrequired = true\n",
        encoding="utf-8",
    )
    (path / ".gitignore").write_text(".build/\n", encoding="utf-8")
    (path / "file.txt").write_text("base\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "init")
    return path


def make_workspace(repo: Path) -> tuple[WorkspaceDomain, str]:
    mgr = WorkspaceDomain(repo)
    record = mgr.create_workspace("task")
    ws = record.payload["workspace_id"]
    worktree = Path(record.payload["worktree_path"])
    (worktree / "file.txt").write_text("change\n", encoding="utf-8")
    git(worktree, "add", "file.txt")
    git(worktree, "commit", "-m", "change")
    receipt = {
        "receipt_id": "r1",
        "workspace_id": ws,
        "worktree_hash_before": "before",
        "worktree_hash_after": mgr.compute_worktree_hash(worktree),
        "commands_executed": ["edit"],
        "status": "success",
        "authoritative": True,
    }
    mgr.receipt_dir.mkdir(parents=True, exist_ok=True)
    (mgr.receipt_dir / f"{ws}_run.json").write_text(json.dumps(receipt), encoding="utf-8")
    return mgr, ws


def test_apply_refuses_when_main_worktree_dirty(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    mgr, ws = make_workspace(repo)
    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    try:
        mgr.apply_workspace(ws)
        assert False, "expected failure"
    except RuntimeError as exc:
        assert "dirty" in str(exc)


def test_apply_refuses_without_execution_receipt(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    mgr = WorkspaceDomain(repo)
    record = mgr.create_workspace("task")
    try:
        mgr.apply_workspace(record.payload["workspace_id"])
        assert False, "expected failure"
    except RuntimeError as exc:
        assert "gates" in str(exc)


def test_review_bundle_creates_files(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    mgr, ws = make_workspace(repo)
    bundle = mgr.build_review_bundle(ws)
    review_dir = mgr.review_path(ws)
    assert (review_dir / "review.json").exists()
    assert (review_dir / "summary.md").exists()
    assert (review_dir / "diff.patch").exists()
    assert (review_dir / "validation.json").exists()
    assert bundle["workspace_id"] == ws


def test_validator_failure_blocks_apply(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "pyproject.toml").write_text(
        "[tool.rig]\n[[tool.rig.validators]]\nid = \"bad\"\nargv = [\"python\", \"-c\", \"import sys; sys.exit(1)\"]\nrequired = true\n",
        encoding="utf-8",
    )
    mgr, ws = make_workspace(repo)
    mgr.generate_validation_result(ws)
    assert mgr.load_workspace(ws).payload["status"] == "blocked"


def test_status_transition_rejects_skips(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    mgr = WorkspaceDomain(repo)
    record = mgr.create_workspace("task")
    try:
        mgr.transition_workspace(record.payload["workspace_id"], "applied")
        assert False, "expected failure"
    except ValueError:
        pass


def test_workspace_bootstrap_creates_governed_rig_layout(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    mgr = WorkspaceDomain(repo)
    for rel in [
        ".rig",
        ".rig/worktrees",
        ".rig/artifacts",
        ".rig/replay",
        ".rig/topology",
        ".rig/receipts",
        ".rig/runtime",
        ".rig/cache",
    ]:
        assert (repo / rel).exists(), rel
    record = mgr.create_workspace("task")
    assert Path(record.payload["worktree_path"]).exists()
