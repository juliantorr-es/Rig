from __future__ import annotations

import sys
from dataclasses import field
from pathlib import Path
from typing import Any, Optional

from rig_tools.contracts import ActionDefinition, CommandPlan, CommandSafety

class ActionRegistry:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.rig_py = str(repo_root / "scripts" / "rig.py")
        self.python = sys.executable
        self.actions: dict[str, ActionDefinition] = {}
        self._register_defaults()

    def _register_defaults(self):
        # Observe
        self.register(ActionDefinition(
            action_id="refresh_status", 
            label="Refresh Status", 
            description="Refreshes the current Rig status and monitor snapshot.",
            argv_template=[self.python, self.rig_py, "monitor", "snapshot"],
            accepts_task=False,
            requires_task=False,
            allowed_modes=["safe", "action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="monitor_snapshot", 
            label="Monitor Snapshot",
            description="Triggers a full monitor snapshot and dependency check.",
            argv_template=[self.python, self.rig_py, "monitor", "snapshot"],
            accepts_task=False,
            requires_task=False,
            allowed_modes=["safe", "action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="prompt_status", 
            label="Prompt Status",
            description="Shows the status of prompt telemetry and regressions.",
            argv_template=[self.python, self.rig_py, "prompt", "status"],
            accepts_task=False,
            requires_task=False,
            allowed_modes=["safe", "action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="agent_status", 
            label="Agent Status",
            description="Displays active and pending agent runs.",
            argv_template=[self.python, self.rig_py, "agent", "status"],
            accepts_task=False,
            requires_task=False,
            allowed_modes=["safe", "action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="schema_validate_results", 
            label="Validate Schema",
            description="Validates the latest results against Rig schemas.",
            argv_template=[self.python, self.rig_py, "schema", "validate", "--family", "rig.result.v1"],
            accepts_task=False,
            requires_task=False,
            allowed_modes=["safe", "action", "auto-approve"],
            requires_confirmation=False
        ))

        # Plan / Prepare
        self.register(ActionDefinition(
            action_id="context_build", 
            label="Build Context",
            description="Compresses and packs current context for agent consumption.",
            argv_template=[self.python, self.rig_py, "context", "build", "--purpose", "loop-planner", "--max-chars", "16000"],
            accepts_task=True, 
            requires_task=True,
            allowed_modes=["safe", "action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="loop_plan", 
            label="Loop Plan",
            description="Generates a multi-step loop plan using the local LLM.",
            argv_template=[self.python, self.rig_py, "loop", "plan", "--backend", "mlx", "--model", "mlx-community/Qwen3-4B-Instruct-2507-4bit"],
            accepts_task=True, 
            requires_task=True,
            allowed_modes=["safe", "action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="agent_plan", 
            label="Agent Plan",
            description="Generates a single-agent implementation plan.",
            argv_template=[self.python, self.rig_py, "agent", "plan", "--backend", "mlx", "--model", "mlx-community/Qwen3-4B-Instruct-2507-4bit"],
            accepts_task=True, 
            requires_task=True,
            allowed_modes=["action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="bundle_session_dry_run", 
            label="Bundle Dry",
            description="Performs a dry-run of a session review bundle.",
            argv_template=[self.python, self.rig_py, "bundle", "session", "--dry-run"],
            accepts_task=True, 
            requires_task=True,
            allowed_modes=["safe", "action", "auto-approve"],
            requires_confirmation=False
        ))

        # Action
        self.register(ActionDefinition(
            action_id="queue_add_read_only_x3", 
            label="Queue x3",
            description="Adds 3 read-only exploration steps to the loop queue.",
            argv_template=[self.python, self.rig_py, "queue", "add", "--mode", "read-only", "--max-steps", "3"],
            accepts_task=True, 
            requires_task=True,
            allowed_modes=["action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="queue_run_one", 
            label="Run Queue (1)",
            description="Executes the next single job in the supervisor queue.",
            argv_template=[self.python, self.rig_py, "queue", "run", "--max-jobs", "1"],
            accepts_task=False,
            requires_task=False,
            allowed_modes=["action", "auto-approve"],
            requires_confirmation=False
        ))
        self.register(ActionDefinition(
            action_id="bundle_session", 
            label="Bundle Session",
            description="Finalizes and bundles a session review package.",
            argv_template=[self.python, self.rig_py, "bundle", "session"],
            accepts_task=True, 
            requires_task=True,
            allowed_modes=["action", "auto-approve"],
            requires_confirmation=True
        ))
        self.register(ActionDefinition(
            action_id="git_plan_commit", 
            label="Git Commit Plan",
            description="Proposes a git commit plan based on recent changes.",
            argv_template=[self.python, self.rig_py, "git", "commit-plan"],
            accepts_task=True, 
            requires_task=True,
            allowed_modes=["action", "auto-approve"],
            requires_confirmation=False,
            mutates_git=False # TUI only plans, doesn't commit yet
        ))

    def register(self, action: ActionDefinition):
        action.validate()
        self.actions[action.action_id] = action

    def build_plan(self, action_id: str, selected_task: Optional[str], mode: str) -> CommandPlan:
        action = self.actions.get(action_id)
        
        # Unique ID for the plan
        import uuid
        plan_id = str(uuid.uuid4())[:8]

        if not action:
            return CommandPlan(
                plan_id=plan_id,
                action_id=action_id,
                mode=mode if mode in ("safe", "action", "auto-approve") else "safe",
                argv=[],
                working_directory=str(self.repo_root),
                timeout_seconds=300,
                allowed=False,
                disabled_reason=f"Unknown action: {action_id}",
                safety=CommandSafety()
            )

        # Mode check
        is_allowed = mode in action.allowed_modes
        disabled_reason = None
        if not is_allowed:
            disabled_reason = f"Action '{action.label}' requires {', '.join(action.allowed_modes)} mode"

        # Task requirement check
        if action.requires_task and not selected_task:
            is_allowed = False
            disabled_reason = f"Action '{action.label}' requires a selected task"

        # Build argv
        argv = list(action.argv_template)
        if selected_task and action.accepts_task:
            # Check if {task} placeholder exists
            placeholders = [i for i, x in enumerate(argv) if "{task}" in x]
            if placeholders:
                for idx in placeholders:
                    argv[idx] = argv[idx].replace("{task}", selected_task)
            else:
                # Append --task
                argv.extend(["--task", selected_task])

        return CommandPlan(
            plan_id=plan_id,
            action_id=action_id,
            task=selected_task,
            mode=mode if mode in ("safe", "action", "auto-approve") else "safe",
            argv=argv,
            working_directory=str(self.repo_root),
            timeout_seconds=action.timeout_seconds,
            allowed=is_allowed,
            disabled_reason=disabled_reason,
            safety=CommandSafety(
                mutates_git=action.mutates_git,
                mutates_main_worktree=action.mutates_main_worktree,
                launches_external_agent=action.launches_external_agent
            )
        )
