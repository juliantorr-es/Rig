# Projection Contract Lockdown - Phase 4

> **Status:** IN PROGRESS
> **Priority:** CRITICAL
> **Do Not Start:** Without reading AGENTS.md Git discipline rules

## Summary

Phase 4 locks down projections as governed presentation contracts derived solely from canonical authority state. This is the final layer of Rig's authority model: receipts and audit events are the source of truth, and projections are the guaranteed-accurate presentation of that truth to the frontend.

**Core Problem:**
- Projections exist and are consumed by frontend widgets
- But projection output is not fully deterministic or locked down
- Authority claims in projections are not systematically checked against receipt/audit backing
- No golden tests prevent projection shape drift
- No frontend integrity status widget exists to show projection health

**Core Solution:**
- Formal projection contracts with required/optional/placeholder/authority fields
- Projection validation engine integrated with existing integrity checks
- Golden snapshot tests that fail on any projection shape drift
- IntegrityStatusCard widget showing projection contract health
- Projection builder integration to surface contract status

## Non-Goals (STRICT)

- NO new product features
- NO monetization work
- NO external connectors
- NO databases
- NO background workers
- NO OAuth
- NO SaaS work
- NO frontend authority logic (widgets remain dumb renderers)
- NO destructive Git commands
- NO staging
- NO commits

## Doctrine

```
Projections are Presentation Contracts
├── Derived from canonical authority state only
├── Rendered by dumb frontend widgets
├── Never authoritative themselves
└── Always traceable to receipts/audit events

Frontend Widgets
├── Render projection data ONLY
├── Never fetch
├── Never mutate
├── Never decide authority
├── textContent only (no innerHTML)
└── Safe fallbacks for all missing fields
```

## Authority Chain

```
Canonical Receipts + Audit Events (SOURCE OF TRUTH)
    ↓
    Workspace Domain (workspace.py)
    ↓
    Workspace Status Summary (workspace_status.py)
    ↓
    Projection Contracts (projection_contracts.py) [NEW]
    ↓
    Projection Builder (projection_builder.py) [UPDATED]
    ↓
    UI Projection (projections.py)
    ↓
    Widget Registry (registry.js)
    ↓
    Frontend Renderers (widgets/*.js)
    ↓
    Integrity Status Card (integrity-status-card.js) [NEW]
```

## Phase Deliverables

### Phase 1 - Projection Contract Inventory ✅

**File:** `docs/architecture/projection-contract-lockdown.md`

Document every widget/projection contract:
- Widget type
- Projection source
- Canonical authority source
- Required/optional/placeholder fields
- Authority-sensitive fields
- Receipt-backed fields
- Audit-backed fields
- Frontend renderer file
- Test coverage
- Drift risk

**Status:** COMPLETE

---

### Phase 2 - Canonical Projection Contracts

**File:** `src/rig/domain/projection_contracts.py` [NEW]

Implement:
```python
- ProjectionContract
- ProjectionField
- ProjectionAuthorityBinding
- ProjectionContractViolation
- ProjectionContractCheckResult
```

Each contract supports:
- Required fields
- Placeholder policy
- Allowed value sets
- Authority binding metadata
- Receipt-backed requirement flag
- Audit-backed requirement flag
- Deterministic validation ordering

Contracts for:
- ProposalLifecycleConsole
- AuditTrailCard
- FundingSummaryCard
- ReceiptSummaryCard
- IntegrityStatusCard [NEW]
- BackendStatus
- EmptyStateCard
- WorkspaceHeader
- WorkspaceGitState
- WorkspaceLaneSummary
- ValidatorStack
- CommandProgressCard
- EvidenceCard
- ReceiptList

**Status:** NOT STARTED

---

### Phase 3 - Projection Validation Engine

**File:** `src/rig/domain/integrity.py` [UPDATED]

Add helpers:
```python
- validate_projection_contract()
- validate_projection_authority_bindings()
- validate_projection_placeholders()
- validate_projection_receipt_backing()
- validate_projection_audit_backing()
- build_projection_contract_summary()
```

Rules:
- Deterministic validation only
- No frontend logic
- No filesystem mutation
- No hidden repair
- Uses existing IntegrityFinding/IntegrityCheckResult patterns
- Missing fields produce explicit findings
- Authority claims without receipt/audit backing produce errors/critical

**File:** `src/rig/commands_doctor.py` [UPDATED]

Update `rig doctor projections` to output:
- Contract count
- Projection violation count
- Missing required fields
- Authority binding failures
- Placeholder violations
- Receipt backing failures
- Audit backing failures

**File:** `src/rig/commands_doctor.py` [UPDATED]

Update `rig doctor all` to include projection validation

**Status:** NOT STARTED

---

### Phase 4 - Golden Projection Snapshots

**Directory:** `tests/golden/projections/` [NEW]

Deterministic snapshot fixtures:
1. `empty_workspace_projection.json`
2. `workspace_with_canonical_receipts.json`
3. `workspace_with_missing_receipts.json`
4. `workspace_with_advisory_only_data.json`
5. `workspace_with_validation_failure.json`
6. `workspace_with_review_apply_chain.json`
7. `corrupted_authority_projection.json`

**File:** `tests/test_projection_contracts.py` [NEW]

Golden tests that:
- Normalize volatile fields (timestamps, repo paths)
- Use stable JSON key ordering
- Fail on required field disappearance
- Fail on authority-sensitive field name drift
- Fail on placeholder semantics drift
- Fail on receipt/audit-backed fields becoming unbacked
- Fail on frontend widget contract mismatch

**Status:** NOT STARTED

---

### Phase 5 - Frontend Integrity Surface

**File:** `src/rig_tools/static/js/widgets/integrity-status-card.js` [NEW]

Implement IntegrityStatusCard widget:
- Projection-only (no fetching, no mutation)
- Dumb renderer (textContent/createElement only)
- Safe fallbacks for all missing fields
- Deterministic output
- Registered in widget registry

Renders:
- integrity_status
- contract_status
- projection_violation_count
- authority_mismatch_count
- receipt_backing_failure_count
- audit_backing_failure_count
- next_integrity_action

**File:** `tests/test_ui_frontend_logic.py` [UPDATED]

Add tests for:
- Clean projection
- Missing fields
- Authority mismatch
- Advisory-only warning
- Critical violation

**File:** `src/rig_tools/static/js/widgets/registry.js` [UPDATED]

Register IntegrityStatusCard in widget registry.

**Status:** NOT STARTED

---

### Phase 6 - Projection Builder Integration

**File:** `src/rig/domain/projection_builder.py` [UPDATED]

Update build_projection() and _build_empty_projection() to include:
- integrity_status
- projection_contract_status
- projection_violation_count
- authority_mismatch_count
- receipt_backing_failure_count
- audit_backing_failure_count
- stale_receipt_detected
- orphaned_receipt_detected
- orphaned_audit_detected
- next_integrity_action

Rules:
- These fields come from canonical integrity/projection validation
- No heuristic authority inference
- Use explicit placeholders where data is missing
- Avoid recursive projection validation loops

**Status:** NOT STARTED

---

## Validation Commands (Must All Pass)

```bash
# Syntax
python3.14 -m compileall -q src tests

# Type checking
python3.14 -m pyright --project pyrightconfig.json

# Targeted linting
python3.14 -m ruff check src/rig/domain/projection_contracts.py
python3.14 -m ruff check tests/test_projection_contracts.py

# Unit tests
python3.14 -m pytest tests/test_integrity.py
python3.14 -m pytest tests/test_receipt_envelope.py
python3.14 -m pytest tests/test_workspace_audit.py
python3.14 -m pytest tests/test_workspace_control_plane.py
python3.14 -m pytest tests/test_ui_frontend_logic.py
python3.14 -m pytest tests/test_projection_contracts.py

# Doctor validation
python3.14 -m rig doctor projections
python3.14 -m rig doctor all

# CLI validation
python3.14 -m rig --help
python3.14 -m rig ui --help
python3.14 -m rig window open --dry-run
```

## Documentation Deliverables

1. `docs/architecture/projection-contract-lockdown.md` ✅ COMPLETE
2. `docs/sprints/projection-contract-lockdown-phase-4.md` ✅ COMPLETE
3. `docs/architecture/integrity-validation.md` [UPDATED]
4. `docs/architecture/projection-renderer-frontend.md` [NEW]

## Acceptance Criteria

This task is **NOT COMPLETE** unless all of the following are true:

- [ ] Projection contracts module exists (`src/rig/domain/projection_contracts.py`)
- [ ] Projection contracts defined for all existing widgets
- [ ] `rig doctor projections` validates contract violations
- [ ] `rig doctor all` includes projection validation
- [ ] Golden projection snapshots exist (`tests/golden/projections/`)
- [ ] Golden snapshot tests exist and pass (`tests/test_projection_contracts.py`)
- [ ] Authority claims checked against canonical receipt/audit backing
- [ ] IntegrityStatusCard frontend widget exists and renders
- [ ] IntegrityStatusCard registered in widget registry
- [ ] Projection builder includes contract validation fields
- [ ] All validation commands pass
- [ ] All documentation complete

## Implementation Order

```
1. Phase 1: Projection Contract Inventory ✅
   └── docs/architecture/projection-contract-lockdown.md

2. Phase 2: Canonical Projection Contracts
   └── src/rig/domain/projection_contracts.py

3. Phase 3: Projection Validation Engine
   ├── src/rig/domain/integrity.py (update)
   └── src/rig/commands_doctor.py (update)

4. Phase 4: Golden Projection Snapshots
   ├── tests/golden/projections/
   └── tests/test_projection_contracts.py

5. Phase 5: Frontend Integrity Surface
   ├── src/rig_tools/static/js/widgets/integrity-status-card.js
   └── src/rig_tools/static/js/widgets/registry.js (update)

6. Phase 6: Projection Builder Integration
   └── src/rig/domain/projection_builder.py (update)

7. Documentation Updates
   ├── docs/architecture/integrity-validation.md
   └── docs/architecture/projection-renderer-frontend.md
```

## Rollback Constraints

- NO destructive Git commands
- NO commits (even if user requests)
- NO staging
- Preserve pre-existing dirty files (src/rig/commands_doctor.py is modified)
- Patch-forward only

## File Change Summary (Expected)

**Created:**
- `src/rig/domain/projection_contracts.py`
- `tests/test_projection_contracts.py`
- `src/rig_tools/static/js/widgets/integrity-status-card.js`
- `tests/golden/projections/*.json` (multiple)
- `docs/architecture/projection-contract-lockdown.md`
- `docs/sprints/projection-contract-lockdown-phase-4.md`
- `docs/architecture/integrity-validation.md` (if not exists)
- `docs/architecture/projection-renderer-frontend.md`

**Modified:**
- `src/rig/domain/integrity.py` (add projection validation helpers)
- `src/rig/commands_doctor.py` (add projection validation command)
- `src/rig/domain/projection_builder.py` (add integrity fields)
- `src/rig_tools/static/js/widgets/registry.js` (register IntegrityStatusCard)
- `tests/test_ui_frontend_logic.py` (add frontend integrity tests)

**Not Modified:**
- Any external connector files
- Any database-related files
- Any OAuth/SaaS files
- Any monetization files
