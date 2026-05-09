#!/usr/bin/env python3
"""work_commit.py — Governed commit helper for ADR mission work.

Usage:
    python3 scripts/work_commit.py <task_id> --mission <id> --worker <name> \
        --message "Commit message" [--dry-run]

Behavior:
1. Runs work_status.py to regenerate projection.
2. Runs work_doctor.py — refuses if doctor fails.
3. Stages only files within task/mission allowed_paths.
4. Does NOT stage protected paths.
5. Prints the planned commit with trailers:
       Task: <task_id>
       Mission: <mission_id>
       Rig-Work-Doctor: passed
6. In --dry-run mode: prints plan without executing git add or git commit.
7. In apply mode: prints exact commands for the user to run (does not run git add/commit itself,
   because AGENTS.md requires explicit user authorization for those commands).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    load_task, get_mission, path_matches_any,
    repo_root,
)


def _run_script(script: str, task_id: str, *extra: str) -> int:
    scripts_dir = Path(__file__).resolve().parent
    r = subprocess.run(
        [sys.executable, str(scripts_dir / script), task_id, *extra],
        text=True,
    )
    return r.returncode


def _dirty_files_in_allowed(allowed: list[str], protected: list[str]) -> list[str]:
    r = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        text=True, capture_output=True,
    )
    if r.returncode != 0:
        return []
    result = []
    for line in r.stdout.splitlines():
        if len(line) >= 3:
            f = line[3:].strip()
            if path_matches_any(f, allowed) and not path_matches_any(f, protected):
                result.append(f)
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work_commit.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task_id")
    p.add_argument("--mission", metavar="MISSION_ID")
    p.add_argument("--worker", required=True, metavar="NAME")
    p.add_argument("--message", required=True, metavar="MSG", help="Commit message body.")
    p.add_argument("--dry-run", action="store_true", help="Show plan only; do not mutate.")
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
            allowed = mission["allowed_paths"]
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    # Step 1: Run work_status.py
    print("--- Running work_status.py ---")
    _run_script("work_status.py", args.task_id)

    # Step 2: Run work_doctor.py
    print("--- Running work_doctor.py ---")
    rc = _run_script("work_doctor.py", args.task_id)
    if rc != 0:
        print("\nERROR: work_doctor.py failed. Refusing to prepare commit.", file=sys.stderr)
        return 1

    # Step 3: Compute stageable files
    stageable = _dirty_files_in_allowed(allowed, protected)

    # Build commit message with trailers
    trailers = [
        f"Task: {args.task_id}",
    ]
    if args.mission:
        trailers.append(f"Mission: {args.mission}")
    trailers.append("Rig-Work-Doctor: passed")
    full_message = args.message.strip() + "\n\n" + "\n".join(trailers)

    print()
    print("=== Commit Plan ===")
    print(f"Task:    {args.task_id}")
    if args.mission:
        print(f"Mission: {args.mission}")
    print(f"Worker:  {args.worker}")
    print(f"Files to stage ({len(stageable)}):")
    for f in stageable:
        print(f"  {f}")
    print(f"\nCommit message:\n{full_message}")

    if args.dry_run:
        print("\nDRY RUN — no git commands executed.")
        return 0

    if not stageable:
        print("\nNothing to stage. Exiting without commit.", file=sys.stderr)
        return 1

    # Print user-run commands (AGENTS.md requires explicit user authorization for git add/commit)
    print("\nRun these commands to commit (authorization required per AGENTS.md §4):")
    print(f"  git add {' '.join(stageable)}")
    print(f"  git commit -m {repr(full_message)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
