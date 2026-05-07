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


def test_checkpoint_include_selects_only_included_dirty_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        dirty_files=(
            " M src/rig/domain/projection_builder.py",
            "?? src/rig/domain/git_helper.py",
            "?? src/rig/domain/_git_helper.py",
        ),
        branch_matches_convention=True,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0?? src/rig/domain/git_helper.py\0?? src/rig/domain/_git_helper.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    plan = rat.build_checkpoint_plan(
        "gemini",
        "ui-cockpit",
        path,
        "msg",
        include=("src/rig/domain/git_helper.py",),
    )
    assert plan.files_to_stage == ("src/rig/domain/git_helper.py",)
    assert plan.excluded_files == ()


def test_checkpoint_include_repeated_preserves_exact_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        dirty_files=(" M src/rig/domain/projection_builder.py", "?? src/rig_tools/static/index.html"),
        branch_matches_convention=True,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0?? src/rig_tools/static/index.html\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    plan = rat.build_checkpoint_plan(
        "gemini",
        "ui-cockpit",
        path,
        "msg",
        include=("src/rig/domain/projection_builder.py", "src/rig_tools/static/index.html"),
    )
    assert plan.files_to_stage == ("src/rig/domain/projection_builder.py", "src/rig_tools/static/index.html")


def test_checkpoint_exclude_removes_only_excluded_dirty_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        dirty_files=(
            " M src/rig/domain/projection_builder.py",
            " M src/rig_tools/static/index.html",
            "?? src/rig/domain/_git_helper.py",
        ),
        branch_matches_convention=True,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0 M src/rig_tools/static/index.html\0?? src/rig/domain/_git_helper.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    plan = rat.build_checkpoint_plan(
        "gemini",
        "ui-cockpit",
        path,
        "msg",
        exclude=("src/rig/domain/_git_helper.py",),
    )
    assert plan.files_to_stage == ("src/rig/domain/projection_builder.py", "src/rig_tools/static/index.html")
    assert plan.excluded_files == ("src/rig/domain/_git_helper.py",)


def test_checkpoint_exclude_repeated_works(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        dirty_files=(
            " M src/rig/domain/projection_builder.py",
            " M src/rig_tools/static/index.html",
            "?? src/rig/domain/_git_helper.py",
        ),
        branch_matches_convention=True,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0 M src/rig_tools/static/index.html\0?? src/rig/domain/_git_helper.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    plan = rat.build_checkpoint_plan(
        "gemini",
        "ui-cockpit",
        path,
        "msg",
        exclude=("src/rig/domain/_git_helper.py", "src/rig_tools/static/index.html"),
    )
    assert plan.files_to_stage == ("src/rig/domain/projection_builder.py",)
    assert plan.excluded_files == ("src/rig/domain/_git_helper.py", "src/rig_tools/static/index.html")


def test_checkpoint_refuses_include_and_exclude_together(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(rat, "_run_git", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0", stderr=""))
    with pytest.raises(ValueError):
        rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg", include=("src/rig/domain/projection_builder.py",), exclude=("src/rig/domain/_git_helper.py",))


def test_checkpoint_refuses_include_path_that_is_not_dirty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(rat, "_run_git", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0", stderr=""))
    with pytest.raises(ValueError):
        rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg", include=("src/rig/domain/git_helper.py",))


def test_checkpoint_refuses_exclude_path_that_is_not_dirty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(rat, "_run_git", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0", stderr=""))
    with pytest.raises(ValueError):
        rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg", exclude=("src/rig/domain/git_helper.py",))


def test_checkpoint_refuses_zero_selected_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    monkeypatch.setattr(rat, "_run_git", lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0", stderr=""))
    with pytest.raises(ValueError):
        rat.build_checkpoint_plan("gemini", "ui-cockpit", path, "msg", exclude=("src/rig/domain/projection_builder.py",))


def test_checkpoint_dry_run_prints_selected_and_excluded_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
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
        dirty_files=(
            " M src/rig/domain/projection_builder.py",
            "?? src/rig/domain/_git_helper.py",
        ),
        branch_matches_convention=True,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0?? src/rig/domain/_git_helper.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    result = rat.cmd_checkpoint(SimpleNamespace(
        agent="gemini",
        task="ui-cockpit",
        path=str(path),
        message="msg",
        include=None,
        exclude=("src/rig/domain/_git_helper.py",),
        dry_run=True,
    ))
    assert result == 0
    out = capsys.readouterr().out
    assert "dirty_files:" in out
    assert "excluded_files:" in out
    assert "files_to_stage:" in out
    assert "src/rig/domain/projection_builder.py" in out
    assert "src/rig/domain/_git_helper.py" in out


def test_checkpoint_real_stages_only_selected_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
        dirty_files=(
            " M src/rig/domain/projection_builder.py",
            " M src/rig_tools/static/index.html",
            "?? src/rig/domain/_git_helper.py",
        ),
        branch_matches_convention=True,
    ))

    def planner_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return SimpleNamespace(returncode=0, stdout=" M src/rig/domain/projection_builder.py\0 M src/rig_tools/static/index.html\0?? src/rig/domain/_git_helper.py\0", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    calls: list[list[str]] = []

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["status", "--porcelain=v1", "-z"]:
            return planner_git(args, cwd=cwd, check=check)
        calls.append(args)
        if args == ["-C", str(path), "add", "--", "src/rig/domain/projection_builder.py", "src/rig_tools/static/index.html"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["-C", str(path), "commit", "-m", "msg"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    result = rat.cmd_checkpoint(SimpleNamespace(
        agent="gemini",
        task="ui-cockpit",
        path=str(path),
        message="msg",
        include=None,
        exclude=("src/rig/domain/_git_helper.py",),
        dry_run=False,
    ))
    assert result == 0
    assert ["-C", str(path), "add", "--", "src/rig/domain/projection_builder.py", "src/rig_tools/static/index.html"] in calls
    assert all(args != ["-C", str(path), "add", ".",] for args in calls)
    assert all(args != ["-C", str(path), "add", "-A"] for args in calls)


def test_review_validates_slugs(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        rat.build_review_report("Gemini", "ui-cockpit", tmp_path)


def test_review_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rat.build_review_report("gemini", "ui-cockpit", tmp_path / "missing")


def test_review_reports_branch_head_and_dirty_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path)
    assert report.branch == "feature/ui-cockpit-widgets"
    assert report.head == "7d47eb3"
    assert report.dirty is False
    assert report.branch_matches_convention is False


def test_review_ready_for_review_when_clean_and_ahead(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path)
    assert report.ready_for_review is True
    assert report.ahead == 1
    assert report.behind == 0
    assert report.changed_files == ("M\tsrc/rig/domain/git_helper.py",)


def test_review_not_ready_when_branch_is_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "main-lane"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="main",
        expected_branch="agent/task/gemini",
        head="abcd123",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t0\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "main-lane", path)
    assert report.ready_for_review is False
    assert "branch is main" in report.blockers


def test_review_not_ready_when_dirty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=True,
        dirty_files=(" M src/file.py",),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path)
    assert report.ready_for_review is False
    assert "worktree is dirty" in report.blockers


def test_review_not_ready_when_ahead_count_is_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t0\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path)
    assert report.ready_for_review is False
    assert "lane has no commits ahead of base" in report.blockers


def test_review_branch_mismatch_is_warning_not_blocker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path)
    assert "branch does not match preferred agent convention" in report.warnings
    assert "branch does not match preferred agent convention" not in report.blockers


def test_review_reports_changed_files_vs_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\nA\tsrc/rig_tools/static/index.html\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path)
    assert report.changed_files == ("M\tsrc/rig/domain/git_helper.py", "A\tsrc/rig_tools/static/index.html")


def test_review_reports_commits_ahead_of_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path)
    assert report.commits == ("7d47eb3 Add UI cockpit projection widgets",)


def test_review_does_not_call_mutating_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    calls: list[list[str]] = []

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append(args)
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    rat.build_review_report("gemini", "ui-cockpit", path)
    assert all("add" not in args and "commit" not in args and "push" not in args and "merge" not in args and "rebase" not in args and "reset" not in args and "clean" not in args and "stash" not in args for args in calls)


def test_review_supports_custom_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "feature/base"]:
            return SimpleNamespace(returncode=0, stdout="feature/base\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "feature/base...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="1\t2\n", stderr="")
        if args == ["diff", "--name-status", "feature/base...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "feature/base..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path, base="feature/base")
    assert report.base == "feature/base"
    assert report.ahead == 2
    assert report.behind == 1


def test_review_handles_base_resolution_failure_as_blocker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="fatal: ambiguous argument 'main'")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_review_report("gemini", "ui-cockpit", path)
    assert report.ready_for_review is False
    assert any("unable to resolve base ref" in blocker or "fatal: ambiguous argument" in blocker for blocker in report.blockers)


def test_promote_requires_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    result = rat.cmd_promote(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(path), base="main", target=None, strategy="manual", dry_run=False))
    assert result == 1
    assert "requires --dry-run" in capsys.readouterr().err


def test_promote_validates_slugs(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        rat.build_promote_report("Gemini", "ui-cockpit", tmp_path, dry_run=True)


def test_promote_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rat.build_promote_report("gemini", "ui-cockpit", tmp_path / "missing", dry_run=True)


def test_promote_output_includes_dry_run_and_would_not_mutate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)

    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    result = rat.cmd_promote(SimpleNamespace(agent="gemini", task="ui-cockpit", path=str(path), base="main", target="sprint/ui-cockpit", strategy="manual", dry_run=True))
    assert result == 0
    out = capsys.readouterr().out
    assert "dry_run: true" in out
    assert "would_mutate: false" in out


def test_promote_blocks_main_source_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "main-lane"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="main",
        expected_branch="agent/task/gemini",
        head="abcd123",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t0\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/main-lane"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "main-lane", path, dry_run=True)
    assert "branch is main" in report.blockers
    assert report.ready_to_promote is False


def test_promote_blocks_dirty_worktree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=True,
        dirty_files=(" M src/file.py",),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, dry_run=True)
    assert report.ready_to_promote is False
    assert "worktree is dirty" in report.blockers


def test_promote_blocks_zero_commits_ahead_of_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t0\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, dry_run=True)
    assert report.ready_to_promote is False
    assert "lane has no commits ahead of base" in report.blockers


def test_promote_blocks_unresolved_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "missing-base"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="fatal: ambiguous argument 'missing-base'")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, base="missing-base", dry_run=True)
    assert report.ready_to_promote is False
    assert any("missing-base" in blocker or "unable to resolve base ref" in blocker for blocker in report.blockers)


def test_promote_blocks_target_equal_to_source_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/feature/ui-cockpit-widgets"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, target="feature/ui-cockpit-widgets", dry_run=True)
    assert "target branch equals source branch" in report.blockers


def test_promote_warns_on_branch_mismatch_and_behind_base(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="8\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, dry_run=True)
    assert "branch does not match preferred agent convention" in report.warnings
    assert "lane is behind base" in report.warnings


def test_promote_warns_when_target_branch_does_not_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, dry_run=True)
    assert "target branch does not exist yet" in report.warnings


def test_promote_supports_strategy_pr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, strategy="pr", dry_run=True)
    assert report.strategy == "pr"
    assert any("gh pr create" in command for command in report.future_commands)


def test_promote_supports_strategy_squash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, strategy="squash", dry_run=True)
    assert report.strategy == "squash"
    assert any("squash" in line for line in report.planned_operations)


def test_promote_supports_strategy_cherry_pick(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, strategy="cherry-pick", dry_run=True)
    assert report.strategy == "cherry-pick"
    assert any("cherry-pick" in line for line in report.future_commands)


def test_promote_rejects_unknown_strategy(tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    with pytest.raises(ValueError):
        rat.build_promote_report("gemini", "ui-cockpit", path, strategy="unknown", dry_run=True)


def test_promote_reports_changed_files_and_commits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="A\tsrc/rig/domain/git_helper.py\nM\tsrc/rig_tools/static/index.html\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, dry_run=True)
    assert report.changed_files == ("A\tsrc/rig/domain/git_helper.py", "M\tsrc/rig_tools/static/index.html")
    assert report.commits == ("7d47eb3 Add UI cockpit projection widgets",)


def test_promote_does_not_call_mutating_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    calls: list[list[str]] = []

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append(args)
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    rat.build_promote_report("gemini", "ui-cockpit", path, dry_run=True)
    assert all("add" not in args and "commit" not in args and "push" not in args and "merge" not in args and "rebase" not in args and "reset" not in args and "clean" not in args and "stash" not in args for args in calls)


def test_promote_requires_porcelain_status_for_dirty_decision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=True,
        dirty_files=(" M src/file.py",),
        branch_matches_convention=False,
    ))

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_promote_report("gemini", "ui-cockpit", path, dry_run=True)
    assert report.dirty is True
    assert "worktree is dirty" in report.blockers


def test_recommend_validates_slugs(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        rat.build_recommendation_report("Gemini", "ui-cockpit", tmp_path)


def test_recommend_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rat.build_recommendation_report("gemini", "ui-cockpit", tmp_path / "missing")


def test_recommend_is_read_only_and_does_not_call_mutating_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    calls: list[list[str]] = []

    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append(args)
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path)
    assert report.dry_run is True
    assert report.would_mutate is False
    assert all("add" not in args and "commit" not in args and "push" not in args and "merge" not in args and "rebase" not in args and "reset" not in args and "clean" not in args and "stash" not in args for args in calls)


def test_recommend_returns_hold_when_branch_is_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "main-lane"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="main",
        expected_branch="agent/task/gemini",
        head="abcd123",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t0\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/main-lane"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "main-lane", path)
    assert report.recommended_path == "hold"
    assert report.ready is False


def test_recommend_returns_hold_when_worktree_dirty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=True,
        dirty_files=(" M src/file.py",),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path)
    assert report.recommended_path == "hold"
    assert "worktree is dirty" in report.blockers


def test_recommend_returns_hold_when_ahead_is_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t0\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path)
    assert report.recommended_path == "hold"


def test_recommend_returns_hold_when_base_cannot_resolve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="fatal: ambiguous argument 'main'")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path)
    assert report.recommended_path == "hold"
    assert any("unable to resolve base ref" in blocker or "fatal: ambiguous argument" in blocker for blocker in report.blockers)


def test_recommend_default_returns_review_for_gemini_like_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="10\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="A\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path)
    assert report.recommended_path == "review"
    assert report.ready is True
    assert "branch does not match preferred agent convention" in report.warnings
    assert "lane is behind base" in report.warnings
    assert "target branch does not exist yet" in report.warnings


def test_recommend_respects_prefer_pr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=True,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path, prefer="pr")
    assert report.recommended_path == "pr"
    assert any("gh pr create" in command for command in report.future_commands)


def test_recommend_respects_prefer_squash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=True,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path, prefer="squash")
    assert report.recommended_path == "squash"
    assert any("rig agent lane promote" in command for command in report.future_commands)


def test_recommend_respects_prefer_cherry_pick(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=True,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path, prefer="cherry-pick")
    assert report.recommended_path == "cherry-pick"
    assert any("rig agent lane promote" in command for command in report.future_commands)


def test_recommend_invalid_prefer_falls_back_to_hold(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=True,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path, prefer="totally-unknown")
    assert report.recommended_path == "hold"
    assert report.ready is False


def test_recommend_includes_validations_and_future_commands(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=False,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="A\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path)
    assert report.validations_to_run
    assert report.future_commands


def test_recommend_reports_warning_for_pr_push_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Rig-worktrees" / "ui-cockpit"
    path.mkdir(parents=True)
    monkeypatch.setattr(rat, "inspect_attached_worktree", lambda agent, task, path, repo_root=None: rat.AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch="feature/ui-cockpit-widgets",
        expected_branch="agent/ui-cockpit/gemini",
        head="7d47eb3",
        dirty=False,
        dirty_files=(),
        branch_matches_convention=True,
    ))
    def fake_run_git(args: list[str], *, cwd: Path | None = None, check: bool = False):
        if args == ["rev-parse", "--verify", "main"]:
            return SimpleNamespace(returncode=0, stdout="main\n", stderr="")
        if args == ["rev-list", "--left-right", "--count", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="0\t1\n", stderr="")
        if args == ["diff", "--name-status", "main...HEAD"]:
            return SimpleNamespace(returncode=0, stdout="M\tsrc/rig/domain/git_helper.py\n", stderr="")
        if args == ["log", "--oneline", "--decorate", "main..HEAD"]:
            return SimpleNamespace(returncode=0, stdout="7d47eb3 Add UI cockpit projection widgets\n", stderr="")
        if args == ["show-ref", "--verify", "--quiet", "refs/heads/sprint/ui-cockpit"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(rat, "_run_git", fake_run_git)
    report = rat.build_recommendation_report("gemini", "ui-cockpit", path, prefer="pr")
    assert report.recommended_path == "pr"
    assert any("gh pr create" in command for command in report.future_commands)


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
