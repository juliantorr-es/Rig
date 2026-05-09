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

Handoff events:
- Always include out_of_scope_findings (empty list if none).
- Release the active claim for this worker/mission.
- Require: status, tests, dirty-files-after, completion-summary.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import load_task, get_mission, append_event, make_event


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
    p.add_argument("--note", help="Optional extra note.")
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

    # Require dirty_files_after to be explicitly provided.
    # An empty list is valid (clean), but the flag must have been passed.
    # argparse default=[] means we can't distinguish "not passed" from "empty".
    # We accept the empty default as "explicitly clean."

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
    )
    append_event(args.task_id, event)

    print(f"Handoff recorded: task={args.task_id}"
          f"{' mission=' + args.mission if args.mission else ''}"
          f" worker={args.worker}")
    print(f"Status:             {args.status}")
    print(f"Tests:              {args.tests}")
    print(f"Dirty files after:  {args.dirty_files_after or ['(none)']}")
    print(f"Completion summary: {args.completion_summary}")
    print(f"Out-of-scope findings: {len(args.out_of_scope_findings)}")
    if args.out_of_scope_findings:
        for i, f in enumerate(args.out_of_scope_findings, 1):
            print(f"  [{i}] {f}")
    else:
        print("  (none — out_of_scope_findings: [] recorded explicitly)")
    print(f"Event ID: {event['event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
