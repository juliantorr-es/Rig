# PublicOps Governance Architecture

## Purpose

This document describes the governed public operations (PublicOps) and funding intake architecture for Rig. It establishes the authority boundaries and connector model for Phase 1 of the intake/funding spine.

## Core Doctrine

**Rig remains the authority.** External systems (Google Forms, Google Sheets, GitHub Issues, etc.) are **connectors and presentation surfaces only**. They do not become source of truth.

- No payment processing
- No Stripe integration
- No hosted SaaS
- No authentication systems
- No background workers
- No persistent event streaming infra
- No queues
- No cloud-first architecture
- No granting merge rights
- No making external systems authoritative

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Rig Authority Boundary                       │
├─────────────────────────────────────────────────────────────────┤
│  Local-first, governed intake/funding substrate                  │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ Normalized        │  │ Canonical        │  │ Local        │ │
│  │ Domain Models     │  │ Resolvers        │  │ Store        │ │
│  │                  │  │                  │  │ (advisory)    │ │
│  │ - PublicIntakePacket │  │ - resolve_funding│  │              │ │
│  │ - FundingPledge   │  │   _state()       │  │ .build/rig/  │ │
│  │ - SponsorSummary   │  │ - resolve_public │  │ public_intake│ │
│  │ - PublicSyncReceipt│  │   _visibility()  │  │ /            │ │
│  │ - ProposalFundingState│ │- resolve_priority│ │              │ │
│  └──────────────────┘  │   _class()       │  └──────────────┘ │
│                          └──────────────────┘                    │
│                                    ▲                                  │
│                                    │                                  │
│                   ┌────────────────┼────────────────┐                 │
│                   │                │                │                 │
│                   ▼                ▼                ▼                 │
│          ┌───────────────┐ ┌──────────┐ ┌──────────────┐              │
│          │ Google Forms  │ │GitHub    │ │Google Sheets │              │
│          │ Connector     │ │Issues    │ │Connector     │              │
│          │ (STUB)        │ │Connector │ │(STUB)         │              │
│          │               │ │(STUB)    │ │              │              │
│          └───────────────┘ └──────────┘ └──────────────┘              │
│                   ▲                ▲                ▲                 │
│                   │                │                │                 │
│              External Systems (Connectors Only)                   │
└─────────────────────────────────────────────────────────────────┘
```

## governance Model

### Authority Flow

1. **External System** → Connector reads data (read-only)
2. **Connector** → Produces normalized `PublicIntakePacket`
3. **Connector** → Generates `PublicSyncReceipt` (advisory only)
4. **Rig** → Validates and accepts/rejects packets
5. **Rig** → Aggregates into `ProposalFundingState`
6. **Projection** → Emits funding state to UI
7. **Widget** → Renders funding summary (dumb)

### Connector Contract

All connectors MUST:

1. **Produce normalized packets** - Output `PublicIntakePacket` objects
2. **Never mutate authority state directly** - Write only to local intake store
3. **Generate sync receipts** - `PublicSyncReceipt` for every import operation
4. **Support dry-run mode** - `dry_run=True` means no persistence
5. **Be deterministic** - Same input produces same output
6. **Be side-effect free** - No external mutations beyond local store

### Local Store

Phase 1 uses local file-based storage:

- `.build/rig/public_intake/packets.jsonl` - Intake packets (JSONL)
- `.build/rig/public_intake/pledges/*.json` - Funding pledges

This is **advisory only** and does NOT make the local store authoritative. Rig's workspace/proposal system remains the source of truth.

## Normalized Domain Models

### PublicIntakePacket

normalized packet from external public intake sources. Includes:

- `packet_id` - Deterministic ID
- `source` - Connector identifier (google_forms, github_issues, google_sheets)
- `source_id` - External system ID
- `raw_payload` - Original external data (for audit)
- `title`, `description` - Normalized content
- `submitter_email`, `submitter_name` - Submitter info
- `priority_class` - Requested priority
- `requested_funding_usd` - Funding request
- `is_community_requested` - Community flag
- `lifecycle_state` - Current state in lifecycle
- `sync_receipt_id` - Reference to sync receipt

### FundingPledge

A funding pledge from a sponsor:

- `pledge_id` - Unique pledge identifier
- `sponsor_id` - Sponsor identifier
- `proposal_id` - Proposal being funded
- `amount_usd` - Pledge amount
- `currency` - Currency (default: USD)
- `status` - active, withdrawn, fulfilled
- `is_anonymous` - Anonymous sponsor flag

### SponsorSummary

Aggregated sponsor information:

- `sponsor_id`, `name`, `handle` - Sponsor identity
- `is_anonymous` - Anonymity flag
- `total_pledged_usd` - Total pledged across all proposals
- `pledge_count` - Number of pledges

### PublicSyncReceipt

Receipt for sync operations:

- `receipt_id` - Unique sync ID
- `operation` - Operation type (public_intake_import)
- `connector` - Connector name
- `items_processed`, `items_created`, `items_updated`, `items_skipped`
- `dry_run` - Whether this was a dry-run operation
- `status` - started, completed, failed
- `packet_ids` - IDs of processed packets

### ProposalFundingState

Aggregated funding state for a proposal:

- `proposal_id` - Proposal identifier
- `lifecycle_state` - Current lifecycle state
- `funding_status` - unfunded, partially_funded, funded
- `total_pledged_usd` - Total pledged for this proposal
- `sponsor_count` - Number of unique sponsors
- `public_visibility` - not_public, internal, public
- `priority_class` - Effective priority class
- `requested_acceleration_class` - Requested acceleration
- `is_community_requested` - Community flag

## Lifecycle States

### Canonical States

```
submitted     → Initial state when intake packet is received
triaged       → Packet has been reviewed and categorized
deduplicated  → Duplicate of existing proposal identified
accepted      → Proposal accepted for further consideration
rejected      → Proposal rejected
funding_open  → Funding round is open
funded        → Funding goal met
scheduled     → Implementation scheduled
implemented   → Implementation complete
validated     → Validation passed
released      → Released to users
closed        → Closed/archived
```

### State Transitions

```
submitted → triaged → accepted → funding_open → funded → scheduled → implemented → validated → released → closed
                       ↓
                  deduplicated → (merged with existing)
                       ↓
                     rejected → closed
```

## Canonical Resolvers

### resolve_funding_state()

Determines funding status from:

- `lifecycle_state` - Primary signal
- `total_pledged_usd` - Current pledge total
- `funding_goal_usd` - Target (if specified)

Returns: unfunded, partially_funded, funded, funding_open, funding_closed

### resolve_public_visibility()

Determines visibility from:

- `lifecycle_state` - Primary signal
- `is_public` - Direct flag
- `public_visibility_override` - Explicit override

Returns: not_public, internal, public

### resolve_priority_class()

Determines effective priority from:

- `requested_class` - Proposal's requested class
- `lifecycle_state` - Current state
- `is_community_requested` - Community flag
- `sponsor_count` - Number of sponsors

Returns: standard, elevated, high, urgent, unscheduled

## Proposal Enrichment

`build_proposal_funding_enrichment()` adds funding metadata to projections:

- `pledge_totals` - Total USD and count
- `sponsor_count` - Number of sponsors
- `funding_status` - Resolved funding state
- `public_visibility` - Resolved visibility
- `requested_acceleration_class` - Acceleration request
- `is_community_requested` - Community flag
- `advisory_only` - Always true for Phase 1

## Frontend Integration

### FundingSummaryCard Widget

A dumb widget that renders:

- Title: "Funding Summary"
- Funding status badge (severity based on state)
- Public visibility badge
- Pledge summary: "$X,XXX pledged (N pledges)" + sponsor count
- Priority/acceleration class badge
- Community requested indicator
- Details section: Total Pledged, Total Pledges, Sponsor Count, Funding Status, Visibility
- Advisory only note

### Projection Integration

The `FundingSummaryCard` widget can be included in `UIProjection.widgets` alongside `ProposalLifecycleConsole`. Future work: integrate funding data directly into the lifecycle console.

## CLI Commands

### rig public intake list

List public intake packets from a connector or local store.

```bash
rig public intake list --connector google_forms --limit 5
rig public intake list --limit 10
```

### rig public intake import --dry-run

Import packets from a connector. Dry-run mode is default.

```bash
rig public intake import --connector google_forms --dry-run --limit 5
rig public intake import --connector github_issues --dry-run --since 2026-01-01
```

### rig public funding summary

Show funding summary for proposals.

```bash
rig public funding summary --proposal-id PR-123
rig public funding summary --all
```

### rig public funding export

Export funding data in JSON or CSV format.

```bash
rig public funding export --format json
rig public funding export --proposal-id PR-123 --format csv
```

## Connector Stubs (Phase 1)

### GoogleFormsIntakeAdapter

- Generates sample Google Forms submission data
- Normalizes to `PublicIntakePacket`
- Supports dry-run

### GoogleSheetsSyncAdapter

- Generates sample Google Sheets row data
- Normalizes to `PublicIntakePacket`
- Supports dry-run

### GitHubIssueSyncAdapter

- Generates sample GitHub Issues data
- Parses labels for funding/priority metadata
- Normalizes to `PublicIntakePacket`
- Supports dry-run

## Placeholders (Explicit)

- `unfunded` - Proposal has no funding
- `anonymous` - Anonymous sponsor
- `not_public` - Not publicly visible
- `unscheduled` - No schedule assigned
- `advisory_only` - Metadata is not authoritative

## Acceptance Criteria

- [x] Deterministic projections
- [x] No new authority leaks
- [x] No external system becomes source of truth
- [x] No background workers
- [x] All new rendering uses projection data only
- [x] Dry-run import path works
- [x] compileall passes
- [x] Targeted pytest passes
- [x] Existing UI still boots cleanly

## Future Work

- Real connector implementations with API integration
- Local intake store as proper authority (requires governance promotion)
- Funding threshold automation
- Public visibility workflows
- Priority class promotion logic
- Deduplication heuristics
- connector registry and discovery
- Webhook-based Sync (still no background workers - use CLI polling)

## Non-Goals (Reiterated)

- No payment processing
- No Stripe integration
- No hosted SaaS
- No authentication systems
- No background workers
- No queues
- No cloud-first architecture
- No granting merge rights
- No making Google Workspace authoritative
