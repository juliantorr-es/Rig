"""work_research.py — Start or complete Sprint Research phase.

Mandatory read-only planning before sprint implementation.

Usage:
    # Start research for a sprint
    python3 scripts/work_research.py <task_id> --sprint <sprint_id> --worker <name> --action start
    
    # Complete research for a sprint
    python3 scripts/work_research.py <task_id> --sprint <sprint_id> --worker <name> --action complete \
        --research-summary <path> \
        --repo-inventory <path> \
        --relevant-files <path> \
        --current-state <path> \
        --risk-notes <path> \
        --mission-plan <path> \
        --validation-plan <path> \
        --out-of-scope-findings <path>

Sprint Research Rules:
- Research is MANDATORY before any implementation.
- Research is READ-ONLY — no file edits except writing artifacts.
- Must use installed Python tooling (pathlib, json, ast, difflib, subprocess, tokenize).
- Must use CLI tools (rg, fd, git diff, git status --porcelain=v1).
- Must identify expected files before mutation begins.
- Must define validation commands before mutation begins.
- Must record out-of-current-scope findings.

Artifacts are written to: .rig/work/adr/<task_id>/sprints/<sprint_id>/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure scripts directory is on path for imports
_scripts_dir = Path(__file__).parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

from _work_lib import (
    ADR_WORK_ROOT,
    append_event,
    load_task,
    make_event,
    sprint_workspace,
)


def get_sprint(task: dict, sprint_id: str) -> dict:
    """Get sprint by ID from task."""
    for s in task.get("sprints", []):
        if s.get("id") == sprint_id:
            return s
    raise ValueError(
        f"Sprint '{sprint_id}' not found in task '{task['id']}'.\n"
        f"Known sprints: {[s.get('id') for s in task.get('sprints', [])]}"
    )


def validate_research_artifacts(artifacts: dict) -> list[str]:
    """Validate that required research artifacts are provided."""
    required = [
        "research_summary",
        "repo_inventory",
        "relevant_files",
        "current_state",
        "risk_notes",
        "mission_plan",
        "validation_plan",
    ]
    missing = [name for name in required if not artifacts.get(name)]
    return missing


def write_research_artifacts(task_id: str, sprint_id: str, artifacts: dict) -> dict[str, str]:
    """Write research artifacts to the sprint workspace. Returns dict of written paths."""
    sprint_dir = sprint_workspace(task_id, sprint_id)
    sprint_dir.mkdir(parents=True, exist_ok=True)
    
    written = {}
    for name, path in artifacts.items():
        if path:
            dest = sprint_dir / Path(path).name
            dest.write_text(Path(path).read_text() if Path(path).exists() else path)
            written[name] = str(dest.relative_to(sprint_dir))
    
    return written


def main() -> int:
    p = argparse.ArgumentParser(
        prog="work_research.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("task_id", metavar="TASK_ID", help="ADR task ID")
    p.add_argument("--sprint", metavar="SPRINT_ID", required=True, help="Sprint ID")
    p.add_argument("--worker", metavar="WORKER", required=True, help="Agent/worker name")
    p.add_argument(
        "--action",
        metavar="ACTION",
        choices=["start", "complete"],
        required=True,
        help="Start or complete sprint research",
    )
    
    # Artifacts for complete action
    p.add_argument("--research-summary", metavar="PATH", default="", help="Path to research summary file")
    p.add_argument("--repo-inventory", metavar="PATH", default="", help="Path to repo inventory file")
    p.add_argument("--relevant-files", metavar="PATH", default="", help="Path to relevant files file")
    p.add_argument("--current-state", metavar="PATH", default="", help="Path to current state file")
    p.add_argument("--risk-notes", metavar="PATH", default="", help="Path to risk notes file")
    p.add_argument("--mission-plan", metavar="PATH", default="", help="Path to mission plan file")
    p.add_argument("--patch-batches", metavar="PATH", default="", help="Path to patch batches plan")
    p.add_argument("--validation-plan", metavar="PATH", default="", help="Path to validation plan file")
    p.add_argument("--out-of-scope-findings", metavar="PATH", default="", help="Path to out-of-scope findings")
    
    args = p.parse_args()
    
    task = load_task(args.task_id)
    sprint = get_sprint(task, args.sprint)
    
    ts = datetime.now(timezone.utc).isoformat()
    
    if args.action == "start":
        # Validate sprint research hasn't already started or completed
        current_research_status = sprint.get("research_status", "not_started")
        if current_research_status == "completed":
            print(f"ERROR: Sprint {args.sprint} research already completed.")
            return 1
        
        event = make_event(
            event_type="sprint_research_started",
            task_id=args.task_id,
            sprint_id=args.sprint,
            worker=args.worker,
            ts=ts,
            note=f"Starting research for sprint {args.sprint} on task {args.task_id}",
        )
        append_event(args.task_id, event)
        
        # Update sprint research_status
        sprint["research_status"] = "in_progress"
        sprint["research_started_at"] = ts
        
        # Write updated task
        task_path = ADR_WORK_ROOT / args.task_id / "task.json"
        task_path.write_text(json.dumps(task, indent=2) + "\n")
        
        print(f"Sprint research STARTED: task={args.task_id} sprint={args.sprint} worker={args.worker}")
        print(f"Artifacts directory: .rig/work/adr/{args.task_id}/sprints/{args.sprint}/")
        print(f"Next: Complete research with --action complete and provide all required artifacts.")
        return 0
    
    else:  # action == "complete"
        # Validate sprint research is in progress
        current_research_status = sprint.get("research_status", "not_started")
        if current_research_status != "in_progress":
            print(f"ERROR: Sprint {args.sprint} research not in progress (status: {current_research_status}).")
            return 1
        
        # Collect artifacts
        artifacts = {
            "research_summary": args.research_summary,
            "repo_inventory": args.repo_inventory,
            "relevant_files": args.relevant_files,
            "current_state": args.current_state,
            "risk_notes": args.risk_notes,
            "mission_plan": args.mission_plan,
            "patch_batches": args.patch_batches,
            "validation_plan": args.validation_plan,
            "out_of_scope_findings": args.out_of_scope_findings,
        }
        
        missing = validate_research_artifacts(artifacts)
        if missing:
            print(f"ERROR: Missing required research artifacts: {', '.join(missing)}")
            return 1
        
        # Write artifacts to sprint workspace
        written = write_research_artifacts(args.task_id, args.sprint, artifacts)
        
        # Build event with artifact list
        artifact_list = list(written.values())
        event = make_event(
            event_type="sprint_research_completed",
            task_id=args.task_id,
            sprint_id=args.sprint,
            worker=args.worker,
            ts=ts,
            note=f"Completed research for sprint {args.sprint}",
            research_artifacts=artifact_list,
        )
        append_event(args.task_id, event)
        
        # Update sprint research_status
        sprint["research_status"] = "completed"
        sprint["research_completed_at"] = ts
        sprint["research_artifacts_path"] = f".rig/work/adr/{args.task_id}/sprints/{args.sprint}"
        
        # Write updated task
        task_path = ADR_WORK_ROOT / args.task_id / "task.json"
        task_path.write_text(json.dumps(task, indent=2) + "\n")
        
        print(f"Sprint research COMPLETED: task={args.task_id} sprint={args.sprint} worker={args.worker}")
        print(f"Artifacts written to: .rig/work/adr/{args.task_id}/sprints/{args.sprint}/")
        for name, path in written.items():
            print(f"  {name}: {path}")
        print(f"Next: Implementation may begin. Use work_claim.py to claim missions.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
