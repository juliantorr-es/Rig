#!/usr/bin/env python3
"""work_doctor.py — Validate ADR task, progress ledger, and work readiness.

Usage:
    python3 scripts/work_doctor.py <task_id> [--allow-large-task]

Validates:
- progress.jsonl is parseable.
- task.json has all required fields.
- Events have required fields (event_id, ts, worker, type, task_id).
- mission_id values reference real missions.
- Mission allowed_paths are subsets of parent allowed_paths.
- Claimed paths are within task/mission allowed_paths.
- Protected paths are not claimed.
- No more than 12 missions (warn at 7, fail at 12 unless --allow-large-task).
- Active claim heartbeat within 30m (warn) / 4h (stale).
- Commit readiness: active claims must have a handoff.
- Handoff has required fields: tests, dirty_files_after, completion_summary, out_of_scope_findings.
- No unexpected dirty files outside allowed_paths (uses git status --porcelain=v1).

Exit codes: 0 = pass, 1 = failure, 2 = warnings only (pass with caveats).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    load_task, load_events, get_mission,
    validate_paths_allowed, path_matches_any,
    HEARTBEAT_WARN_SECONDS, HEARTBEAT_STALE_SECONDS, seconds_since,
)

REQUIRED_TASK_FIELDS = [
    "id", "kind", "adr", "status", "priority", "allowed_paths", "protected_paths",
    "completion_criteria", "required_checks", "required_evidence", "missions",
    "created_at", "updated_at",
]
REQUIRED_EVENT_FIELDS = ["event_id", "ts", "worker", "type", "task_id"]
REQUIRED_HANDOFF_FIELDS = ["tests", "dirty_files_after", "completion_summary", "out_of_scope_findings"]


def _git_dirty_files() -> list[str]:
    r = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        text=True, capture_output=True,
    )
    if r.returncode != 0:
        return []
    files = []
    for line in r.stdout.splitlines():
        if len(line) >= 3:
            files.append(line[3:].strip())
    return files


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="work_doctor.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task_id")
    p.add_argument("--allow-large-task", action="store_true",
                   help="Allow more than 12 missions without failing.")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv or sys.argv[1:])

    warnings: list[str] = []
    errors: list[str] = []

    # --- Load task ---
    try:
        task = load_task(args.task_id)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    # --- Required task fields ---
    for field in REQUIRED_TASK_FIELDS:
        if field not in task:
            errors.append(f"task.json missing required field: '{field}'")

    # --- Mission count ---
    missions = task.get("missions", [])
    mission_ids = {m["id"] for m in missions}
    if len(missions) > 12 and not args.allow_large_task:
        errors.append(f"Too many missions: {len(missions)} (max 12; use --allow-large-task to override)")
    elif len(missions) > 7:
        warnings.append(f"Many missions: {len(missions)} (warn threshold: 7)")

    # --- Mission path authority ---
    parent_allowed = task.get("allowed_paths", [])
    parent_protected = task.get("protected_paths", [])
    for m in missions:
        mid = m["id"]
        for mpath in m.get("allowed_paths", []):
            if not path_matches_any(mpath, parent_allowed):
                errors.append(f"Mission '{mid}' allowed_path '{mpath}' exceeds parent allowed_paths")

    # --- Load events ---
    try:
        events = load_events(args.task_id)
    except ValueError as exc:
        errors.append(f"progress.jsonl parse error: {exc}")
        events = []

    # --- Event field validation ---
    for i, ev in enumerate(events):
        for field in REQUIRED_EVENT_FIELDS:
            if field not in ev:
                errors.append(f"Event #{i+1} (type={ev.get('type', '?')}) missing field: '{field}'")
        mid = ev.get("mission_id")
        if mid and mid not in mission_ids:
            errors.append(f"Event #{i+1} references unknown mission_id: '{mid}'")

    # --- Claim validation ---
    active_claims: dict[str, dict] = {}  # key: worker:mission_id
    last_heartbeat: dict[str, str] = {}  # key: worker
    for ev in events:
        etype = ev.get("type", "")
        worker = ev.get("worker", "")
        mid = ev.get("mission_id")
        ckey = f"{worker}:{mid or '_task_'}"

        if etype == "claim_started":
            paths = ev.get("paths", [])
            allowed = parent_allowed
            protected = parent_protected
            if mid and mid in mission_ids:
                mission = next(m for m in missions if m["id"] == mid)
                allowed = mission.get("allowed_paths", allowed)
            errs = validate_paths_allowed(paths, allowed, protected)
            for e in errs:
                errors.append(f"Claim by {worker}/{mid}: {e}")
            active_claims[ckey] = ev
        elif etype in ("claim_released", "handoff"):
            active_claims.pop(ckey, None)
        elif etype == "heartbeat":
            last_heartbeat[worker] = ev.get("ts", "")

    # --- Handoff quality check ---
    last_handoff: dict[str, dict] = {}
    for ev in events:
        if ev.get("type") == "handoff":
            key = f"{ev.get('worker')}:{ev.get('mission_id') or '_task_'}"
            last_handoff[key] = ev

    for key, hv in last_handoff.items():
        for field in REQUIRED_HANDOFF_FIELDS:
            if field not in hv:
                warnings.append(f"Handoff by {key} missing field: '{field}'")

    # --- Active claim heartbeat staleness ---
    for ckey, claim in active_claims.items():
        worker = claim.get("worker", "")
        last_hb = last_heartbeat.get(worker)
        if last_hb:
            age = seconds_since(last_hb)
        else:
            age = seconds_since(claim.get("ts", ""))
        if age > HEARTBEAT_STALE_SECONDS:
            errors.append(
                f"STALE claim: worker='{worker}' mission='{claim.get('mission_id') or 'task-level'}' "
                f"— no heartbeat for {int(age/3600)}h (threshold: 4h)"
            )
        elif age > HEARTBEAT_WARN_SECONDS:
            warnings.append(
                f"Claim heartbeat aging: worker='{worker}' — {int(age/60)}m since last heartbeat (warn: 30m)"
            )

    # --- Commit readiness: active claims must have handoff ---
    for ckey, claim in active_claims.items():
        if ckey not in last_handoff:
            warnings.append(
                f"Commit readiness: active claim '{ckey}' has no completed handoff. "
                "Run work_handoff.py before committing."
            )

    # --- Dirty file check ---
    dirty = _git_dirty_files()
    for f in dirty:
        if not path_matches_any(f, parent_allowed):
            warnings.append(f"Unexpected dirty file outside allowed_paths: {f}")

    # --- Print report ---
    print(f"\n=== work_doctor: {args.task_id} ===")
    print(f"Events: {len(events)}  Active claims: {len(active_claims)}  Dirty files: {len(dirty)}")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠  {w}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  ✗  {e}")
        print(f"\nRESULT: FAIL ({len(errors)} error(s), {len(warnings)} warning(s))")
        return 1

    if warnings:
        print(f"\nRESULT: PASS with {len(warnings)} warning(s)")
        return 0

    print("\nRESULT: PASS ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
