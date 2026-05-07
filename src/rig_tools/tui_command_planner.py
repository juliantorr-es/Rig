from __future__ import annotations

from pathlib import Path

from rig_tools.contracts import CommandPlan, CommandSafety


def plan(repo_root: Path, action_id: str, argv: list[str], *, task: str | None = None) -> CommandPlan:
    return CommandPlan(
        plan_id="tui-plan",
        action_id=action_id,
        task=task,
        mode="safe",
        argv=argv,
        working_directory=str(repo_root),
        timeout_seconds=300,
        allowed=True,
        safety=CommandSafety(shell=False, mutates_git=False, mutates_main_worktree=False, launches_external_agent=False),
    )
