#!/usr/bin/env python3
"""work_note.py — Append a note or out-of-scope finding event.

Usage:
    # Regular note:
    python3 scripts/work_note.py <task_id> --mission <id> --worker <name> --note "text"

    # Out-of-scope finding:
    python3 scripts/work_note.py <task_id> --mission <id> --worker <name> \
        --out-of-scope --note "Found X outside scope; not touching."

Out-of-scope findings:
- Are observations only.
- Must not expand current mission scope.
- Must not authorize edits outside allowed_paths.
- Will appear in status output and generated notes/out-of-scope-findings.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import load_task, get_mission, append_event, make_event


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work_note.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task_id")
    p.add_argument("--mission", metavar="MISSION_ID")
    p.add_argument("--worker", required=True, metavar="NAME")
    p.add_argument("--note", required=True, help="Note text")
    p.add_argument("--out-of-scope", action="store_true",
                   help="Record as an out_of_scope_finding instead of a plain note.")
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

    event_type = "out_of_scope_finding" if args.out_of_scope else "note"
    event = make_event(
        event_type,
        args.task_id,
        args.worker,
        mission_id=args.mission,
        note=args.note,
    )
    append_event(args.task_id, event)

    label = "Out-of-scope finding" if args.out_of_scope else "Note"
    print(f"{label} recorded: task={args.task_id}"
          f"{' mission=' + args.mission if args.mission else ''}"
          f" worker={args.worker}")
    if args.out_of_scope:
        print("Note: This finding is an observation only. It does not expand mission scope.")
    print(f"Event ID: {event['event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
