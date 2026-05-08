# Receipt Formalization Phase 2

## Overview

This document describes Phase 2 of the Receipt Formalization initiative: making receipts a first-class deterministic domain artifact used consistently across workspace mutations, validation results, review bundles, public intake sync, proposal lifecycle projections, and audit trails.

**Phase 1 Status**: Workspace Authority + Auditability spine exists with `workspace_audit.py` providing AuditEvent, AuditActor, AuditSubject, AuditReceiptLink, and WorkspaceAuditTrail primitives.

**Phase 2 Goal**: Create canonical ReceiptEnvelope domain objects that unify all receipt-like artifacts under a single, deterministic, JSON-serializable schema.

---

## Receipt-Like Artifact Inventory (Phase 1 Findings)

### Current Artifact Types

| # | Artifact Type | Path Pattern | Schema Version | Authority Level | Subject Type | Actor/Source | Schema Stability | Linkable from Audit Events | Projectable | Risk Level | Gap |
|---|--------------|--------------|----------------|----------------|--------------|---------------|------------------|--------------------------|-------------|------------|-----|
| 1 | Workspace Create Receipt | `.build/rig/receipts/ws_create_{workspace_id}.json` | `rig.workspace_create_receipt.v1` | Authoritative | workspace | cli | Medium | YES | YES | HIGH | Not canonical ReceiptEnvelope |
| 2 | Workspace Transition Receipt | `.build/rig/receipts/ws_trans_{ws_id}_{old}_to_{new}.json` | `rig.workspace_transition_receipt.v1` | Authoritative | workspace | cli | Medium | YES | YES | HIGH | Not canonical ReceiptEnvelope |
| 3 | Apply Receipt | `.build/rig/receipts/{workspace_id}_apply.json` | `rig.apply_receipt.v1` | Authoritative | workspace | cli | Medium | PARTIAL | YES | CRITICAL | Not canonical ReceiptEnvelope, missing audit event link |
| 4 | Execution Receipt | `.build/rig/receipts/{workspace_id}_run.json` | N/A | Authoritative | execution | domain | Low | YES | NO | MEDIUM | Exists in receipts.py but not used by workspace |
| 5 | Validation Result | `.build/rig/validation/{workspace_id}/validation.json` | `rig.validation_result.v1` | Authoritative | validation | domain | Medium | NO | YES | HIGH | Not a formal receipt |
| 6 | Review Bundle | `.build/rig/reviews/{workspace_id}/review.json` | `rig.review_bundle.v1` | Authoritative | review_bundle | domain | Medium | NO | YES | MEDIUM | File bundle, not formal receipt |
| 7 | Public Sync Receipt | `.build/rig/public_intake/receipts/{receipt_id}.json` | N/A | Advisory Only | public_sync | connector | Low | YES | NO | MEDIUM | PublicSyncReceipt exists but inconsistent schema |
| 8 | Validator Receipt | via FilesystemReceiptStore | N/A | Authoritative | validator | domain | Low | NO | NO | LOW | Exists in receipts.py but not integrated |

### Artifact Classification

#### Authoritative (Rig Domain)
- Workspace create/transition/apply receipts
- Validation results
- Review bundles
- Execution receipts
- Validator receipts

#### Advisory Only (Connector Layer)
- Public sync receipts
- Public intake packets
- Funding pledges

---

## Canonical Receipt Domain Design

### File Location
- **Primary**: `src/rig/domain/receipts.py` (extend existing)
- **Union imports**: Create `src/rig/domain/receipt_envelope.py` for canonical types

### Core Placeholder Constants

All required placeholders (matching workspace_audit.py):

```python
PLACEHOLDER_UNKNOWN = "unknown"
PLACEHOLDER_UNAVAILABLE = "unavailable"
PLACEHOLDER_NOT_CREATED = "not_created"
PLACEHOLDER_NOT_RUN = "not_run"
PLACEHOLDER_NOT_PROOF = "not_proof"
PLACEHOLDER_ADVISORY_ONLY = "advisory_only"
PLACEHOLDER_NOT_AUTHORITATIVE = "not_authoritative"
PLACEHOLDER_NO_RECEIPT = "no_receipt"
```

### Canonical Receipt Types

#### ReceiptEnvelope (Primary)

The unified container for all receipts:

```python
@dataclass(frozen=True, slots=True)
class ReceiptEnvelope:
    schema_version: str  # e.g., "rig.receipt_envelope.v1"
    receipt_id: str
    receipt_type: str  # workspace_create, workspace_transition, apply, validation, review, sync
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

#### Supporting Types

```python
@dataclass(frozen=True, slots=True)
class ReceiptActor:
    actor_id: str
    actor_kind: str  # cli, domain, connector, system
    display_name: Optional[str] = None
    is_human: bool = False
    is_authoritative: bool = True

@dataclass(frozen=True, slots=True)
class ReceiptSubject:
    subject_id: str
    subject_kind: str  # workspace, validation, review, apply, sync, execution
    display_name: Optional[str] = None
    workspace_id: Optional[str] = None
    authoritative: bool = True
    advisory_only: bool = False

@dataclass(frozen=True, slots=True)
class ReceiptInput:
    input_id: str
    input_kind: str
    reference: str  # path or URI
    hash: Optional[str] = None
    summary: str = ""

@dataclass(frozen=True, slots=True)
class ReceiptOutput:
    output_id: str
    output_kind: str
    reference: str  # path or URI
    hash: Optional[str] = None
    status: str = "unknown"  # success, failed, pending

@dataclass(frozen=True, slots=True)
class ReceiptDecision:
    decision_id: str
    decision_kind: str  # allowed, blocked, pending
    reason: str
    authoritative: bool = True

@dataclass(frozen=True, slots=True)
class ReceiptEvidence:
    evidence_id: str
    evidence_kind: str  # file, log, diff, snapshot
    reference: str  # path or URI
    hash: Optional[str] = None
    mime_type: Optional[str] = None
```

#### Receipt Write Result

```python
@dataclass(frozen=True, slots=True)
class ReceiptWriteResult:
    receipt_id: str
    receipt_path: Path
    receipt_envelope: ReceiptEnvelope
    status: str  # "success", "failed"
    error: Optional[str] = None
```

#### Receipt Index Entry

```python
@dataclass(frozen=True, slots=True)
class ReceiptIndexEntry:
    entry_id: str
    receipt_id: str
    receipt_type: str
    workspace_id: Optional[str]
    receipt_path: Path
    created_at: str
    authority_level: str
    advisory_only: bool
```

### Helper Functions

| Function | Purpose |
|----------|---------|
| `build_receipt_id(prefix, workspace_id, parts)` | Deterministic receipt ID generation |
| `build_receipt_envelope(...)` | Factory for ReceiptEnvelope |
| `receipt_to_dict(envelope)` | JSON-serializable dict conversion |
| `receipt_from_dict(data)` | Reconstruct from dict |
| `write_receipt(store, envelope)` | Persist to filesystem |
| `read_receipt(store, receipt_id)` | Load from filesystem |
| `index_receipts(repo_root)` | Build index of all receipts |
| `resolve_receipt_authority(envelope)` | Classify authority |
| `resolve_receipt_completeness(envelope)` | Check field completeness |
| `resolve_receipt_projection_summary(envelopes)` | Summarize for projection |

---

## Receipt Schema Versions

| Version | Description | Status |
|---------|-------------|--------|
| `rig.receipt_envelope.v1` | Initial canonical envelope | ACTIVE |
| `rig.workspace_create_receipt.v1` | Legacy workspace create | LEGACY |
| `rig.workspace_transition_receipt.v1` | Legacy workspace transition | LEGACY |
| `rig.apply_receipt.v1` | Legacy apply | LEGACY |
| `rig.validation_result.v1` | Legacy validation | LEGACY |
| `rig.review_bundle.v1` | Legacy review bundle | LEGACY |

### Migration Strategy

1. **Phase 2**: Add canonical ReceiptEnvelope types alongside existing receipts
2. **Phase 3**: Update workspace.py to produce canonical receipts (dual-write during transition)
3. **Phase 4**: Convert validation results to canonical receipts via adapter
4. **Phase 5**: Add receipt index for backward compatibility
5. **Phase 6**: Update projections to consume canonical receipt data
6. **Phase 7**: Add tests, deprecate old formats

---

## Deterministic ID Rules

Receipt IDs must be deterministic for the same inputs:

```python
def build_receipt_id(
    receipt_type: str,
    workspace_id: Optional[str] = None,
    additional_parts: Optional[list[str]] = None,
) -> str:
    """Build a deterministic receipt ID.
    
    Examples:
        workspace_create: ws_create_{workspace_id}
        workspace_transition: ws_trans_{workspace_id}_{old_status}_to_{new_status}
        apply: ws_apply_{workspace_id}
        validation: ws_val_{workspace_id}
        sync: sync_{connector}_{timestamp_hash}
    """
    parts = [receipt_type]
    if workspace_id:
        parts.append(workspace_id)
    if additional_parts:
        parts.extend(additional_parts)
    
    # Use underscore-joined for readability
    # For sync receipts, include hash of timestamp for uniqueness
    return "_".join(parts)
```

---

## Authority Classification Rules

| Receipt Type | Authority Level | Reason |
|--------------|-----------------|--------|
| workspace_create | authoritative | Rig domain mutation |
| workspace_transition | authoritative | Rig domain mutation |
| workspace_apply | authoritative | Git main branch mutation |
| validation | authoritative | Rig domain validation |
| review_bundle | authoritative | Rig domain evidence |
| execution | authoritative | Rig domain execution |
| validator_run | authoritative | Rig domain validation |
| public_sync | advisory_only | Connector-produced, external data |
| public_intake_packet | advisory_only | External system data |
| funding_pledge | advisory_only | External funding data |

### Resolution Function

```python
def resolve_receipt_authority(
    receipt_type: str,
    actor_kind: str,
    subject_kind: str,
) -> dict[str, Any]:
    """Resolve authority classification for a receipt."""
    # Public intake/funding are ALWAYS advisory only
    if receipt_type in ("public_sync", "public_intake_packet", "funding_pledge"):
        return {
            "authoritative": False,
            "advisory_only": True,
            "reason": "External system data is advisory_only by doctrine",
        }
    
    # Connector actions are NOT authoritative
    if actor_kind == "connector":
        return {
            "authoritative": False,
            "advisory_only": True,
            "reason": "Connector actions are not authoritative",
        }
    
    # Default: authoritative
    return {
        "authoritative": True,
        "advisory_only": False,
        "reason": "Rig domain mutations are authoritative",
    }
```

---

## Completeness Resolution

```python
def resolve_receipt_completeness(envelope: ReceiptEnvelope) -> dict[str, Any]:
    """Resolve completeness of a receipt envelope.
    
    Checks for required fields and placeholders.
    """
    required_fields = {
        "receipt_id": True,
        "receipt_type": True,
        "authority_level": True,
        "created_at": True,
        "actor": True,
        "subject": True,
    }
    
    missing = []
    for field, is_required in required_fields.items():
        value = getattr(envelope, field, None)
        if is_required and (value is None or value == ""):
            missing.append(field)
    
    # Check for placeholder values
    placeholder_fields = {
        "authority_level": PLACEHOLDER_UNKNOWN,
        "created_at": PLACEHOLDER_NOT_CREATED,
        "summary": PLACEHOLDER_UNKNOWN,
    }
    
    placeholders_used = []
    for field, placeholder in placeholder_fields.items():
        value = getattr(envelope, field, None)
        if value == placeholder:
            placeholders_used.append(field)
    
    is_complete = len(missing) == 0 and len(placeholders_used) == 0
    
    return {
        "complete": is_complete,
        "missing_fields": tuple(missing),
        "placeholder_fields": tuple(placeholders_used),
        "completeness_score": 1.0 if is_complete else 0.5 if len(missing) == 0 else 0.0,
    }
```

---

## Projection Summary Resolution

```python
def resolve_receipt_projection_summary(
    envelopes: list[ReceiptEnvelope],
) -> dict[str, Any]:
    """Resolve projection summary from receipt envelopes."""
    total = len(envelopes)
    authoritative = [e for e in envelopes if not e.advisory_only]
    advisory = [e for e in envelopes if e.advisory_only]
    
    # Count by type
    type_counts: dict[str, dict[str, int]] = {}
    for env in envelopes:
        kind = env.receipt_type
        if kind not in type_counts:
            type_counts[kind] = {"authoritative": 0, "advisory": 0}
        if env.advisory_only:
            type_counts[kind]["advisory"] += 1
        else:
            type_counts[kind]["authoritative"] += 1
    
    # Find last authoritative
    last_auth = None
    for env in sorted(envelopes, key=lambda e: e.created_at, reverse=True):
        if not env.advisory_only:
            last_auth = env.receipt_id
            break
    
    # Get missing receipt actions
    missing_actions = []
    
    return {
        "receipt_count": total,
        "authoritative_count": len(authoritative),
        "advisory_count": len(advisory),
        "missing_receipt_count": 0,  # Would be calculated from expected vs actual
        "last_receipt_id": last_auth or PLACEHOLDER_NO_RECEIPT,
        "last_receipt_summary": (authoritative[-1].summary if authoritative else 
                                  advisory[-1].summary if advisory else 
                                  PLACEHOLDER_UNKNOWN),
        "type_counts": type_counts,
        "validation_status": resolve_validation_receipt_status(envelopes),
        "review_status": resolve_review_receipt_status(envelopes),
        "apply_gate_status": resolve_apply_gate_receipt_status(envelopes),
        "next_missing_receipt_action": resolve_next_missing_action(envelopes),
    }
```

---

## Implementation Phases

### Phase 2: Canonical Receipt Domain (THIS PHASE)
- [x] Define placeholder constants
- [x] Define ReceiptEnvelope and all supporting dataclasses
- [x] Implement helper functions
- [ ] Add to `src/rig/domain/receipts.py`
- [ ] Ensure JSON serializability
- [ ] Ensure deterministic equality

### Phase 3: Migrate Workspace Receipts
- [ ] Update `WorkspaceDomain.create_workspace()` to produce ReceiptEnvelope
- [ ] Update `WorkspaceDomain.transition_workspace()` to produce ReceiptEnvelope
- [ ] Update `WorkspaceDomain.apply_workspace()` to produce ReceiptEnvelope
- [ ] Add backward compatibility for old receipt fields
- [ ] Link receipts to audit events (bidirectional)
- [ ] Preserve existing tests

### Phase 4: Formalize Validation Receipts (COMPLETED)
- [x] Create `build_validation_receipt()` helper function
- [x] Convert validation result dict to ReceiptEnvelope
- [x] Support placeholders: `no_validation`, `validation_failed`, `validation_incomplete`
- [x] Create `build_gate_decision_receipt()` for validation/apply gates
- [x] Integrate with `generate_validation_result()` in workspace.py
- [x] Produces canonical receipt alongside legacy validation.json
- [x] Gate decision receipts link to validation receipts

### Phase 5: Formalize Review Bundles (COMPLETED)
- [x] Create `build_review_bundle_receipt()` helper function
- [x] Create `build_apply_receipt()` for apply operations
- [x] Support placeholders: `no_review_bundle`, `review_incomplete`, `no_apply_gate`, `apply_blocked`
- [x] Review bundles remain as files/directories (backward compat)
- [x] Canonical receipt index entry created for each bundle
- [x] Integrate with `build_review_bundle()` in workspace.py
- [x] Apply gate decision receipts link to review bundle receipts

### Phase 6: Projection Integration (COMPLETED)
- [x] Update `resolve_receipt_projection_summary()` with all required fields
- [x] Add fields: `authoritative_receipt_count`, `advisory_receipt_count`, `missing_receipt_count`
- [x] Add fields: `validation_receipt_status`, `review_receipt_status`, `apply_gate_receipt_status`
- [x] Add fields: `gate_decision_status`, `next_missing_receipt_action`, `auditability_status`
- [x] Add fields: `authoritative_evidence_available`
- [x] Compute missing receipt count based on expected types
- [x] Compute auditability status (not_auditable, minimally_auditable, partially_auditable, fully_auditable)
- [x] Projection data derived from canonical receipt state (Phase 6 doctrine)

### Phase 7: Tests (COMPLETED)
- [x] ReceiptEnvelope serialization tests
- [x] Receipt ID stability tests
- [x] Advisory public sync receipts cannot become authoritative
- [x] Workspace create/transition/apply use canonical receipts
- [x] Audit events link to receipt IDs/paths
- [x] Validation result `build_validation_receipt()` produces formal receipt
- [x] Missing validation produces placeholders
- [x] Review bundle receipt can be indexed
- [x] Projection summary reports counts correctly (all Phase 6 fields)
- [x] Frontend renders missing and populated states safely
- [x] Legacy receipt compatibility via `convert_legacy_to_envelope()`
- [x] Phase 4-6 helper functions have dedicated tests (9 new tests)

---

## Validation Commands

```bash
# Syntax check (Python 3.14)
python3.14 -m compileall -q src tests

# Type check with pyright
python3.14 -m pyright --project pyrightconfig.json

# Run tests
python3.14 -m pytest tests/test_workspace_audit.py -v
python3.14 -m pytest tests/test_workspace_control_plane.py -v
python3.14 -m pytest tests/test_ui_frontend_logic.py -v
python3.14 -m pytest tests/test_receipt_envelope.py -v

# Smoke tests
python3.14 -m rig --help
python3.14 -m rig ui --help
python3.14 -m rig window open --dry-run
```

---

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `src/rig/domain/receipt_envelope.py` | Created | Canonical ReceiptEnvelope module with all domain types |
| `src/rig/domain/workspace.py` | Modified | Phase 3: canonical receipts for create/transition/apply; Phase 4: validation receipts; Phase 5: review bundle receipts |
| `src/rig/domain/workspace_audit.py` | Created | Audit trail primitives (pre-existing) |
| `src/rig/domain/projection_builder.py` | Modified | Projection builder (pre-existing, Phase 6 uses enhanced projection summary) |
| `tests/test_receipt_envelope.py` | Created | 72 tests: 63 original + 9 for Phases 4-6 |
| `docs/architecture/receipt-formalization.md` | Created | Architecture documentation with Phases 4-6 |
| `docs/sprints/receipt-formalization-phase-2.md` | Created | This sprint document with Phases 4-6 marked complete |

---

## Non-Goals

- No external APIs
- No OAuth
- No Stripe/payment work
- No hosted SaaS
- No background workers
- No queue systems
- No database migration
- No destructive Git commands
