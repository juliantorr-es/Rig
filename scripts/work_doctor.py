#!/usr/bin/env python3
"""work_doctor.py — Validate ADR task, progress ledger, and work readiness.

Usage:
    python3 scripts/work_doctor.py <task_id> [--allow-large-task]

Validates:
- progress.jsonl is parseable.
- task.json has all required fields (sprints or missions).
- Events have required fields (event_id, ts, worker, type, task_id).
- mission_id values reference real missions.
- Claimed paths are within task/mission allowed_paths.
- Protected paths are not claimed.
- No more than 12 missions per sprint (warn at 7, fail at 12 unless --allow-large-task).
- Active claim heartbeat within 30m (warn) / 4h (stale).
- Commit readiness: active claims must have a handoff.
- Handoff has required fields: tests, dirty_files_after, completion_summary, out_of_scope_findings.
- Sprint Research: All sprints must have completed research before implementation.
- Patch Batches: Commit readiness fails if patch batch evidence is required but missing.
- Merge-friendliness: Commit readiness fails if patches applied without merge-friendliness evidence.
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
    load_task, load_events, get_mission, get_sprint,
    validate_paths_allowed, path_matches_any,
    HEARTBEAT_WARN_SECONDS, HEARTBEAT_STALE_SECONDS, seconds_since,
)

REQUIRED_TASK_FIELDS = [
    "id", "kind", "adr", "status", "priority", "allowed_paths", "protected_paths",
    "completion_criteria", "required_checks", "required_evidence",
]
# Note: "missions" is optional if using "sprints" (new structure)
# At least one of missions or sprints must be present

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

    # --- Check for missions or sprints ---
    missions = task.get("missions", [])
    sprints = task.get("sprints", [])
    
    if not missions and not sprints:
        errors.append("task.json must have either 'missions' or 'sprints' (or both for new structure)")
    
    # Get all mission IDs (from sprints or flat missions)
    mission_ids = set()
    for m in missions:
        mission_ids.add(m["id"])
    for s in sprints:
        for m in s.get("missions", []):
            mission_ids.add(m["id"])
    
    # --- Sprint Research Check (MANDATORY) ---
    if sprints:
        # Build sprint research status from events
        sprint_research_status: dict[str, str] = {}
        try:
            events = load_events(args.task_id)
        except ValueError:
            events = []
        
        for ev in events:
            etype = ev.get("type", "")
            sprint_id = ev.get("sprint_id", "")
            if etype == "sprint_research_started":
                sprint_research_status[sprint_id] = "in_progress"
            elif etype == "sprint_research_completed":
                sprint_research_status[sprint_id] = "completed"
            elif etype == "sprint_research_blocked":
                sprint_research_status[sprint_id] = "blocked"
        
        # Check each sprint has completed research if it has missions in progress
        for s in sprints:
            s_id = s.get("id", "")
            s_status = s.get("status", "not_started")
            s_research = sprint_research_status.get(s_id, "not_started")
            
            # If sprint has missions that are claimed/in_progress, research MUST be completed
            s_missions = s.get("missions", [])
            has_active_missions = any(
                m.get("status") in ("claimed", "in_progress")
                for m in s_missions
            )
            
            if has_active_missions and s_research != "completed":
                errors.append(
                    f"Sprint '{s_id}' has active missions but research is not completed "
                    f"(status: {s_research}). Research is MANDATORY before implementation."
                )
            elif s_research == "not_started" and s_status != "not_started":
                warnings.append(
                    f"Sprint '{s_id}' is {s_status} but research not started. "
                    "Research is mandatory before implementation."
                )

    # --- Mission count ---
    total_missions = len(mission_ids)
    if total_missions > 12 and not args.allow_large_task:
        errors.append(f"Too many missions: {total_missions} (max 12; use --allow-large-task to override)")
    elif total_missions > 7:
        warnings.append(f"Many missions: {total_missions} (warn threshold: 7)")

    # --- Mission path authority ---
    parent_allowed = task.get("allowed_paths", [])
    parent_protected = task.get("protected_paths", [])
    
    # Check both flat missions and sprint missions
    all_missions_list = list(missions)
    for s in sprints:
        all_missions_list.extend(s.get("missions", []))
    
    for m in all_missions_list:
        mid = m["id"]
        parent_allowed_for_mission = parent_allowed
        
        # Find the containing sprint to get its allowed_paths
        containing_sprint = None
        for s in sprints:
            if mid in [mm.get("id") for mm in s.get("missions", [])]:
                containing_sprint = s
                break
        
        # Use most specific allowed_paths: task -> sprint -> mission
        if containing_sprint:
            sprint_allowed = containing_sprint.get("allowed_paths", [])
            if sprint_allowed:
                parent_allowed_for_mission = sprint_allowed
        
        for mpath in m.get("allowed_paths", []):
            if not path_matches_any(mpath, parent_allowed_for_mission):
                errors.append(f"Mission '{mid}' allowed_path '{mpath}' exceeds parent allowed_paths")

    # --- Load events (if not already loaded) ---
    if 'events' not in locals():
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
                mission = next((m for m in all_missions_list if m["id"] == mid), None)
                if mission:
                    allowed = mission.get("allowed_paths", allowed)
            errs = validate_paths_allowed(paths, allowed, protected)
            for e in errs:
                errors.append(f"Claim by {worker}/{mid}: {e}")
            active_claims[ckey] = ev
        elif etype in ("claim_released", "handoff"):
            active_claims.pop(ckey, None)
        elif etype == "heartbeat":
            last_heartbeat[worker] = ev.get("ts", "")

    # --- Patch Batch Evidence Check ---
    # Collect patch batch events
    patch_batch_events = [
        ev for ev in events
        if ev.get("type") in [
            "patch_batch_planned",
            "patch_batch_prechecked",
            "patch_batch_applied",
            "patch_batch_validated",
            "patch_batch_blocked",
        ]
    ]
    
    # Find missions that have been claimed or are in progress
    active_missions = set()
    for ckey, claim in active_claims.items():
        mid = claim.get("mission_id")
        if mid:
            active_missions.add(mid)
    
    # Check that any active mission with patch batches has required evidence
    for pb_ev in patch_batch_events:
        pb_id = pb_ev.get("patch_batch_id", "")
        pb_type = pb_ev.get("type", "")
        mid = pb_ev.get("mission_id", "")
        
        if mid in active_missions:
            # Check if there's a planned batch without precheck
            if pb_type == "patch_batch_planned":
                has_precheck = any(
                    e.get("patch_batch_id") == pb_id and e.get("type") == "patch_batch_prechecked"
                    for e in patch_batch_events
                )
                if not has_precheck:
                    warnings.append(
                        f"Patch batch '{pb_id}' for mission '{mid}' was planned but not prechecked. "
                        "Run 'git apply --check' before applying."
                    )
            
            # Check if there's an applied batch without validation
            if pb_type == "patch_batch_applied":
                has_validation = any(
                    e.get("patch_batch_id") == pb_id and e.get("type") == "patch_batch_validated"
                    for e in patch_batch_events
                )
                if not has_validation:
                    warnings.append(
                        f"Patch batch '{pb_id}' for mission '{mid}' was applied but not validated. "
                        "Run validation after each batch."
                    )
            
            # Check if there's an applied batch without merge-friendliness check
            if pb_type == "patch_batch_applied":
                has_merge_check = any(
                    e.get("patch_batch_id") == pb_id and e.get("type") == "patch_batch_merge_friendly_checked"
                    for e in patch_batch_events
                )
                if not has_merge_check:
                    errors.append(
                        f"Patch batch '{pb_id}' for mission '{mid}' was applied without merge-friendliness check. "
                        "Merge-friendliness is required before applying patches. "
                        "Run 'python3 scripts/work_patch_batch.py --action merge-friendly' before apply."
                    )
                else:
                    # Check if merge-friendliness check passed
                    merge_check = next(
                        e for e in patch_batch_events
                        if e.get("patch_batch_id") == pb_id and e.get("type") == "patch_batch_merge_friendly_checked"
                    )
                    if not merge_check.get("safe_to_apply", False):
                        errors.append(
                            f"Patch batch '{pb_id}' for mission '{mid}' was applied but merge-friendliness "
                            f"check reported unsafe: {merge_check.get('result', 'unknown')}. "
                            f"Blocked reasons: {merge_check.get('blocked_reasons', [])}"
                        )
            
            # Check if precheck passed but merge-friendliness not checked yet
            if pb_type == "patch_batch_prechecked" and pb_ev.get("precheck_passed", False):
                has_merge_check = any(
                    e.get("patch_batch_id") == pb_id and e.get("type") == "patch_batch_merge_friendly_checked"
                    for e in patch_batch_events
                )
                if not has_merge_check:
                    warnings.append(
                        f"Patch batch '{pb_id}' for mission '{mid}' precheck passed but merge-friendliness "
                        "not yet checked. Run merge-friendliness check before apply."
                    )

    # --- Handoff quality check ---
    last_handoff: dict[str, dict] = {}
    for ev in events:
        if ev.get("type") == "handoff":
            key = f"{ev.get('worker')}:{ev.get('mission_id') or '_task_'}"
            last_handooff[key] = ev

    for key, hv in last_handoff.items():
        for field in REQUIRED_HANDOFF_FIELDS:
            if field not in hv:
                warnings.append(f"Handoff by {key} missing field: '{field}'")
        
        # --- Forge Gate Evidence Check ---
        # If handoff status is ready_for_review, verify forge gates were checked.
        status = hv.get("status", "")
        if status == "ready_for_review":
            forge_gates_checked = hv.get("forge_gates_checked", False)
            forge_evidence = hv.get("forge_evidence", {})
            forge_skip_explicit = hv.get("forge_gate_skip_explicit", False)
            
            if not forge_gates_checked and not forge_skip_explicit:
                errors.append(
                    f"Handoff by {key} has status 'ready_for_review' but forge gates were not checked. "
                    f"Use work_handoff.py (which runs forge gates automatically) or include --skip-forge-gates with explicit documentation."
                )
            elif forge_gates_checked and not forge_evidence.get("forge_promotion_ready", False):
                # Forge gates were checked but promotion is not ready
                blockers = forge_evidence.get("forge_promotion_blockers", [])
                blocker_codes = [b.get("code", "") for b in blockers]
                if blocker_codes:
                    errors.append(
                        f"Handoff by {key} has status 'ready_for_review' but forge promotion gates FAILED. "
                        f"Blockers: {', '.join(blocker_codes)}. "
                        f"Forge gates must pass for ready_for_review status."
                    )
                else:
                    errors.append(
                        f"Handoff by {key} has status 'ready_for_review' but forge promotion is not ready. "
                        f"Forge gates must pass for ready_for_review status."
                    )
            elif forge_skip_explicit:
                # User explicitly skipped - this is allowed but noted
                warnings.append(
                    f"Handoff by {key} has status 'ready_for_review' with --skip-forge-gates. "
                    f"Forge promotion gates were NOT checked. This bypasses important safety checks."
                )

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
    
    if sprints:
        print(f"Sprints: {len(sprints)}  Total missions: {total_missions}")
        if sprints:
            research_status = {}
            for ev in events:
                if ev.get("type") == "sprint_research_completed":
                    research_status[ev.get("sprint_id", "")] = "completed"
            incomplete = [
                s.get("id", "") for s in sprints
                if research_status.get(s.get("id", "")) != "completed"
            ]
            if incomplete:
                print(f"Research incomplete for: {', '.join(incomplete)}")
    else:
        print(f"Missions: {total_missions}")

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
