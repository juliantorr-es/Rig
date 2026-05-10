#!/usr/bin/env python3
"""work_blocked.py — Record a blocked event for a task or mission.

Usage:
    python3 scripts/work_blocked.py <task_id> --worker <name> --note "Reason for block." \
        [--mission <id>] [--out-of-scope-finding "text"] [...]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import load_task, get_mission, append_event, make_event


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work_blocked.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task_id")
    p.add_argument("--mission", metavar="MISSION_ID")
    p.add_argument("--worker", required=True, metavar="NAME")
    p.add_argument("--note", required=True, help="Reason for being blocked.")
    p.add_argument("--out-of-scope-finding", action="append", default=[],
                   dest="out_of_scope_findings", metavar="TEXT",
                   help="Out-of-scope finding to record alongside the blocked event. May repeat.")
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

    extra: dict = {}
    if args.out_of_scope_findings:
        extra["out_of_scope_findings"] = args.out_of_scope_findings

    event = make_event(
        "blocked",
        args.task_id,
        args.worker,
        mission_id=args.mission,
        note=args.note,
        **extra,
    )
    append_event(args.task_id, event)

    print(f"Blocked event recorded: task={args.task_id}"
          f"{' mission=' + args.mission if args.mission else ''}"
          f" worker={args.worker}")
    print(f"Reason: {args.note}")
    if args.out_of_scope_findings:
        print(f"Out-of-scope findings recorded: {len(args.out_of_scope_findings)}")
    print(f"Event ID: {event['event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
