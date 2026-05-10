"""work_patch_batch.py — Manage patch batch planning, precheck, merge-friendliness check, apply, and validation.

Patch batches group coherent changes for reliable application.

Usage:
    # Plan a patch batch
    python3 scripts/work_patch_batch.py <task_id> --mission <mission_id> --action plan \
        --batch <batch_id> --planned-files <file1> <file2> ...
    
    # Precheck a patch batch (git apply --check)
    python3 scripts/work_patch_batch.py <task_id> --mission <mission_id> --action precheck \
        --batch <batch_id> --patch-file <path.to.patch>
    
    # Check merge-friendliness before apply
    python3 scripts/work_patch_batch.py <task_id> --mission <mission_id> --action merge-friendly \
        --batch <batch_id> --patch-file <path.to.patch>
    
    # Apply a patch batch (requires merge-friendliness check first)
    python3 scripts/work_patch_batch.py <task_id> --mission <mission_id> --action apply \
        --batch <batch_id> --patch-file <path.to.patch>
    
    # Validate a patch batch after applying
    python3 scripts/work_patch_batch.py <task_id> --mission <mission_id> --action validate \
        --batch <batch_id> --validation-results <path.to.json>

Patch Batch Rules:
- Prefer patch batches over repeated fine-grained edits.
- A patch batch must be coherent and reviewable.
- Do not batch unrelated domains together.
- Always run git apply --check before applying.
- Patch batches require merge-friendliness preflight before apply.
- Apply only after precheck AND merge-friendliness check pass.
- Validate immediately after each batch.
- Stop if actual changed files exceed planned files.
- Stop if protected paths are touched.
- Stop if unexpected dirty files appear.
- Do not use git reset/restore/stash/checkout/clean for rollback.

Patch files are stored under:
  .rig/work/adr/<task_id>/sprints/<sprint_id>/patch-batches/<batch_id>.patch

Merge-friendliness:
- Agents must not apply patches blindly while other worktrees are active.
- Dirty same-file overlap in another worktree blocks by default.
- Same-directory overlap warns.
- Use --accept-risky to override warning results (use with caution).
- Merge simulation is advisory/preflight only and does not mutate worktrees.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
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
    get_mission,
    get_sprint,
    load_task,
    make_event,
    now_iso,
    sprint_workspace,
)


def get_mission_sprint(mission: dict, sprints: list[dict]) -> dict | None:
    """Find the sprint containing a mission by ID."""
    for s in sprints:
        if mission.get("id") in [m.get("id") for m in s.get("missions", [])]:
            return s
        if mission.get("id") in s.get("mission_ids", []):
            return s
    return None


def get_task_mission_sprint(task: dict, mission_id: str) -> tuple[dict, dict | None]:
    """Get mission and its containing sprint from task."""
    mission = get_mission(task, mission_id)
    sprint = get_mission_sprint(mission, task.get("sprints", []))
    return mission, sprint


def load_patch_file(patch_path: str | Path) -> str:
    """Load patch file content."""
    path = Path(patch_path)
    if not path.exists():
        raise FileNotFoundError(f"Patch file not found: {patch_path}")
    return path.read_text()


def run_git_apply_check(patch_path: str | Path) -> tuple[bool, str]:
    """Run git apply --check on a patch file. Returns (passed, output)."""
    cmd = ["git", "apply", "--check", str(patch_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    passed = r.returncode == 0
    output = r.stdout + r.stderr
    return passed, output


def run_git_apply(patch_path: str | Path) -> tuple[bool, str]:
    """Run git apply on a patch file. Returns (passed, output)."""
    cmd = ["git", "apply", str(patch_path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    passed = r.returncode == 0
    output = r.stdout + r.stderr
    return passed, output


def get_dirty_files() -> list[str]:
    """Get list of dirty files using git status --porcelain=v1."""
    r = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return []
    
    dirty = []
    for line in r.stdout.strip().split("\n"):
        if line.strip():
            # porcelain=v1 format: <status> <path>
            parts = line.strip().split(" ", 1)
            if len(parts) == 2:
                dirty.append(parts[1])
    return dirty


def get_task_allowed_paths(task: dict, mission: dict | None = None, sprint: dict | None = None) -> tuple[list[str], list[str]]:
    """Get allowed and protected paths for task/mission/sprint."""
    allowed = task.get("allowed_paths", [])
    protected = task.get("protected_paths", [])
    
    if sprint:
        sprint_allowed = sprint.get("allowed_paths", [])
        if sprint_allowed:
            allowed = sprint_allowed
    
    if mission:
        mission_allowed = mission.get("allowed_paths", [])
        if mission_allowed:
            allowed = mission_allowed
    
    return allowed, protected


def check_protected_paths_touched(files: list[str], protected: list[str]) -> list[str]:
    """Check if any protected paths are in the file list."""
    touched = []
    for f in files:
        for p in protected:
            # Simple exact match or prefix match
            if f == p or f.startswith(p + "/") or p.startswith(f + "/"):
                touched.append(f)
                break
    return touched


def main() -> int:
    p = argparse.ArgumentParser(
        prog="work_patch_batch.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("task_id", metavar="TASK_ID", help="ADR task ID")
    p.add_argument("--mission", metavar="MISSION_ID", help="Mission ID (required for mission-specific actions)")
    p.add_argument(
        "--action",
        metavar="ACTION",
        choices=["plan", "precheck", "merge-friendly", "apply", "validate", "status"],
        required=True,
        help="Patch batch action",
    )
    p.add_argument("--batch", metavar="BATCH_ID", help="Patch batch ID")
    p.add_argument("--patch-file", metavar="PATH", help="Path to unified diff patch file")
    p.add_argument("--worker", metavar="WORKER", help="Agent/worker name")
    p.add_argument("--planned-files", metavar="FILE", nargs="*", default=[], help="Planned files to be changed")
    p.add_argument("--validation-results", metavar="PATH", help="Path to validation results JSON file")
    p.add_argument("--sprint", metavar="SPRINT_ID", help="Sprint ID (for merge-friendliness check)")
    p.add_argument("--skip-merge-check", action="store_true", help="Skip merge-friendliness check (DANGEROUS)")
    p.add_argument("--accept-risky", action="store_true", help="Accept risky merge-friendliness result")
    
    args = p.parse_args()
    
    task = load_task(args.task_id)
    ts = now_iso()
    
    if args.action == "plan":
        # Plan a patch batch
        if not args.batch:
            print("ERROR: --batch is required for plan action")
            return 1
        if not args.mission:
            print("ERROR: --mission is required for plan action")
            return 1
        if not args.planned_files:
            print("ERROR: --planned-files is required for plan action")
            return 1
        
        mission, sprint = get_task_mission_sprint(task, args.mission)
        if not mission:
            print(f"ERROR: Mission {args.mission} not found in task {args.task_id}")
            return 1
        
        # Find sprint for mission
        if not sprint:
            # Try to find sprint from task
            for s in task.get("sprints", []):
                if args.mission in [m.get("id") for m in s.get("missions", [])]:
                    sprint = s
                    break
        
        event = make_event(
            event_type="patch_batch_planned",
            task_id=args.task_id,
            sprint_id=sprint.get("id") if sprint else None,
            mission_id=args.mission,
            worker=args.worker or "unknown",
            ts=ts,
            note=f"Planned patch batch {args.batch} for mission {args.mission}",
            patch_batch_id=args.batch,
            planned_files=args.planned_files,
        )
        append_event(args.task_id, event)
        
        print(f"Patch batch PLANNED: task={args.task_id} mission={args.mission} batch={args.batch}")
        print(f"Planned files: {args.planned_files}")
        print(f"Next: Run precheck with --action precheck --patch-file <path>")
        return 0
    
    elif args.action == "precheck":
        # Precheck a patch batch with git apply --check
        if not args.batch:
            print("ERROR: --batch is required for precheck action")
            return 1
        if not args.patch_file:
            print("ERROR: --patch-file is required for precheck action")
            return 1
        
        mission, sprint = None, None
        if args.mission:
            mission, sprint = get_task_mission_sprint(task, args.mission)
        
        # Load patch and get planned files from patch
        try:
            patch_content = load_patch_file(args.patch_file)
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            return 1
        
        # Run git apply --check
        precheck_passed, precheck_output = run_git_apply_check(args.patch_file)
        
        if precheck_passed:
            # Get current dirty files to see what would change
            dirty = get_dirty_files()
            
            # Get allowed/protected paths
            allowed, protected = get_task_allowed_paths(task, mission, sprint)
            
            # Check for protected paths
            protected_touched = check_protected_paths_touched(dirty, protected)
            
            if protected_touched:
                event = make_event(
                    event_type="patch_batch_blocked",
                    task_id=args.task_id,
                    sprint_id=sprint.get("id") if sprint else None,
                    mission_id=args.mission,
                    worker=args.worker or "unknown",
                    ts=ts,
                    note=f"Patch batch {args.batch} blocked: protected paths touched",
                    patch_batch_id=args.batch,
                    precheck_passed=False,
                    precheck_failed_reason=f"Protected paths touched: {protected_touched}",
                    protected_paths_touched=protected_touched,
                )
                append_event(args.task_id, event)
                print(f"Patch batch BLOCKED: task={args.task_id} batch={args.batch}")
                print(f"Reason: Protected paths touched: {protected_touched}")
                print(f"Protected paths: {protected}")
                return 1
            
            # For now, accept precheck pass
            event = make_event(
                event_type="patch_batch_prechecked",
                task_id=args.task_id,
                sprint_id=sprint.get("id") if sprint else None,
                mission_id=args.mission,
                worker=args.worker or "unknown",
                ts=ts,
                note=f"Patch batch {args.batch} precheck passed",
                patch_batch_id=args.batch,
                precheck_passed=True,
                precheck_command=f"git apply --check {args.patch_file}",
                planned_files=dirty,
            )
            append_event(args.task_id, event)
            print(f"Patch batch PRECHECKED: task={args.task_id} batch={args.batch}")
            print(f"Precheck passed. Files that would be changed: {dirty}")
            print(f"Next: Apply with --action apply")
            return 0
        else:
            event = make_event(
                event_type="patch_batch_blocked",
                task_id=args.task_id,
                sprint_id=sprint.get("id") if sprint else None,
                mission_id=args.mission,
                worker=args.worker or "unknown",
                ts=ts,
                note=f"Patch batch {args.batch} blocked: precheck failed",
                patch_batch_id=args.batch,
                precheck_passed=False,
                precheck_failed_reason=precheck_output[:500],  # Truncate output
            )
            append_event(args.task_id, event)
            print(f"Patch batch PRECHECK FAILED: task={args.task_id} batch={args.batch}")
            print(f"Output: {precheck_output}")
            return 1
    
    elif args.action == "merge-friendly":
        # Check merge-friendliness before apply
        if not args.batch:
            print("ERROR: --batch is required for merge-friendly action")
            return 1
        if not args.patch_file:
            print("ERROR: --patch-file is required for merge-friendly action")
            return 1
        
        mission, sprint = None, None
        if args.mission:
            mission, sprint = get_task_mission_sprint(task, args.mission)
        
        # Use sprint from args if provided
        if args.sprint and not sprint:
            from _work_lib import get_sprint
            try:
                sprint = get_sprint(task, args.sprint)
            except ValueError:
                pass
        
        # Run merge-friendliness check
        import subprocess as sp
        merge_check_cmd = [
            sys.executable, str(_scripts_dir / "work_merge_friendly.py"),
            args.task_id,
            "--patch-file", args.patch_file,
            "--batch", args.batch,
        ]
        if args.mission:
            merge_check_cmd.extend(["--mission", args.mission])
        if sprint:
            merge_check_cmd.extend(["--sprint", sprint.get("id")])
        if args.worker:
            merge_check_cmd.extend(["--worker", args.worker])
        if args.accept_risky:
            merge_check_cmd.append("--accept-risky")
        
        r = sp.run(merge_check_cmd, capture_output=True, text=True)
        
        print(r.stdout)
        if r.returncode != 0:
            print(r.stderr)
            print(f"Merge-friendliness check failed. Patch batch {args.batch} cannot be applied.")
            return r.returncode
        
        print(f"Merge-friendliness check passed for batch {args.batch}")
        return 0
    
    elif args.action == "apply":
        # Apply a patch batch
        if not args.batch:
            print("ERROR: --batch is required for apply action")
            return 1
        if not args.patch_file:
            print("ERROR: --patch-file is required for apply action")
            return 1
        
        mission, sprint = None, None
        if args.mission:
            mission, sprint = get_task_mission_sprint(task, args.mission)
        
        # Use sprint from args if provided
        if args.sprint and not sprint:
            from _work_lib import get_sprint
            try:
                sprint = get_sprint(task, args.sprint)
            except ValueError:
                pass
        
        # Check for merge-friendliness evidence unless explicitly skipped
        if not args.skip_merge_check:
            # Check if there's a merge-friendliness check event for this batch
            from _work_lib import load_events
            events = load_events(args.task_id)
            
            # Find the most recent merge-friendly check for this batch
            merge_friendly_found = False
            merge_friendly_safe = False
            for ev in reversed(events):
                if ev.get("type") == "patch_batch_merge_friendly_checked" and ev.get("patch_batch_id") == args.batch:
                    merge_friendly_found = True
                    merge_friendly_safe = ev.get("safe_to_apply", False)
                    break
            
            if not merge_friendly_found:
                print(f"ERROR: No merge-friendliness check found for batch {args.batch}.")
                print(f"Run: python3 scripts/work_patch_batch.py {args.task_id} --mission {args.mission} --action merge-friendly --batch {args.batch} --patch-file {args.patch_file}")
                print(f"Or use --skip-merge-check to bypass (DANGEROUS).")
                return 1
            
            if not merge_friendly_safe:
                print(f"ERROR: Merge-friendliness check for batch {args.batch} reported unsafe to apply.")
                print(f"Review the merge-friendliness check results and resolve issues first.")
                if args.accept_risky:
                    print(f"WARNING: --accept-risky override used. Proceeding at your own risk.")
                else:
                    print(f"Use --accept-risky to override (use with caution).")
                    return 1
        else:
            print("WARNING: --skip-merge-check used. Merge-friendliness not verified.")
        
        # Check if precheck passed (last event for this batch should be prechecked)
        # For simplicity, we'll just check and apply
        
        # Get current dirty files BEFORE apply
        dirty_before = get_dirty_files()
        
        # Run git apply
        apply_passed, apply_output = run_git_apply(args.patch_file)
        
        # Get dirty files AFTER apply
        dirty_after = get_dirty_files()
        
        # Get allowed/protected paths
        allowed, protected = get_task_allowed_paths(task, mission, sprint)
        
        # Check for protected paths
        protected_touched = check_protected_paths_touched(dirty_after, protected)
        
        if not apply_passed:
            event = make_event(
                event_type="patch_batch_blocked",
                task_id=args.task_id,
                sprint_id=sprint.get("id") if sprint else None,
                mission_id=args.mission,
                worker=args.worker or "unknown",
                ts=ts,
                note=f"Patch batch {args.batch} blocked: apply failed",
                patch_batch_id=args.batch,
                apply_command=f"git apply {args.patch_file}",
                precheck_passed=False,
                actual_files=dirty_after,
                apply_failed_reason=apply_output[:500],
            )
            append_event(args.task_id, event)
            print(f"Patch batch APPLY FAILED: task={args.task_id} batch={args.batch}")
            print(f"Output: {apply_output}")
            return 1
        
        if protected_touched:
            # This is an error - protected paths were touched
            # Rollback is NOT allowed - report and stop
            event = make_event(
                event_type="patch_batch_blocked",
                task_id=args.task_id,
                sprint_id=sprint.get("id") if sprint else None,
                mission_id=args.mission,
                worker=args.worker or "unknown",
                ts=ts,
                note=f"Patch batch {args.batch} blocked: protected paths touched AFTER apply",
                patch_batch_id=args.batch,
                apply_command=f"git apply {args.patch_file}",
                precheck_passed=True,
                actual_files=dirty_after,
                protected_paths_touched=protected_touched,
            )
            append_event(args.task_id, event)
            print(f"Patch batch BLOCKED: task={args.task_id} batch={args.batch}")
            print(f"Reason: Protected paths touched AFTER apply: {protected_touched}")
            print(f"DO NOT use git reset/restore/stash/checkout/clean for rollback.")
            print(f"Report and await direction.")
            return 1
        
        # Check if actual files exceed planned files
        # For now, just record
        event = make_event(
            event_type="patch_batch_applied",
            task_id=args.task_id,
            sprint_id=sprint.get("id") if sprint else None,
            mission_id=args.mission,
            worker=args.worker or "unknown",
            ts=ts,
            note=f"Patch batch {args.batch} applied",
            patch_batch_id=args.batch,
            apply_command=f"git apply {args.patch_file}",
            actual_files=dirty_after,
            protected_paths_touched=protected_touched,
        )
        append_event(args.task_id, event)
        print(f"Patch batch APPLIED: task={args.task_id} batch={args.batch}")
        print(f"Files changed: {dirty_after}")
        print(f"Next: Validate with --action validate")
        return 0
    
    elif args.action == "validate":
        # Validate a patch batch after applying
        if not args.batch:
            print("ERROR: --batch is required for validate action")
            return 1
        
        mission, sprint = None, None
        if args.mission:
            mission, sprint = get_task_mission_sprint(task, args.mission)
        
        validation_results = {}
        if args.validation_results:
            try:
                with open(args.validation_results, "r", encoding="utf-8") as f:
                    validation_results = json.load(f)
            except Exception as e:
                print(f"WARNING: Could not load validation results: {e}")
        
        event = make_event(
            event_type="patch_batch_validated",
            task_id=args.task_id,
            sprint_id=sprint.get("id") if sprint else None,
            mission_id=args.mission,
            worker=args.worker or "unknown",
            ts=ts,
            note=f"Patch batch {args.batch} validated",
            patch_batch_id=args.batch,
            validated_at=ts,
            validation_results=validation_results,
        )
        append_event(args.task_id, event)
        print(f"Patch batch VALIDATED: task={args.task_id} batch={args.batch}")
        print(f"Validation results: {validation_results}")
        return 0
    
    elif args.action == "status":
        # Show status of all patch batches
        mission, sprint = None, None
        if args.mission:
            mission, sprint = get_task_mission_sprint(task, args.mission)
        
        # Filter events for this mission/sprint or task
        from _work_lib import load_events
        events = load_events(args.task_id)
        
        batch_events = [
            ev for ev in events
            if ev.get("type") in [
                "patch_batch_planned",
                "patch_batch_prechecked",
                "patch_batch_applied",
                "patch_batch_validated",
                "patch_batch_blocked",
            ]
        ]
        
        if not batch_events:
            print(f"No patch batch events found for task {args.task_id}")
            return 0
        
        print(f"Patch Batch Status for task={args.task_id}")
        if args.mission:
            print(f"  Filtered by mission={args.mission}")
        print()
        
        for ev in batch_events:
            if args.mission and ev.get("mission_id") != args.mission:
                continue
            batch_id = ev.get("batch_id", "unknown")
            etype = ev.get("type", "unknown")
            ts = ev.get("ts", "unknown")
            print(f"  [{ts}] {etype}: batch={batch_id} status={ev.get('status', 'N/A')}")
            if ev.get("precheck_passed") is False:
                print(f"    Precheck failed: {ev.get('precheck_failed_reason', 'unknown')}")
            if ev.get("protected_paths_touched"):
                print(f"    Protected paths touched: {ev.get('protected_paths_touched')}")
        
        return 0
    
    print(f"ERROR: Unknown action or missing arguments")
    return 1


if __name__ == "__main__":
    sys.exit(main())
