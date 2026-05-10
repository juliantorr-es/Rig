"""Rig workflow command chains CLI.

This module provides the `rig workflow` command for running workflow chains.
Workflow chains are deterministic validation sequences that replace manual
command checklists.

ADR 0009: Agentic Workflow Refinement
Sprint: Workflow Command Chains

Core principles:
- Agents run workflow contexts, not manual command checklists
- `mission_handoff` is the canonical pre-handooff gate
- `promotion_dry_run` is the canonical pre-promotion dry-run gate
- All initial contexts are non-mutating and agent-allowed
- User must explicitly consent to mutating contexts via --allow-mutating
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from rig.domain.workflow_chains import (
    WorkflowCommand,
    WorkflowCommandResult,
    WorkflowContext,
    WorkflowRunResult,
    get_builtin_workflow_context,
    list_builtin_workflow_contexts,
    run_workflow_context,
)


def _emit(payload: dict[str, object]) -> None:
    """Emit JSON payload to stdout."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def _serialize_workflow_command(cmd: WorkflowCommand) -> dict[str, Any]:
    """Serialize WorkflowCommand to JSON-compatible dict."""
    return {
        "id": cmd.id,
        "command": list(cmd.command),
        "required": cmd.required,
        "mutates_state": cmd.mutates_state,
        "agent_allowed": cmd.agent_allowed,
        "description": cmd.description,
    }


def _serialize_workflow_context(ctx: WorkflowContext) -> dict[str, Any]:
    """Serialize WorkflowContext to JSON-compatible dict."""
    return {
        "id": ctx.id,
        "description": ctx.description,
        "agent_allowed": ctx.agent_allowed,
        "mutates_state": ctx.mutates_state,
        "commands": [_serialize_workflow_command(c) for c in ctx.commands],
    }


def _serialize_workflow_command_result(result: WorkflowCommandResult) -> dict[str, Any]:
    """Serialize WorkflowCommandResult to JSON-compatible dict."""
    return {
        "id": result.id,
        "command": list(result.command),
        "returncode": result.returncode,
        "passed": result.passed,
        "required": result.required,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _serialize_workflow_run_result(result: WorkflowRunResult) -> dict[str, Any]:
    """Serialize WorkflowRunResult to JSON-compatible dict."""
    return {
        "context_id": result.context_id,
        "passed": result.passed,
        "results": [_serialize_workflow_command_result(r) for r in result.results],
        "blockers": list(result.blockers),
        "evidence_path": result.evidence_path,
    }


def _emit_human_workflow_context(ctx: WorkflowContext) -> None:
    """Emit human-readable workflow context info."""
    print(f"  Context: {ctx.id}")
    print(f"    Description: {ctx.description}")
    print(f"    Agent allowed: {ctx.agent_allowed}")
    print(f"    Mutates state: {ctx.mutates_state}")
    print(f"    Commands ({len(ctx.commands)}):")
    for cmd in ctx.commands:
        print(f"      - {cmd.id}: {cmd.description}")


def _emit_human_workflow_run_result(result: WorkflowRunResult) -> None:
    """Emit human-readable workflow run result."""
    print(f"Workflow Run Result: {result.context_id}")
    print(f"  Passed: {'Yes' if result.passed else 'No'}")
    print(f"  Commands executed: {len(result.results)}")
    print()

    for r in result.results:
        status = "PASSED" if r.passed else "FAILED"
        req_marker = " [required]" if r.required else " [optional]"
        print(f"  [{status}{req_marker}] {r.id}")
        print(f"    Command: {' '.join(r.command)}")
        print(f"    Exit code: {r.returncode}")
        if r.stdout:
            stdout_lines = r.stdout.splitlines()
            print(f"    Stdout: {stdout_lines[0]}")
            if len(stdout_lines) > 1:
                print(f"            (... truncated, {len(stdout_lines)} lines)")
        if r.stderr:
            stderr_lines = r.stderr.splitlines()
            print(f"    Stderr: {stderr_lines[0]}")
            if len(stderr_lines) > 1:
                print(f"            (... truncated, {len(stderr_lines)} lines)")

    if result.blockers:
        print()
        print(f"  Blockers ({len(result.blockers)}):")
        for b in result.blockers:
            print(f"    - {b}")

    if result.evidence_path:
        print()
        print(f"  Evidence: {result.evidence_path}")


def _workflow_list_handler(
    json_output: bool = False,
) -> int:
    """Handler for `rig workflow list` command.

    Lists all available workflow contexts.

    Args:
        json_output: If True, emit JSON; otherwise human-readable text

    Returns:
        Exit code (0 = success)
    """
    contexts = list_builtin_workflow_contexts()

    if json_output:
        payload = {
            "workflow_contexts": [_serialize_workflow_context(ctx) for ctx in contexts],
            "count": len(contexts),
        }
        _emit(payload)
        return 0

    print("Available Workflow Contexts")
    print("+" * 40)
    print()

    for ctx in contexts:
        _emit_human_workflow_context(ctx)
        print()

    print(f"Total: {len(contexts)} context(s)")
    return 0


def _workflow_run_handler(
    context_id: str,
    repo_root: Path,
    json_output: bool = False,
    no_evidence: bool = False,
    agent: bool = False,
    allow_mutating: bool = False,
) -> int:
    """Handler for `rig workflow run` command.

    Runs a specific workflow context.

    Args:
        context_id: The workflow context ID to run
        repo_root: Path to the git repository
        json_output: If True, emit JSON; otherwise human-readable text
        no_evidence: If True, don't write evidence file
        agent: If True, enforce agent_allowed check
        allow_mutating: If True, allow running mutating contexts

    Returns:
        Exit code (0 = passed, 1 = failed)
    """
    # Get the context
    try:
        context = get_builtin_workflow_context(context_id)
    except ValueError as e:
        if json_output:
            _emit({"status": "error", "error": str(e)})
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    # Agent check
    if agent and not context.agent_allowed:
        if json_output:
            _emit({"status": "error", "error": f"Context '{context_id}' is not agent-allowed"})
        else:
            print(f"Error: Context '{context_id}' is not agent-allowed", file=sys.stderr)
        return 1

    # Mutating check
    if context.mutates_state and not allow_mutating:
        if json_output:
            _emit({"status": "error", "error": f"Context '{context_id}' mutates state; use --allow-mutating to allow"})
        else:
            print(f"Error: Context '{context_id}' mutates state; use --allow-mutating to allow", file=sys.stderr)
        return 1

    # Also check individual commands for agent/mutating if context passes
    for cmd in context.commands:
        if agent and not cmd.agent_allowed:
            if json_output:
                _emit({"status": "error", "error": f"Command '{cmd.id}' in context '{context_id}' is not agent-allowed"})
            else:
                print(f"Error: Command '{cmd.id}' in context '{context_id}' is not agent-allowed", file=sys.stderr)
            return 1
        if cmd.mutates_state and not allow_mutating:
            if json_output:
                _emit({"status": "error", "error": f"Command '{cmd.id}' in context '{context_id}' mutates state; use --allow-mutating to allow"})
            else:
                print(f"Error: Command '{cmd.id}' in context '{context_id}' mutates state; use --allow-mutating to allow", file=sys.stderr)
            return 1

    # Run the workflow
    try:
        result = run_workflow_context(
            context_id=context_id,
            repo_path=repo_root,
            write_evidence=not no_evidence,
        )
    except Exception as e:
        if json_output:
            _emit({"status": "error", "error": str(e)})
        else:
            print(f"Error running workflow: {e}", file=sys.stderr)
        return 1

    # Output results
    if json_output:
        _emit(_serialize_workflow_run_result(result))
    else:
        _emit_human_workflow_run_result(result)

    return 0 if result.passed else 1


def _workflow_handler(
    repo_root: Path,
    subcommand: str | None = None,
    context_id: str | None = None,
    json_output: bool = False,
    no_evidence: bool = False,
    agent: bool = False,
    allow_mutating: bool = False,
    list_contexts: bool = False,
) -> int:
    """Main handler for `rig workflow` command.

    Args:
        repo_root: Path to the git repository
        subcommand: Subcommand ('run' or 'list')
        context_id: Context ID for 'run' subcommand
        json_output: If True, emit JSON
        no_evidence: If True, don't write evidence
        agent: If True, enforce agent_allowed check
        allow_mutating: If True, allow mutating contexts
        list_contexts: If True, list available contexts

    Returns:
        Exit code
    """
    if list_contexts or subcommand == "list":
        return _workflow_list_handler(json_output=json_output)

    if subcommand == "run":
        if context_id is None:
            if json_output:
                _emit({"status": "error", "error": "--context-id is required for 'run' subcommand"})
            else:
                print("Error: --context-id is required for 'run' subcommand", file=sys.stderr)
            return 1
        return _workflow_run_handler(
            context_id=context_id,
            repo_root=repo_root,
            json_output=json_output,
            no_evidence=no_evidence,
            agent=agent,
            allow_mutating=allow_mutating,
        )

    # Default: show help
    if json_output:
        _emit({"status": "error", "error": "Unknown subcommand. Use 'run' or 'list'"})
    else:
        print("Error: Unknown subcommand. Use 'rig workflow run --help' or 'rig workflow list'")
    return 1


def register(subparsers, helpers) -> None:
    """Register workflow command with CLI.

    Args:
        subparsers: argparse subparsers object from main CLI
        helpers: Object with repo_root attribute
    """
    parser = subparsers.add_parser(
        "workflow",
        help="Workflow command chains for agent validation gates",
        description="Run deterministic workflow chains instead of manual command checklists. "
                    "Agents run workflow contexts (e.g., mission_handoff) for validation.",
    )

    workflow_sub = parser.add_subparsers(dest="workflow_subcommand", required=True)

    # workflow list subcommand
    list_parser = workflow_sub.add_parser(
        "list",
        help="List available workflow contexts",
        description="List all built-in workflow contexts with their commands and properties.",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output JSON instead of human-readable text",
    )
    list_parser.set_defaults(
        handler=lambda args: _workflow_list_handler(
            json_output=args.json,
        )
    )

    # workflow run subcommand
    run_parser = workflow_sub.add_parser(
        "run",
        help="Run a workflow context",
        description="Run a specific workflow context by ID. Stops on first required command failure.",
    )
    run_parser.add_argument(
        "context_id",
        nargs="?",
        default=None,
        help="Workflow context ID to run (e.g., 'mission_handoff', 'promotion_dry_run')",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output JSON instead of human-readable text",
    )
    run_parser.add_argument(
        "--no-evidence",
        action="store_true",
        default=False,
        help="Don't write evidence file",
    )
    run_parser.add_argument(
        "--agent",
        action="store_true",
        default=False,
        help="Enforce agent_allowed check (fail if context or any command is not agent-allowed)",
    )
    run_parser.add_argument(
        "--allow-mutating",
        action="store_true",
        default=False,
        help="Allow running mutating contexts (default: false). User must explicitly consent.",
    )
    run_parser.set_defaults(
        handler=lambda args: _workflow_run_handler(
            context_id=args.context_id,
            repo_root=helpers.repo_root,
            json_output=args.json,
            no_evidence=args.no_evidence,
            agent=args.agent,
            allow_mutating=args.allow_mutating,
        )
    )
