#!/usr/bin/env python3
"""work_status.py — Regenerate ADR-local projection and print task status.

Usage:
    python3 scripts/work_status.py <task_id>
    python3 scripts/work_status.py adr0004-runtime-streaming-consolidation

Regenerates:
    .rig/work/adr/<task_id>/projection.json
    .rig/work/adr/<task_id>/notes/out-of-scope-findings.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    compute_projection, load_task, load_events,
    projection_json_path, regenerate_findings_md,
    HEARTBEAT_WARN_SECONDS, HEARTBEAT_STALE_SECONDS, seconds_since,
)


def main(argv: list[str] | None = None) -> int:
    args = (argv or sys.argv)[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    task_id = args[0]

    try:
        task = load_task(task_id)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        events = load_events(task_id)
    except ValueError as exc:
        print(f"ERROR parsing progress.jsonl: {exc}", file=sys.stderr)
        return 1

    projection = compute_projection(task_id)

    # Write projection.json (strip internal key before persisting)
    proj_path = projection_json_path(task_id)
    proj_path.parent.mkdir(parents=True, exist_ok=True)
    persisted = {k: v for k, v in projection.items() if not k.startswith("_")}
    proj_path.write_text(json.dumps(persisted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Regenerate notes
    regenerate_findings_md(task_id, projection)

    # Print summary
    print(f"\n=== Work Status: {task_id} ===")
    print(f"ADR:         {task.get('adr', '')}")
    print(f"Status:      {task.get('status', '')}")
    print(f"Priority:    {task.get('priority', '')}")
    print(f"Events:      {len(events)}")
    print(f"Generated:   {projection['generated_at']}")
    print()

    print("Missions:")
    for m in projection["missions"]:
        claim_info = f"  [claimed by {m['active_claim']}]" if m["active_claim"] else ""
        hb_info = ""
        if m["last_heartbeat"]:
            age = seconds_since(m["last_heartbeat"])
            hb_info = f"  (last hb: {int(age/60)}m ago)"
        print(f"  {m['id']:<50} {m['status']:<18}{claim_info}{hb_info}")
    print()

    if projection["active_claims"]:
        print("Active claims:")
        for c in projection["active_claims"]:
            print(f"  worker={c['worker']}  mission={c.get('mission_id') or '(task-level)'}"
                  f"  since={c['claimed_at']}")
        print()

    if projection["stale_claims"]:
        print("⚠  STALE CLAIMS:")
        for c in projection["stale_claims"]:
            print(f"  {c}")
        print()

    if projection["conflicts"]:
        print("✗  CONFLICTS:")
        for conflict in projection["conflicts"]:
            print(f"  {conflict}")
        print()

    lhb = projection["last_heartbeat_by_worker"]
    if lhb:
        print("Last heartbeat by worker:")
        for w, ts in lhb.items():
            age = seconds_since(ts)
            warn = " ⚠ (>30m)" if age > HEARTBEAT_WARN_SECONDS else ""
            stale = " ✗ STALE" if age > HEARTBEAT_STALE_SECONDS else ""
            print(f"  {w}: {ts}{warn}{stale}")
        print()

    oosf_count = projection["out_of_scope_findings_count"]
    if oosf_count:
        print(f"Out-of-scope findings: {oosf_count}  (see notes/out-of-scope-findings.md)")
        print()

    print(f"Next safe action: {projection['next_safe_action']}")
    print(f"\nProjection written to: {proj_path}")
    print(f"Findings notes written to: {proj_path.parent / 'notes' / 'out-of-scope-findings.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
