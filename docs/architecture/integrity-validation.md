# Integrity Validation Architecture

## Overview

This document describes the **Integrity Validation Engine** implemented in Phase 3 of the Workspace Integrity Fortification. It provides deterministic validation over workspace/audit/receipt state to ensure invalid authority state becomes difficult to create, easy to detect, and impossible to silently ignore.

## Core Doctrine

1. **Deterministic validation only** - Same state produces same findings
2. **No mutation during checks** - Pure validation functions
3. **JSON-serializable output** - All findings are exportable
4. **No hidden repair behavior** - Explicit findings only
5. **Projection-safe** - Findings can be used by UI projections

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Integrity Validation Engine                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Input: Repository State                                           │
│  ├─ Workspace Records (.build/rig/workspaces/*.json)              │
│  ├─ Receipts (.build/rig/receipts/*.json)                          │
│  └─ Audit Events (.build/rig/audit/*.json)                         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  validate_repository_integrity(repo_root)                       ││
│  │    ┌─────────────────┐  ┌─────────────────┐                  ││
│  │    │ validate_workspace│  │ validate_receipt│                  ││
│  │    │ validate_audit    │  │ validate_proj... │                  ││
│  │    └─────────────────┘  └─────────────────┘                  ││
│  └─────────────────────────────────────────────────────────────┘│
│                             │                                          │
│                             ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    IntegritySummary                            ││
│  │  - total_checks: int                                           ││
│  │  - total_findings: int                                         ││
│  │  - findings_by_severity: Dict[str, int]                       ││
│  │  - findings_by_violation_code: Dict[str, int]                 ││
│  │  - findings_by_subject_type: Dict[str, int]                   ││
│  │  - check_results: Tuple[IntegrityCheckResult, ...]            ││
│  │  - all_findings: Tuple[IntegrityFinding, ...]                 ││
│  │  - overall_status: str ("clean", "warnings", "errors", "crit")││
│  │  - integrity_score: float (0.0 - 1.0)                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                   │
│  Output: Deterministic Findings                                     │
│  - Human-readable CLI output                                       │
│  - Machine-readable JSON output                                     │
│  - Non-zero exit codes on critical failures                          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
              ┌───────────────────────┐
              │  CLI (rig doctor)      │
              │  - rig doctor all      │
              │  - rig doctor workspace│
              │  - rig doctor receipts│
              │  - rig doctor audit    │
              │  - rig doctor projections│
              └───────────────────────┘
```

## Data Types

### Severity Levels

| Level | Value | Numeric Order | Required Action |
|-------|-------|---------------|-----------------|
| INFO | `info` | 0 | Optional review |
| WARNING | `warning` | 1 | Review recommended |
| ERROR | `error` | 2 | Manual investigation required |
| CRITICAL | `critical` | 3 | IMMEDIATE manual intervention required |

### IntegrityFinding

Represents a single integrity finding. Frozen dataclass with:

```python
@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    finding_id: str              # Unique ID for this finding
    violation_code: IntegrityViolationCode  # Canonical violation code
    severity: IntegritySeverity  # Severity level
    title: str                   # Short human-readable title
    message: str                 # Detailed message
    subject_type: str            # "workspace", "receipt", "audit_event", "projection"
    subject_id: str              # ID of the subject
    details: Dict[str, Any]      # Additional context
    timestamp: str               # ISO 8601 timestamp
```

### IntegrityCheckResult

Result of validating a single subject:

```python
@dataclass(frozen=True, slots=True)
class IntegrityCheckResult:
    subject_id: str
    subject_type: str
    check_name: str
    passed: bool
    findings: Tuple[IntegrityFinding, ...]
    warnings: int
    errors: int
    critical: int
    info: int
```

### IntegritySummary

Aggregate summary of all integrity checks:

```python
@dataclass(frozen=True, slots=True)
class IntegritySummary:
    total_checks: int
    total_findings: int
    findings_by_severity: Dict[str, int]
    findings_by_violation_code: Dict[str, int]
    findings_by_subject_type: Dict[str, int]
    check_results: Tuple[IntegrityCheckResult, ...]
    all_findings: Tuple[IntegrityFinding, ...]
    overall_status: str  # "clean", "warnings", "errors", "critical"
    integrity_score: float  # 0.0 - 1.0
```

## Validation Functions

### Core Validation

| Function | Input | Output |
|----------|-------|--------|
| `validate_workspace_integrity()` | `workspaceRecord: dict` | `IntegrityCheckResult` |
| `validate_receipt_integrity()` | `receipt: Any, receipt_path: Path, repo_root: Path, all_ids: Set[str]` | `IntegrityCheckResult` |
| `validate_audit_integrity()` | `event: Any, event_path: Path, repo_root: Path, all_ids: Set[str]` | `IntegrityCheckResult` |
| `validate_projection_integrity()` | `projection_data: dict, repo_root: Path` | `IntegrityCheckResult` |
| `validate_repository_integrity()` | `repo_root: Path` | `IntegritySummary` |

### Builder Functions

| Function | Input | Output |
|----------|-------|--------|
| `build_integrity_summary()` | `check_results: List[IntegrityCheckResult]` | `IntegritySummary` |
| `resolve_integrity_status()` | `summary: IntegritySummary` | `str` |

## Integrity Checks Implemented

### Workspace Check Functions

1. **`check_workspace_lifecycle_integrity()`**
   - WS-001: Valid workspace status
   - WS-002: Valid state transitions (from ALLOWED_TRANSITIONS)
   - WS-003: `applied` is terminal
   - WS-004: `blocked` is terminal
   - WS-008: Status history order (no time travel)

2. **`check_workspace_authority_integrity()`**
   - VG-001: Applied workspace must have apply receipt
   - VG-003: Validation failed must block apply_eligibility
   - VG-002: Apply gate cannot be allowed with blocked validation

### Receipt Check Functions

**`check_receipt_integrity()`** validates:
- MISSING_CANONICAL_FIELDS: Required fields (receipt_id, receipt_type) present
- AUTHORITATIVE_FIELD_PLACEHOLDER: Placeholder values not in critical fields
- PUBLIC_INTAKE_AUTHORITATIVE: Public intake/funding/sync receipts must be advisory
- MISSING_RELATED_RECEIPT: Related receipt IDs must reference existing receipts
- STALE_INPUT_REFERENCE: Input references must exist
- STALE_OUTPUT_REFERENCE: Output references must exist
- STALE_EVIDENCE_REFERENCE: Evidence references must exist

### Audit Event Check Functions

**`check_audit_event_integrity()`** validates:
- AE-004: Authoritative events must have advisory_only=False
- AE-005: Advisory-only events must have advisory_only=True, authoritative=False
- AE-002: Authoritative events must have receipt_id or explicit reason
- AE-003: receipt_status must match actual receipt existence
- OA-001: Event workspace reference must exist

### Repository-Level Checks

**`validate_repository_integrity()`** additionally checks:
- ORPHANED_RECEIPT_FILE: Receipts referencing non-existent workspaces
- ORPHANED_AUDIT_EVENT_FILE: Audit events referencing non-existent workspaces
- DUPLICATE_RECEIPT_IDS: Receipt ID uniqueness across all receipt files

## CLI Commands

### `rig doctor all`

Validate all integrity aspects of the repository.

**Options:**
- `--json`: Output JSON
- `--strict`: Exit non-zero on errors (not just critical)

**Example:**
```bash
$ rig doctor all
Rig Integrity Check - All
========================================
Overall Status: clean
Integrity Score: 1.00
Total Checks: 5
Total Findings: 0

All integrity checks passed!

$ rig doctor all --json
{
  "all_findings": [],
  "check_results": [...],
  "findings_by_severity": {},
  "findings_by_subject_type": {},
  "findings_by_violation_code": {},
  "integrity_score": 1.0,
  "overall_status": "clean",
  "total_checks": 5,
  "total_findings": 0
}
```

### `rig doctor workspace`

Validate workspace integrity only.

**Options:**
- `--json`: Output JSON
- `--strict`: Exit non-zero on errors

### `rig doctor receipts`

Validate receipt integrity only.

**Options:**
- `--json`: Output JSON
- `--strict`: Exit non-zero on errors

### `rig doctor audit`

Validate audit event integrity only.

**Options:**
- `--json`: Output JSON
- `--strict`: Exit non-zero on errors

### `rig doctor projections`

Validate projection integrity.

**Options:**
- `--json`: Output JSON

## Exit Codes

| Condition | Exit Code |
|-----------|-----------|
| All checks pass | 0 |
| Critical findings present | 1 |
| Errors present (with --strict) | 1 |
| Validation error | 1 |

## Deterministic Guarantees

All integrity validation functions are **deterministic**:

1. **Same input state produces same findings** - No randomness, no timestamps in finding IDs
2. **Findings are ordered deterministically** - Sorted by subject type, then subject ID
3. **JSON output is stable** - `sort_keys=True` for consistent serialization
4. **No side effects** - Validation functions do not modify any state

## Performance Considerations

- Repository scan is O(n) where n is total workspaces + receipts + audit events
- Each validation check is O(1) or O(m) where m is the number of related objects
- Memory usage is bounded by the number of findings, not the repository size
- No expensive operations (hashing, encoding) during validation

## Known Limitations

1. **No cross-repository validation** - Only validates within a single repository
2. **No historical validation** - Does not validate state transitions over time
3. **No concurrent modification detection** - Assumes repository is static during validation
4. **No content validation** - Only validates structural integrity, not content validity

## Integration with Projections

Integrity findings can be integrated into projections for UI display. See Phase 4 for projection fortification.

## Integration with UI

Integrity status can be displayed in the AuditTrailCard widget. See Phase 5 for frontend integration.

## Testing

See `tests/test_integrity.py` for comprehensive tests covering:
- All type definitions
- All validation functions
- Deterministic behavior
- Golden tests for serialization
- Integration tests

## File Changes

| File | Change |
|------|--------|
| `src/rig/domain/integrity.py` | Created - Integrity validation engine |
| `src/rig/commands_doctor.py` | Modified - Added doctor integrity subcommands |
| `tests/test_integrity.py` | Created - Comprehensive integrity tests |
| `docs/architecture/workspace-integrity-rules.md` | Created - Canonical integrity rules |
| `docs/architecture/integrity-validation.md` | Created - This document |
| `docs/sprints/workspace-integrity-fortification-phase-3.md` | To be created - Sprint documentation |

## Validation Commands

```bash
# Syntax check
python -m compileall -q src tests

# Type check
python -m pyright --project pyrightconfig.json

# Run integrity tests
python -m pytest tests/test_integrity.py -v

# Run all doctor-related tests
python -m pytest tests/test_integrity.py tests/test_workspace_audit.py tests/test_receipt_envelope.py -v

# Run doctor commands
python -m rig doctor all
python -m rig doctor all --json
python -m rig doctor workspace
python -m rig doctor receipts
python -m rig doctor audit
python -m rig doctor projections
```
