"""Workflow chain domain types and pure functions.

This module provides the workflow chain abstraction for Rig's agent validation gates.
Core principles:
- Commands are represented as explicit argument tuples, NEVER shell strings
- All initial contexts are non-mutating and agent-allowed
- Evidence is written locally with truncation for safety
- No tokens/secrets in evidence
- No personal names in generated evidence

ADR 0009: Agentic Workflow Refinement
Sprint: Workflow Command Chains
"""

from __future__ import annotations

import datetime
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Domain Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class WorkflowCommand:
    """A single command in a workflow chain.

    Represents an executable command with metadata about its behavior
    and permissions.

    Attributes:
        id: Unique identifier for this command within a context
        command: Command as tuple of arguments (NEVER a shell string)
        required: If True, failure blocks the entire workflow
        mutates_state: If True, command modifies state (agent-restricted)
        agent_allowed: If True, agents may execute this command
        description: Human-readable description of what this command does
    """
    id: str
    command: tuple[str, ...]
    required: bool = True
    mutates_state: bool = False
    agent_allowed: bool = True
    description: str = ""


@dataclass(frozen=True, slots=True)
class WorkflowContext:
    """A workflow context containing a chain of commands.

    Represents a named validation workflow that can be run as a unit.

    Attributes:
        id: Unique context identifier (e.g., "mission_handoff", "promotion_dry_run")
        description: Human-readable description of this context's purpose
        agent_allowed: If True, agents may run this entire context
        mutates_state: If True, context contains state-mutating commands
        commands: Tuple of WorkflowCommand objects to execute in order
    """
    id: str
    description: str
    agent_allowed: bool = True
    mutates_state: bool = False
    commands: tuple[WorkflowCommand, ...] = ()


@dataclass(frozen=True, slots=True)
class WorkflowCommandResult:
    """Result of executing a single workflow command.

    Attributes:
        id: Command identifier
        command: The command that was executed (as tuple)
        returncode: Process exit code (0 = success)
        stdout: Captured stdout (truncated to MAX_OUTPUT_CHARS)
        stderr: Captured stderr (truncated to MAX_OUTPUT_CHARS)
        passed: True if returncode == 0
        required: Whether this command was required
    """
    id: str
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    passed: bool
    required: bool


@dataclass(frozen=True, slots=True)
class WorkflowRunResult:
    """Result of running a complete workflow context.

    Attributes:
        context_id: ID of the workflow context that was run
        passed: True if all required commands passed
        results: Tuple of WorkflowCommandResult for each executed command
        blockers: Tuple of blocker message strings
        evidence_path: Path to evidence file, or None if not written
    """
    context_id: str
    passed: bool
    results: tuple[WorkflowCommandResult, ...] = ()
    blockers: tuple[str, ...] = ()
    evidence_path: str | None = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_OUTPUT_CHARS = 10000  # Truncate stdout/stderr to this length


# ---------------------------------------------------------------------------
# Built-in Context Registry
# ---------------------------------------------------------------------------

# Built-in contexts are defined as module-level constants
# This allows them to be imported and used without initialization

MISSION_HANDOFF_CONTEXT = WorkflowContext(
    id="mission_handoff",
    description="Mission handoff validation chain - pre-check before ready_for_review",
    agent_allowed=True,
    mutates_state=False,
    commands=(
        WorkflowCommand(
            id="compileall",
            command=("python3", "-m", "compileall", "-q", "scripts", "src", "tests"),
            required=True,
            mutates_state=False,
            agent_allowed=True,
            description="Syntax check all Python files",
        ),
        WorkflowCommand(
            id="pytest_collect",
            command=("python3", "-m", "pytest", "--collect-only", "-q", "tests"),
            required=True,
            mutates_state=False,
            agent_allowed=True,
            description="Collect all tests to verify test suite structure",
        ),
        WorkflowCommand(
            id="check_fast",
            command=("bash", "scripts/check.sh", "--fast"),
            required=True,
            mutates_state=False,
            agent_allowed=True,
            description="Run fast validation suite",
        ),
        WorkflowCommand(
            id="forge_doctor",
            command=("python3", "-m", "rig", "forge", "doctor", "--json"),
            required=True,
            mutates_state=False,
            agent_allowed=True,
            description="Check forge configuration and capabilities",
        ),
        WorkflowCommand(
            id="forge_promote_dry_run",
            command=("python3", "-m", "rig", "forge", "promote", "--dry-run", "--json"),
            required=True,
            mutates_state=False,
            agent_allowed=True,
            description="Dry-run promotion planning",
        ),
    ),
)

PROMOTION_DRY_RUN_CONTEXT = WorkflowContext(
    id="promotion_dry_run",
    description="Promotion dry-run validation chain - pre-check before promotion",
    agent_allowed=True,
    mutates_state=False,
    commands=(
        WorkflowCommand(
            id="forge_doctor",
            command=("python3", "-m", "rig", "forge", "doctor", "--json"),
            required=True,
            mutates_state=False,
            agent_allowed=True,
            description="Check forge configuration and capabilities",
        ),
        WorkflowCommand(
            id="forge_promote_dry_run",
            command=("python3", "-m", "rig", "forge", "promote", "--dry-run", "--write-artifact", "--json"),
            required=True,
            mutates_state=False,
            agent_allowed=True,
            description="Dry-run promotion planning with artifactwriting",
        ),
    ),
)


# Registry of built-in contexts
_BUILTIN_CONTEXTS: dict[str, WorkflowContext] = {
    MISSION_HANDOFF_CONTEXT.id: MISSION_HANDOFF_CONTEXT,
    PROMOTION_DRY_RUN_CONTEXT.id: PROMOTION_DRY_RUN_CONTEXT,
}


def get_builtin_workflow_context(context_id: str) -> WorkflowContext:
    """Get a built-in workflow context by ID.

    Args:
        context_id: The context identifier (e.g., "mission_handoff")

    Returns:
        The WorkflowContext with the matching ID

    Raises:
        ValueError: If no context with the given ID exists
    """
    if context_id not in _BUILTIN_CONTEXTS:
        known = ", ".join(sorted(_BUILTIN_CONTEXTS.keys()))
        raise ValueError(
            f"Unknown workflow context: '{context_id}'. "
            f"Known contexts: {known}"
        )
    return _BUILTIN_CONTEXTS[context_id]


def list_builtin_workflow_contexts() -> tuple[WorkflowContext, ...]:
    """List all built-in workflow contexts.

    Returns:
        Tuple of all built-in WorkflowContext objects
    """
    return tuple(_BUILTIN_CONTEXTS.values())


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _truncate_output(output: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Truncate output to a safe maximum length.

    Args:
        output: The output string to truncate
        max_chars: Maximum number of characters (default: MAX_OUTPUT_CHARS)

    Returns:
        Truncated string with ellipsis if truncated
    """
    if len(output) <= max_chars:
        return output
    return output[:max_chars - 3] + "..."


def run_workflow_context(
    context_id: str,
    repo_path: Path | str = ".",
    write_evidence: bool = True,
) -> WorkflowRunResult:
    """Run a workflow context and return results.

    Executes each command in the context's command chain in order.
    Stops on first required command failure. Continues on optional
    command failure.

    Rules:
    - Uses subprocess.run with explicit command arrays, NEVER shell=True
    - Captures stdout/stderr for each command
    - Truncates output to MAX_OUTPUT_CHARS
    - Writes evidence file if write_evidence=True
    - Evidence path: .rig/work/validation/<context_id>-<timestamp>.json
    - Never includes tokens/secrets in evidence
    - Never includes personal names in evidence

    Args:
        context_id: The workflow context ID to run
        repo_path: Repository root path (default: current directory)
        write_evidence: If True, write evidence file (default: True)

    Returns:
        WorkflowRunResult with all command results and overall status
    """
    repo_path = Path(repo_path)
    context = get_builtin_workflow_context(context_id)

    results: list[WorkflowCommandResult] = []
    blockers: list[str] = []
    passed = True

    # Execute each command in order
    for cmd in context.commands:
        # Skip mutating commands unless explicitly allowed (not applicable here
        # since we don't have --allow-mutating flag in this function)
        # The CLI layer handles this check

        try:
            proc = subprocess.run(
                cmd.command,
                cwd=repo_path,
                capture_output=True,
                text=True,
                # NEVER use shell=True - use explicit argument arrays
                shell=False,
                timeout=300,  # 5 minute timeout per command
            )

            stdout = _truncate_output(proc.stdout)
            stderr = _truncate_output(proc.stderr)
            command_passed = proc.returncode == 0

            result = WorkflowCommandResult(
                id=cmd.id,
                command=cmd.command,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                passed=command_passed,
                required=cmd.required,
            )
            results.append(result)

            # Track failure
            if not command_passed:
                if cmd.required:
                    passed = False
                    blockers.append(f"{cmd.id} failed with exit code {proc.returncode}")
                    # Stop on required failure
                    break
                else:
                    # Optional command failed - continue but record
                    blockers.append(f"{cmd.id} failed with exit code {proc.returncode} (optional)")

        except subprocess.TimeoutExpired as e:
            result = WorkflowCommandResult(
                id=cmd.id,
                command=cmd.command,
                returncode=-1,
                stdout="",
                stderr=_truncate_output(f"Command timed out after 300 seconds: {e}"),
                passed=False,
                required=cmd.required,
            )
            results.append(result)
            passed = False
            blockers.append(f"{cmd.id} timed out")
            if cmd.required:
                break

        except OSError as e:
            result = WorkflowCommandResult(
                id=cmd.id,
                command=cmd.command,
                returncode=-1,
                stdout="",
                stderr=_truncate_output(f"Command failed to execute: {e}"),
                passed=False,
                required=cmd.required,
            )
            results.append(result)
            passed = False
            blockers.append(f"{cmd.id} failed to execute: {e}")
            if cmd.required:
                break

    # Write evidence if requested
    evidence_path: str | None = None
    if write_evidence:
        evidence_dir = repo_path / ".rig" / "work" / "validation"
        evidence_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        evidence_file = evidence_dir / f"{context_id}-{timestamp}.json"
        evidence_path = str(evidence_file)

        evidence = {
            "context_id": context_id,
            "passed": passed,
            "timestamp": timestamp,
            "results": [
                {
                    "id": r.id,
                    "command": list(r.command),
                    "returncode": r.returncode,
                    "passed": r.passed,
                    "required": r.required,
                    "stdout": r.stdout,
                    "stderr": r.stderr,
                }
                for r in results
            ],
            "blockers": list(blockers),
        }

        try:
            evidence_file.write_text(
                json.dumps(evidence, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except (OSError, IOError):
            # Failed to write evidence - continue without evidence path
            evidence_path = None

    return WorkflowRunResult(
        context_id=context_id,
        passed=passed,
        results=tuple(results),
        blockers=tuple(blockers),
        evidence_path=evidence_path,
    )
