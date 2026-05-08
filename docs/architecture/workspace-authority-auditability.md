# Workspace Authority & Auditability Architecture

## Overview

This document describes the architecture for Rig's workspace authority and auditability spine. It establishes how every workspace/proposal mutation is made auditable, every gate decision traceable, and every UI projection derived from canonical state rather than frontend assumptions.

## Core Doctrine

1. **Rig remains the authority** - External systems (connectors) are advisory only
2. **Deterministic dataclasses only** - All models are frozen, serializable
3. **No side effects** - Domain primitives perform no I/O
4. **No frontend authority logic** - UI only renders backend-projected data
5. **No external systems as authority** - Connectors produce normalized packets, never mutate state
6. **Public intake remains advisory_only** - Funding, sync operations are explicitly marked
7. **Unknown values use explicit placeholders** - Clear null state representation

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      Rig Authority Boundary                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Domain Layer ( Pure )                     │   │
│  │  ┌──────────────  ┌──────────────  ┌──────────────────┐  │   │
│  │  │ AuditActor    │ │ AuditSubject │ │ AuditEvent       │  │   │
│  │  │ AuditDecision │ │ AuditReceipt │ │ AuditReceiptLink │  │   │
│  │  │ Workspace     │ │ Link          │ │                  │  │   │
│  │  └──────────────  └──────────────  └──────────────────┘  │   │
│  │                                                      │   │
│  │           Deterministic  │  JSON-serializable    │   │
│  │           No side effects │  No frontend logic    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Mutation Handlers ( Side-Effect )             │   │
│  │                                                           │   │
│  │  WorkspaceDomain.create_workspace()   ──► AuditEvent      │   │
│  │         │                      +------------------+          │   │
│  │         ▼                      ▼                  │          │   │
│  │  ┌──────────────┐    ┌─────────────────┐      │          │   │
│  │  │ Workspace    │    │ Receipt         │      │          │   │
│  │  │ Record       │    │ (Filesystem)    │      │          │   │
│  │  └──────────────┘    └─────────────────┘      │          │   │
│  │         │                                   │           │          │   │
│  │         ▼                                   ▼           │          │   │
│  │  AuditEvent saved        Receipt saved        │          │   │
│  │  to .build/rig/audit/   to .build/rig/receipts/  │          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                Projection Layer ( Read-Only )               │   │
│  │                                                           │   │
│  │  build_projection()  ◄────────────── WorkspaceAuditTrail   │   │
│  │         │                              “그렇이 obras   │
│  │         ▼                                           │   │
│  │  AuditTrailCard widget ◄───────────── auditability_state   │   │
│  │         │                                           │   │
│  │         ▼                                           │   │
│  │  Dumb rendering: textContent only, no authority decisions │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
            ┌─────────────────────────┐
            │    External Systems      │
            │  (Connectors Only)       │
            │  - Google Forms          │
            │  - GitHub Issues         │
            │  - Google Sheets         │
            │                           │
            │  Produce normalized      │
            │  PublicIntakePacket       │
            │  Generate PublicSyncReceipt│
            │  ADVISORY ONLY           │
            └─────────────────────────┘
```

## Components

### Audit Primitives Module (`workspace_audit.py`)

#### Placeholder Constants

All required placeholders for explicit null state representation:

| Placeholder | Purpose |
|-------------|---------|
| `unknown` | Unknown state |
| `unavailable` | Data unavailable |
| `not_created` | Resource not created |
| `not_run` | Operation not run |
| `not_proof` | Not proof-level evidence |
| `advisory_only` | Advisory only, not authoritative |
| `not_authoritative` | Not authoritative |
| `no_receipt` | No receipt available |

#### Enums

- **AuditAction**: CREATE, READ, UPDATE, DELETE, TRANSITION, APPLY, REVIEW, VALIDATE, IMPORT, SYNC, UNKNOWN
- **AuditSubjectKind**: WORKSPACE, WORKSPACE_RECORD, WORKSPACE_STATUS, PROPOSAL, PROPOSAL_STATE, VALIDATION, VALIDATION_RESULT, REVIEW_BUNDLE, RECEIPT, EXECUTION_RECEIPT, VALIDATOR_RECEIPT, APPLY_RECEIPT, PUBLIC_INTAKE_PACKET, PUBLIC_SYNC_RECEIPT, FUNDING_PLEDGE, WORKTREE, GIT_BRANCH, GIT_MAIN, UNKNOWN
- **AuditDecision**: ALLOWED, BLOCKED, PENDING, UNKNOWN, NOT_APPLICABLE, ADVISORY_ONLY
- **AuditReceiptStatus**: EXISTS, LINKED, MISSING, NOT_REQUIRED, ADVISORY_ONLY, NOT_AUTHORITATIVE, NO_RECEIPT

#### Models

All models are frozen dataclasses with `slots=True` for memory efficiency:

```python
@dataclass(frozen=True, slots=True)
class AuditActor:
    actor_id: str
    actor_kind: str
    display_name: Optional[str] = None
    is_human: bool = False
    is_authoritative: bool = True

@dataclass(frozen=True, slots=True)
class AuditSubject:
    subject_id: str
    subject_kind: AuditSubjectKind = AuditSubjectKind.UNKNOWN
    display_name: Optional[str] = None
    workspace_id: Optional[str] = None
    authoritative: bool = True
    advisory_only: bool = False

@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    action: AuditAction = AuditAction.UNKNOWN
    actor: AuditActor = field(default_factory=AuditActor.unknown)
    subject: AuditSubject = field(default_factory=AuditSubject.unknown)
    decision: AuditDecision = AuditDecision.UNKNOWN
    timestamp: str = field(default_factory=lambda: ...)
    status: str = PLACEHOLDER_UNKNOWN
    summary: str = ""
    receipt_id: Optional[str] = None
    receipt_kind: Optional[str] = None
    receipt_status: AuditReceiptStatus = AuditReceiptStatus.MISSING
    workspace_id: Optional[str] = None
    details: dict = field(default_factory=dict)
    authoritative: bool = True
    advisory_only: bool = False

@dataclass(frozen=True, slots=True)
class AuditReceiptLink:
    link_id: str
    event_id: str
    receipt_id: str
    receipt_kind: str
    workspace_id: Optional[str] = None
    status: AuditReceiptStatus = AuditReceiptStatus.MISSING
    authoritative: bool = True
    advisory_only: bool = False

@dataclass(frozen=True, slots=True)
class WorkspaceAuditTrail:
    workspace_id: str
    events: Tuple[AuditEvent, ...] = ()
    receipt_links: Tuple[AuditReceiptLink, ...] = ()
    audit_completeness: str = PLACEHOLDER_UNKNOWN
    last_authoritative_event_id: Optional[str] = None
    receipt_status_summary: dict = field(default_factory=dict)
    missing_receipts: Tuple[str, ...] = ()
    advisory_only_events: int = 0
    authoritative_events: int = 0
```

#### Resolution Helpers

| Helper | Purpose |
|--------|---------|
| `resolve_mutation_authority()` | Classify mutation authority (authoritative vs advisory) |
| `resolve_receipt_status()` | Determine receipt existence status |
| `resolve_audit_completeness()` | Calculate audit completeness score |
| `build_workspace_audit_trail()` | Construct complete audit trail from events |
| `build_auditability_state()` | Build projection-ready auditability state |

### Workspace Domain Integration

The `WorkspaceDomain` class in `workspace.py` has been extended with:

1. **New directories**:
   - `self.audit_dir = self.build_root / "audit"`

2. **New methods**:
   - `audit_trail_path(workspace_id)` - Path to audit trail JSON
   - `audit_event_path(event_id)` - Path to individual audit event JSON
   - `_save_audit_event(event)` - Save audit event to filesystem
   - `_save_audit_receipt(receipt, receipt_id)` - Save receipt to filesystem

3. **Modified methods** (now produce audit events and receipts):
   - `create_workspace(task)` - Creates workspace + workspace_create_receipt + AuditEvent
   - `transition_workspace(workspace_id, new_status)` - Transitions status + workspace_transition_receipt + AuditEvent
   - `apply_workspace(workspace_id)` - Applies workspace + apply_receipt + AuditEvent (already had receipt, now has audit event)

4. **Workspace record enhancements**:
   - `receipt_paths` - List of all receipt file paths
   - `audit_event_ids` - List of all audit event IDs

### Public Intake Fixes

The `commands_public_intake.py` module now:

1. **Saves sync receipts to filesystem** via `_save_sync_receipt()`:
   - Previously: `PublicSyncReceipt` was only returned in-memory
   - Now: Saved to `.build/rig/public_intake/receipts/{receipt_id}.json`
   - This provides durable audit trail for public intake imports

2. **Includes receipt path in response**:
   - `sync_receipt_path` field added to import response

### Projection Integration

The `projection_builder.py` module now:

1. **Imports audit helpers**:
   ```python
   from rig.domain.workspace_audit import (
       build_auditability_state,
       WorkspaceAuditTrail,
       PLACEHOLDER_UNKNOWN,
       PLACEHOLDER_NOT_CREATED,
   )
   ```

2. **New widget**: `_workspace_audit_trail_widget()` - Builds audit trail widget data

3. **Layout update**: Added `workspace.audit_trail` to the main layout section

### Frontend Widget

New file: `src/rig_tools/static/js/widgets/audit-trail-card.js`

- **Dumb rendering only** - No fetching, no authority decisions
- **Projection-only data** - Consumes data from backend projection
- **Safe fallbacks** - Uses placeholder values for missing data
- **textContent only** - No innerHTML injection (XSS protection)
- **Patch-based rendering** - Clears element before re-rendering

## Mutation Path Audit Map

See `docs/sprints/workspace-authority-auditability-spine.md` for the complete audit map.

### Summary by Receipt Status

| Receipt Status | Count | Paths |
|---------------|-------|-------|
| produces_receipt | 3 | create_workspace, transition_workspace, apply_workspace |
| links_to_receipt | 2 | build_review_bundle, apply_workspace |
| implicit_receipt | 2 | generate_validation_result, build_review_bundle |
| advisory_only | 3 | public_intake_import (now saves receipt), _save_intake_packet, funding_summary_cmd |

### Critical Gaps Addressed

1. ✅ **Workspace Creation**: Now produces `workspace_create_receipt.json` + AuditEvent
2. ✅ **Workspace Transition**: Now produces `workspace_transition_receipt_{ws_id}_{old}_to_{new}.json` + AuditEvent
3. ✅ **Public Intake Sync**: `PublicSyncReceipt` now persisted to filesystem
4. ✅ **Workspace Save**: audit_event_ids tracked in workspace records
5. ✅ **Apply**: Already had receipt, now also produces AuditEvent

### Audit Completeness Score: 100%

All mutation paths now either:
- Produce a receipt
- Link to an existing receipt
- Explicitly record why no receipt exists (advisory_only)

## Authority Classification

### Authoritative (Rig Domain)
- Workspace creation
- Workspace status transitions
- Workspace apply
- Validation runs
- Review bundles
- Receipt creation

### Advisory Only (Connector Layer)
- Public intake imports
- Public intake packet saves
- Funding pledges
- Sync operations from external systems

**Rule**: Connector actions are NEVER authoritative. Rig remains the sole authority.

## Auditing Works

### For every workspace mutation:

```
1. Mutation occurs (e.g., create_workspace)
2. Domain layer creates:
   - Receipt (durable record of what happened)
   - AuditEvent (who did what to what with what result)
   - AuditReceiptLink (links event to receipt)
3. Files saved to filesystem:
   - Receipt: .build/rig/receipts/{receipt_id}.json
   - Audit Event: .build/rig/audit/{event_id}.json
4. Workspace record updated:
   - receipt_paths: [..., receipt_file_path]
   - audit_event_ids: [..., event_id]
5. Projection updated:
   - workspace.audit_trail widget receives auditability_state
6. UI renders:
   - AuditTrailCard displays completeness, event counts, missing receipts
```

### Public Intake Auditing:

```
1. Connector import runs
2. Packets created + PublicSyncReceipt created
3. Files saved to filesystem:
   - Packets: .build/rig/public_intake/packets.jsonl
   - Sync Receipt: .build/rig/public_intake/receipts/{receipt_id}.json
4. Response includes sync_receipt_path for traceability
5. Public intake data marked advisory_only in all projections
```

## Projection Data

The `workspace.audit_trail` widget receives:

```json
{
  "audit_completeness": "complete" | "not_proof" | "not_run" | "not_created" | "unknown",
  "last_authoritative_event_id": "ws_create_abc123" | "unknown",
  "receipt_status_summary": {
    "workspace_create": {"exists": 1, "missing": 0},
    "workspace_transition": {"exists": 1, "missing": 0},
    ...
  },
  "missing_receipts": ["receipt_kind_one", ...],
  "advisory_only_events": 0,
  "authoritative_events": 2,
  "advisory_only_warning": "Public intake and funding data is advisory_only.",
  "next_missing_audit_action": "Create receipts for: ..." | "no_receipt"
}
```

## UI Integration

The AuditTrailCard widget renders:

1. **Title**: "Audit Trail"
2. **Completeness Status**: Color-coded badge
   - green (complete)
   - yellow (not_proof, not_run)
   - gray (not_created, unknown)
3. **Event Counts**: Authoritative vs Advisory Only
4. **Last Authoritative Event**: Event ID display
5. **Missing Receipts**: List if any
6. **Action Hint**: What to do next
7. **Warning**: Advisory only reminder

## Testing

See `tests/test_workspace_audit.py` for comprehensive tests covering:

- All placeholder constants defined
- All enum values correct
- All models are deterministic dataclasses
- All models are JSON-serializable
- No side effects
- Public intake remains advisory_only
- Funding remains advisory_only
- Authority classification works correctly
- Receipt status resolution works correctly
- Audit completeness calculation works correctly
- Full audit flow integration

## Validation Commands

```bash
# Syntax check
python -m compileall -q src tests

# Type check with pyright
python -m pyright --project pyrightconfig.json

# Run workspace audit tests
python -m pytest tests/test_workspace_audit.py -v

# Run existing tests
python -m pytest tests/test_workspace_control_plane.py -v
python -m pytest tests/test_ui_frontend_logic.py -v

# Smoke test CLI
python -m rig --help
python -m rig ui --help
python -m rig window open --dry-run
```

## Non-Goals (Confirmed)

- ❌ No payment processing
- ❌ No OAuth
- ❌ No real Google/GitHub API calls
- ❌ No hosted SaaS work
- ❌ No background workers
- ❌ No queue systems
- ❌ No marketplace work
- ❌ No new monetization behavior
- ❌ No destructive Git commands
- ❌ No staging or committing

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/sprints/workspace-authority-auditability-spine.md` | Created | Phase 1 audit map |
| `src/rig/domain/workspace_audit.py` | Created | Audit primitives module |
| `src/rig/domain/workspace.py` | Modified | Added audit event production to mutations |
| `src/rig/commands_public_intake.py` | Modified | Save sync receipts to filesystem |
| `src/rig/domain/projection_builder.py` | Modified | Added audit trail widget |
| `src/rig_tools/static/js/widgets/audit-trail-card.js` | Created | Frontend audit trail widget |
| `tests/test_workspace_audit.py` | Created | Comprehensive audit tests |

## Clean Commit Message

```
Add workspace authority and auditability spine
```

Note: No "Generated by" or "Co-Authored-By" lines - per AGENTS.md policy.
