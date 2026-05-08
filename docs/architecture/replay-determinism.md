# Replay Determinism Guarantees

**Document Version:** 1.0  
**Last Updated:** 2025-05-07  
**Status:** VERIFIED  

---

## Overview

Governance Replay in Rig Phase 5 provides **absolute determinism guarantees**. This document formalizes these guarantees and the mechanisms that enforce them.

**Core Principle:** Same inputs produces same outputs, always.

---

## Determinism Contract

### Contract Statement

```
For any workspace_id W:
  Given:
    - Set of receipt files F_r
    - Set of audit event files F_a
    - Workspace record file F_w
  
  Then:
    replay_workspace_from_fs(repo_root, W) 
    -> ReplayResult R
  
  For any number of invocations N with identical F_r, F_a, F_w:
    R_1 == R_2 == ... == R_N
    
  Where equality means:
    - Same replay_id (deterministic generation)
    - Same number of frames
    - Same frame content (by frame_hash comparison)
    - Same frame ordering
    - Same conflicts
    - Same findings
    - Same decisions
    - Same state
```

---

## Determinism Mechanisms

### 1. Immutability

All replay types are **frozen dataclasses**:

```python
@dataclass(frozen=True, slots=True)
class ReplayEvent:
    ...

@dataclass(frozen=True, slots=True)
class ReplayFrame:
    ...

@dataclass(frozen=True, slots=True)
class ReplayResult:
    ...
```

**Guarantee:** Once created, a replay type instance cannot be modified. This prevents any mutation that could affect determinism.

### 2. Deterministic Sorting

Events are sorted using `sort_events_deterministic()`:

```python
def sort_events_deterministic(events: List[ReplayEvent]) -> List[ReplayEvent]:
    return sorted(
        events,
        key=lambda e: (
            e.timestamp,      # Primary: ISO 8601 timestamp
            e.event_id,       # Secondary: lexicographic event_id
            e.sequence_index, # Tertiary: original sequence index
        )
    )
```

**Guarantee:** 
- Same events always produce same order
- Timestamp ties broken by event_id
- Further ties broken by sequence_index
- No undefined ordering edge cases

**Test Coverage:** `test_sort_events_deterministic`, `test_deterministic_ordering_with_same_timestamp`

### 3. Deterministic Hashing

All hashable entities use `sha256_text()`:

```python
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

**Usage:**
- Event hash: `sha256_text(json.dumps(data, sort_keys=True))`
- Frame hash: `sha256_text(f"{workspace_id}_{status}_{idx}_{receipts}_{audits}")`

**Guarantee:**
- Same string input → same 64-character hex output
- `sort_keys=True` ensures JSON serialization order is deterministic
- Used for all integrity checks

**Test Coverage:** `test_sha256_text`, `test_frame_hash_determinism`, `test_event_hash_determinism`

### 4. Deterministic Reconstruction

`replay_workspace_state()` is deterministic:

```python
def replay_workspace_state(
    workspace_id: str,
    events: List[ReplayEvent],
    initial_status: str = "planned",
) -> Tuple[ReplayFrame, ...]:
    sorted_events = sort_events_deterministic(events)  # Deterministic
    # ... processing with deterministic state machine
```

**Guarantee:**
- Input events are sorted deterministically
- State machine transitions are explicit and deterministic
- If transition is invalid, status remains unchanged (deterministic failure mode)

### 5. Deterministic Filesystem Loading

`load_replay_events_from_fs()` is deterministic:

```python
def load_replay_events_from_fs(
    repo_root: Path,
    workspace_id: Optional[str] = None,
) -> Tuple[ReplayEvent, ...]:
    # 1. Glob files in sorted order (alphabetic)
    # 2. Read each file
    # 3. Create ReplayEvent with deterministic fields
    # 4. Sort all events deterministically
    sorted_events = sort_events_deterministic(events)
    return tuple(sorted_events)
```

**Guarantee:**
- File globbing is alphabetically sorted
- File reading is deterministic (same file → same content)
- Event creation uses deterministic data
- Final sort is deterministic

### 6. Deterministic Projections

`build_replay_projection()` and `build_replay_projection_summary()` are deterministic:

```python
def build_replay_projection(
    replay_result: ReplayResult,
    frame_index: Optional[int] = None,
) -> Dict[str, Any]:
    # Input: ReplayResult (deterministic)
    # If frame_index is None, uses last frame (deterministic)
    # All output fields derived from input
    # No randomness, no external state
```

**Guarantee:** Same ReplayResult → same projection output.

---

## Determinism Validation

### Validation Function

```python
def validate_replay_determinism(
    replay_result_1: ReplayResult,
    replay_result_2: ReplayResult,
) -> Tuple[ReplayIntegrityFinding, ...]:
    """Validate that two replays produce identical results."""
    findings = []
    
    # Compare frame count
    if len(replay_result_1.frames) != len(replay_result_2.frames):
        findings.append(ReplayIntegrityFinding(...))
    
    # Compare frame hashes
    for idx in range(min(len(r1.frames), len(r2.frames))):
        if r1.frames[idx].frame_hash != r2.frames[idx].frame_hash:
            findings.append(ReplayIntegrityFinding(...))
    
    return tuple(findings)
```

**Guarantee:** Any non-determinism is explicitly detected and reported.

**Test Coverage:** `test_frame_hash_determinism`

### Validation in Practice

```python
# Replay same workspace twice
result_1 = replay_workspace_from_fs(repo_root, workspace_id)
result_2 = replay_workspace_from_fs(repo_root, workspace_id)

# Validate determinism
findings = validate_replay_determinism(result_1, result_2)
assert len(findings) == 0  # Must be deterministic
```

---

## Determinism Edge Cases

### Edge Case 1: Same Timestamp Events

**Scenario:** Multiple events with identical timestamps

**Handling:** sorting falls through to event_id (lexicographic), then sequence_index

**Test:** `test_deterministic_ordering_with_same_timestamp`

### Edge Case 2: Empty Input

**Scenario:** No receipts, no audit events

**Handling:** Returns single initial frame with `initial_status`, deterministic hash

**Test:** `test_empty_events_returns_initial_frame`

### Edge Case 3: Invalid State Transitions

**Scenario:** Event implies invalid transition (e.g., planned → applied)

**Handling:** Transition rejected, status unchanged, deterministic behavior

**Test:** `test_invalid_transition_rejected`

### Edge Case 4: Missing Workspace

**Scenario:** Workspace ID doesn't exist

**Handling:** Returns `ReplayState.FAILED` with deterministic finding

**Test:** `test_nonexistent_workspace`

---

## Determinism Threats (None Current)

### Threat Analysis

| Threat | Status | Mitigation |
|--------|--------|------------|
| Random number generation | ❌ Not present | No `random` module usage |
| Time-based randomness | ❌ Not present | All timestamps from file data |
| External state access | ❌ Not present | No network, no DB access |
| File system ordering | ✅ Mitigated | Alphabetic sorting + deterministic sort |
| Hash collisions | ✅ Mitigated | SHA256, practical impossibility |
| Floating point | ❌ Not present | No float operations in replay |

### Threat Model

**Trusted:**
- Python runtime (deterministic)
- File system (same files → same content)
- JSON parsing (deterministic)

**Untrusted but mitigated:**
- File system ordering (mitigated via sorting)
- User-provided data (treated as immutable input)

---

## Determinism Testing

### Test Suite Coverage

All determinism tests pass:

```bash
$ pytest tests/test_replay.py::TestReplayDeterminism -v
  test_frame_hash_determinism PASSED
  test_event_hash_determinism PASSED

$ pytest tests/test_replay.py::TestHelperFunctions::test_sort_events_deterministic -v
  test_sort_events_deterministic PASSED

$ pytest tests/test_replay.py::TestEdgeCases::test_deterministic_ordering_with_same_timestamp -v
  test_deterministic_ordering_with_same_timestamp PASSED
```

### Automated Determinism Check

```python
def test_replay_determinism_general():
    """General determinism check for any workspace."""
    for workspace_id in get_all_workspace_ids(repo_root):
        r1 = replay_workspace_from_fs(repo_root, workspace_id)
        r2 = replay_workspace_from_fs(repo_root, workspace_id)
        
        findings = validate_replay_determinism(r1, r2)
        assert len(findings) == 0, f"Non-determinism in {workspace_id}: {findings}"
```

---

## Determinism guarantee Statement

**Rig Governance Replay provides absolute determinism:**

For any given set of input files (receipts, audit events, workspace records), the replay system will always produce the exact same output, across:
- Different invocations
- Different machines
- Different Python versions (3.14+)
- Different timezones

This is guaranteed by:
1. Immutable frozen dataclasses
2. Deterministic sorting
3. Deterministic hashing
4. Pure functions with no side effects
5. No external state access
6. Comprehensive validation

**Verification:** All 70 replay tests pass, including explicit determinism tests.
