#!/usr/bin/env python3
"""work_claim.py — Claim a task or mission before beginning work.

Usage:
    python3 scripts/work_claim.py <task_id> --mission <mission_id> --worker <name> \
        --paths <glob> [--paths <glob> ...] [--note <text>]

Appends a claim_started event to the ADR-local progress.jsonl.
Validates that claimed paths are within task/mission allowed_paths.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    load_task, get_mission, append_event, make_event,
    validate_paths_allowed,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work_claim.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task_id", help="ADR task ID (e.g. adr0004-runtime-streaming-consolidation)")
    p.add_argument("--mission", metavar="MISSION_ID", help="Mission to claim (optional; claim task-level if omitted)")
    p.add_argument("--worker", required=True, metavar="NAME", help="Agent or user name")
    p.add_argument("--paths", action="append", default=[], metavar="GLOB", help="Path(s) being claimed; may repeat")
    p.add_argument("--note", help="Optional note")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv or sys.argv[1:])

    try:
        task = load_task(args.task_id)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    allowed = task["allowed_paths"]
    protected = task["protected_paths"]

    if args.mission:
        try:
            mission = get_mission(task, args.mission)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        allowed = mission["allowed_paths"]

    errors = validate_paths_allowed(args.paths, allowed, protected)
    if errors:
        print("ERROR: Path validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1

    event = make_event(
        "claim_started",
        args.task_id,
        args.worker,
        mission_id=args.mission,
        note=args.note,
        paths=args.paths,
    )
    append_event(args.task_id, event)

    print(f"Claim started: task={args.task_id}"
          f"{' mission=' + args.mission if args.mission else ''}"
          f" worker={args.worker}")
    print(f"Event ID: {event['event_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
