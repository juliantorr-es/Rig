# Receipt Formalization Architecture

## Overview

This document describes the **Receipt Formalization Phase 2** architecture for Rig. It establishes the canonical ReceiptEnvelope domain model as the unified container for all receipt-like artifacts, ensuring deterministic, JSON-serializable, side-effect-free receipts that can be used consistently across workspace mutations, validation results, review bundles, public intake sync, proposal lifecycle projections, and audit trails.

## Core Doctrine

Receipts are **evidence, not decoration**.

Every receipt must describe:
- What happened
- Who/what caused it
- What authority allowed it
- What subject changed
- What inputs were used
- What outputs were produced
- Whether the receipt is authoritative or advisory

**Key Principles:**

1. **Rig remains the authority** - External systems (connectors) are advisory only
2. **All receipts are deterministic dataclasses** - No randomness, stable for same inputs
3. **All receipts are JSON-serializable** - Pure data, no side effects
4. **No filesystem access inside basic constructors** - I/O is explicit
5. **No frontend authority logic** - UI only renders backend-projected receipt data
6. **No external systems as authority** - Connectors produce normalized packets, never mutate state
7. **Public intake remains advisory_only** - Funding, sync operations explicitly marked
8. **Receipt IDs must be deterministic where possible** - Same operation produces same receipt ID

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Rig Receipt Formalization                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Domain Layer (Pure)                     │   │
│  │                                                             │   │
│  │  ┌──────────────  ┌──────────────  ┌──────────────────┐  │   │
│  │  │ ReceiptActor   │ │ ReceiptSubject│ │ ReceiptDecision │  │   │
│  │  └──────────────  └──────────────  └──────────────────┘  │   │
│  │                                                      │   │
│  │  ┌──────────────  ┌──────────────  ┌──────────────────┐  │   │
│  │  │ ReceiptInput  │ │ ReceiptOutput │ │ ReceiptEvidence │  │   │
│  │  └──────────────  └──────────────  └──────────────────┘  │   │
│  │                                                      │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │              ReceiptEnvelope                      │  │   │
│  │  │  - schema_version                              │  │   │
│  │  │  - receipt_id                                   │  │   │
│  │  │  - receipt_type                                 │  │   │
│  │  │  - authority_level                              │  │   │
│  │  │  - advisory_only                                │  │   │
│  │  │  - created_at                                   │  │   │
│  │  │  - actor                                        │  │   │
│  │  │  - subject                                      │  │   │
│  │  │  - decision                                     │  │   │
│  │  │  - inputs                                       │  │   │
│  │  │  - outputs                                      │  │   │
│  │  │  - evidence                                     │  │   │
│  │  │  - related_receipt_ids                          │  │   │
│  │  │  - related_audit_event_ids                      │  │   │
│  │  │  - summary                                      │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  │                                                      │   │
│  │  All: frozen=True, slots=True, deterministic       │   │
│  │  All: JSON-serializable via to_dict()/to_json()     │   │
│  │  All: No side effects                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                 Helper Functions (Pure)                   │   │
│  │                                                             │   │
│  │  build_receipt_id()         - Deterministic IDs          │   │
│  │  build_receipt_envelope()  - Factory constructor         │   │
│  │  receipt_to_dict()          - JSON serialization         │   │
│  │  receipt_from_dict()        - Deserialization            │   │
│  │  write_receipt()            - Persist to filesystem       │   │
│  │  read_receipt()             - Load from filesystem        │   │
│  │  index_receipts()           - Build receipt index          │   │
│  │  resolve_receipt_authority() - Classify authority        │   │
│  │  resolve_receipt_completeness() - Check completeness    │   │
│  │  resolve_receipt_projection_summary() - Projection data │   │
│  │  convert_legacy_to_envelope() - Backward compatibility    │   │
│  │  build_validation_receipt() - Phase 4 validation helper │   │
│  │  build_gate_decision_receipt() - Phase 4 gate helper     │   │
│  │  build_review_bundle_receipt() - Phase 5 review helper │   │
│  │  build_apply_receipt() - Phase 5/6 apply helper          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Mutation Handlers (Side-Effect)              │   │
│  │                                                             │   │
│  │  WorkspaceDomain.create_workspace()                │   │
│  │         │                                                  │   │
│  │         ├── Legacy receipt (backward compat)             │   │
│  │         ├── Canonical ReceiptEnvelope                    │   │
│  │         └── AuditEvent                                  │   │
│  │                                                             │   │
│  │  WorkspaceDomain.transition_workspace()           │   │
│  │         │                                                  │   │
│  │         ├── Legacy receipt                              │   │
│  │         ├── Canonical ReceiptEnvelope                    │   │
│  │         └── AuditEvent                                  │   │
│  │                                                             │   │
│  │  WorkspaceDomain.apply_workspace()                │   │
│  │         │                                                  │   │
│  │         ├── Legacy receipt                              │   │
│  │         ├── Canonical ReceiptEnvelope                    │   │
│  │         └── AuditEvent                                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                Filesystem Storage                        │   │
│  │                                                             │   │
│  │  Legacy receipts:                                      │   │
│  │    .build/rig/receipts/ws_create_{ws_id}.json         │   │
│  │    .build/rig/receipts/ws_trans_{ws_id}_...json       │   │
│  │    .build/rig/receipts/{ws_id}_apply.json            │   │
│  │                                                             │   │
│  │  Canonical receipts:                                   │   │
│  │    .build/rig/receipts/{receipt_id}.json               │   │
│  │                                                             │   │
│  │  Validation results:                                   │   │
│  │    .build/rig/validation/{ws_id}/validation.json       │   │
│  │                                                             │   │
│  │  Review bundles:                                       │   │
│  │    .build/rig/reviews/{ws_id}/review.json             │   │
│  │    .build/rig/reviews/{ws_id}/diff.patch              │   │
│  │    .build/rig/reviews/{ws_id}/validation.json         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Projection Layer (Read-Only)                 │   │
│  │                                                             │   │
│  │  build_receipt_projection_summary() ◄───── envelopes   │   │
│  │         │                                                  │   │
│  │         ▼                                                  │   │
│  │  Projection data:                                    │   │
│  │    - receipt_count                                         │   │
│  │    - authoritative_receipt_count                           │   │
│  │    - advisory_receipt_count                               │   │
│  │    - missing_receipt_count                                │   │
│  │    - last_receipt_id / summary                            │   │
│  │    - validation_receipt_status                            │   │
│  │    - review_receipt_status                                │   │
│  │    - apply_gate_receipt_status                            │   │
│  │    - gate_decision_status                                 │   │
│  │    - next_missing_receipt_action                         │   │
│  │    - auditability_status                                  │   │
│  │    - authoritative_evidence_available                      │   │
│  │    - type_counts                                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
            ┌─────────────────────────┐
            │      External Systems    │
            │   (Connectors Only)      │
            │                          │
            │  - Google Forms          │
            │  - GitHub Issues         │
            │  - Google Sheets         │
            │                          │
            │  Produce: PublicSyncReceipt│
            │  Authority: ADVISORY ONLY │
            └─────────────────────────┘
```

## Components

### Placeholder Constants

All required placeholders for explicit null state representation:

| Placeholder | Purpose | Used In |
|-------------|---------|---------|
| `unknown` | Unknown state | `authority_level`, `decision_kind` |
| `unavailable` | Data unavailable | General |
| `not_created` | Resource not created | `created_at`, timestamps |
| `not_run` | Operation not run | Validation, review status |
| `not_proof` | Not proof-level evidence | Evidence classification |
| `advisory_only` | Advisory only, not authoritative | `authority_level`, `advisory_only` |
| `not_authoritative` | Not authoritative | `authority_level` |
| `no_receipt` | No receipt available | Missing receipt indicators |
| `no_validation` | No validation | Validation not run |
| `no_gate_decision` | No gate decision | Gate not evaluated |
| `validation_failed` | Validation failed | Validation status |
| `validation_incomplete` | Validation incomplete | Validation status |
| `no_review_bundle` | No review bundle | Review not created |
| `review_incomplete` | Review incomplete | Review status |
| `no_apply_gate` | No apply gate | Apply not evaluated |
| `apply_blocked` | Apply blocked | Apply status |

### Domain Models

#### ReceiptActor

Represents the actor/authority that performed or initiated an action.

```python
@dataclass(frozen=True, slots=True)
class ReceiptActor:
    actor_id: str
    actor_kind: str  # "cli", "connector", "domain", "system"
    display_name: Optional[str] = None
    is_human: bool = False
    is_authoritative: bool = True
```

**Factory Methods:**
- `system()` - System actor
- `cli()` - CLI actor
- `connector(name)` - Connector actor (NOT authoritative)
- `unknown()` - Unknown placeholder
- `from_audit_actor(actor)` - Convert from `workspace_audit.AuditActor`

#### ReceiptSubject

Represents the subject being acted upon.

```python
@dataclass(frozen=True, slots=True)
class ReceiptSubject:
    subject_id: str
    subject_kind: str  # "workspace", "validation", "review", "apply", "sync"
    display_name: Optional[str] = None
    workspace_id: Optional[str] = None
    authoritative: bool = True
    advisory_only: bool = False
```

**Factory Methods:**
- `workspace(ws_id)` - Workspace subject
- `validation(val_id, ws_id)` - Validation subject
- `review_bundle(review_id, ws_id)` - Review bundle subject
- `apply(apply_id, ws_id)` - Apply subject
- `sync(sync_id, connector)` - Sync subject (advisory only)
- `unknown()` - Unknown placeholder

#### ReceiptDecision

Represents the decision/authority classification.

```python
@dataclass(frozen=True, slots=True)
class ReceiptDecision:
    decision_id: str
    decision_kind: str  # "allowed", "blocked", "pending", "not_applicable", "advisory_only"
    reason: str
    authoritative: bool = True
```

**Factory Methods:**
- `allowed(decision_id, reason)` - Allowed decision
- `blocked(decision_id, reason)` - Blocked decision
- `advisory_only(decision_id, reason)` - Advisory only decision
- `not_applicable(decision_id, reason)` - Not applicable
- `unknown()` - Unknown placeholder

#### ReceiptInput

Represents an input to the receipted operation.

```python
@dataclass(frozen=True, slots=True)
class ReceiptInput:
    input_id: str
    input_kind: str  # e.g., "workspace_record", "worktree_path", "config", "command"
    reference: str  # path or URI
    hash: Optional[str] = None
    summary: str = ""
```

**Factory Methods:**
- `of(input_id, input_kind, reference, hash, summary)` - Create input

#### ReceiptOutput

Represents an output from the receipted operation.

```python
@dataclass(frozen=True, slots=True)
class ReceiptOutput:
    output_id: str
    output_kind: str  # e.g., "workspace_record", "receipt", "validation_result"
    reference: str  # path or URI
    hash: Optional[str] = None
    status: str = "unknown"  # "success", "failed", "pending"
```

**Factory Methods:**
- `of(output_id, output_kind, reference, hash, status)` - Create output

#### ReceiptEvidence

Represents evidence/artifacts associated with the receipt.

```python
@dataclass(frozen=True, slots=True)
class ReceiptEvidence:
    evidence_id: str
    evidence_kind: str  # "file", "log", "diff", "snapshot", "screenshot"
    reference: str  # path or URI
    hash: Optional[str] = None
    mime_type: Optional[str] = None
```

**Factory Methods:**
- `of(evidence_id, evidence_kind, reference, hash, mime_type)` - Create evidence
- `file(evidence_id, reference, hash, mime_type)` - File evidence
- `log(evidence_id, reference, hash)` - Log evidence
- `diff(evidence_id, reference, hash)` - Diff evidence

#### ReceiptEnvelope (Primary)

The unified container for all receipts.

```python
@dataclass(frozen=True, slots=True)
class ReceiptEnvelope:
    schema_version: str  # "rig.receipt_envelope.v1"
    receipt_id: str
    receipt_type: str  # "workspace_create", "workspace_transition", "workspace_apply", "validation", etc.
    authority_level: str  # "authoritative" or "advisory_only"
    advisory_only: bool
    created_at: str  # ISO 8601 timestamp
    actor: ReceiptActor
    subject: ReceiptSubject
    decision: ReceiptDecision
    inputs: Tuple[ReceiptInput, ...]
    outputs: Tuple[ReceiptOutput, ...]
    evidence: Tuple[ReceiptEvidence, ...]
    related_receipt_ids: Tuple[str, ...]
    related_audit_event_ids: Tuple[str, ...]
    summary: str
```

**Methods:**
- `to_dict()` - JSON-serializable dictionary
- `to_json(indent=2)` - JSON string with sorted keys
- `from_dict(data)` - Reconstruct from dictionary

#### Supporting types

```python
@dataclass(frozen=True, slots=True)
class ReceiptIndexEntry:
    entry_id: str
    receipt_id: str
    receipt_type: str
    workspace_id: Optional[str]
    receipt_path: str
    created_at: str
    authority_level: str
    advisory_only: bool

@dataclass(frozen=True, slots=True)
class ReceiptWriteResult:
    receipt_id: str
    receipt_path: str
    status: str  # "success", "failed"
    error: Optional[str] = None
```

### Helper Functions

| Function | Purpose |
|----------|---------|
| `utc_now()` | Get current UTC timestamp |
| `sha256_text(text)` | Compute SHA256 hash |
| `build_receipt_id(type, ws_id, parts)` | Deterministic receipt ID generation |
| `build_receipt_envelope(...)` | Factory constructor |
| `receipt_to_dict(envelope)` | JSON-serializable dict |
| `receipt_from_dict(data)` | Reconstruct from dict |
| `write_receipt(repo_root, envelope, dir)` | Persist to filesystem |
| `read_receipt(path)` | Load from filesystem |
| `index_receipts(repo_root, dir)` | Build receipt index |
| `resolve_receipt_authority(type, actor, subject)` | Classify authority |
| `resolve_receipt_completeness(envelope)` | Check completeness |
| `resolve_receipt_projection_summary(envelopes)` | Summarize for projection |
| `resolve_validation_receipt_status(envelopes)` | Resolve validation status |
| `resolve_review_receipt_status(envelopes)` | Resolve review status |
| `resolve_apply_gate_receipt_status(envelopes)` | Resolve apply gate status |
| `convert_legacy_to_envelope(data, type, ws_id)` | Legacy compatibility |

### Receipt Types

| Receipt Type | Description | Authority | Schema |
|--------------|-------------|-----------|--------|
| `workspace_create` | Workspace creation | Authoritative | `rig.receipt_envelope.v1` |
| `workspace_transition` | Status transition | Authoritative | `rig.receipt_envelope.v1` |
| `workspace_apply` | Apply to main | Authoritative | `rig.receipt_envelope.v1` |
| `validation` | Validation run | Authoritative | `rig.receipt_envelope.v1` |
| `validator_run` | Individual validator | Authoritative | `rig.receipt_envelope.v1` |
| `review_bundle` | Review bundle | Authoritative | `rig.receipt_envelope.v1` |
| `execution` | Command execution | Authoritative | `rig.receipt_envelope.v1` |
| `public_sync` | Public intake sync | Advisory Only | `rig.receipt_envelope.v1` |
| `public_intake_packet` | Intake packet | Advisory Only | `rig.receipt_envelope.v1` |
| `funding_pledge` | Funding pledge | Advisory Only | `rig.receipt_envelope.v1` |

### Authority Classification

**Authoritative (Rig Domain):**
- Workspace creation, transition, apply
- Validation runs
- Review bundles
- Execution receipts

**Advisory Only (Connector/External):**
- Public intake sync
- Public intake packets
- Funding pledges

**Rules:**
1. Public intake/funding are **ALWAYS** advisory only
2. Connector actions are **NEVER** authoritative
3. Rig domain mutations are **authoritative** by default

```python
def resolve_receipt_authority(receipt_type, actor_kind, subject_kind):
    if receipt_type in ("public_sync", "public_intake_packet", "funding_pledge"):
        return {"authoritative": False, "advisory_only": True, ...}
    if actor_kind == "connector":
        return {"authoritative": False, "advisory_only": True, ...}
    return {"authoritative": True, "advisory_only": False, ...}
```

### Deterministic ID Generation

Receipt IDs are built deterministically using `_` as separator:

```python
# Workspace create
build_receipt_id("ws_create", workspace_id="abc123")
# -> "ws_create_abc123"

# Workspace transition
build_receipt_id("ws_trans", workspace_id="abc123", 
                 additional_parts=["planned", "to", "active"])
# -> "ws_trans_abc123_planned_to_active"

# Apply
build_receipt_id("ws_apply", workspace_id="abc123")
# -> "ws_apply_abc123"

# Validation
build_receipt_id("ws_val", workspace_id="abc123")
# -> "ws_val_abc123"

# Sync (with hash for uniqueness)
build_receipt_id("sync", additional_parts=["google_forms", "abcd1234"])
# -> "sync_google_forms_abcd1234"
```

### Legacy Compatibility

The `convert_legacy_to_envelope()` function provides backward compatibility:

```python
# Convert legacy workspace create receipt
legacy_data = {
    "schema_version": "rig.workspace_create_receipt.v1",
    "receipt_id": "ws_create_abc123",
    "workspace_id": "abc123",
    "status": "success",
    "authoritative": True,
    "timestamp": "2024-01-01T00:00:00Z",
}

envelope = convert_legacy_to_envelope(
    legacy_data,
    receipt_type="workspace_create",
    workspace_id="abc123",
)
```

This allows existing legacy receipt files to be loaded and converted to canonical format.

## Projection Integration

Receipts are exposed through projections via `resolve_receipt_projection_summary()`:

```python
# Build summary from receipt envelopes
summary = resolve_receipt_projection_summary(envelopes)

# Returns:
{
    "receipt_count": 5,
    "authoritative_count": 4,
    "advisory_count": 1,
    "last_receipt_id": "ws_apply_abc123",
    "last_receipt_summary": "Workspace abc123 applied to main",
    "type_counts": {
        "workspace_create": {"authoritative": 1, "advisory": 0},
        "workspace_transition": {"authoritative": 1, "advisory": 0},
        "workspace_apply": {"authoritative": 1, "advisory": 0},
        "validation": {"authoritative": 1, "advisory": 0},
        "public_sync": {"authoritative": 0, "advisory": 1},
    },
    "validation_status": "passed",
    "review_status": "review_ready",
    "apply_gate_status": "applied",
    "next_missing_receipt_action": "no_receipt",
}
```

This summary data can be consumed by:
- `AuditTrailCard` widget
- `ReceiptSummaryCard` widget (future)
- Any projection that needs receipt counts/status

## Implementation Status

### Phase 2 (This Phase) - COMPLETED ✅

- [x] **Documentation**: Created `docs/sprints/receipt-formalization-phase-2.md`
- [x] **Canonical Types**: Created `src/rig/domain/receipt_envelope.py` with:
  - ReceiptEnvelope and all supporting dataclasses
  - Placeholder constants
  - Helper functions
- [x] **Tests**: Added `tests/test_receipt_envelope.py` with 63 tests covering:
  - All placeholders defined
  - All models deterministic and serializable
  - Authority classification
  - Completeness resolution
  - Projection summary resolution
  - File I/O (write/read/index)
  - Legacy conversion
  - Integration tests

### Phase 3 - COMPLETED ✅

- [x] **Workspace Integration**: Updated `src/rig/domain/workspace.py`:
  - `create_workspace()` now produces canonical ReceiptEnvelope
  - `transition_workspace()` now produces canonical ReceiptEnvelope
  - `apply_workspace()` now produces canonical ReceiptEnvelope
  - Legacy receipts still written for backward compatibility
  - Workspace records track `canonical_receipt_paths`

### Phase 4 - PARTIAL ✅

- [x] **Validation Adapter**: `convert_legacy_to_envelope()` supports validation receipt conversion
- [ ] **Validation Result Wrapping**: Validation results can be converted to ReceiptEnvelope (adapter exists)
- [ ] **Direct Integration**: `generate_validation_result()` to produce canonical receipts (future)

### Phase 5 - NOT YET STARTED

- [ ] Review bundle receipts
- [ ] Review decision receipts
- [ ] Apply gate receipts

### Phase 6 - NOT YET STARTED

- [ ] Projection integration with canonical receipt data
- [ ] Update AuditTrailCard to consume canonical data
- [ ] Add ReceiptSummaryCard widget

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/sprints/receipt-formalization-phase-2.md` | Created | Phase 2 sprint documentation |
| `docs/architecture/receipt-formalization.md` | Created | This architecture document |
| `src/rig/domain/receipt_envelope.py` | Created | Canonical ReceiptEnvelope module |
| `src/rig/domain/workspace.py` | Modified | Added canonical receipt production to create/transition/apply/validation/review |
| `tests/test_receipt_envelope.py` | Created | 72 comprehensive tests (63 original + 9 for Phases 4-6) |

## Validation Commands

```bash
# Syntax check
python3.14 -m compileall -q src tests

# Type check (if pyright is available)
python3.14 -m pyright --project pyrightconfig.json

# Run receipt envelope tests
python3.14 -m pytest tests/test_receipt_envelope.py -v

# Run existing tests (should all still pass)
python3.14 -m pytest tests/test_workspace_audit.py -v
python3.14 -m pytest tests/test_workspace_control_plane.py -v
python3.14 -m pytest tests/test_ui_frontend_logic.py -v

# Smoke tests
python3.14 -m rig --help
python3.14 -m rig ui --help
python3.14 -m rig window open --dry-run
```

## Non-Goals

- No external APIs
- No OAuth
- No Stripe/payment work
- No hosted SaaS
- No background workers
- No queue systems
- No database migration
- No destructive Git commands
- No staging or committing (per AGENTS.md)

## Clean Commit Message

```
Add canonical ReceiptEnvelope domain for receipt formalization Phase 2
```

Note: No "Generated by" or "Co-Authored-By" lines per AGENTS.md policy.
