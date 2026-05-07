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


def test_attach_reports_matching_branch_and_clean_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "Rig"
    worktree_path = tmp_path / "Rig-worktrees" / "rig-gemini-ui-cockpit"
    worktree_path.mkdir(parents=True)

    calls: list[tuple[list[str], Path | None]] = []

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append((args, cwd))
        if args == ["rev-parse", "--show-toplevel"]:
            return SimpleNamespace(returncode=0, stdout=str(repo_root) + "\n", stderr="")
        if args == ["rev-parse", "--git-common-dir"]:
            return SimpleNamespace(returncode=0, stdout=".git\n", stderr="")
        if args == ["rev-parse", "--short", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="abcd123\n", stderr="")
        if args == ["branch", "--show-current"]:
            return SimpleNamespace(returncode=0, stdout="agent/ui-cockpit/gemini\n", stderr="")
        if args == ["status", "--short", "--branch"]:
            return SimpleNamespace(returncode=0, stdout="## agent/ui-cockpit/gemini\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    result = rat.cmd_attach(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(worktree_path)))
    assert result == 0
    assert any(args == ["rev-parse", "--show-toplevel"] for args, _ in calls)


def test_attach_reports_nonmatching_branch_and_dirty_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo_root = tmp_path / "Rig"
    worktree_path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    worktree_path.mkdir(parents=True)

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--show-toplevel"]:
            return SimpleNamespace(returncode=0, stdout=str(repo_root) + "\n", stderr="")
        if args == ["rev-parse", "--git-common-dir"]:
            return SimpleNamespace(returncode=0, stdout=".git\n", stderr="")
        if args == ["rev-parse", "--short", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="175c824\n", stderr="")
        if args == ["branch", "--show-current"]:
            return SimpleNamespace(returncode=0, stdout="feature/ui-cockpit-widgets\n", stderr="")
        if args == ["status", "--short", "--branch"]:
            return SimpleNamespace(returncode=0, stdout="## feature/ui-cockpit-widgets\n M src/file.py\n?? new.py\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    result = rat.cmd_attach(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(worktree_path)))
    assert result == 0
    out = capsys.readouterr().out
    assert "branch_matches_convention: false" in out
    assert "dirty: true" in out
    assert "M src/file.py" in out
    assert "?? new.py" in out
    assert "Branch does not match convention." in out


def test_attach_rejects_missing_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(rat, "_run_git", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected git call")))
    result = rat.cmd_attach(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(tmp_path / "missing")))
    assert result == 1
    assert "does not exist" in capsys.readouterr().err


def test_attach_rejects_invalid_slugs(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        rat.inspect_attached_worktree("Gemini", "ui-cockpit", tmp_path)


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
