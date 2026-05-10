#!/usr/bin/env python3
"""work_status.py — Regenerate ADR-local projection and print task status.

Usage:
    python3 scripts/work_status.py <task_id>
    python3 scripts/work_status.py adr0004-runtime-streaming-consolidation

Regenerates:
    .rig/work/adr/<task_id>/projection.json
    .rig/work/adr/<task_id>/notes/out-of-scope-findings.md

Now supports:
    - Sprint Research status
    - Patch Batch status and summaries
    - Sprint-based mission organization
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    compute_projection,
    load_task,
    load_events,
    projection_json_path,
    regenerate_findings_md,
    HEARTBEAT_WARN_SECONDS,
    HEARTBEAT_STALE_SECONDS,
    seconds_since,
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
    proj_path.write_text(
        json.dumps(persisted, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

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

    # Sprint Research Status
    research_complete = projection.get("research_complete", True)
    sprints = projection.get("sprints", [])
    if sprints:
        print("Sprint Research Status:")
        for s in sprints:
            research_status = s.get("research_status", "not_started")
            status_icon = "✓" if research_status == "completed" else "○" if research_status == "in_progress" else "✗"
            print(f"  {status_icon} {s['id']}: {s['title']} -> {research_status}")
        if not research_complete:
            print("  ⚠  RESEARCH INCOMPLETE - Implementation cannot begin")
        print()

    # Patch Batch Summary
    patch_summary = projection.get("patch_batches_summary", {})
    if patch_summary:
        print("Patch Batch Summary:")
        print(f"  Planned:    {patch_summary.get('total_planned', 0)}")
        print(f"  Prechecked: {patch_summary.get('total_prechecked', 0)}")
        print(f"  Applied:   {patch_summary.get('total_applied', 0)}")
        print(f"  Validated: {patch_summary.get('total_validated', 0)}")
        print(f"  Blocked:   {patch_summary.get('total_blocked', 0)}")
        if patch_summary.get("blocked_reasons"):
            print(f"  Blocked reasons: {', '.join(patch_summary['blocked_reasons'])}")
        print()

    # Missions with Patch Batch info
    missions = projection.get("missions", [])
    print("Missions:")
    for m in missions:
        claim_info = f"  [claimed by {m['active_claim']}]" if m["active_claim"] else ""
        hb_info = ""
        if m["last_heartbeat"]:
            age = seconds_since(m["last_heartbeat"])
            hb_info = f"  (last hb: {int(age / 60)}m ago)"
        
        # Patch batch info for mission
        pb_info = ""
        patch_batches = m.get("patch_batches", [])
        if patch_batches:
            pb_statuses = [pb.get("status", "unknown") for pb in patch_batches]
            pb_info = f"  [patches: {len(patch_batches)}]"
            if any(s == "blocked" for s in pb_statuses):
                pb_info += " ⚠BLOCKED"
            # Check for merge-friendliness status
            merge_checked = sum(1 for pb in patch_batches if pb.get("merge_friendly_checked"))
            merge_safe = sum(1 for pb in patch_batches if pb.get("merge_friendly_safe") == True)
            if merge_checked > 0:
                pb_info += f" merge-{merge_safe}/{merge_checked}"
                if merge_safe < merge_checked:
                    pb_info += " ⚠UNSAFE"
        
        print(f"  {m['id']:<45} {m['status']:<18}{claim_info}{hb_info}{pb_info}")
    print()

    # Forge Readiness (from latest handoff with forge evidence)
    forge_readiness = projection.get("forge_readiness", {})
    if forge_readiness.get("forge_gates_checked") or forge_readiness.get("forge_promotion_ready") is not None:
        print("Forge Readiness:")
        gates_checked = forge_readiness.get("forge_gates_checked", False)
        print(f"  Gates checked:     {'Yes' if gates_checked else 'No'}")
        if gates_checked or forge_readiness.get("forge_promotion_ready") is not None:
            print(f"  Promotion ready:   {'Yes' if forge_readiness.get('forge_promotion_ready') else 'No'}")
            print(f"  Mode:              {forge_readiness.get('forge_mode', 'unknown')}")
            print(f"  Promotion mode:    {forge_readiness.get('promotion_mode', 'unknown')}")
            files_count = forge_readiness.get("reviewability_changed_file_count", 0)
            max_files = forge_readiness.get("reviewability_max_changed_files", 300)
            print(f"  Files changed:     {files_count} / {max_files}")
            over_budget = forge_readiness.get("reviewability_over_budget", False)
            print(f"  Over budget:       {'Yes' if over_budget else 'No'}")
        print()

    if projection["active_claims"]:
        print("Active claims:")
        for c in projection["active_claims"]:
            sprint_info = f"  sprint={c.get('sprint_id') or 'N/A'}" if c.get("sprint_id") else ""
            print(
                f"  worker={c['worker']}  mission={c.get('mission_id') or '(task-level)'}"
                f"  since={c['claimed_at']}{sprint_info}"
            )
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
    print(
        f"Findings notes written to: {proj_path.parent / 'notes' / 'out-of-scope-findings.md'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
