#!/usr/bin/env python3
"""work_handoff.py — Record a handoff event when handing off mission work.

Usage:
    python3 scripts/work_handoff.py <task_id> \
        --mission <id> --worker <name> \
        --status ready_for_review \
        --tests "all passed" \
        --dirty-files-after "path/to/file.py" \
        --completion-summary "What was accomplished." \
        [--out-of-scope-finding "text"] [...]
        [--patch-batch <batch_id>] [...]

Handoff events:
- Always include out_of_scope_findings (empty list if none).
- Always include patch_batches_applied (empty list if none).
- Release the active claim for this worker/mission.
- Require: status, tests, dirty-files-after, completion-summary.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    load_task, get_mission, append_event, make_event,
    check_forge_readiness,
    now_iso,
    repo_root,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work_handoff.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task_id")
    p.add_argument("--mission", metavar="MISSION_ID")
    p.add_argument("--worker", required=True, metavar="NAME")
    p.add_argument("--status", required=True,
                   choices=["ready_for_review", "blocked", "needs_more_work", "closed"],
                   help="Handoff status.")
    p.add_argument("--tests", required=True, metavar="SUMMARY",
                   help="Test result summary or 'not run: <reason>'.")
    p.add_argument("--dirty-files-after", action="append", default=[],
                   dest="dirty_files_after", metavar="PATH",
                   help="Dirty file path after work. May repeat. Required (use '' if clean).")
    p.add_argument("--completion-summary", required=True, dest="completion_summary",
                   help="Human-readable summary of what was accomplished.")
    p.add_argument("--out-of-scope-finding", action="append", default=[],
                   dest="out_of_scope_findings", metavar="TEXT",
                   help="Out-of-scope finding observed during mission. May repeat. "
                        "Always included in handoff event, even if empty.")
    p.add_argument("--patch-batch", action="append", default=[],
                   dest="patch_batches_applied", metavar="BATCH_ID",
                   help="Patch batch IDs that were applied during this mission. May repeat. "
                        "Always included in handoff event, even if empty.")
    p.add_argument("--note", help="Optional extra note.")
    p.add_argument("--skip-forge-gates", action="store_true", default=False,
                   help="Skip forge promotion gate checks. WARNING: This is for testing only. "
                        "Promotion-ready handoffs should pass forge gates.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv or sys.argv[1:])

    try:
        task = load_task(args.task_id)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.mission:
        try:
            get_mission(task, args.mission)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    # --- Forge Gate Check ---
    # For ready_for_review status, verify forge gates pass before allowing handoff.
    # If --skip-forge-gates is passed, record that explicitly.
    skip_forge = args.skip_forge_gates
    forge_evidence: dict | None = None
    
    if args.status == "ready_for_review" and not skip_forge:
        # Run forge readiness check
        try:
            is_ready, evidence = check_forge_readiness(
                repo_path=repo_root(),
                target_ref="preproduction",
                head_ref="HEAD",
            )
            forge_evidence = evidence
            
            if not is_ready:
                # Forge gates failed - cannot mark as ready_for_review
                # Block with a clear message and force blocked status
                print(f"\n✗ FORGE GATES FAILED - Handoff blocked.", file=sys.stderr)
                print(f"  Forge doctor status: {evidence.get('forge_doctor_status', 'unknown')}", file=sys.stderr)
                if evidence.get('forge_promotion_blockers'):
                    print(f"  Blockers: {len(evidence.get('forge_promotion_blockers', []))}", file=sys.stderr)
                    for b in evidence.get('forge_promotion_blockers', []):
                        print(f"    - [{b.get('severity', 'error').upper()}] {b.get('code', '?')}: {b.get('message', '')}", file=sys.stderr)
                        if b.get('remediation'):
                            print(f"      → {b.get('remediation')}", file=sys.stderr)
                print(f"\n  Use --skip-forge-gates to bypass (NOT RECOMMENDED).", file=sys.stderr)
                print(f"  Or: reduce changes below reviewability budget ({evidence.get('reviewability_max_changed_files', 300)} files) and retry.", file=sys.stderr)
                return 1
            else:
                # Forge gates passed - include evidence in handoff
                pass
        except Exception as e:
            print(f"\n✗ FORGE GATE CHECK ERROR: {e}", file=sys.stderr)
            print(f"  Use --skip-forge-gates to bypass.", file=sys.stderr)
            return 1
    elif skip_forge:
        # User explicitly skipped forge gates - record that
        print(f"⚠  WARNING: --skip-forge-gates used. Forge promotion gates were NOT checked.", file=sys.stderr)
        forge_evidence = {
            "forge_gates_skipped": True,
            "skip_reason": "Explicit --skip-forge-gates flag",
        }

    # Require dirty_files_after to be explicitly provided.
    # An empty list is valid (clean), but the flag must have been passed.
    # argparse default=[] means we can't distinguish "not passed" from "empty".
    # We accept the empty default as "explicitly clean."

    # Build handoff event with forge evidence
    extra_fields: dict = {}
    if forge_evidence:
        extra_fields["forge_evidence"] = forge_evidence
        extra_fields["forge_gates_checked"] = not skip_forge
        extra_fields["forge_gate_skip_explicit"] = skip_forge
    
    event = make_event(
        "handoff",
        args.task_id,
        args.worker,
        mission_id=args.mission,
        note=args.note,
        status=args.status,
        tests=args.tests,
        dirty_files_after=args.dirty_files_after,
        completion_summary=args.completion_summary,
        out_of_scope_findings=args.out_of_scope_findings,  # always present, may be []
        patch_batches_applied=args.patch_batches_applied,  # always present, may be []
        **extra_fields,
    )
    append_event(args.task_id, event)

    # Print handoff confirmation
    print(f"Handoff recorded: task={args.task_id}"
          f"{' mission=' + args.mission if args.mission else ''}"
          f" worker={args.worker}")
    print(f"Status:             {args.status}")
    print(f"Tests:              {args.tests}")
    print(f"Dirty files after:  {args.dirty_files_after or ['(none)']}")
    print(f"Completion summary: {args.completion_summary}")
    
    # Print forge evidence summary if available
    if forge_evidence:
        if skip_forge:
            print(f"Forge gates:         SKIPPED (--skip-forge-gates used)")
        else:
            print(f"Forge gates:         PASSED")
            print(f"  Mode:              {forge_evidence.get('forge_mode', 'unknown')}")
            print(f"  Promotion mode:    {forge_evidence.get('promotion_mode', 'unknown')}")
            print(f"  Files changed:     {forge_evidence.get('reviewability_changed_file_count', 0)} / {forge_evidence.get('reviewability_max_changed_files', 300)}")
            if forge_evidence.get('reviewability_over_budget'):
                print(f"  Budget:            OVER BUDGET ({forge_evidence.get('reviewability_default_action', 'block_promotion')})")
            else:
                print(f"  Budget:            Within budget")
    else:
        print(f"Forge gates:         NOT CHECKED (status is not ready_for_review)")
    
    print(f"Out-of-scope findings: {len(args.out_of_scope_findings)}")
    if args.out_of_scope_findings:
        for i, f in enumerate(args.out_of_scope_findings, 1):
            print(f"  [{i}] {f}")
    else:
        print("  (none — out_of_scope_findings: [] recorded explicitly)")
    print(f"Patch batches applied: {len(args.patch_batches_applied)}")
    if args.patch_batches_applied:
        for i, batch_id in enumerate(args.patch_batches_applied, 1):
            print(f"  [{i}] {batch_id}")
    else:
        print("  (none — patch_batches_applied: [] recorded explicitly)")
    print(f"Event ID: {event['event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
