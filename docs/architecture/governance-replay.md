# Governance Replay & Time-Travel Architecture

**Phase 5: Reconstructable Authority State**

## Overview

Rig Phase 5 implements **Governance Replay & Time-Travel**, enabling deterministic reconstruction of workspace state from canonical receipts and audit events alone. This provides forensic replay capabilities and integrity validation over the complete governance history.

**Core Doctrine:** Authority state is reconstructable evidence.

- A workspace state **must be** derivable from:
  - Canonical receipts (ReceiptEnvelope)
  - Canonical audit events (AuditEvent)
  - Deterministic replay rules

- Replay is **NOT** event sourcing hype
- Replay is **governance reconstruction + forensic replay**
- Rig remains the final authority on what changes are applied

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Governance Replay Layer                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  Receipts    │◄──►│ Audit Events │◄──►│ Replay Rules     │   │
│  │ (Canonical)  │    │ (Canonical)  │    │ (Deterministic)   │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│           ▲                  ▲                    ▲            │
│           │                  │                    │            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    Replay Engine                          │  │
│  │  - replay_workspace_state()                             │  │
│  │  - replay_workspace_lifecycle()                         │  │
│  │  - replay_receipt_chain()                               │  │
│  │  - replay_audit_chain()                                 │  │
│  │  - replay_workspace_from_fs()                           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                          ▲                                       │
│                          │                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    Replay Result                         │  │
│  │  - Frames (ReplayFrame)                                 │  │
│  │  - Snapshots (ReplaySnapshot)                           │  │
│  │  - Conflicts (ReplayConflict)                           │  │
│  │  - Findings (ReplayIntegrityFinding)                   │  │
│  │  - Decisions (ReplayDecision)                           │  │
│  │  - State (ReplayState)                                 │  │
│  └─────────────────────────────────────────────────────────┘  │
│                          ▲                                       │
│                          │                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                 Time-Travel Projections                   │  │
│  │  - build_replay_projection()                           │  │
│  │  - build_replay_projection_summary()                    │  │
│  │  - ReplayTimelineCard (frontend widget)                │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                            ▲   ▲   ▲
                            │   │   │
              ┌─────────────┼─────────────┼─────────────┐
              │             │             │             │
              ▼             ▼             ▼             ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  CLi Commands    │ │   Integrity      │ │   Doctor        │
│  rig replay ...  │ │   Validation     │ │   Checks        │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

## Canonical Replay Types

### ReplayEvent
Represents a single event in the replay sequence (from receipt or audit event).

**Fields:**
- `event_id`: Unique identifier
- `event_kind`: RECEIPT, AUDIT, WORKSPACE, VALIDATION, REVIEW, APPLY, GATE
- `source_id`: Original receipt_id or event_id
- `workspace_id`: Associated workspace
- `timestamp`: ISO 8601 timestamp
- `sequence_index`: Deterministic ordering index
- `data`: Full event data dict
- `authoritative`: Whether this event is authoritative
- `advisory_only`: Whether this event is advisory only
- `hash`: SHA256 hash for determinism verification

**Creation:**
```python
# From ReceiptEnvelope
event = ReplayEvent.from_receipt(envelope, sequence_index=0)

# From AuditEvent  
event = ReplayEvent.from_audit_event(audit_event, sequence_index=0)

# Placeholder for missing
event = ReplayEvent.placeholder(workspace_id="ws_123")
```

### ReplayFrame
Represents the state at a specific point in the replay sequence.

**Fields:**
- `frame_index`: Sequential frame number
- `events`: All ReplayEvents up to this frame
- `workspace_id`: Workspace identifier
- `workspace_status`: Current workspace status (planned, active, executed, ...)
- `status_history`: Complete history of status changes
- `receipt_chain`: Ordered receipt IDs
- `audit_chain`: Ordered audit event IDs
- `authority_state`: Dict tracking authoritative state changes
- `advisory_state`: Dict tracking advisory-only state changes
- `frame_hash`: SHA256 hash of frame state
- `previous_frame_hash`: Hash of previous frame for chain integrity
- `is_terminal`: Whether this is a terminal state
- `terminal_reason`: Reason for terminal state if applicable

**Properties:**
- `has_authoritative_evidence`: True if frame contains authoritative events
- `has_advisory_only`: True if frame contains advisory-only events

### ReplayCursor
Tracks position within replay sequence for navigation.

**Fields:**
- `current_frame_index`: Current position
- `total_frames`: Total frames available
- `workspace_id`: Associated workspace
- `can_go_back`: Can navigate to previous frame
- `can_go_forward`: Can navigate to next frame
- `current_frame_hash`: Hash of current frame

**Methods:**
- `go_back()`: Move to previous frame
- `go_forward()`: Move to next frame
- `go_to(index)`: Move to specific frame

### ReplayDecision
Represents authority decision at a specific replay frame.

**Decision Kinds:** ALLOWED, BLOCKED, PENDING, ADVISORY_ONLY, NOT_APPLICABLE, CONTRADICTION

**Factories:**
```python
ReplayDecision.allowed(decision_id, reason, frame_index, workspace_id)
ReplayDecision.blocked(decision_id, reason, frame_index, workspace_id)
ReplayDecision.create_advisory_only(decision_id, reason, frame_index, workspace_id)
ReplayDecision.contradiction(decision_id, reason, frame_index, workspace_id)
```

### ReplaySnapshot
Complete snapshot of replay state at a point in time.

**Fields:**
- `snapshot_id`: Unique snapshot identifier
- `workspace_id`: Associated workspace
- `frame`: The ReplayFrame at this snapshot
- `cursor`: ReplayCursor at this snapshot
- `decisions`: ReplayDecisions up to this point
- `integrity_findings`: ReplayIntegrityFindings at this point
- `authoritative_evidence_available`: Boolean flag
- `advisory_only_evidence_present`: Boolean flag

### ReplayConflict
Represents an issue preventing complete reconstruction.

**Conflict Types:**
- IMPOSSIBLE_TRANSITION: Invalid state transition detected
- MISSING_RECEIPT: Receipt referenced but not found
- MISSING_AUDIT_EVENT: Audit event referenced but not found
- STALE_RECEIPT_CHAIN: Receipt references stale paths
- ORPHANED_AUDIT_EVENT: Audit event with no corresponding receipt
- ADVISORY_ESCALATION: Advisory-only event attempting authoritative action
- CONTRADICTORY_GATE_DECISION: Conflicting gate decisions
- NON_DETERMINISTIC_ORDERING: Events not ordered deterministically
- AUTHORITY_MISMATCH: Authority classification mismatch

**Severity Levels:** INFO, WARNING, ERROR, CRITICAL

### ReplayIntegrityFinding
Single integrity finding from replay validation.

Similarly to IntegrityFinding but specific to replay concerns.

### ReplayResult
Complete result of a replay operation.

**Fields:**
- `replay_id`: Unique replay identifier
- `workspace_id`: Associated workspace
- `frames`: Tuple of all ReplayFrames
- `snapshots`: Tuple of all ReplaySnapshots
- `conflicts`: Tuple of ReplayConflicts
- `findings`: Tuple of ReplayIntegrityFindings
- `decisions`: Tuple of ReplayDecisions
- `start_frame_index`: First frame index
- `end_frame_index`: Last frame index
- `state`: Overall replay state (PENDING, PROCESSING, COMPLETE, FAILED, PARTIAL)
- `summary`: Dict with aggregated summary data

**Properties:**
- `is_complete`: State is COMPLETE
- `is_partial`: State is PARTIAL
- `has_conflicts`: Has one or more conflicts
- `has_findings`: Has one or more findings
- `has_authoritative_evidence`: Any frame has authoritative evidence

## Workspace State Reconstruction

### replay_workspace_state()
```python
frames = replay_workspace_state(
    workspace_id="ws_123",
    events=[...],           # List of ReplayEvent
    initial_status="planned"
)
```

Processes events in deterministic order and builds state at each frame.

**Behavior:**
1. Sorts events by timestamp, then event_id, then sequence_index
2. Filters to events for the specified workspace
3. For each event, extracts status changes
4. Validates transitions against ALLOWED_TRANSITIONS
5. Builds receipt_chain and audit_chain
6. Tracks authority and advisory state separately
7. Detects terminal states (blocked, applied)

### replay_workspace_lifecycle()
```python
result = replay_workspace_lifecycle(
    workspace_record={...},  # Workspace dict from filesystem
    receipts=[...],          # List of ReceiptEnvelope
    audit_events=[...]       # List of AuditEvent
)
```

Main entry point for workspace replay. Combines:
- Receipt chain reconstruction
- Audit chain reconstruction
- Orphaned event detection
- Unreferenced receipt detection
- Snapshot generation at each frame

### Valid Workspace Status & Transitions

**Valid Statuses:** planned, active, blocked, executed, validated, review_ready, applied

**Allowed Transitions:**
```
planned     -> active
active      -> executed, blocked
executed    -> validated, blocked
validated   -> review_ready, blocked
review_ready-> applied, blocked
blocked    -> (terminal)
applied    -> (terminal)
```

## Time-Travel Projections

### build_replay_projection()
```python
projection = build_replay_projection(
    replay_result=result,
    frame_index=None  # Default: last frame
)
```

Returns dict with:
- `type`: "ReplayProjection"
- `replay_id`, `workspace_id`, `frame_index`, `total_frames`
- `workspace_status`, `status_history`
- `receipt_chain`, `audit_chain`
- `authoritative_evidence_available`, `advisory_only_evidence_present`
- `is_terminal`, `terminal_reason`
- `has_conflicts`, `conflict_count`, `conflict_types`
- `finding_count`, `findings_by_severity`
- `state`, `authority_state`, `advisory_state`

### build_replay_projection_summary()
```python
summary = build_replay_projection_summary(replay_result)
```

Returns aggregated summary with:
- `type`: "ReplaySummary"
- All projection fields
- `conflicts_by_type`: Count by conflict type
- `findings_by_severity`: Count by severity
- Flags: `has_impossible_transitions`, `has_missing_receipts`, etc.

### Frontend Widget: ReplayTimelineCard

**Contract:**
- Input: Projection data from `build_replay_projection()`
- Render: Timeline with:
  - Frame index
  - Lifecycle transitions
  - Receipt chain continuity
  - Audit continuity
  - Integrity findings
  - Authoritative/advisory distinctions

**Requirements:**
- Dumb renderer only (no fetching, no mutation)
- `textContent` / `createElement` only
- Deterministic rendering
- No authority logic

## Replay Integrity Validation

### validate_replay_determinism()
```python
findings = validate_replay_determinism(result1, result2)
```

Compares two ReplayResults to ensure they produce identical results.
- Frame count must match
- Frame hashes must match

### validate_replay_consistency()
```python
findings = validate_replay_consistency(replay_result, workspace_record)
```

Validates ReplayResult against canonical workspace record:
- Final status must match
- Receipt chain must include all receipts from record

### validate_replay_projection_consistency()
```python
findings = validate_replay_projection_consistency(replay_result, projection_dict)
```

Validates projection matches replay result:
- Workspace ID must match
- Frame count must match
- State must match

### validate_replay_receipt_continuity()
```python
findings = validate_replay_receipt_continuity(
    receipt_chain=("r1", "r2", "r3"),
    all_receipt_ids={"r1", "r2", "r3", "r4"}
)
```

Validates receipt chain is complete and continuous:
- All receipts in chain must exist in all_receipt_ids
- Detects gaps in numeric sequences (if applicable)

## CLI Commands

### rig replay workspace <id>
Replay workspace state from receipts and audit events.

**Options:**
- `--json`: Output as JSON
- `--frame <n>`: Show specific frame
- `--strict`: Exit non-zero on warnings
- `--summary`: Show only summary
- `--show-integrity`: Show integrity findings

**Example:**
```bash
# Full replay with summary
rig replay workspace demo --summary

# JSON output for specific frame
rig replay --json workspace demo --frame 2

# Check integrity
rig replay workspace demo --show-integrity
```

### rig replay receipts
Replay receipt chain.

**Options:**
- `--workspace-id <id>`: Filter by workspace
- `--json`: Output as JSON
- `--summary`: Show summary

**Example:**
```bash
# All receipts
rig replay receipts

# Receipts for specific workspace
rig replay receipts --workspace-id demo

# JSON output
rig replay --json receipts --workspace-id demo
```

### rig replay audit
Replay audit event chain.

**Options:**
- `--workspace-id <id>`: Filter by workspace
- `--json`: Output as JSON
- `--summary`: Show summary

**Example:**
```bash
rig replay audit --workspace-id demo --json
```

### rig replay projection <workspace_id>
Build replay projection.

**Options:**
- `--frame <n>`: Specific frame index
- `--summary`: Show summary (default)
- `--no-summary`: Show full projection
- `--json`: Output as JSON
- `--show-integrity`: Include integrity findings

**Example:**
```bash
# Summary projection
rig replay projection demo

# Full projection for frame 3
rig replay projection demo --no-summary --frame 3

# JSON output
rig replay --json projection demo --summary
```

### rig replay timeline
Show complete timeline view.

**Options:**
- `--workspace-id <id>`: Filter by workspace (shows all if not specified)
- `--frame <n>`: Show specific frame
- `--summary`: Show summary
- `--json`: Output as JSON
- `--show-integrity`: Show integrity information

**Example:**
```bash
# Timeline for all workspaces
rig replay timeline

# Timeline for specific workspace with integrity
rig replay timeline --workspace-id demo --show-integrity

# JSON output
rig replay --json timeline --workspace-id demo
```

## Integrity Checks

Replay integrity validation fails loudly on:

### Contradictory Authority Chains
- Authoritative receipt claims impossible transition
- Advisory-only receipt blocks authoritative action
- Terminal state transitions attempted

### Impossible Replay States
- Status transitions not in ALLOWED_TRANSITIONS
- Receipt chain references non-existent receipts
- Audit events reference non-existent receipts

### Non-Deterministic Replay Ordering
- Same inputs produce different frame counts
- Same inputs produce different frame hashes

### Authority Escalation Through Replay
- Advisory-only actor creates authoritative receipt
- Connector creates authoritative receipt
- Public intake marked as authoritative

### Replay/Projection Divergence
- Projection workspace_id doesn't match replay
- Projection frame count doesn't match replay
- Projection state doesn't match replay

## Placeholder Semantics

All replay placeholders are explicit and normalized:

**Common Placeholders:**
- `unknown`: Generic unknown value
- `unavailable`: Data temporarily unavailable
- `not_created`: Data never created
- `not_run`: Operation never run
- `no_receipt`: No receipt available
- `advisory_only`: Explicitly advisory
- `not_authoritative`: Explicitly not authoritative

**Replay-Specific Placeholders:**
- `no_evidence`: No evidence available
- `stale_reference`: Reference points to stale data
- `orphaned`: Data with no parent reference
- `contradiction`: Contradictory state detected
- `gap`: Missing sequence element

## Key Guarantees

### 1. Deterministic Replay
- Same inputs → same ReplayResult
- Frame hashes are deterministic
- Event ordering is deterministic
- No hidden mutation during replay

### 2. Tolerates Incomplete History
- Works with missing receipts (detected as findings)
- Works with missing audit events (detected as findings)
- Works with partial workspace records
- Partial state is explicit (ReplayState.PARTIAL)

### 3. Explicit Findings
- All issues are surfaced as ReplayConflict or ReplayIntegrityFinding
- No silent failures
- No auto-repair
- Findings are part of ReplayResult

### 4. Authority Preservation
- Authoritative vs advisory distinctions maintained
- ReplayDecision preserves authority classification
- ReplayFrame tracks authority_state and advisory_state separately
- Projections expose authoritative_evidence_available flag

### 5. Projection Safety
- Projections are pure functions of replay state
- No frontend authority logic
- All projection data traceable to canonical receipts/audit events

## Testing

**Test File:** `tests/test_replay.py`

**Test Coverage:**
- All replay types are deterministic dataclasses
- All replay types are JSON-serializable
- Replay state reconstruction from receipts + audit events
- Replay projections work correctly
- Replay integrity validation detects issues
- Replay preserves authority/advisory distinctions
- Replay tolerates incomplete history
- Replay findings remain explicit

**Golden Tests:**
- Clean workspace lifecycle replay
- Advisory-only receipts
- Missing validation receipts
- Stale receipt references
- Orphaned audit chains
- Contradictory gate decisions
- Replay/projection mismatch

## Files Created/Modified

**New Files:**
- `src/rig/domain/replay.py` - Core replay types and functions
- `src/rig/commands_replay.py` - CLI commands
- `tests/test_replay.py` - Unit and golden tests
- `docs/architecture/governance-replay.md` - This document

**Modified Files:**
- `src/rig/cli/main.py` - Added commands_replay import and registration

## Future Enhancements (NOT in scope)

The following are explicitly **NOT** part of Phase 5:
- Distributed systems
- Hosted SaaS
- Networking
- Databases
- WebSocket/event streaming
- Queues
- Background workers
- CRDT systems
- Live collaborative editing
- Automatic repair/migration
- Destructive Git commands
- Staging
- Commits

## See Also

- [Workspace Authority and Auditability](workspace-authority-auditability.md)
- [Receipt Formalization](receipt-formalization.md)
- [Workspace Integrity Rules](workspace-integrity-rules.md)
- [Projection Contract Lockdown](projection-contract-lockdown.md)
