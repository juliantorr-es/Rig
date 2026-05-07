from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import rig_agent_worktree as rat


def test_validate_slug_accepts_valid_slugs() -> None:
    assert rat.validate_slug("gemini", "agent") == "gemini"
    assert rat.validate_slug("task-123", "task") == "task-123"


@pytest.mark.parametrize("value", ["Gemini", "task_1", "task.1", "task/1", "", "with space"])
def test_validate_slug_rejects_invalid_slugs(value: str) -> None:
    with pytest.raises(ValueError):
        rat.validate_slug(value, "agent")


def test_resolve_worktree_plan_builds_expected_paths() -> None:
    repo_root = Path("/repo/Rig")
    plan = rat.resolve_worktree_plan("codex", "bootstrap", repo_root=repo_root)
    assert plan.branch == "agent/bootstrap/codex"
    assert plan.worktree_path == Path("/repo/Rig-worktrees/rig-codex-bootstrap")


def test_prompt_contains_guardrails() -> None:
    plan = rat.resolve_worktree_plan("vibe", "safe-change", repo_root=Path("/repo/Rig"))
    prompt = rat.print_prompt("vibe", "safe-change", plan)
    assert "Before doing anything, read AGENTS.md" in prompt
    assert str(plan.worktree_path) in prompt
    assert "git rev-parse --show-toplevel" in prompt
    assert "Do not run forbidden Git commands." in prompt


def test_remove_refuses_dirty_worktree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "Rig"
    worktree_path = tmp_path / "Rig-worktrees" / "rig-codex-task"
    worktree_path.mkdir(parents=True)

    monkeypatch.setattr(rat, "resolve_worktree_plan", lambda agent, task, repo_root=None, base=rat.DEFAULT_BASE: rat.WorktreePlan(
        repo_root=repo_root or tmp_path / "Rig",
        worktree_root=tmp_path / "Rig-worktrees",
        worktree_path=worktree_path,
        branch="agent/task/codex",
        base=rat.DEFAULT_BASE,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args[:3] == ["-C", str(worktree_path), "status"]:
            return SimpleNamespace(returncode=0, stdout=" M file.txt\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)

    result = rat.cmd_remove(SimpleNamespace(agent="codex", task="task", dry_run=False))
    assert result == 1
