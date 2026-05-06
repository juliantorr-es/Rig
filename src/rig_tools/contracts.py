from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, List, Optional, Literal

# Versions
ACTION_DEFINITION_VERSION = "rig.action_definition.v1"
COMMAND_PLAN_VERSION = "rig.command_plan.v1"
ACTION_RESULT_VERSION = "rig.action_result.v1"

@dataclass
class ActionDefinition:
    action_id: str
    label: str
    description: str
    argv_template: List[str]
    accepts_task: bool
    requires_task: bool
    allowed_modes: List[Literal["safe", "action", "auto-approve"]]
    requires_confirmation: bool
    mutates_git: bool = False
    mutates_main_worktree: bool = False
    launches_external_agent: bool = False
    timeout_seconds: int = 300
    writes_receipts: bool = True
    disabled_reason: Optional[str] = None
    schema_version: str = ACTION_DEFINITION_VERSION
    authoritative: bool = True

    def validate(self) -> None:
        if not self.action_id:
            raise ValueError("action_id is required")
        if not isinstance(self.argv_template, list):
            raise ValueError("argv_template must be a list of strings")
        for mode in self.allowed_modes:
            if mode not in ("safe", "action", "auto-approve"):
                raise ValueError(f"Unknown mode: {mode}")

@dataclass
class CommandSafety:
    shell: bool = False
    mutates_git: bool = False
    mutates_main_worktree: bool = False
    launches_external_agent: bool = False

@dataclass
class CommandPlan:
    plan_id: str
    action_id: str
    mode: Literal["safe", "action", "auto-approve"]
    argv: List[str]
    working_directory: str
    timeout_seconds: int
    allowed: bool
    safety: CommandSafety
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    task: Optional[str] = None
    disabled_reason: Optional[str] = None
    schema_version: str = COMMAND_PLAN_VERSION
    authoritative: bool = True

    def validate(self) -> None:
        if not self.plan_id:
            raise ValueError("plan_id is required")
        if not isinstance(self.argv, list):
            raise ValueError("argv must be a list of strings")
        if self.safety.shell:
            raise ValueError("shell=True is strictly forbidden in CommandPlan")
        if self.mode not in ("safe", "action", "auto-approve"):
            raise ValueError(f"Unknown mode: {self.mode}")

@dataclass
class ActionResult:
    result_id: str
    plan_id: str
    action_id: str
    status: Literal["passed", "failed", "blocked", "timeout"]
    exit_code: int
    started_at: str
    finished_at: str
    duration_ms: int
    human_summary: str
    task: Optional[str] = None
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    schema_version: str = ACTION_RESULT_VERSION
    authoritative: bool = True

    def validate(self) -> None:
        if self.status not in ("passed", "failed", "blocked", "timeout"):
            raise ValueError(f"Unknown status: {self.status}")

def validate_action_definition(data: dict) -> None:
    ActionDefinition(**data).validate()

def validate_command_plan(data: dict) -> None:
    safety_data = data.pop("safety")
    safety = CommandSafety(**safety_data)
    CommandPlan(safety=safety, **data).validate()

def validate_action_result(data: dict) -> None:
    ActionResult(**data).validate()
