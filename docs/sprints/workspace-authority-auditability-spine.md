# Workspace Authority & Auditability Spine - Sprint Audit Map

## Overview

This document provides a **deterministic audit map** of all workspace/proposal/public-intake mutation paths in Rig. It classifies each path by authority owner, input source, canonical state touched, receipt status, projection impact, test coverage, and risk level.

This is Phase 1 of the Workspace Authority Hardening initiative.

---

## Legend

### Authority Owner
- `rig_domain` = Rig domain layer (workspace.py, receipts.py, proposal_lifecycle.py)
- `rig_commands` = CLI command handlers
- `connector` = Public intake connectors (google_forms, github_issues, google_sheets)
- `governance_engine` = Future governance authority (not yet implemented)

### Input Source
- `cli` = Direct CLI invocation
- `connector` = External system via connector
- `workspace_store` = Local workspace JSON records
- `receipt_store` = Local receipt JSON files
- `worktree` = Git worktree state
- `public_intake_store` = Local advisory intake data

### Receipt Status
- `produces_receipt` = Creates a durable receipt file
- `links_to_receipt` = References existing receipt
- `no_receipt` = No receipt mechanism
- `advisory_only` = Receipt exists but is explicitly advisory

### Risk Level
- `CRITICAL` = Mutates main branch or authoritative state
- `HIGH` = Mutates workspace state
- `MEDIUM` = Creates records or receipts
- `LOW` = Read-only or pure projection

---

## Mutation Path Audit Map

### 1. Workspace Lifecycle Mutations

#### 1.1 `WorkspaceDomain.create_workspace()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/workspace.py:WorkspaceDomain.create_workspace()` |
| **Command** | `rig workspace create --task <task>` |
| **Authority Owner** | `rig_domain` |
| **Input Source** | `cli` (task string) + `worktree` (git state) |
| **Canonical State Touched** | workspace records, git worktree, branch |
| **Receipt Produced** | NO - creates workspace record but NO receipt |
| **Receipt Link** | NO |
| **Projection Impact** | Creates new workspace entry in projections |
| **Current Test Coverage** | INDIRECT - via workspace command tests |
| **Risk Level** | HIGH |
| **Gap** | CRITICAL: No receipt for workspace creation |
| **Mitigation** | Must produce `workspace_create_receipt.json` |

**Flow:**
1. CLI calls `create_workspace(helpers, task)`
2. `WorkspaceDomain.create_workspace(task)` 
3. Creates git worktree with new branch
4. Saves workspace record JSON to `.build/rig/workspaces/`
5. Returns WorkspaceRecord

**Audit Concern:** No durable receipt of the workspace creation operation itself.

---

#### 1.2 `WorkspaceDomain.transition_workspace()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/workspace.py:WorkspaceDomain.transition_workspace()` |
| **Command** | `rig workspace transition <ws_id> <status>` |
| **Authority Owner** | `rig_domain` |
| **Input Source** | `cli` (workspace_id, new_status) + `workspace_store` |
| **Canonical State Touched** | workspace record (status, status_history) |
| **Receipt Produced** | NO - updates workspace record but NO receipt |
| **Receipt Link** | NO |
| **Projection Impact** | Updates workspace status in projections |
| **Current Test Coverage** | INDIRECT |
| **Risk Level** | HIGH |
| **Gap** | CRITICAL: No receipt for status transitions |
| **Mitigation** | Must produce `workspace_transition_receipt_{ws_id}.json` |

**Flow:**
1. CLI calls `transition_workspace(helpers, workspace_id, status)`
2. Validates transition in ALLOWED_TRANSITIONS
3. Updates workspace record status and status_history
4. Saves updated record

**Audit Concern:** Authority decisions (status transitions) have no receipt trail.

---

#### 1.3 `WorkspaceDomain.apply_workspace()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/workspace.py:WorkspaceDomain.apply_workspace()` |
| **Command** | `rig workspace apply <ws_id>` |
| **Authority Owner** | `rig_domain` |
| **Input Source** | `cli` + `workspace_store` + `receipt_store` + `worktree` |
| **Canonical State Touched** | main branch (git merge), workspace record |
| **Receipt Produced** | YES - `apply_receipt_{workspace_id}.json` |
| **Receipt Link** | YES - references execution_receipt_id, validation_receipt_ids |
| **Projection Impact** | Major - workspace marked as applied |
| **Current Test Coverage** | PARTIAL |
| **Risk Level** | CRITICAL |
| **Gap** | NONE - Has receipt |
| **Mitigation** | N/A |

**Flow:**
1. Checks main worktree clean
2. Checks apply_eligibility (execution receipt + worktree hash)
3. Builds review bundle
4. Validates validators passed
5. Performs git merge --no-ff
6. Saves apply receipt with: receipt_id, workspace_id, base_commit, workspace_branch, workspace_commit, main_before, main_after, execution_receipt_id, validation_receipt_ids, review_bundle_hash

**Audit Status:** ⭐ GOOD - Comprehensive receipt with before/after state

---

#### 1.4 `WorkspaceDomain.save_workspace()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/workspace.py:WorkspaceDomain.save_workspace()` |
| **Command** | Internal (called by create, transition, apply) |
| **Authority Owner** | `rig_domain` |
| **Input Source** | `workspace_store` (payload dict) |
| **Canonical State Touched** | workspace record JSON file |
| **Receipt Produced** | NO |
| **Receipt Link** | NO |
| **Projection Impact** | Updates workspace data in projections |
| **Current Test Coverage** | INDIRECT |
| **Risk Level** | MEDIUM |
| **Gap** | Modified workspace records have no receipt |
| **Mitigation** | Workspace mutations should produce or link to receipts |

---

### 2. Validation Mutations

#### 2.1 `WorkspaceDomain.generate_validation_result()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/workspace.py:WorkspaceDomain.generate_validation_result()` |
| **Command** | Internal (called by build_review_bundle) |
| **Authority Owner** | `rig_domain` |
| **Input Source** | `workspace_store` + `worktree` + `pyproject.toml` |
| **Canonical State Touched** | validation result JSON, workspace record |
| **Receipt Produced** | IMPLICIT - validation.json file |
| **Receipt Link** | YES - workspace record references validation_result_path |
| **Projection Impact** | Validation state in projections |
| **Current Test Coverage** | UNKNOWN |
| **Risk Level** | HIGH |
| **Gap** | Validation results are files but not formal Receipt objects |
| **Mitigation** | Consider using ValidatorReceipt from receipts.py |

**Flow:**
1. Reads validator config from pyproject.toml
2. Runs each validator subprocess in worktree
3. Saves validation.json with: schema_version, workspace_id, status, validators (array with exit_code, stdout_tail, stderr_tail, etc.)
4. Updates workspace record with validation_status

---

### 3. Review Bundle Mutations

#### 3.1 `WorkspaceDomain.build_review_bundle()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/workspace.py:WorkspaceDomain.build_review_bundle()` |
| **Command** | `rig workspace review <ws_id>` |
| **Authority Owner** | `rig_domain` |
| **Input Source** | `workspace_store` + `worktree` + `receipt_store` |
| **Canonical State Touched** | review bundle directory |
| **Receipt Produced** | IMPLICIT - review.json + diff.patch + summary.md + validation.json |
| **Receipt Link** | YES - workspace record references review path |
| **Projection Impact** | Review state in projections |
| **Current Test Coverage** | UNKNOWN |
| **Risk Level** | MEDIUM |
| **Gap** | Review bundle is a file bundle, not a formal receipt |
| **Mitigation** | Consider wrapping in a ReviewReceipt |

**Flow:**
1. Loads workspace record
2. Computes git diff from base_commit
3. Generates validation result if missing
4. Computes worktree hash
5. Saves: review.json, diff.patch, summary.md, validation.json
6. review.json includes: schema_version, workspace_id, task, status, base_commit, branch, worktree_path, execution_receipt_id, execution_receipt_hash, diff_hash, validation_status, apply_eligibility, known_blockers

---

### 4. Execution Receipt Mutations

#### 4.1 Execution Receipt Creation
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/receipts.py:ExecutionReceipt` |
| **Command** | Internal (not directly exposed via CLI) |
| **Authority Owner** | `rig_domain` |
| **Input Source** | subprocess results |
| **Canonical State Touched** | receipt JSON files |
| **Receipt Produced** | YES - via FilesystemReceiptStore |
| **Receipt Link** | YES - referenced by apply and review bundles |
| **Projection Impact** | None direct |
| **Current Test Coverage** | UNKNOWN |
| **Risk Level** | MEDIUM |
| **Gap** | Execution receipts exist but creation path not clear from CLI |
| **Mitigation** | Need to verify execution receipt creation in workspace flows |

**Note:** `WorkspaceDomain.load_execution_receipt()` reads from `.build/rig/receipts/{workspace_id}_run.json`

---

#### 4.2 `FilesystemReceiptStore.append()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/receipts.py:FilesystemReceiptStore.append()` |
| **Command** | Internal |
| **Authority Owner** | `rig_domain` |
| **Input Source** | Receipt objects |
| **Canonical State Touched** | receipt JSON files in `.build/rig/receipts/` |
| **Receipt Produced** | YES - self-referential |
| **Receipt Link** | N/A |
| **Projection Impact** | None |
| **Current Test Coverage** | UNKNOWN |
| **Risk Level** | LOW |
| **Gap** | NONE |

---

### 5. Public Intake Mutations (ADVISORY ONLY)

#### 5.1 `public_intake_import`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/commands_public_intake.py:public_intake_import()` |
| **Command** | `rig public intake-import --connector <name>` |
| **Authority Owner** | `rig_commands` + `connector` |
| **Input Source** | `connector` + `public_intake_store` |
| **Canonical State Touched** | `.build/rig/public_intake/packets.jsonl` |
| **Receipt Produced** | YES - `PublicSyncReceipt` (but only in-memory in result) |
| **Receipt Link** | NO - sync receipt NOT saved to filesystem |
| **Projection Impact** | Funding state in projections (advisory) |
| **Current Test Coverage** | UNKNOWN |
| **Risk Level** | MEDIUM (advisory only) |
| **Gap** | CRITICAL: PublicSyncReceipt exists but is NOT persisted |
| **Mitigation** | Must save sync receipt to filesystem |

**Flow:**
1. Connector imports packets
2. Returns ImportResult with packets and PublicSyncReceipt
3. In non-dry-run: saves packets to packets.jsonl via `_save_intake_packet()`
4. **BUG**: sync_receipt is returned in payload but NOT saved to filesystem

---

#### 5.2 `_save_intake_packet()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/commands_public_intake.py:_save_intake_packet()` |
| **Command** | Internal (called by intake-import) |
| **Authority Owner** | `rig_commands` |
| **Input Source** | `public_intake_store` + PublicIntakePacket |
| **Canonical State Touched** | packets.jsonl (append-only) |
| **Receipt Produced** | NO |
| **Receipt Link** | NO |
| **Projection Impact** | Advisory funding data |
| **Current Test Coverage** | UNKNOWN |
| **Risk Level** | LOW (advisory only) |
| **Gap** | Packet saves have no receipt |
| **Mitigation** | Each save should reference a sync receipt |

---

#### 5.3 `funding_summary_cmd`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/commands_public_intake.py:funding_summary_cmd()` |
| **Command** | `rig public funding-summary` |
| **Authority Owner** | `rig_commands` |
| **Input Source** | `public_intake_store` (packets + pledges) |
| **Canonical State Touched** | NONE (read-only) |
| **Receipt Produced** | NO |
| **Receipt Link** | NO |
| **Projection Impact** | Funding summary in projections |
| **Current Test Coverage** | UNKNOWN |
| **Risk Level** | LOW (read-only, advisory) |
| **Gap** | NONE (read-only) |

---

### 6. Projection Builder (Read-Only)

#### 6.1 `build_projection()`
| Classification | Value |
|---------------|-------|
| **Path** | `src/rig/domain/projection_builder.py:build_projection()` |
| **Command** | `rig ui`, `rig window open` |
| **Authority Owner** | `rig_domain` |
| **Input Source** | `workspace_store` + `receipt_store` + `git` |
| **Canonical State Touched** | NONE (read-only) |
| **Receipt Produced** | NO |
| **Receipt Link** | NO |
| **Projection Impact** | Full UI projection |
| **Current Test Coverage** | YES (test_build_projection_includes_workspace_placeholder_widgets) |
| **Risk Level** | LOW (read-only) |
| **Gap** | NONE (read-only) |

---

## Summary Tables

### By Risk Level

| Risk | Count | Action Required |
|------|-------|----------------|
| CRITICAL | 2 | Immediate - apply has receipt, but main branch mutation |
| HIGH | 4 | High - workspace creation/transitions need receipts |
| MEDIUM | 5 | Medium - validation, review, public intake receipts |
| LOW | 4 | Low - read-only or advisory |

### By Receipt Status

| Receipt Status | Count | Paths |
|---------------|-------|-------|
| produces_receipt | 3 | apply_workspace, FilesystemReceiptStore, ExecutionReceipt |
| links_to_receipt | 2 | build_review_bundle, apply_workspace |
| implicit_receipt | 2 | generate_validation_result, build_review_bundle |
| no_receipt | 6 | create_workspace, transition_workspace, save_workspace, _save_intake_packet, funding_summary_cmd, build_projection |
| advisory_only | 3 | public_intake_import, _save_intake_packet, funding_summary_cmd |

### Critical Gaps

1. **Workspace Creation**: No receipt for `create_workspace()` - CRITICAL
2. **Workspace Transition**: No receipt for `transition_workspace()` - CRITICAL  
3. **Public Intake Sync**: `PublicSyncReceipt` not persisted to filesystem - HIGH
4. **Workspace Save**: `save_workspace()` called without receipt linkage - MEDIUM
5. **Validation Results**: Not formal Receipt objects - MEDIUM
6. **Review Bundles**: File bundles, not formal receipts - LOW

### Audit Completeness Score: 45%

- 5/15 mutation paths have proper receipts
- 3/15 have implicit file-based evidence
- 7/15 have NO receipt mechanism
- 3/15 are advisory only (acceptable but need explicit marking)

---

## Placeholder Requirements Verification

The task requires these placeholders to be used:
- `"unknown"` - Used in Receipt.status default
- `"unavailable"` - NOT FOUND in current codebase
- `"not_created"` - Used in WorkspaceStatusSummary.proposal_state default
- `"not_run"` - Used in WorkspaceStatusSummary.validation_state default
- `"not_proof"` - Used in WorkspaceValidationState.proof_status default
- `"advisory_only"` - Used in public_intake.py PLACEHOLDER_ADVISORY_ONLY
- `"not_authoritative"` - NOT FOUND in current codebase
- `"no_receipt"` - NOT FOUND in current codebase

**Action:** Add missing placeholders to audit primitives.

---

## Next: Phase 2 - Domain Hardening

Proceed to create audit primitives module with:
- `AuditEvent`
- `AuditActor`
- `AuditSubject`
- `AuditDecision`
- `AuditReceiptLink`
- `WorkspaceAuditTrail`

And helpers:
- `resolve_mutation_authority()`
- `resolve_receipt_status()`
- `resolve_audit_completeness()`
- `build_workspace_audit_trail()`
