# Funding Intake Spine Sprint

## Sprint Status

**Phase 1: COMPLETE** - Local-first, governed intake/funding substrate implemented.

## Sprint Name

Governed PublicOps + Funding Intake Spine

## Sprint Goal

Create a local-first, governed intake/funding substrate that allows:

- External feature proposals (via connectors)
- Proposal boosting/funding pledges
- Public intake synchronization
- Advisory-only monetization metadata

**Without** making external systems authoritative.

## Product Increment

At the end of Phase 1, Rig can:

1. Define normalized domain models for public intake and funding
2. Import packets from external connectors (stubs)
3. Resolve funding state, public visibility, and priority class deterministically
4. Enrich proposal lifecycle projections with funding metadata
5. Render funding summaries in the UI (via FundingSummaryCard widget)
6. List, import, and export via CLI commands

## Implementation Summary

### New Domain Models (`src/rig/domain/public_intake.py`)

**`PublicIntakePacket`** - Normalized packet from external sources:
- packet_id, source, source_id, raw_payload
- title, description, submitter info
- priority_class, requested_funding_usd, is_community_requested
- lifecycle_state, sync_receipt_id, dry_run

**`FundingPledge`** - Individual funding pledge:
- pledge_id, sponsor_id, proposal_id, amount_usd, currency
- pledged_at, status (active/withdrawn/fulfilled)
- message, is_anonymous

**`SponsorSummary`** - Aggregated sponsor data:
- sponsor_id, name, handle, avatar_url
- is_anonymous, total_pledged_usd, pledge_count
- first_pledge_at, last_pledge_at

**`PublicSyncReceipt`** - Sync operation receipt:
- receipt_id, operation, connector
- items_processed/created/updated/skipped
- dry_run, status, error_summary, packet_ids

**`ProposalFundingState`** - Aggregated funding state:
- proposal_id, lifecycle_state, funding_status
- total_pledged_usd, total_pledged_count, sponsor_count
- is_public, public_visibility
- priority_class, requested_acceleration_class
- is_community_requested

### Canonical Resolvers

**`resolve_funding_state()`**
- Input: lifecycle_state, total_pledged_usd, funding_goal_usd
- Output: unfunded, partially_funded, funded, funding_open, funding_closed

**`resolve_public_visibility()`**
- Input: lifecycle_state, is_public, public_visibility_override
- Output: not_public, internal, public

**`resolve_priority_class()`**
- Input: requested_class, lifecycle_state, is_community_requested, sponsor_count
- Output: standard, elevated, high, urgent, unscheduled

### Connectors (`src/rig/domain/connectors/`)

**`PublicIntakeConnector`** - Protocol defining connector contract:
- Must produce `PublicIntakePacket` objects
- Must generate `PublicSyncReceipt`
- Must support dry-run mode
- Must be deterministic and side-effect free

**`GoogleFormsIntakeAdapter`** - STUB connector for Google Forms
- Generates sample data
- Normalizes form responses to packets
- Full dry-run support

**`GoogleSheetsSyncAdapter`** - STUB connector for Google Sheets
- Generates sample data
- Normalizes sheet rows to packets
- Full dry-run support

**`GitHubIssueSyncAdapter`** - STUB connector for GitHub Issues
- Generates sample data
- Parses labels for funding/priority metadata
- Normalizes issues to packets
- Full dry-run support

### CLI Commands (`src/rig/commands_public_intake.py`)

**`rig public intake list`**
- List packets from connector or local store
- Options: --connector, --limit, --source-config

**`rig public intake import`**
- Import packets from connector
- Dry-run mode by default
- Options: --connector (required), --dry-run, --limit, --since, --source-config

**`rig public funding summary`**
- Show funding summary
- Options: --proposal-id, --all, --limit

**`rig public funding export`**
- Export funding data
- Options: --proposal-id, --format (json/csv)

### Frontend (`src/rig_tools/static/js/widgets/funding-summary-card.js`)

**`FundingSummaryCard`** widget:
- Dumb renderer (projection-only)
- No fetching, no authority logic
- Safe fallback rendering
- Uses textContent/createElement only

Displays:
- Funding status badge
- Public visibility badge
- Pledge summary line
- Priority/acceleration class badge
- Community requested indicator
- Details section (Total Pledged, Total Pledges, Sponsor Count, etc.)
- Advisory only note

### Projection Builder Integration

`build_proposal_funding_enrichment()` provides enrichment data that can be:
- Added to `ProposalLifecycleProjection` in future work
- Consumed by `FundingSummaryCard` widget independently

### Documentation

**`docs/architecture/publicops-governance.md`** - Full architecture documentation
- Core doctrine and authority boundaries
- Normalized domain models
- Lifecycle states and transitions
- Canonical resolvers
- Connector contract and stubs
- CLI commands
- Acceptance criteria

**`docs/sprints/funding-intake-spine.md`** - This document

## Acceptance Gates

- [x] Deterministic projections
- [x] No new authority leaks
- [x] No external system becomes source of truth
- [x] No background workers
- [x] All new rendering uses projection data only
- [x] Dry-run import path works
- [x] compileall passes
- [x] Targeted pytest passes
- [x] Existing UI still boots cleanly

## Validation Commands

```bash
# Syntax validation
python3.14 -m compileall -q src tests

# CLI help
python3.14 -m rig ui --help
python3.14 -m rig public --help
python3.14 -m rig public intake list --help
python3.14 -m rig public intake import --help
python3.14 -m rig public funding summary --help
python3.14 -m rig public funding export --help

# Dry-run test
python3.14 -m rig public intake import --connector google_forms --dry-run --limit 3
python3.14 -m rig public intake list --connector google_forms --limit 3
python3.14 -m rig public funding summary --all
python3.14 -m rig public funding export --format json

# UI boot test
python3.14 -m rig window open --dry-run
```

## Non-Goals (Phase 1)

- Payment processing
- Stripe integration
- Hosted SaaS
- Authentication systems
- Persistent event streaming infra
- Background workers
- Queues
- Cloud-first architecture
- Granting merge rights
- Making Google Workspace authoritative
- Real API implementations for connectors

## Future Work

### Phase 2 (Not Implemented)

- Real connector implementations with actual API calls
- Local intake store promoted to advisory authority
- Funding threshold automation and alerts
- Public visibility workflows with governance
- Priority class promotion logic
- Deduplication heuristics
- Connector registry and auto-discovery
- Webhook-based sync (CLI-polling based to avoid background workers)

### Phase 3 (Not Planned)

- Integration with actual payment processing (requires governance decision)
- Hosted components (requires governance decision)
- Full proposal-to-workspace workflow integration

## Design Decisions

### Why Stubs?

Phase 1 intentionally uses stub connectors because:
1. Real API integration requires credentials and OAuth flows
2. External system APIs may change
3. Connectors should be tested with real data before production use
4. Rig remains the authority regardless of connector implementation
5. Stubs demonstrate the interface and can be replaced incrementally

### Why Local-first?

- No cloud dependency
- No authentication requirements for Phase 1
- All state is inspectable on disk
- Easy to debug and audit
- Can be promoted to shared storage later

### Why Advisory Only?

- Phase 1 is infrastructure only
- Authority promotion requires governance decision
- Prevents accidental authority leaks
- Allows gradual adoption

### Why No Background Workers?

- Keeps architecture simple
- Avoids operational complexity
- CLI polling is sufficient for Phase 1
- Can be added later if needed

## Task Breakdown

### Done

1. ✅ Normalized domain models
2. ✅ Lifecycle states
3. ✅ Canonical resolvers
4. ✅ Proposal enrichment
5. ✅ Explicit placeholders
6. ✅ FundingSummaryCard widget
7. ✅ Connector abstractions (stubs)
8. ✅ CLI commands
9. ✅ Architecture documentation
10. ✅ Sprint documentation

### Validation

11. ✅ compileall passes
12. ✅ CLI commands work
13. ✅ Dry-run mode verified
14. ✅ Widget registry updated
15. ✅ Existing UI still boots

## Related Documents

- [PublicOps Governance Architecture](../architecture/publicops-governance.md)
- [Proposal Lifecycle Console](../sprints/proposal-lifecycle-console.md)
- [Projection Renderer Frontend](../architecture/projection-renderer-frontend.md)
- [Workspace Status Summary](../architecture/workspace-status-summary.md)
