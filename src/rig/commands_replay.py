"""Replay CLI commands for Rig.

This module provides the CLI interface for governance replay & time-travel.
Implements Phase 5 CLI commands:
- rig replay workspace <id>
- rig replay receipts
- rig replay audit
- rig replay projection
- rig replay timeline

Options:
- --json
- --frame <n>
- --strict
- --summary
- --show-integrity
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

from rig_tools.core.io import read_json


def _emit(payload: dict[str, Any]) -> None:
    """Emit JSON output."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def _replay_workspace(
    repo_root: Path,
    workspace_id: str,
    *,
    json_output: bool = False,
    frame: Optional[int] = None,
    strict: bool = False,
    summary: bool = False,
    show_integrity: bool = False,
) -> int:
    """Replay workspace state from receipts and audit events.
    
    Args:
        repo_root: Repository root path
        workspace_id: The workspace ID to replay
        json_output: Output as JSON
        frame: Specific frame index to show (default: last)
        strict: Exit non-zero on errors
        summary: Show only summary
        show_integrity: Show integrity findings
        
    Returns:
        Exit code (0 on success)
    """
    from rig.domain.replay import (
        replay_workspace_from_fs,
        build_replay_projection,
        build_replay_projection_summary,
        ReplayState,
    )
    
    try:
        # Replay workspace from filesystem
        replay_result = replay_workspace_from_fs(repo_root, workspace_id)
        
        if json_output:
            if summary:
                projection_summary = build_replay_projection_summary(replay_result)
                _emit(projection_summary)
            elif frame is not None:
                projection = build_replay_projection(replay_result, frame_index=frame)
                _emit(projection)
            else:
                _emit(replay_result.to_dict())
            
            # Exit non-zero on errors
            if replay_result.has_conflicts or (strict and replay_result.has_findings):
                return 1
            return 0
        
        # Human-readable output
        print(f"Replay: Workspace {workspace_id}")
        print(f"  Replay ID: {replay_result.replay_id}")
        print(f"  State: {replay_result.state.value}")
        print(f"  Total frames: {len(replay_result.frames)}")
        
        if replay_result.frames:
            last_frame = replay_result.frames[-1]
            print(f"  Current status: {last_frame.workspace_status}")
            print(f"  Receipt chain: {len(last_frame.receipt_chain)} receipts")
            print(f"  Audit chain: {len(last_frame.audit_chain)} events")
            print(f"  Authoritative evidence: {last_frame.has_authoritative_evidence}")
            print(f"  Advisory evidence: {last_frame.has_advisory_only}")
            print(f"  Terminal: {last_frame.is_terminal}")
            if last_frame.is_terminal:
                print(f"  Terminal reason: {last_frame.terminal_reason}")
        
        # Show conflicts
        if replay_result.conflicts:
            print(f"\n  Conflicts: ({len(replay_result.conflicts)})")
            for conflict in replay_result.conflicts:
                print(f"    [{conflict.severity.value.upper()}] {conflict.title}: {conflict.message}")
        
        # Show findings if requested
        if show_integrity and replay_result.findings:
            print(f"\n  Integrity Findings: ({len(replay_result.findings)})")
            for finding in replay_result.findings:
                print(f"    [{finding.severity.value.upper()}] {finding.title}: {finding.message}")
        
        # Show specific frame if requested
        if frame is not None:
            if 0 <= frame < len(replay_result.frames):
                target_frame = replay_result.frames[frame]
                print(f"\n  Frame {frame}:")
                print(f"    Status: {target_frame.workspace_status}")
                print(f"    Events: {len(target_frame.events)}")
                print(f"    Receipt chain: {list(target_frame.receipt_chain)}")
                print(f"    Audit chain: {list(target_frame.audit_chain)}")
                print(f"    Hash: {target_frame.frame_hash}")
            else:
                print(f"\n  Error: Frame index {frame} out of range (0-{len(replay_result.frames) - 1})")
                if strict:
                    return 1
        
        # Show summary if requested
        if summary:
            projection_summary = build_replay_projection_summary(replay_result)
            print(f"\n  Summary:")
            print(f"    Total frames: {projection_summary['total_frames']}")
            print(f"    Total conflicts: {projection_summary['total_conflicts']}")
            print(f"    Total findings: {projection_summary['total_findings']}")
            print(f"    Current status: {projection_summary['current_status']}")
            print(f"    Terminal: {projection_summary['is_terminal']}")
            if projection_summary.get("terminal_reason"):
                print(f"    Terminal reason: {projection_summary['terminal_reason']}")
            print(f"    Authoritative evidence: {projection_summary['authoritative_evidence_available']}")
            
            # Show conflict types
            conflict_types = projection_summary.get("conflicts_by_type", {})
            if conflict_types:
                print(f"    Conflicts by type:")
                for ctype, count in conflict_types.items():
                    print(f"      {ctype}: {count}")
            
            # Show findings by severity
            findings_by_severity = projection_summary.get("findings_by_severity", {})
            if findings_by_severity and any(v > 0 for v in findings_by_severity.values()):
                print(f"    Findings by severity:")
                for severity, count in findings_by_severity.items():
                    if count > 0:
                        print(f"      {severity}: {count}")
            
            # Show flags
            flags = [
                ("impossible_transitions", "Impossible transitions"),
                ("missing_receipts", "Missing receipts"),
                ("missing_audit_events", "Missing audit events"),
                ("stale_references", "Stale references"),
                ("orphaned_events", "Orphaned events"),
                ("contradictions", "Contradictions"),
            ]
            for flag_key, label in flags:
                if projection_summary.get(flag_key, False):
                    print(f"    FLAG: {label} detected")
        
        # Exit non-zero on errors
        if replay_result.has_conflicts:
            return 1
        if strict and replay_result.has_findings:
            return 1
        
        return 0
        
    except Exception as e:
        if json_output:
            _emit({"status": "error", "error": str(e), "message": f"Failed to replay workspace {workspace_id}"})
        else:
            print(f"Error replaying workspace {workspace_id}: {e}", file=sys.stderr)
        return 1


def _replay_receipts(
    repo_root: Path,
    *,
    json_output: bool = False,
    workspace_id: Optional[str] = None,
    frame: Optional[int] = None,
    strict: bool = False,
    summary: bool = False,
    show_integrity: bool = False,
) -> int:
    """Replay receipt chain.
    
    Args:
        repo_root: Repository root path
        json_output: Output as JSON
        workspace_id: Optional workspace ID filter
        frame: Specific frame index (not applicable for receipt chain only)
        strict: Exit non-zero on errors
        summary: Show summary
        show_integrity: Show integrity findings
        
    Returns:
        Exit code
    """
    from rig.domain.replay import (
        replay_receipt_chain,
        sort_events_deterministic,
        load_replay_events_from_fs,
    )
    from rig.domain.receipt_envelope import read_receipt
    
    try:
        # Load all receipts
        receipt_dir = repo_root / ".build" / "rig" / "receipts"
        receipts = []
        
        if receipt_dir.exists():
            for receipt_file in sorted(receipt_dir.glob("*.json")):
                envelope = read_receipt(receipt_file)
                if envelope:
                    if workspace_id is None or envelope.subject.workspace_id == workspace_id:
                        receipts.append(envelope)
            
            # Check subdirectories
            for subdir in receipt_dir.iterdir():
                if subdir.is_dir():
                    for receipt_file in sorted(subdir.glob("*.json")):
                        envelope = read_receipt(receipt_file)
                        if envelope:
                            if workspace_id is None or envelope.subject.workspace_id == workspace_id:
                                receipts.append(envelope)
        
        # Build receipt chain
        receipt_events = replay_receipt_chain(receipts, workspace_id)
        sorted_events = sort_events_deterministic(list(receipt_events))
        
        if json_output:
            output = {
                "type": "receipt_chain_replay",
                "workspace_id": workspace_id or "all",
                "total_receipts": len(sorted_events),
                "receipt_ids": [e.source_id for e in sorted_events],
                "events": [e.to_dict() for e in sorted_events],
            }
            if workspace_id:
                output["workspace_id"] = workspace_id
            _emit(output)
            return 0
        
        # Human-readable output
        print(f"Receipt Chain Replay")
        if workspace_id:
            print(f"  Workspace: {workspace_id}")
        else:
            print(f"  All workspaces")
        print(f"  Total receipts: {len(sorted_events)}")
        
        if sorted_events:
            print(f"\n  Receipt chain:")
            for idx, event in enumerate(sorted_events):
                print(f"    {idx + 1}. {event.source_id} ({event.timestamp})")
                if event.advisory_only:
                    print(f"       [ADVISORY ONLY]")
                if event.authoritative:
                    print(f"       [AUTHORITATIVE]")
        
        return 0
        
    except Exception as e:
        if json_output:
            _emit({"status": "error", "error": str(e), "message": "Failed to replay receipts"})
        else:
            print(f"Error replaying receipts: {e}", file=sys.stderr)
        return 1


def _replay_audit(
    repo_root: Path,
    *,
    json_output: bool = False,
    workspace_id: Optional[str] = None,
    frame: Optional[int] = None,
    strict: bool = False,
    summary: bool = False,
    show_integrity: bool = False,
) -> int:
    """Replay audit chain.
    
    Args:
        repo_root: Repository root path
        json_output: Output as JSON
        workspace_id: Optional workspace ID filter
        frame: Specific frame index (not applicable)
        strict: Exit non-zero on errors
        summary: Show summary
        show_integrity: Show integrity findings
        
    Returns:
        Exit code
    """
    from rig.domain.replay import (
        replay_audit_chain,
        sort_events_deterministic,
        load_replay_events_from_fs,
    )
    from rig_tools.core.io import read_json
    
    try:
        # Load all audit events
        audit_dir = repo_root / ".build" / "rig" / "audit"
        audit_events_data = []
        
        if audit_dir.exists():
            for audit_file in sorted(audit_dir.glob("*.json")):
                data = read_json(audit_file)
                if isinstance(data, dict):
                    if workspace_id is None or data.get("workspace_id") == workspace_id:
                        audit_events_data.append(data)
        
        # Convert to ReplayEvents
        from rig.domain.replay import ReplayEvent, ReplayEventKind
        audit_events = []
        for idx, data in enumerate(audit_events_data):
            event = ReplayEvent(
                event_id=f"replay_audit_{data.get('event_id', f'audit_{idx}')}",
                event_kind=ReplayEventKind.AUDIT,
                source_id=data.get("event_id", f"audit_{idx}"),
                workspace_id=data.get("workspace_id"),
                timestamp=data.get("timestamp", ""),
                sequence_index=idx,
                data=data,
                authoritative=data.get("authoritative", True) and not data.get("advisory_only", False),
                advisory_only=data.get("advisory_only", False),
                hash="",
            )
            audit_events.append(event)
        
        sorted_events = sort_events_deterministic(audit_events)
        
        if json_output:
            output = {
                "type": "audit_chain_replay",
                "workspace_id": workspace_id or "all",
                "total_audit_events": len(sorted_events),
                "event_ids": [e.source_id for e in sorted_events],
                "events": [e.to_dict() for e in sorted_events],
            }
            if workspace_id:
                output["workspace_id"] = workspace_id
            _emit(output)
            return 0
        
        # Human-readable output
        print(f"Audit Chain Replay")
        if workspace_id:
            print(f"  Workspace: {workspace_id}")
        else:
            print(f"  All workspaces")
        print(f"  Total audit events: {len(sorted_events)}")
        
        if sorted_events:
            print(f"\n  Audit chain:")
            for idx, event in enumerate(sorted_events):
                action = event.data.get("action", "unknown")
                decision = event.data.get("decision", "unknown")
                print(f"    {idx + 1}. {event.source_id} ({event.timestamp})")
                print(f"       Action: {action}, Decision: {decision}")
                if event.advisory_only:
                    print(f"       [ADVISORY ONLY]")
        
        return 0
        
    except Exception as e:
        if json_output:
            _emit({"status": "error", "error": str(e), "message": "Failed to replay audit events"})
        else:
            print(f"Error replaying audit events: {e}", file=sys.stderr)
        return 1


def _replay_projection(
    repo_root: Path,
    *,
    json_output: bool = False,
    workspace_id: Optional[str] = None,
    frame: Optional[int] = None,
    strict: bool = False,
    summary: bool = True,  # Default to summary for projection
    show_integrity: bool = False,
) -> int:
    """Replay and build projection.
    
    Args:
        repo_root: Repository root path
        json_output: Output as JSON
        workspace_id: Workspace ID to replay (required for projection)
        frame: Specific frame index
        strict: Exit non-zero on errors
        summary: Show summary projection
        show_integrity: Show integrity findings in projection
        
    Returns:
        Exit code
    """
    from rig.domain.replay import (
        replay_workspace_from_fs,
        build_replay_projection,
        build_replay_projection_summary,
    )
    
    if not workspace_id:
        if json_output:
            _emit({"status": "error", "error": "workspace_id required", "message": "Please specify a workspace_id"})
        else:
            print("Error: workspace_id is required for projection replay", file=sys.stderr)
        return 1
    
    try:
        # Replay workspace
        replay_result = replay_workspace_from_fs(repo_root, workspace_id)
        
        if json_output:
            if summary:
                projection = build_replay_projection_summary(replay_result)
            else:
                projection = build_replay_projection(replay_result, frame_index=frame)
            _emit(projection)
            
            if replay_result.has_conflicts or (strict and replay_result.has_findings):
                return 1
            return 0
        
        # Human-readable output
        if summary:
            projection = build_replay_projection_summary(replay_result)
            print(f"Replay Projection Summary")
            print(f"  Workspace: {projection.get('workspace_id', 'N/A')}")
            print(f"  Total frames: {projection.get('total_frames', 0)}")
            print(f"  State: {projection.get('state', 'unknown')}")
            print(f"  Current status: {projection.get('current_status', 'N/A')}")
            print(f"  Terminal: {projection.get('is_terminal', False)}")
            
            if projection.get("terminal_reason"):
                print(f"  Terminal reason: {projection['terminal_reason']}")
            
            print(f"  Authoritative evidence: {projection.get('authoritative_evidence_available', False)}")
            print(f"  Advisory evidence: {projection.get('advisory_only_evidence_present', False)}")
            
            # Show flags
            flags = [
                ("has_impossible_transitions", "Impossible transitions"),
                ("has_missing_receipts", "Missing receipts"),
                ("has_missing_audit_events", "Missing audit events"),
                ("has_stale_references", "Stale references"),
                ("has_orphaned_events", "Orphaned events"),
                ("has_contradictions", "Contradictions"),
            ]
            for flag_key, label in flags:
                if projection.get(flag_key, False):
                    print(f"  FLAG: {label} detected")
            
            # Show severity breakdown
            findings_by_severity = projection.get("findings_by_severity", {})
            total_findings = sum(findings_by_severity.values())
            if total_findings > 0:
                print(f"  Findings: {total_findings}")
                for severity, count in findings_by_severity.items():
                    if count > 0:
                        print(f"    {severity}: {count}")
        else:
            projection = build_replay_projection(replay_result, frame_index=frame)
            frame_idx = projection.get("frame_index", -1)
            print(f"Replay Projection")
            print(f"  Workspace: {projection.get('workspace_id', 'N/A')}")
            print(f"  Frame: {frame_idx} / {projection.get('total_frames', 0)}")
            print(f"  Status: {projection.get('workspace_status', 'N/A')}")
            print(f"  Receipt chain: {len(projection.get('receipt_chain', []))} items")
            print(f"  Audit chain: {len(projection.get('audit_chain', []))} items")
            print(f"  Terminal: {projection.get('is_terminal', False)}")
            
            if projection.get("terminal_reason"):
                print(f"  Terminal reason: {projection['terminal_reason']}")
        
        if replay_result.has_conflicts:
            return 1
        if strict and replay_result.has_findings:
            return 1
        
        return 0
        
    except Exception as e:
        if json_output:
            _emit({"status": "error", "error": str(e), "message": f"Failed to build replay projection"})
        else:
            print(f"Error building replay projection: {e}", file=sys.stderr)
        return 1


def _replay_timeline(
    repo_root: Path,
    *,
    json_output: bool = False,
    workspace_id: Optional[str] = None,
    frame: Optional[int] = None,
    strict: bool = False,
    summary: bool = False,
    show_integrity: bool = True,  # Default to showing integrity in timeline
) -> int:
    """Replay timeline view.
    
    Shows the complete timeline of events with their relationships.
    
    Args:
        repo_root: Repository root path
        json_output: Output as JSON
        workspace_id: Optional workspace ID filter
        frame: Specific frame to show
        strict: Exit non-zero on errors
        summary: Show summary
        show_integrity: Show integrity information
        
    Returns:
        Exit code
    """
    from rig.domain.replay import (
        load_replay_events_from_fs,
        sort_events_deterministic,
        replay_workspace_from_fs,
    )
    
    try:
        if workspace_id:
            # Replay specific workspace
            replay_result = replay_workspace_from_fs(repo_root, workspace_id)
            events = list(replay_result.frames[-1].events) if replay_result.frames else []
            
            if json_output:
                output = {
                    "type": "timeline",
                    "workspace_id": workspace_id,
                    "total_frames": len(replay_result.frames),
                    "total_events": len(events),
                    "conflicts": [c.to_dict() for c in replay_result.conflicts],
                    "findings": [f.to_dict() for f in replay_result.findings] if show_integrity else [],
                    "events": [e.to_dict() for e in events],
                    "summary": replay_result.summary,
                }
                _emit(output)
                
                if replay_result.has_conflicts or (strict and replay_result.has_findings):
                    return 1
                return 0
            
            # Human-readable output
            print(f"Timeline: Workspace {workspace_id}")
            print(f"  Total frames: {len(replay_result.frames)}")
            print(f"  Total events: {len(events)}")
            print(f"  State: {replay_result.state.value}")
            
            if events:
                print(f"\n  Timeline:")
                for idx, event in enumerate(events):
                    kind = event.event_kind.value.upper()
                    auth = "AUTH" if event.authoritative and not event.advisory_only else "ADV" if event.advisory_only else "N/A"
                    print(f"    {idx + 1:3d}. [{kind:8s}] [{auth:4s}] {event.source_id[:40]}... ({event.timestamp[:19]})")
            
            if show_integrity:
                if replay_result.conflicts:
                    print(f"\n  Conflicts ({len(replay_result.conflicts)}):")
                    for conflict in replay_result.conflicts:
                        print(f"    [{conflict.severity.value.upper()}] {conflict.title}")
                
                if replay_result.findings:
                    print(f"\n  Findings ({len(replay_result.findings)}):")
                    for finding in replay_result.findings:
                        print(f"    [{finding.severity.value.upper()}] {finding.title}")
            
            if replay_result.has_conflicts:
                return 1
            if strict and replay_result.has_findings:
                return 1
            
            return 0
        
        else:
            # Show timeline for all workspaces
            all_events, all_findings = load_replay_events_from_fs(repo_root)
            sorted_events = sort_events_deterministic(list(all_events))
            
            # Group by workspace
            by_workspace: dict[str, list] = {}
            for event in sorted_events:
                ws_id = event.workspace_id or "global"
                if ws_id not in by_workspace:
                    by_workspace[ws_id] = []
                by_workspace[ws_id].append(event)
            
            if json_output:
                output = {
                    "type": "timeline_all",
                    "total_events": len(sorted_events),
                    "workspaces": {},
                }
                for ws_id, events in sorted(by_workspace.items()):
                    output["workspaces"][ws_id] = {
                        "event_count": len(events),
                        "events": [e.to_dict() for e in events],
                    }
                _emit(output)
                return 0
            
            # Human-readable output
            print(f"Timeline: All Workspaces")
            print(f"  Total events: {len(sorted_events)}")
            print(f"  Workspaces: {len(by_workspace)}")
            
            for ws_id in sorted(by_workspace.keys()):
                events = by_workspace[ws_id]
                print(f"\n  Workspace: {ws_id} ({len(events)} events)")
                for idx, event in enumerate(events[:10]):  # Show first 10
                    kind = event.event_kind.value.upper()
                    auth = "AUTH" if event.authoritative and not event.advisory_only else "ADV" if event.advisory_only else "N/A"
                    print(f"      {idx + 1:2d}. [{kind:8s}] [{auth:4s}] {event.source_id[:30]}... ({event.timestamp[:19]})")
                if len(events) > 10:
                    print(f"      ... and {len(events) - 10} more")
            
            return 0
        
    except Exception as e:
        if json_output:
            _emit({"status": "error", "error": str(e), "message": "Failed to build timeline"})
        else:
            print(f"Error building timeline: {e}", file=sys.stderr)
        return 1


def register(subparsers, helpers):
    """Register replay commands with CLI."""
    replay_parser = subparsers.add_parser(
        "replay",
        help="Governance replay & time-travel",
        description="Reconstruct workspace state from receipts + audit events. Determine replay integrity."
    )
    replay_parser.add_argument("--json", action="store_true", help="Output JSON")
    replay_parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings")
    replay_parser.add_argument("--show-integrity", action="store_true", help="Show integrity findings")
    
    replay_sub = replay_parser.add_subparsers(dest="subcmd", required=True)
    
    # replay workspace <id>
    workspace_parser = replay_sub.add_parser(
        "workspace",
        help="Replay workspace state from receipts and audit events"
    )
    workspace_parser.add_argument("workspace_id", help="Workspace ID to replay")
    workspace_parser.add_argument("--frame", type=int, default=None, help="Specific frame index")
    workspace_parser.add_argument("--summary", action="store_true", help="Show only summary")
    workspace_parser.set_defaults(
        handler=lambda args: _replay_workspace(
            helpers.repo_root,
            args.workspace_id,
            json_output=args.json,
            frame=args.frame,
            strict=args.strict,
            summary=args.summary,
            show_integrity=args.show_integrity,
        )
    )
    
    # replay receipts
    receipts_parser = replay_sub.add_parser(
        "receipts",
        help="Replay receipt chain"
    )
    receipts_parser.add_argument("--workspace-id", default=None, help="Filter by workspace ID")
    receipts_parser.add_argument("--frame", type=int, default=None)
    receipts_parser.add_argument("--summary", action="store_true")
    receipts_parser.set_defaults(
        handler=lambda args: _replay_receipts(
            helpers.repo_root,
            json_output=args.json,
            workspace_id=args.workspace_id,
            frame=args.frame,
            strict=args.strict,
            summary=args.summary,
            show_integrity=args.show_integrity,
        )
    )
    
    # replay audit
    audit_parser = replay_sub.add_parser(
        "audit",
        help="Replay audit event chain"
    )
    audit_parser.add_argument("--workspace-id", default=None, help="Filter by workspace ID")
    audit_parser.add_argument("--frame", type=int, default=None)
    audit_parser.add_argument("--summary", action="store_true")
    audit_parser.set_defaults(
        handler=lambda args: _replay_audit(
            helpers.repo_root,
            json_output=args.json,
            workspace_id=args.workspace_id,
            frame=args.frame,
            strict=args.strict,
            summary=args.summary,
            show_integrity=args.show_integrity,
        )
    )
    
    # replay projection
    projection_parser = replay_sub.add_parser(
        "projection",
        help="Build replay projection"
    )
    projection_parser.add_argument("workspace_id", help="Workspace ID for projection")
    projection_parser.add_argument("--frame", type=int, default=None, help="Specific frame index")
    projection_parser.add_argument("--summary", action="store_true", default=True, help="Show summary (default)")
    projection_parser.add_argument("--no-summary", action="store_true", dest="no_summary", help="Show full projection")
    projection_parser.set_defaults(
        handler=lambda args: _replay_projection(
            helpers.repo_root,
            json_output=args.json,
            workspace_id=args.workspace_id,
            frame=args.frame,
            strict=args.strict,
            summary=not getattr(args, 'no_summary', False),
            show_integrity=args.show_integrity,
        )
    )
    
    # replay timeline
    timeline_parser = replay_sub.add_parser(
        "timeline",
        help="Show replay timeline"
    )
    timeline_parser.add_argument("--workspace-id", default=None, help="Filter by workspace ID")
    timeline_parser.add_argument("--frame", type=int, default=None)
    timeline_parser.add_argument("--summary", action="store_true")
    timeline_parser.set_defaults(
        handler=lambda args: _replay_timeline(
            helpers.repo_root,
            json_output=args.json,
            workspace_id=args.workspace_id,
            frame=args.frame,
            strict=args.strict,
            summary=args.summary,
            show_integrity=args.show_integrity,
        )
    )
