#!/usr/bin/env python3
"""work_heartbeat.py — Append a heartbeat event for an active claim.

Usage:
    python3 scripts/work_heartbeat.py <task_id> \
        --mission <mission_id> --worker <name> [--note <text>] \
        [--allow-orphan] [--refresh-projection]

Heartbeats:
- Must include task_id, optional mission_id, worker, note, git_branch, git_head.
- Do NOT mutate task.json.
- Do NOT regenerate projection unless --refresh-projection is passed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    load_task, get_mission, load_events, append_event, make_event, compute_projection,
    projection_json_path, regenerate_findings_md,
)
import json


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work_heartbeat.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task_id")
    p.add_argument("--mission", metavar="MISSION_ID")
    p.add_argument("--worker", required=True, metavar="NAME")
    p.add_argument("--note", help="Progress note")
    p.add_argument("--allow-orphan", action="store_true",
                   help="Allow heartbeat even if no active claim exists for this worker/mission.")
    p.add_argument("--refresh-projection", action="store_true",
                   help="Also regenerate projection.json and notes after appending.")
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

    if not args.allow_orphan:
        events = load_events(args.task_id)
        active = False
        for ev in events:
            if ev.get("type") == "claim_started" and ev.get("worker") == args.worker:
                if ev.get("mission_id") == args.mission:
                    active = True
            elif ev.get("type") in ("claim_released", "handoff") and ev.get("worker") == args.worker:
                if ev.get("mission_id") == args.mission:
                    active = False
        if not active:
            print(
                f"ERROR: No active claim found for worker='{args.worker}' "
                f"mission='{args.mission or '(task-level)'}'. "
                "Use --allow-orphan to bypass.",
                file=sys.stderr,
            )
            return 1

    event = make_event(
        "heartbeat",
        args.task_id,
        args.worker,
        mission_id=args.mission,
        note=args.note,
    )
    append_event(args.task_id, event)
    print(f"Heartbeat recorded: task={args.task_id}"
          f"{' mission=' + args.mission if args.mission else ''}"
          f" worker={args.worker}")
    print(f"Event ID: {event['event_id']}")

    if args.refresh_projection:
        proj = compute_projection(args.task_id)
        proj_path = projection_json_path(args.task_id)
        persisted = {k: v for k, v in proj.items() if not k.startswith("_")}
        proj_path.write_text(json.dumps(persisted, indent=2, ensure_ascii=False) + "\n")
        regenerate_findings_md(args.task_id, proj)
        print(f"Projection refreshed: {proj_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
