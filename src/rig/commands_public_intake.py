"""CLI commands for public intake and funding operations.

Phase 1: Local-first, governed intake/funding spine.
- No payment processing
- No Stripe integration
- No hosted SaaS
- No authentication systems
- No background workers

Connectors are stubs that produce normalized packets.
Rig remains the authority.

Architecture (ADR 0005):
- IntakeRegistry: repo-scoped connector registry (inventory and routing only)
- IntakeStore: packet persistence only
- Connectors: own normalization, config validation
- Sync receipts: operational evidence, NOT moved to IntakeStore (future EvidenceDomain)
- Pledges: funding concern, NOT moved (future extraction)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

from rig.domain.public_intake import (
    PublicIntakePacket,
    FundingPledge,
    SponsorSummary,
    PublicSyncReceipt,
    ProposalFundingState,
    aggregate_funding_state,
    build_proposal_funding_enrichment,
    FUNDING_LIFECYCLE_STATES,
    PLACEHOLDER_UNFUNDED,
    PLACEHOLDER_ADVISORY_ONLY,
)
from rig.domain.intake_registry import IntakeRegistry
from rig.domain.intake_store import IntakeStore


def register(subparsers, helpers):
    """Register public intake and funding CLI commands."""
    
    # Parent command group
    intake_parser = subparsers.add_parser("public", help="Public intake and funding operations")
    intake_sub = intake_parser.add_subparsers(dest="intake_subcommand", required=True)
    
    # public intake list
    intake_list = intake_sub.add_parser("intake-list", help="List public intake packets")
    intake_list.add_argument("--connector", choices=["google_forms", "google_sheets", "github_issues"], default=None)
    intake_list.add_argument("--limit", type=int, default=10)
    intake_list.add_argument("--source-config", type=json.loads, default=None)
    intake_list.set_defaults(handler=lambda args: public_intake_list(helpers, args))
    
    # public intake import
    intake_import = intake_sub.add_parser("intake-import", help="Import public intake packets")
    intake_import.add_argument("--connector", choices=["google_forms", "google_sheets", "github_issues"], required=True)
    intake_import.add_argument("--dry-run", action="store_true", default=True)
    intake_import.add_argument("--limit", type=int, default=10)
    intake_import.add_argument("--since", type=str, default=None)
    intake_import.add_argument("--source-config", type=json.loads, default=None)
    intake_import.set_defaults(handler=lambda args: public_intake_import(helpers, args))
    
    # funding summary
    funding_summary = intake_sub.add_parser("funding-summary", help="Show funding summary for proposals")
    funding_summary.add_argument("--proposal-id", type=str, default=None)
    funding_summary.add_argument("--all", action="store_true", default=False)
    funding_summary.add_argument("--limit", type=int, default=10)
    funding_summary.set_defaults(handler=lambda args: funding_summary_cmd(helpers, args))
    
    # funding export
    funding_export = intake_sub.add_parser("funding-export", help="Export funding data")
    funding_export.add_argument("--proposal-id", type=str, default=None)
    funding_export.add_argument("--format", choices=["json", "csv"], default="json")
    funding_export.set_defaults(handler=lambda args: funding_export_cmd(helpers, args))


def _get_registry(repo_root: Path) -> IntakeRegistry:
    """Get the intake registry for a repo."""
    return IntakeRegistry.from_repo_root(repo_root)


def _get_store(repo_root: Path) -> IntakeStore:
    """Get the intake store for a repo."""
    return IntakeStore(repo_root)


# =============================================================================
# Pledge storage helpers (NOT part of IntakeStore - separate concern)
# These remain in CLI layer as future extraction candidates.
# =============================================================================


def _list_pledges_store_path(repo_root: Path) -> Path:
    """Path to local pledges store."""
    return repo_root / ".build" / "rig" / "public_intake" / "pledges"


def _load_pledges(repo_root: Path, limit: Optional[int] = None) -> list[FundingPledge]:
    """Load funding pledges from local store.
    
    Returns empty list if store doesn't exist.
    Read-only operation.
    """
    store_path = _list_pledges_store_path(repo_root)
    
    if not store_path.exists():
        return []
    
    pledges: list[FundingPledge] = []
    try:
        for pledge_file in sorted(store_path.glob("*.json")):
            try:
                with open(pledge_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pledges.append(FundingPledge(**data))
            except (OSError, IOError, json.JSONDecodeError, TypeError, KeyError):
                continue
            
            if limit and len(pledges) >= limit:
                break
    except (OSError, IOError):
        pass
    
    return pledges


# =============================================================================
# Sync receipt storage (NOT part of IntakeStore - operational evidence)
# Future EvidenceDomain candidate. Kept in CLI layer per ADR 0005.
# =============================================================================


def _save_sync_receipt(repo_root: Path, receipt: PublicSyncReceipt) -> Path:
    """Save a sync receipt to the filesystem for audit trail.
    
    Advisory only - does not make external systems authoritative.
    Persists the receipt so there's a durable record of the import operation.
    
    NOT moved to IntakeStore: sync receipts are operational evidence,
    not ingress persistence. Future EvidenceDomain (ADR 0007) may unify.
    
    Uses same path construction as IntakeStore for consistency,
    but does NOT import from IntakeStore to preserve separation of concerns.
    """
    # Path construction mirrors IntakeStore for consistency
    # but sync receipts remain a separate concern
    store_path = repo_root / ".build" / "rig" / "public_intake"
    receipt_dir = store_path / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    
    receipt_path = receipt_dir / f"{receipt.receipt_id}.json"
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump(receipt.to_dict(), f, indent=2, sort_keys=True)
    
    return receipt_path


# =============================================================================
# Command handlers
# =============================================================================


def public_intake_list(helpers, args):
    """List public intake packets from a connector or local store."""
    repo_root = helpers.repo_root
    registry = _get_registry(repo_root)
    store = _get_store(repo_root)
    
    if args.connector:
        # List from connector
        connector = registry.get_connector(args.connector, args.source_config)
        packets = connector.list_packets(limit=args.limit, source_config=args.source_config)
    else:
        # List from local store
        packets = store.load_packets(limit=args.limit)
    
    payload = {
        "connector": args.connector or "local",
        "count": len(packets),
        "limit": args.limit,
        "packets": [p.to_dict() for p in packets],
    }
    
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def public_intake_import(helpers, args):
    """Import public intake packets from a connector."""
    repo_root = helpers.repo_root
    registry = _get_registry(repo_root)
    store = _get_store(repo_root)
    
    connector = registry.get_connector(args.connector, args.source_config)
    
    result = connector.import_packets(
        source_config=args.source_config,
        since=args.since,
        dry_run=args.dry_run,
        limit=args.limit,
    )
    
    # In non-dry-run mode, save packets AND sync receipt to local store
    if not args.dry_run:
        for packet in result.packets:
            store.save_packet(packet, dry_run=False)
        
        # Sync receipts are operational evidence, not intake persistence
        # Kept separate per ADR 0005 design
        sync_receipt_path = _save_sync_receipt(repo_root, result.receipt)
    else:
        sync_receipt_path = None
    
    payload = {
        "connector": args.connector,
        "dry_run": args.dry_run,
        "result": {
            "operation": result.operation,
            "items_processed": result.receipt.items_processed,
            "items_created": result.receipt.items_created,
            "packet_ids": list(result.receipt.packet_ids),
            "status": result.receipt.status,
            "sync_receipt": result.receipt.to_dict(),
            "sync_receipt_path": str(sync_receipt_path) if sync_receipt_path else None,
        },
        "errors": list(result.errors),
        "packets": [p.to_dict() for p in result.packets],
    }
    
    if args.dry_run:
        payload["dry_run_note"] = "No packets were saved to local store. Use --no-dry-run to persist."
    
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def funding_summary_cmd(helpers, args):
    """Show funding summary for proposals."""
    repo_root = helpers.repo_root
    store = _get_store(repo_root)
    
    if args.all:
        # Load all and summarize
        pledges = _load_pledges(repo_root)
        packets = store.load_packets()
        
        # Group pledges by proposal
        pledge_map: dict[str, list[FundingPledge]] = {}
        for pledge in pledges:
            if pledge.proposal_id not in pledge_map:
                pledge_map[pledge.proposal_id] = []
            pledge_map[pledge.proposal_id].append(pledge)
        
        summaries = []
        for proposal_id, proposal_pledges in pledge_map.items():
            state = aggregate_funding_state(
                proposal_id=proposal_id,
                pledges=proposal_pledges,
                lifecycle_state="submitted",
            )
            summaries.append(state.to_dict())
        
        payload = {
            "total_proposals": len(summaries),
            "total_pledged_usd": sum(s.total_pledged_usd for s in summaries),
            "total_sponsors": sum(s.sponsor_count for s in summaries),
            "summaries": summaries,
        }
    elif args.proposal_id:
        # Single proposal
        pledges = [p for p in _load_pledges(repo_root) if p.proposal_id == args.proposal_id]
        packets = [p for p in store.load_packets() 
                   if p.normalizes_to == args.proposal_id or p.packet_id == args.proposal_id]
        
        enrichment = build_proposal_funding_enrichment(
            proposal_id=args.proposal_id,
            pledges=pledges,
            intake_packets=packets,
        )
        
        state = aggregate_funding_state(
            proposal_id=args.proposal_id,
            pledges=pledges,
            lifecycle_state="submitted",
        )
        
        payload = {
            "proposal_id": args.proposal_id,
            "enrichment": enrichment,
            "funding_state": state.to_dict(),
            "pledges": [p.to_dict() for p in pledges],
            "intake_packets": [p.to_dict() for p in packets],
        }
    else:
        # Default: show overall summary
        pledges = _load_pledges(repo_root)
        packets = store.load_packets()
        
        enrichment = build_proposal_funding_enrichment(
            proposal_id="all",
            pledges=pledges,
            intake_packets=packets,
        )
        
        payload = {
            "proposal_id": "all",
            "enrichment": enrichment,
            "pledge_count": len(pledges),
            "packet_count": len(packets),
            "advisory_only": True,
        }
    
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def funding_export_cmd(helpers, args):
    """Export funding data."""
    repo_root = helpers.repo_root
    
    if args.proposal_id:
        pledges = [p for p in _load_pledges(repo_root) if p.proposal_id == args.proposal_id]
    else:
        pledges = _load_pledges(repo_root)
    
    if args.format == "json":
        payload = {
            "format": "json",
            "pledge_count": len(pledges),
            "total_usd": sum(p.amount_usd for p in pledges if p.status == "active"),
            "pledges": [p.to_dict() for p in pledges],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.format == "csv":
        # Simple CSV export
        if not pledges:
            print("No pledges to export.")
            return 0
        
        # Header
        fields = ["pledge_id", "sponsor_id", "proposal_id", "amount_usd", "currency", "status", "pledged_at"]
        print(",".join(fields))
        
        # Data rows
        for p in pledges:
            row = [
                p.pledge_id,
                p.sponsor_id,
                p.proposal_id,
                str(p.amount_usd),
                p.currency,
                p.status,
                p.pledged_at,
            ]
            print(",".join(row))
    
    return 0
