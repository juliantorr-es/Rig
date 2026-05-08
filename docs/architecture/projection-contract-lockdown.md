# Projection Contract Lockdown

> **Phase 4: Projection Contract Lockdown**
> See: [sprints/projection-contract-lockdown-phase-4.md](../sprints/projection-contract-lockdown-phase-4.md)

## Overview

Rig projections are the **presentation layer** that renders canonical authority state to the frontend. Projections must be:

1. **Deterministic** - Same input state produces identical output
2. **Receipt-backed** - All authoritative claims trace to canonical receipts
3. **Audit-aware** - Projection data reflects audit trail state
4. **Contract-locked** - Widget contracts are stable and versioned

**Core Doctrine:**
> Projections are presentation contracts derived from canonical authority state.
> Frontend widgets render projection data only.
> No projection may claim authority that cannot be traced to canonical receipts/audit events.

## Authority Chain

```
Canonical Authority State (Receipts + Audit Events)
    ↓
Workspace Domain State (workspace.py)
    ↓
Workspace Status Summary (workspace_status.py)
    ↓
Projection Builder (projection_builder.py)
    ↓
UI Projection (projections.py)
    ↓
Widget Registry (registry.js)
    ↓
Frontend Renderers (widgets/*.js)
```

## Current Projection Contract Inventory

### Widget Type: AppTitle

| Aspect | Value |
|--------|-------|
| **Widget Type** | AppTitle |
| **Projection Source** | projection_builder.py: `_build_empty_projection()`, `build_projection()` |
| **Canonical Authority Source** | None (static display) |
| **Required Fields** | title, subtitle |
| **Optional Fields** | None |
| **Placeholder Fields** | subtitle (empty string) |
| **Authority-Sensitive Fields** | None |
| **Receipt-Backed Fields** | No |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | registry.js (inline) |
| **Current Test Coverage** | None |
| **Drift Risk** | Low |

---

### Widget Type: GateBadge

| Aspect | Value |
|--------|-------|
| **Widget Type** | GateBadge |
| **Projection Source** | projection_builder.py: `_build_empty_projection()`, `build_projection()` |
| **Canonical Authority Source** | WorkspaceStatusSummary |
| **Required Fields** | label, severity |
| **Optional Fields** | None |
| **Placeholder Fields** | severity (defaults to "info"), label |
| **Authority-Sensitive Fields** | label (workspace status) |
| **Receipt-Backed Fields** | No |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | registry.js (inline) |
| **Current Test Coverage** | None |
| **Drift Risk** | Low |

---

### Widget Type: MetricStack

| Aspect | Value |
|--------|-------|
| **Widget Type** | MetricStack |
| **Projection Source** | projection_builder.py: `_build_empty_projection()`, `build_projection()` |
| **Canonical Authority Source** | Workspace records, queue snapshot |
| **Required Fields** | title, items |
| **Optional Fields** | None |
| **Placeholder Fields** | items (empty list) |
| **Authority-Sensitive Fields** | items.values (job count, workspace count, provider count) |
| **Receipt-Backed Fields** | No (advisory queue state) |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | registry.js (inline) |
| **Current Test Coverage** | None |
| **Drift Risk** | Medium (queue snapshot is advisory) |

---

### Widget Type: WorkspaceHeader

| Aspect | Value |
|--------|-------|
| **Widget Type** | WorkspaceHeader |
| **Projection Source** | projection_builder.py: `_workspace_header_widget()` |
| **Canonical Authority Source** | WorkspaceStatusSummary |
| **Required Fields** | repo_root, workspace_id, workspace_status, workspace_path, branch, head |
| **Optional Fields** | authority_label |
| **Placeholder Fields** | workspace_id (None), workspace_path (None), head (None) |
| **Authority-Sensitive Fields** | workspace_id, workspace_status, workspace_path, branch, head |
| **Receipt-Backed Fields** | No |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | workspace-header.js |
| **Current Test Coverage** | test_workspace_control_plane.py (implicit) |
| **Drift Risk** | Low |

**Renderer Contract:**
- repo_root: string
- workspace_id: string | null
- workspace_status: string
- workspace_path: string | null
- branch: string
- head: string | null
- authority_label: string

---

### Widget Type: WorkspaceGitState

| Aspect | Value |
|--------|-------|
| **Widget Type** | WorkspaceGitState |
| **Projection Source** | projection_builder.py: `_workspace_git_state_widget()` |
| **Canonical Authority Source** | git commands (subprocess) |
| **Required Fields** | branch, head, dirty, dirty_files_count, safe_to_commit |
| **Optional Fields** | reason |
| **Placeholder Fields** | branch ("HEAD"), head (None), dirty (false) |
| **Authority-Sensitive Fields** | branch, head, dirty, safe_to_commit |
| **Receipt-Backed Fields** | No |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | workspace-git-state.js |
| **Current Test Coverage** | test_workspace_control_plane.py |
| **Drift Risk** | Low |

**Renderer Contract:**
- branch: string
- head: string | null
- dirty: boolean
- dirty_files_count: number
- safe_to_commit: boolean
- reason: string

---

### Widget Type: WorkspaceLaneSummary

| Aspect | Value |
|--------|-------|
| **Widget Type** | WorkspaceLaneSummary |
| **Projection Source** | projection_builder.py: `_workspace_lane_summary_widget()` |
| **Canonical Authority Source** | Workspace records list |
| **Required Fields** | status, lane_count, active_lanes, clean_lanes, review_ready_lanes, workspace_records, connected, message |
| **Optional Fields** | next_action |
| **Placeholder Fields** | status ("not_connected"), lane_count (0), connected (false) |
| **Authority-Sensitive Fields** | All fields (advisory - agent lanes not connected) |
| **Receipt-Backed Fields** | No |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | workspace-lane-summary.js |
| **Current Test Coverage** | test_workspace_control_plane.py |
| **Drift Risk** | **HIGH** - Advisory only, not connected to workspace integration yet |

**Renderer Contract:**
- status: string
- lane_count: number
- active_lanes: number
- clean_lanes: number
- review_ready_lanes: number
- workspace_records: number
- connected: boolean
- message: string
- next_action: string

---

### Widget Type: ProposalLifecycleConsole

| Aspect | Value |
|--------|-------|
| **Widget Type** | ProposalLifecycleConsole |
| **Projection Source** | proposal_lifecycle.py: `build_proposal_lifecycle_projection()` |
| **Canonical Authority Source** | WorkspaceStatusSummary, workspace records |
| **Required Fields** | lifecycle_id, stage, title, summary, current_gate, allowed_actions, blocked_actions, next_safe_action, recommendation_state, proposal_state, validation_state, progress_state, auditability_state, warnings, metadata |
| **Optional Fields** | workspace_path |
| **Placeholder Fields** | stage ("workspace_unselected"), title, summary, recommendation_state (unknown), proposal_state (unknown), validation_state (unknown) |
| **Authority-Sensitive Fields** | stage, current_gate, recommendation_state, proposal_state, validation_state |
| **Receipt-Backed Fields** | Yes (validation_state, proposal_state via workspace records) |
| **Audit-Backed Fields** | Yes (auditability_state) |
| **Frontend Renderer File** | proposal-lifecycle-console.js |
| **Current Test Coverage** | test_workspace_control_plane.py, test_ui_frontend_logic.py |
| **Drift Risk** | **HIGH** - Core lifecycle widget, must be locked down |

**Renderer Contract:**
- lifecycle_id: string
- stage: string
- title: string
- summary: string
- workspace_path: string | null
- current_gate: string
- allowed_actions: array of {id, label, enabled, description}
- blocked_actions: array of {id, label, reason}
- next_safe_action: string
- recommendation_state: object with status, title, summary, source_surface, files, last_updated, next_action
- proposal_state: object with status, title, summary, worktree_path, changed_files, next_action
- validation_state: object with status, title, summary, surface, command, passed_count, failed_count, last_run_at, proof_status, next_action
- progress_state: object with transient (must be true), source (must be "progress_event")
- auditability_state: object with progress_receipts (must be "not_created"), progress_receipt_plan (must be "advisory_only"), receipt_candidate (must be "inert"), evidence_refs (must be "inert")
- warnings: array of strings
- metadata: object

**Authority Boundaries (INVARIANTS):**
- `progress_state.transient` MUST be `true`
- `progress_state.source` MUST be `"progress_event"`
- `auditability_state.progress_receipts` MUST be `"not_created"`
- `auditability_state.progress_receipt_plan` MUST be `"advisory_only"`
- `auditability_state.receipt_candidate` MUST be `"inert"`
- `auditability_state.evidence_refs` MUST be `"inert"`
- NO receipts may be created by this projection
- NO progress events may be persisted

---

### Widget Type: AuditTrailCard

| Aspect | Value |
|--------|-------|
| **Widget Type** | AuditTrailCard |
| **Projection Source** | projection_builder.py: `_workspace_audit_trail_widget()` |
| **Canonical Authority Source** | WorkspaceAuditTrail, workspace records, audit directory, receipt directory |
| **Required Fields** | audit_completeness, last_authoritative_event_id, receipt_status_summary, missing_receipts, advisory_only_events, authoritative_events |
| **Optional Fields** | next_missing_audit_action, advisory_only_warning |
| **Placeholder Fields** | audit_completeness ("not_created"/"unknown"), last_authoritative_event_id ("unknown"), missing_receipts (empty) |
| **Authority-Sensitive Fields** | audit_completeness, authoritative_events, missing_receipts |
| **Receipt-Backed Fields** | Yes (receipt_status_summary, receipt counting) |
| **Audit-Backed Fields** | Yes (audit directory scanning, audit events) |
| **Frontend Renderer File** | audit-trail-card.js |
| **Current Test Coverage** | test_workspace_control_plane.py (implicit) |
| **Drift Risk** | Medium |

**Renderer Contract:**
- audit_completeness: string ("unknown", "not_created", "not_proof", "not_run", "complete")
- last_authoritative_event_id: string | "unknown"
- receipt_status_summary: object with counts by receipt kind
- missing_receipts: array of strings (receipt kinds that are missing)
- advisory_only_events: number
- authoritative_events: number
- advisory_only_warning: string (always present)
- next_missing_audit_action: string (placeholder or action description)

---

### Widget Type: EmptyStateCard

| Aspect | Value |
|--------|-------|
| **Widget Type** | EmptyStateCard |
| **Projection Source** | projection_builder.py: `_build_empty_projection()` |
| **Canonical Authority Source** | None (static messages) |
| **Required Fields** | title, body |
| **Optional Fields** | actions |
| **Placeholder Fields** | title, body |
| **Authority-Sensitive Fields** | None |
| **Receipt-Backed Fields** | No |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | empty-state-card.js |
| **Current Test Coverage** | test_ui_frontend_logic.py |
| **Drift Risk** | Low |

**Renderer Contract:**
- title: string
- body: string
- actions: array | undefined

---

### Widget Type: EvidenceCard

| Aspect | Value |
|--------|-------|
| **Widget Type** | EvidenceCard |
| **Projection Source** | projection_builder.py: `_build_empty_projection()`, `build_projection()` |
| **Canonical Authority Source** | Validation results, receipts |
| **Required Fields** | title, state, body |
| **Optional Fields** | None |
| **Placeholder Fields** | state.label ("None"/"Available"), state.severity ("idle"/"info") |
| **Authority-Sensitive Fields** | state, body |
| **Receipt-Backed Fields** | No (references validation receipts) |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | registry.js (inline) |
| **Current Test Coverage** | None |
| **Drift Risk** | Low |

**Renderer Contract:**
- title: string
- state: object with label (string) and severity (string)
- body: string

---

### Widget Type: ValidatorStack

| Aspect | Value |
|--------|-------|
| **Widget Type** | ValidatorStack |
| **Projection Source** | projection_builder.py: `build_projection()` |
| **Canonical Authority Source** | Workspace validation results |
| **Required Fields** | title, state, summary, items, run_in_progress, running_validator_id |
| **Optional Fields** | None |
| **Placeholder Fields** | state (missing), summary ("No validation performed yet."), items (empty), run_in_progress (false) |
| **Authority-Sensitive Fields** | state, items, summary |
| **Receipt-Backed Fields** | Yes (validator receipts via workspace) |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | validator-stack.js |
| **Current Test Coverage** | test_ui_frontend_logic.py |
| **Drift Risk** | Low |

**Renderer Contract:**
- title: string
- state: object with label (string) and severity (string)
- summary: string
- items: array of ValidatorItem
- run_in_progress: boolean
- running_validator_id: string | null

---

### Widget Type: ReceiptList

| Aspect | Value |
|--------|-------|
| **Widget Type** | ReceiptList |
| **Projection Source** | projection_builder.py: `_build_empty_projection()`, `build_projection()` |
| **Canonical Authority Source** | Receipt store, workspace receipt paths |
| **Required Fields** | title, receipts |
| **Optional Fields** | None |
| **Placeholder Fields** | receipts (empty list) |
| **Authority-Sensitive Fields** | receipts |
| **Receipt-Backed Fields** | **YES** - Directly backed by ReceiptEnvelope.to_projection() |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | receipt-list.js |
| **Current Test Coverage** | None |
| **Drift Risk** | Low |

**Renderer Contract:**
- title: string
- receipts: array of ReceiptProjection objects

---

### Widget Type: BackendStatus

| Aspect | Value |
|--------|-------|
| **Widget Type** | BackendStatus |
| **Projection Source** | projection_builder.py: `_workspace_command_progress_widget()` |
| **Canonical Authority Source** | None (static) |
| **Required Fields** | title, body, revision |
| **Optional Fields** | None |
| **Placeholder Fields** | None |
| **Authority-Sensitive Fields** | None |
| **Receipt-Backed Fields** | No |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | backend-status.js |
| **Current Test Coverage** | None |
| **Drift Risk** | Low |

**Renderer Contract:**
- title: string
- body: string
- revision: number

---

### Widget Type: CommandProgressCard

| Aspect | Value |
|--------|-------|
| **Widget Type** | CommandProgressCard |
| **Projection Source** | projection_builder.py: `_workspace_command_progress_widget()` |
| **Canonical Authority Source** | Progress events (future) |
| **Required Fields** | command, phase, status, level, message, sequence, timestamp, events, metadata |
| **Optional Fields** | None |
| **Placeholder Fields** | command (""), phase ("operation.log"), status ("unknown"), events (empty) |
| **Authority-Sensitive Fields** | All (currently advisory/placeholder) |
| **Receipt-Backed Fields** | No |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | command-progress-card.js |
| **Current Test Coverage** | test_ui_frontend_logic.py |
| **Drift Risk** | Medium (future-proofing needed) |

**Renderer Contract:**
- command: string
- phase: string
- status: string
- level: string
- message: string
- sequence: number
- timestamp: string (ISO)
- events: array
- metadata: object

---

### Widget Type: FundingSummaryCard

| Aspect | Value |
|--------|-------|
| **Widget Type** | FundingSummaryCard |
| **Projection Source** | public_intake.py (advisory only) |
| **Canonical Authority Source** | NONE - External systems are NOT authoritative |
| **Required Fields** | title, summary, total, advisory_note |
| **Optional Fields** | pledge_count, backer_count, funding_status |
| **Placeholder Fields** | All fields have advisory defaults |
| **Authority-Sensitive Fields** | NONE - All data is advisory_only |
| **Receipt-Backed Fields** | No (external data) |
| **Audit-Backed Fields** | No |
| **Frontend Renderer File** | funding-summary-card.js |
| **Current Test Coverage** | None |
| **Drift Risk** | **CRITICAL** - Must always show advisory_only warning |

**Renderer Contract:**
- title: string
- summary: string
- total: number
- advisory_note: string (MUST contain "advisory_only" warning)
- pledge_count: number (optional)
- backer_count: number (optional)
- funding_status: string (optional)

**INVARIANT:** This widget MUST display a clear advisory-only warning. External funding systems are NOT authoritative.

---

## Integrity Status Card (NEW - Phase 4)

| Aspect | Value |
|--------|-------|
| **Widget Type** | IntegrityStatusCard |
| **Projection Source** | projection_builder.py (to be added) |
| **Canonical Authority Source** | IntegritySummary from integrity.py |
| **Required Fields** | integrity_status, contract_status, projection_violation_count, authority_mismatch_count, receipt_backing_failure_count, audit_backing_failure_count, next_integrity_action |
| **Optional Fields** | stale_receipt_detected, orphaned_receipt_detected, orphaned_audit_detected |
| **Placeholder Fields** | integrity_status ("unknown"), next_integrity_action ("No integrity issues detected") |
| **Authority-Sensitive Fields** | All fields |
| **Receipt-Backed Fields** | Yes (via integrity validation) |
| **Audit-Backed Fields** | Yes (via integrity validation) |
| **Frontend Renderer File** | integrity-status-card.js (to be created) |
| **Current Test Coverage** | To be added |
| **Drift Risk** | Medium |

## Contract Violation Tracking

Projections are locked down as governed contracts through:

1. **Required Field Validation**: All required fields must be present
2. **Placeholder Policy**: Explicit placeholders for missing data (never null/undefined)
3. **Authority Binding**: Authority-sensitive fields must trace to canonical state
4. **Receipt-Backed Check**: Fields claiming receipt backing must have audit trail evidence
5. **Audit-Backed Check**: Fields claiming audit backing must have audit event evidence

### Violation Codes for Projection Contracts

| Code | Severity | Description |
|------|----------|-------------|
| PC-001 | WARNING | Projection missing integrity_status field |
| PC-002 | ERROR | Projection integrity status mismatch |
| PC-003 | CRITICAL | Frontend claims authority not backed by receipts/audit |
| PC-004 | ERROR | Frontend contains authority inference logic |
| PC-005 | ERROR | Read-only violation (projection claims to mutate state) |
| PH-002 | ERROR | Invalid placeholder usage |
| PH-004 | ERROR | Authoritative field has placeholder value |

## Golden Snapshot Policy

Golden snapshots lock down projection shape to prevent drift:

1. **Snapshot Location**: `tests/golden/projections/`
2. **Normalization**: Volatile fields (timestamps, paths) normalized before comparison
3. **Stable JSON**: Key ordering is stable (sorted)
4. **Failure Modes**: Tests fail if required fields disappear or authority claims drift

### Golden Snapshot Fixtures Required

1. `empty_workspace_projection.json` - No active workspace
2. `workspace_with_canonical_receipts.json` - Full receipt chain
3. `workspace_with_missing_receipts.json` - Partial receipt chain
4. `workspace_with_advisory_only_data.json` - Public intake/funding only
5. `workspace_with_validation_failure.json` - Validation failed state
6. `workspace_with_review_apply_chain.json` - Full review/apply receipt chain
7. `corrupted authority_projection.json` - Authority mismatch for testing

## Frontend Renderer Boundaries

**DOCTRINE:**
- Widgets are dumb renderers
- NO fetching from external sources
- NO mutation of state
- NO timers or async behavior
- textContent only (XSS-safe)
- Safe fallbacks for all missing fields
- Deterministic output

**FORBIDDEN in Widget Renderers:**
- `fetch()`, `XMLHttpRequest`
- `setInterval`, `setTimeout`
- `innerHTML` (use `textContent`)
- Direct access to backend APIs
- Mutation of projection data
- Authority inference logic

## Projection Contract Lockdown Checklist

- [ ] All widgets documented with full contract inventory
- [ ] Projection contract module implemented (projection_contracts.py)
- [ ] Contracted validation wired into integrity.py
- [ ] rig doctor projections validates all contracts
- [ ] Golden snapshots created and locked
- [ ] IntegrityStatusCard widget implemented
- [ ] Projection builder includes contract status fields
- [ ] All validation commands pass
- [ ] Documentation complete
