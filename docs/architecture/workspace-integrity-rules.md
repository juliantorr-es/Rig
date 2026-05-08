# Workspace Integrity Rules

## Overview

This document defines the **canonical integrity rules and invariants** for Rig's workspace/proposal/audit/receipt state. These rules ensure that invalid authority state becomes difficult to create, easy to detect, and impossible to silently ignore.

## Core Doctrine

- **Rig is the final authority** - No external system can override Rig's authority decisions
- **Deterministic validation** - All integrity checks must produce the same result given the same state
- **Explicit findings only** - No silent failures; every violation produces a clear, actionable finding
- **No auto-repair** - Integrity checks detect and report, but never silently fix
- **Projection-safety** - Frontend renders only what backend projections explicitly provide

---

## Canonical Invariants

### Workspace Lifecycle Transition Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `WS-001` | workspace status MUST be one of: `planned`, `active`, `blocked`, `executed`, `validated`, `review_ready`, `applied` | critical |
| `WS-002` | ALLOWED_TRANSITIONS define the only valid state changes; any other transition is INVALID | critical |
| `WS-003` | `applied` status is TERMINAL - no transitions out of `applied` | critical |
| `WS-004` | `blocked` status is TERMINAL - no transitions out of `blocked` | critical |
| `WS-005` | A workspace CANNOT transition to `applied` without passing through `review_ready` | error |
| `WS-006` | A workspace CANNOT transition to `review_ready` without passing through `validated` | error |
| `WS-007` | A workspace CANNOT transition to `validated` without passing through `executed` | error |
| `WS-008` | Status history MUST be monotonically increasing in time (no time travel) | error |

**Valid Transitions Matrix:**
```
planned     -> active
active      -> executed, blocked
executed    -> validated, blocked
validated   -> review_ready, blocked
review_ready-> applied, blocked
blocked     -> (no transitions)
applied     -> (no transitions)
```

### Proposal Lifecycle Transition Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `PR-001` | Proposal states MUST follow: `draft` -> `submitted` -> `review` -> `accepted`/`rejected`/`withdrawn` | error |
| `PR-002` | Terminal proposal states (`accepted`, `rejected`, `withdrawn`) CANNOT transition | critical |
| `PR-003` | A proposal CANNOT be `accepted` without a linked authoritative review receipt | error |
| `PR-004` | Proposal state transitions MUST produce corresponding AuditEvent | warning |

### Receipt Authority Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `RA-001` | All Rig domain receipts (workspace, validation, apply) MUST be authoritative (`authoritative=True`) | critical |
| `RA-002` | All connector-produced receipts MUST be advisory only (`authoritative=False, advisory_only=True`) | critical |
| `RA-003` | Public intake receipts MUST be advisory only | critical |
| `RA-004` | Funding pledge receipts MUST be advisory only | critical |
| `RA-005` | An advisory receipt CANNOT unblock an apply gate | critical |
| `RA-006` | An advisory receipt CANNOT override a blocked validation gate | critical |
| `RA-007` | Apply gate CANNOT be `allowed` if validation gate produced `blocked` | critical |
| `RA-008` | Apply gate CANNOT be authoritative if validation_failed | critical |

### Audit Event Linkage Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `AE-001` | Every authoritative mutation MUST have a corresponding AuditEvent | error |
| `AE-002` | Every AuditEvent with `authoritative=True` MUST have a receipt_id OR explicit reason why not | error |
| `AE-003` | AuditEvent.receipt_status MUST accurately reflect whether the linked receipt exists | error |
| `AE-004` | Authoritative AuditEvents MUST have `advisory_only=False` | critical |
| `AE-005` | Advisory-only AuditEvents MUST have `advisory_only=True, authoritative=False` | critical |
| `AE-006` | AuditEvent action MUST match the actual mutation performed | warning |

### Receipt Linkage Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `RL-001` | Every workspace MUST have at least one receipt path in `receipt_paths` after creation | error |
| `RL-002` | Every authoritative AuditEvent MUST have a corresponding receipt OR explicit NO_RECEIPT reason | error |
| `RL-003` | Receipt links in AuditReceiptLink MUST point to existing receipt files | warning |
| `RL-004` | `related_receipt_ids` in ReceiptEnvelope MUST reference existing receipts OR be empty | warning |
| `RL-005` | `related_audit_event_ids` in ReceiptEnvelope MUST reference existing audit events OR be empty | warning |

### Validation/Gate/Apply Relationship Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `VG-001` | Workspace CANNOT be "applied" without an authoritative apply receipt | critical |
| `VG-002` | Apply gate decision CANNOT be "allowed" if validation gate decision was "blocked" | critical |
| `VG-003` | validation_status "failed" MUST block apply_eligibility | critical |
| `VG-004` | gate_decision "blocked" MUST set apply_eligibility to False | critical |
| `VG-005` | Validation receipt MUST exist before review bundle can be created | error |
| `VG-006` | Review bundle receipt MUST exist before apply gate can be evaluated | error |
| `VG-007` | Apply receipt MUST reference validation, review, and execution receipts | error |

### Projection Completeness Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `PC-001` | Projections MUST expose `integrity_status` field | error |
| `PC-002` | Projection integrity fields MUST match canonical validation results | error |
| `PC-003` | Projections MUST never claim `authoritative_evidence_available=True` if no authoritative receipt exists | critical |
| `PC-004` | Frontend MUST never infer authority from projection data | critical |
| `PC-005` | What backend projects as readable, frontend MUST render as read-only | critical |

### Placeholder Semantics Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `PH-001` | Placeholder values MUST come from canonical placeholder constants | warning |
| `PH-002` | Placeholder values MUST NOT be used for authoritative fields | error |
| `PH-003` | Workspace fields with placeholder values MUST NOT be treated as valid | warning |
| `PH-004` | Receipt fields MUST NOT use placeholders for receipt_id, receipt_type, actor, subject | error |

### Receipt ID Uniqueness Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `RI-001` | All receipt_id values MUST be unique within a repository | critical |
| `RI-002` | Receipt IDs SHOULD be deterministic (same inputs = same ID) | info |
| `RI-003` | Duplicate receipt IDs are INVALID and indicate corruption | critical |

### Stale Receipt Detection Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `SR-001` | A receipt is STALE if it references non-existent paths | warning |
| `SR-002` | A receipt is STALE if its workspace_id references a non-existent workspace | warning |
| `SR-003` | A receipt is STALE if its related_receipt_ids reference non-existent receipts | warning |
| `SR-004` | Stale receipts MUST be detected and reported in integrity findings | info |

### Orphaned Audit Event Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `OA-001` | An audit event is ORPHANED if its workspace_id references a non-existent workspace | warning |
| `OA-002` | An audit event is ORPHANED if its receipt_id references a non-existent receipt | warning |
| `OA-003` | Orphaned audit events MUST be detected and reported | error |

### Orphaned Receipt Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `OR-001` | A receipt is ORPHANED if its workspace_id references a non-existent workspace | warning |
| `OR-002` | A receipt is ORPHANED if it exists without any corresponding audit event linking to it | info |
| `OR-003` | Orphaned receipts MUST be detected and reported | error |

### Invalid Authority Escalation Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `IE-001` | Advisory-only actors CANNOT produce authoritative receipts | critical |
| `IE-002` | Connector actors CANNOT produce authoritative receipts | critical |
| `IE-003` | Public intake actors CANNOT produce authoritative receipts | critical |
| `IE-004` | advisory_only=True receipt CANNOT transition workspace to applied | critical |
| `IE-005` | advisory_only=True receipt CANNOT override validation failure | critical |

### Impossible Gate State Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `IG-001` | validation_gate CANNOT be both "passed" and have failed validators | critical |
| `IG-002` | apply_gate CANNOT be "allowed" if validation_gate is "blocked" | critical |
| `IG-003` | apply_gate CANNOT be "allowed" if review_bundle.apply_eligibility is False | critical |
| `IG-004` | review_bundle CANNOT have apply_eligibility=True if validation_status is "failed" | critical |

### Review Bundle Linkage Invariants

| Invariant ID | Rule | Severity |
|--------------|------|----------|
| `RB-001` | Review bundle receipt MUST have valid workspace_id referencing existing workspace | error |
| `RB-002` | Review bundle receipt MUST link to validation receipt if validation was performed | error |
| `RB-003` | Corrupted review bundle linkage MUST produce explicit integrity findings | error |

---

## Integrity Check Categories

### Critical (impossible state, corruption detected)
- Duplicate receipt IDs
- Advisory receipt unblocks apply gate
- Invalid authority escalation
- Impossible gate states
- Workspace applied without authoritative apply receipt

### Error (violation of required invariants)
- Missing receipt links for authoritative events
- Orphaned audit events
- Orphaned receipts
- Validation/apply contradictions
- Invalid lifecycle transitions

### Warning (potential issues, manual review recommended)
- Stale receipt references
- Missing related receipt IDs
- Placeholder values in non-optional fields
- Incomplete audit trail chains

### Info (informational findings, best practice notes)
- Duplicate receipt paths (same receipt saved to multiple locations)
- Advisory-only receipts without explicit advisory marker
- Receipt chain gaps

---

## Detection Rules

### Missing Receipt Links Detection
```
For each AuditEvent:
  IF event.authoritative == True AND event.receipt_id IS NOT NULL:
    IF receipt file at expected path DOES NOT EXIST:
      FINDING: missing_receipt_link (error)
      Details: event_id, receipt_id, expected_path
```

### Orphaned Receipts Detection
```
For each receipt file in receipt_dir:
  IF receipt.workspace_id IS NOT NULL:
    IF workspace_record for workspace_id DOES NOT EXIST:
      FINDING: orphaned_receipt (warning)
      Details: receipt_id, workspace_id, receipt_path
  
  IF no AuditEvent.receipt_id references this receipt:
    FINDING: unlinked_receipt (info)
    Details: receipt_id, receipt_path
```

### Orphaned Audit Events Detection
```
For each audit event file in audit_dir:
  IF event.workspace_id IS NOT NULL:
    IF workspace_record for workspace_id DOES NOT EXIST:
      FINDING: orphaned_audit_event (warning)
      Details: event_id, workspace_id, event_path
  
  IF event.receipt_id IS NOT NULL AND receipt does NOT EXIST:
    FINDING: broken_receipt_link (error)
    Details: event_id, receipt_id
```

### Stale Receipt References Detection
```
For each receipt:
  For each input in receipt.inputs:
    IF input.reference is a path AND path DOES NOT EXIST:
      FINDING: stale_input_reference (warning)
      Details: receipt_id, input_id, reference_path
  
  For each output in receipt.outputs:
    IF output.reference is a path AND path DOES NOT EXIST:
      FINDING: stale_output_reference (warning)
      Details: receipt_id, output_id, reference_path
  
  For each evidence in receipt.evidence:
    IF evidence.reference is a path AND path DOES NOT EXIST:
      FINDING: stale_evidence_reference (warning)
      Details: receipt_id, evidence_id, reference_path
```

### Advisory Authority Leaks Detection
```
For each receipt:
  IF receipt.authoritative == False AND receipt.advisory_only == True:
    IF receipt.receipt_type IN authoritative-only types:
      FINDING: advisory_authority_leak (critical)
      Details: receipt_id, receipt_type, actor
  
  For each related_receipt_id:
    IF related receipt is advisory_and this receipt claims it as authoritative:
      FINDING: advisory_authority_leak (critical)
      Details: receipt_id, related_receipt_id
```

### Impossible Lifecycle Transitions Detection
```
For each workspace:
  For each transition in status_history:
    IF transition NOT IN ALLOWED_TRANSITIONS for previous status:
      FINDING: invalid_lifecycle_transition (error)
      Details: workspace_id, from_status, to_status
```

### Validation/Apply Contradictions Detection
```
For each workspace:
  IF validation_status == "failed" AND status == "applied":
    FINDING: validation_apply_contradiction (critical)
    Details: workspace_id
  
  IF validation_status == "failed" AND apply_eligibility == True:
    FINDING: validation_apply_contradiction (critical)
    Details: workspace_id
  
  For apply gate decision:
    IF gate_decision == "allowed" AND validation_gate_decision == "blocked":
      FINDING: gate_contradiction (critical)
      Details: workspace_id
```

### Duplicate Receipt IDs Detection
```
Collect all receipt IDs from receipt_dir:
  IF any receipt_id appears more than once:
    FINDING: duplicate_receipt_id (critical)
    Details: receipt_id, list of paths
```

### Projection Authority Mismatch Detection
```
For each projection:
  IF projection.integrity_status == "clean":
    Verify all authoritative receipts referenced actually exist
    IF any referenced receipt does NOT exist:
      FINDING: projection_authority_mismatch (error)
      Details: projection_type, missing_receipt_id
```

### Invalid Placeholder Usage Detection
```
For each receipt:
  IF receipt.receipt_id == PLACEHOLDER_*:
    FINDING: invalid_placeholder_usage (error)
    Details: receipt_id, field_name
  
  IF receipt.actor.actor_id == PLACEHOLDER_UNKNOWN AND receipt.authoritative == True:
    FINDING: invalid_placeholder_usage (error)
    Details: receipt_id
```

### Missing Canonical Fields Detection
```
For each receipt:
  IF receipt_id IS NULL OR empty:
    FINDING: missing_canonical_field (error)
    Details: receipt_type, missing_field
  
  IF receipt_type IS NULL OR empty:
    FINDING: missing_canonical_field (error)
    Details: receipt_id, missing_field
  
  IF created_at IS NULL OR empty:
    FINDING: missing_canonical_field (warning)
    Details: receipt_id
```

### Invalid Receipt Authority Escalation Detection
```
For each receipt:
  IF actor.actor_kind == "connector" AND authoritative == True:
    FINDING: invalid_authority_escalation (critical)
    Details: receipt_id, actor_kind
  
  IF receipt_type IN ("public_sync", "public_intake_packet", "funding_pledge") AND authoritative == True:
    FINDING: invalid_authority_escalation (critical)
    Details: receipt_id, receipt_type
```

### Incomplete Audit Trail Chains Detection
```
For each workspace:
  Collect all AuditEvents for workspace
  
  IF workspace has status != "planned":
    IF no AuditEvent for workspace creation:
      FINDING: incomplete_audit_trail (error)
      Details: workspace_id, missing_event_type
  
  IF workspace status == "applied":
    IF no AuditEvent for workspace apply:
      FINDING: incomplete_audit_trail (error)
      Details: workspace_id
```

---

## Severity Level Definitions

| Severity | Meaning | Required Action |
|----------|---------|-----------------|
| `critical` | Corruption detected, impossible state exists | IMMEDIATE manual intervention required |
| `error` | Invariant violation, state is invalid | Manual investigation and repair required |
| `warning` | Potential issue, may indicate drift | Review recommended |
| `info` | Informational, best practice note | Optional review |

---

## Non-Goals

 these are NOT covered by this integrity system:

- File content validation (syntax, type checking) - handled by separate systems
- Git repository structural integrity - out of scope
- External system data accuracy - connectors provide advisory data only
- Performance or scalability issues
- Network connectivity problems

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-01 | Initial canonical integrity rules for Phase 3 |
