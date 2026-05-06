"""
Anigma Architecture Sentinel CLI integration for rig.py

Authority Class: Class 2 Gate Validator (via delegation)
Mutation Behavior: Non-mutating (delegates to underlying validators)
Canonical Inputs: Anigma sentinel output, loop state
Generated Outputs: Loop artifacts, receipts
Baseline Behavior: Reads only, never writes in gate mode
CI/Review Usage: validate and review phases

This module provides CLI integration for Anigma-specific governance:
- sentinel: Run Anigma Architecture Sentinel validator
- loop: Run Anigma Remediation Loop adapter
"""

from __future__ import annotations

import json
import sys
import subprocess
from pathlib import Path
from typing import Any, Optional

from .paths import repo_root, resolve_repo_path


def register(subparsers, helpers):
    """Registers the 'anigma' command group."""
    parser = subparsers.add_parser("anigma", help="Anigma-specific governance commands")
    anigma_sub = parser.add_subparsers(dest="anigma_command")

    # Sentinel command
    sentinel_parser = anigma_sub.add_parser("sentinel", help="Run Anigma Architecture Sentinel validator")
    sentinel_parser.add_argument("--format", choices=["text", "json", "md"], default="text",
                                  help="Output format (text, json, or markdown)")
    sentinel_parser.add_argument("--explain", action="store_true",
                                  help="Explain the role of the sentinel")
    sentinel_parser.add_argument("--write-hash", action="store_true",
                                  help="Write the current hash to governance docs (manual only)")
    sentinel_parser.add_argument("--dry-run", action="store_true",
                                  help="Do not write receipts")
    sentinel_parser.set_defaults(handler=lambda args: anigma_sentinel(
        format=args.format,
        explain=args.explain,
        write_hash=args.write_hash,
        dry_run=args.dry_run
    ))

    # Loop command group
    loop_parser = anigma_sub.add_parser("loop", help="Anigma Remediation Loop commands")
    loop_sub = loop_parser.add_subparsers(dest="loop_command", required=True)

    # loop status
    loop_status_parser = loop_sub.add_parser("status", help="Show current sentinel and loop status")
    loop_status_parser.add_argument("--format", choices=["json", "md"], default="json")
    loop_status_parser.set_defaults(handler=lambda args: anigma_loop_status(format=args.format))

    # loop plan
    loop_plan_parser = loop_sub.add_parser("plan", help="Create remediation plan")
    loop_plan_parser.add_argument("--from-sentinel", action="store_true",
                                   help="Auto-select from sentinel")
    loop_plan_parser.add_argument("--issue-family", default=None,
                                   help="Specific issue family to plan for")
    loop_plan_parser.add_argument("--issue-code", default=None,
                                   help="Specific issue code to plan for")
    loop_plan_parser.add_argument("--max-steps", type=int, default=3,
                                   help="Max steps in plan")
    loop_plan_parser.add_argument("--format", choices=["json", "md"], default="json")
    loop_plan_parser.set_defaults(handler=lambda args: anigma_loop_plan(
        from_sentinel=args.from_sentinel,
        issue_family=args.issue_family,
        issue_code=args.issue_code,
        max_steps=args.max_steps,
        format=args.format
    ))

    # loop run
    loop_run_parser = loop_sub.add_parser("run", help="Execute remediation loop")
    loop_run_parser.add_argument("--issue-family", default=None,
                                  help="Issue family to remediate")
    loop_run_parser.add_argument("--issue-code", default=None,
                                  help="Specific issue code to remediate")
    loop_run_parser.add_argument("--max-steps", type=int, default=3,
                                  help="Max steps in loop")
    loop_run_parser.add_argument("--mode", choices=["plan_only", "dry_run", "sandbox"],
                                  default="plan_only",
                                  help="Loop execution mode")
    loop_run_parser.add_argument("--format", choices=["json", "md"], default="json")
    loop_run_parser.set_defaults(handler=lambda args: anigma_loop_run(
        issue_family=args.issue_family,
        issue_code=args.issue_code,
        max_steps=args.max_steps,
        mode=args.mode,
        format=args.format
    ))

    # loop show
    loop_show_parser = loop_sub.add_parser("show", help="Show loop run details")
    loop_show_parser.add_argument("--run-id", required=True, help="Run ID to show")
    loop_show_parser.add_argument("--format", choices=["json", "md"], default="json")
    loop_show_parser.set_defaults(handler=lambda args: anigma_loop_show(
        run_id=args.run_id,
        format=args.format
    ))

    # loop list
    loop_list_parser = loop_sub.add_parser("list", help="List all loop runs")
    loop_list_parser.add_argument("--format", choices=["json", "md"], default="json")
    loop_list_parser.set_defaults(handler=lambda args: anigma_loop_list(format=args.format))


def anigma_sentinel(format: str = "text", explain: bool = False,
                    write_hash: bool = False, dry_run: bool = False) -> int:
    """Runs the Anigma Architecture Sentinel governance validator."""
    sentinel_py = resolve_repo_path("scripts", "anigma_architecture_sentinel.py")

    if not sentinel_py.exists():
        # Fallback to old path if not found, but log warning
        sentinel_py = repo_root() / "Scripts" / "anigma_architecture_sentinel.py"
        if not sentinel_py.exists():
            print(f"Error: Anigma Architecture Sentinel not found at {sentinel_py}", file=sys.stderr)
            return 1

    # Build command arguments
    cmd = [sys.executable, str(sentinel_py)]
    
    if explain:
        cmd.append("--explain")
    if write_hash:
        cmd.append("--write-hash")
    if dry_run:
        cmd.append("--dry-run")
    
    cmd.extend(["--format", format])

    # We use subprocess.run here because the sentinel is the authority
    # and we want to pass through its output and exit code directly.
    # textarea hidden
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=False,
            text=True
        )
        return result.returncode
    except FileNotFoundError:
        print(f"Error: Could not execute {cmd[0]}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


def anigma_loop_status(format: str = "json") -> int:
    """Get current Anigma sentinel and loop status."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "rig_tools"))
        from rig_tools.anigma_loop import run_status
        
        status = run_status()
        
        if format == "md":
            # Generate markdown
            md = ["# Anigma Loop Status", ""]
            md.append(f"- Schema Version: `{status.get('schema_version', 'unknown')}`")
            md.append(f"- Status: `{status.get('status', 'unknown')}`")
            md.append(f"- Sentinel Exists: {'Yes' if status.get('exists') else 'No'}")
            if status.get('issue_count'):
                md.append(f"- Total Issues: {status.get('issue_count')}")
            
            if 'issue_families' in status:
                md.append("")
                md.append("## Issue Families")
                for family, info in status['issue_families'].items():
                    md.append(f"- **{family}**: {info.get('count', 0)} issues")
            
            if 'surfaces' in status:
                md.append("")
                md.append("## Surfaces")
                for surface, info in status['surfaces'].items():
                    md.append(f"- **{surface}**: {info.get('status', 'unknown')} - {info.get('issues', {}).get('total', 0)} issues")
            
            if 'loop_artifacts' in status and status['loop_artifacts']:
                md.append("")
                md.append("## Recent Loop Artifacts")
                for artifact in status['loop_artifacts'][:10]:
                    md.append(f"- `{artifact}`")
            
            print("\n".join(md))
        else:
            print(json.dumps(status, indent=2))
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def anigma_loop_plan(
    from_sentinel: bool = False,
    issue_family: Optional[str] = None,
    issue_code: Optional[str] = None,
    max_steps: int = 3,
    format: str = "json"
) -> int:
    """Create a remediation plan."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "rig_tools"))
        from rig_tools.anigma_loop import run_plan
        
        plan = run_plan(
            issue_family=issue_family if from_sentinel is False else None,
            issue_code=issue_code,
            max_steps=max_steps
        )
        
        if format == "md":
            # We need to generate MD from the plan dict
            from rig_tools.anigma_loop import get_loop
            loop = get_loop()
            print(loop._generate_plan_markdown(plan))
        else:
            print(json.dumps(plan.to_dict(), indent=2))
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def anigma_loop_run(
    issue_family: Optional[str] = None,
    issue_code: Optional[str] = None,
    max_steps: int = 3,
    mode: str = "plan_only",
    format: str = "json"
) -> int:
    """Execute a remediation loop."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "rig_tools"))
        from rig_tools.anigma_loop import run_plan, run_loop
        
        plan = run_plan(
            issue_family=issue_family,
            issue_code=issue_code,
            max_steps=max_steps
        )
        
        result = run_loop(plan, mode=mode)
        
        if format == "md":
            from rig_tools.anigma_loop import get_loop
            loop = get_loop()
            print(loop._generate_result_markdown(result))
        else:
            print(json.dumps(result.to_dict(), indent=2))
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def anigma_loop_show(run_id: str, format: str = "json") -> int:
    """Show loop run details."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "rig_tools"))
        from rig_tools.anigma_loop import run_show
        
        data = run_show(run_id)
        if data is None:
            print(f"Run {run_id} not found", file=sys.stderr)
            return 1
        
        if format == "md":
            # Generate markdown
            md = [f"# Loop Run: {run_id}", ""]
            if "loop" in data:
                loop_data = data["loop"]
                md.append(f"- Status: {loop_data.get('status', 'unknown')}")
                md.append(f"- Run ID: {loop_data.get('run_id', 'unknown')}")
                md.append(f"- Mode: {loop_data.get('mode', 'unknown')}")
            if "plan" in data:
                plan_data = data["plan"]
                md.append(f"- Issue Family: {plan_data.get('issue_family', 'unknown')}")
                md.append(f"- Issue Count: {plan_data.get('issue_count', 0)}")
                md.append(f"- Status: {plan_data.get('status', 'unknown')}")
                if plan_data.get("stop_reason"):
                    md.append(f"- Stop Reason: {plan_data.get('stop_reason')}")
            if "events" in data:
                md.append("")
                md.append("## Events")
                for event in data["events"]:
                    md.append(f"- {event}")
            print("\n".join(md))
        else:
            print(json.dumps(data, indent=2))
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def anigma_loop_list(format: str = "json") -> int:
    """List all loop runs."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "rig_tools"))
        from rig_tools.anigma_loop import run_list
        
        runs = run_list()
        
        if format == "md":
            md = ["# Anigma Loop Runs", ""]
            if not runs:
                md.append("No loop runs found.")
            else:
                for run in runs:
                    status = run.get('status', 'unknown')
                    family = run.get('issue_family', 'unknown')
                    has_plan = '✓' if run.get('has_plan') else '✗'
                    has_loop = '✓' if run.get('has_loop') else '✗'
                    md.append(f"- **{run['run_id']}** [{status}]: {family} | Plan:{has_plan} Loop:{has_loop}")
            print("\n".join(md))
        else:
            print(json.dumps(runs, indent=2))
        
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
