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


def test_checkpoint_dry_run_does_not_call_mutating_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    calls: list[list[str]] = []

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append(args)
        if args == ["rev-parse", "--show-toplevel"]:
            return SimpleNamespace(returncode=0, stdout=str(tmp_path / "Rig") + "\n", stderr="")
        if args == ["rev-parse", "--git-common-dir"]:
            return SimpleNamespace(returncode=0, stdout=".git\n", stderr="")
        if args == ["rev-parse", "--short", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="175c824\n", stderr="")
        if args == ["branch", "--show-current"]:
            return SimpleNamespace(returncode=0, stdout="agent/ui-cockpit/gemini\n", stderr="")
        if args == ["status", "--short", "--branch"]:
            return SimpleNamespace(returncode=0, stdout="## agent/ui-cockpit/gemini\n", stderr="")
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/file.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    result = rat.cmd_checkpoint(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(path), message="Add UI cockpit widgets", dry_run=True))
    assert result == 0
    assert any(args == ["status", "--porcelain=v1", "-z"] for args in calls)
    assert all("commit" not in args for args in calls)
    out = capsys.readouterr().out
    assert "files_to_stage" in out
    assert "DRY RUN: git -C" in out


def test_checkpoint_refuses_main_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "main-lane"
    path.mkdir(parents=True)

    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="main",
        expected_branch="agent/task/gemini",
        head="abcd123",
        dirty=True,
        dirty_files=(" M file.py",),
        branch_matches_convention=False,
    ))

    with pytest.raises(ValueError):
        rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg")


def test_checkpoint_refuses_clean_worktree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)

    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="agent/ui-cockpit/gemini",
        expected_branch="agent/ui-cockpit/gemini",
        head="abcd123",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=True,
    ))
    monkeypatch.setattr(rat, "_run_git", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""))
    with pytest.raises(ValueError):
        rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "Add UI cockpit widgets")


def test_checkpoint_refuses_empty_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)

    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="agent/ui-cockpit/gemini",
        expected_branch="agent/ui-cockpit/gemini",
        head="abcd123",
        dirty=True,
        dirty_files=(" M file.py",),
        branch_matches_convention=True,
    ))
    with pytest.raises(ValueError):
        rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "   ")


def test_parse_porcelain_status_extracts_explicit_files_and_conflicts() -> None:
    payload = b" M src/a.py\0?? src/b.py\0UU src/c.py\0"
    files, has_conflict = rat.parse_porcelain_v1_z(payload)
    assert files == ("src/a.py", "src/b.py", "src/c.py")
    assert has_conflict is True


def test_parse_porcelain_status_preserves_exact_paths_and_spaces() -> None:
    payload = b" M src/rig/domain/projection_builder.py\0?? src/rig/domain/git helper.py\0"
    files, has_conflict = rat.parse_porcelain_v1_z(payload)
    assert files == ("src/rig/domain/projection_builder.py", "src/rig/domain/git helper.py")
    assert has_conflict is False


def test_parse_porcelain_status_handles_renames() -> None:
    payload = b"R  old/path.py\0new/path.py\0"
    files, has_conflict = rat.parse_porcelain_v1_z(payload)
    assert files == ("new/path.py",)
    assert has_conflict is False


def test_parse_porcelain_status_refuses_conflicts() -> None:
    payload = b"UU src/conflict.py\0"
    files, has_conflict = rat.parse_porcelain_v1_z(payload)
    assert files == ("src/conflict.py",)
    assert has_conflict is True


def test_checkpoint_summary_includes_lane_details(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)

    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="agent/ui-cockpit/gemini",
        expected_branch="agent/ui-cockpit/gemini",
        head="abcd123",
        dirty=True,
        dirty_files=(" M file.py",),
        branch_matches_convention=True,
    ))
    def status_only(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M file.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", status_only)
    plan = rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "Add UI cockpit widgets")
    assert plan.path == path
    assert plan.branch == "agent/ui-cockpit/gemini"
    assert plan.head == "abcd123"
    assert plan.files_to_stage == ("file.py",)


def test_checkpoint_stages_explicit_files_and_uses_message(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    calls: list[list[str]] = []

    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="agent/ui-cockpit/gemini",
        expected_branch="agent/ui-cockpit/gemini",
        head="abcd123",
        dirty=True,
        dirty_files=(" M file.py",),
        branch_matches_convention=True,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append(args)
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M file.py\0", stderr="")
        if args == ["-C", str(path), "add", "--", "file.py"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["-C", str(path), "commit", "-m", "Add UI cockpit widgets"]:
            return SimpleNamespace(returncode=0, stdout="done\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    result = rat.cmd_checkpoint(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(path), message="Add UI cockpit widgets", dry_run=False))
    assert result == 0
    assert ["-C", str(path), "add", "--", "file.py"] in calls
    assert ["-C", str(path), "commit", "-m", "Add UI cockpit widgets"] in calls
    assert all("add" not in args or "." not in args for args in calls)


def test_checkpoint_does_not_push_merge_rebase_clean_reset_or_stash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="agent/ui-cockpit/gemini",
        expected_branch="agent/ui-cockpit/gemini",
        head="abcd123",
        dirty=True,
        dirty_files=(" M file.py",),
        branch_matches_convention=True,
    ))
    calls: list[list[str]] = []

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append(args)
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M file.py\0", stderr="")
        if args == ["-C", str(path), "add", "--", "file.py"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["-C", str(path), "commit", "-m", "msg"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    rat.cmd_checkpoint(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(path), message="msg", dry_run=False))
    assert all(not any(part in args for part in ("push", "merge", "rebase", "clean", "reset", "stash")) for args in calls)


def test_checkpoint_planner_uses_same_file_list_for_dry_run_and_real(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)

    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="agent/ui-cockpit/gemini",
        expected_branch="agent/ui-cockpit/gemini",
        head="abcd123",
        dirty=True,
        dirty_files=(" M src/rig/domain/projection_builder.py", "?? src/rig/domain/git_helper.py"),
        branch_matches_convention=True,
    ))

    payload = b" M src/rig/domain/projection_builder.py\0?? src/rig/domain/git_helper.py\0"
    monkeypatch.setattr(rat, "_run_git", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=payload, stderr=""))
    dry = rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg")
    real = rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg")
    assert dry.files_to_stage == real.files_to_stage == ("src/rig/domain/projection_builder.py", "src/rig/domain/git_helper.py")


def test_checkpoint_summary_includes_dry_run_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="agent/ui-cockpit/gemini",
        expected_branch="agent/ui-cockpit/gemini",
        head="abcd123",
        dirty=True,
        dirty_files=(" M src/rig/domain/projection_builder.py",),
        branch_matches_convention=True,
    ))
    def status_only(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", status_only)
    plan = rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg")
    assert plan.files_to_stage == ("src/rig/domain/projection_builder.py",)
    assert "projection_builder.py" in str(plan.files_to_stage)


def test_checkpoint_uses_explicit_paths_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="agent/ui-cockpit/gemini",
        expected_branch="agent/ui-cockpit/gemini",
        head="abcd123",
        dirty=True,
        dirty_files=(" M src/rig/domain/projection_builder.py",),
        branch_matches_convention=True,
    ))
    def status_only(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", status_only)
    plan = rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg")

    calls: list[list[str]] = []

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append(args)
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0", stderr="")
        if args == ["-C", str(path), "add", "--", "src/rig/domain/projection_builder.py"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["-C", str(path), "commit", "-m", "msg"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    result = rat.cmd_checkpoint(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(path), message="msg", dry_run=False))
    assert result == 0
    assert ["-C", str(path), "add", "--", "src/rig/domain/projection_builder.py"] in calls
    assert all(args != ["-C", str(path), "add", "."] for args in calls)
    assert all(args != ["-C", str(path), "add", "-A"] for args in calls)
    assert plan.files_to_stage == ("src/rig/domain/projection_builder.py",)


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
