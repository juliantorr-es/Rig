# Runtime Streaming Consolidation

**ADR 0004 — Canonical**

This ADR **evolved** from an initial proposal to consolidate ALL 14 runtime modules (16,010 lines) into one `RuntimeDomain`. That approach was **rejected** after dependency analysis revealed **3 distinct operational strata** that should NOT be unified. This document canonizes the refined approach: **deepen Cluster 2 only** — the streaming subsystem.

**Status**: accepted

**Related ADRs**:
- [0002 Projection Domain Consolidation](0002-projection-domain-consolidation.md) — projection semantics remain separate; streaming owns refresh orchestration only
- [0007 Receipt/Evidence Unification](0007-receipt-evidence-unification.md) — streaming emits events; evidence domain owns persistence

---

## Architectural Lineage: Why Original Approach Was Rejected

### Original Proposal (Superseded)
The initial ADR 0004 proposed unifying **14 files, 16,010 lines** into one `RuntimeDomain` with the reasoning that "the Runtime concept is split across shallow modules with tight coupling."

### Discovery: Three Operational Strata
Dependency and semantic analysis revealed **three distinct clusters**, not one monolith:

| Cluster | Files | Lines | Nature | Verdict |
|---------|-------|-------|--------|---------|
| 1: Event Substrate | `runtime.py`, `runtime_events.py`, `runtime_event_router.py`, `runtime_event_transport.py` | 2,118 | Infrastructure/substrate-level concerns | **DO NOT consolidate** — belongs to broader operational substrate |
| **2: Streaming Loop** | `runtime_stream.py`, `runtime_supervisor.py`, `runtime_websocket.py`, `runtime_projection.py` | **5,915** | Tightly coupled operational loop with shared lifecycle | **GOOD candidate** for deepening |
| 3: Operational Tooling | `runtime_registry.py`, `runtime_tools.py`, `runtime_reconciliation.py`, `runtime_replay.py`, `runtime_benchmark.py`, `runtime_doctor.py` | 8,977 | Multiple operational roles (execution, diagnostics, replay, control-plane, benchmarking) | **DO NOT consolidate** — each may need separate deepening |

### Why Unification Would Create a Semantic Gravity Well
Creating a `RuntimeDomain` that absorbs all 16K lines would:
1. **Mix strata with different lifecycles** — substrate (stable) vs tooling (volatile)
2. **Hide cross-cutting concerns** — replay semantics, topology authority, transport authority would become internal implementation details
3. **Reduce testability** — mocking `RuntimeDomain` means mocking everything, defeating the purpose of seams
4. **Create conceptual drift** — "runtime" would mean both infrastructure AND execution AND diagnostics

**Conclusion**: The original premise was wrong. The codebase does NOT contain "one runtime concept." It contains **adjacent operational concerns** that should remain separate.

---

## Normative Architectural Constraints

> These are **doctrine-level** decisions that define the streaming domain's semantic boundaries. They must not be violated during implementation.

### 1. Projection Authority Separation
**Streaming owns**: invalidation triggering, coalescing, bounded rebuild scheduling, refresh pressure coordination.

**Projection domain owns** (ADR 0002): deterministic rebuild execution, lineage correctness, semantic synthesis, schema/version integrity, canonical projection structure.

**Do NOT**: Allow streaming domain to absorb projection-building semantics. Projection absence is a **normal operational state**, not a failure.

### 2. Stream Identity Model
Two distinct identity concepts:

- **`stream_lineage_id`**: Deterministic identifier derived from `repo_root + semantic_config + workspace_namespace`. Enables replay to reconstruct exact stream lineage.
- **`stream_instance_id`**: Operational instance identifier (monotonic sequence, activation occurrence). Distinguishes multiple live executions of the same logical stream.

`get_events()` uses `stream_instance_id`. Replay uses `stream_lineage_id` for deterministic reconstruction.

### 3. Error Semantics
**Do NOT**: Broad catch-and-wrap that collapses operational causality.

**Do**: Preserve underlying exception lineage through typed operational categories. Errors must retain:
- Which subsystem failed
- Where activation failed
- Whether failure was deterministic
- Whether replay should expect recurrence

**Invariant**: Streaming domain classifies operational failures but **must preserve underlying causality and diagnostic lineage**. Presentation formatting is the CLI's responsibility.

### 3b. Agent Execution / Tool Routing Separation
Agent sandboxing, tool-call normalization, and model-runtime routing are **not** runtime streaming concerns. They belong to the agent-execution/control plane, not Cluster 2 streaming. Do **not** collapse agent tool routing into runtime streaming just because both emit operational events.

### 4. Factory Discipline
- `from_repo_root(repo_root: Path) -> RuntimeStreaming`: **Cold instance** — pure data and wiring only. No sockets, no processes, no threads, no I/O.
- Activation boundary: **`create_stream()`** — first operational call triggers lazy initialization.
- Internal adapters use **lazy initializers** (not instantiated at construction).

### 5. Type Dependency Direction
- `_types.py` contains **only** Cluster 2-owned types (e.g., `StreamHandle`, `StreamState`, `StreamConfig`).
- Cluster 1 types (`RuntimeProvider`, `Capability`, `Proposal`) remain in `runtime.py`. Streaming modules import them explicitly.
- **No** wildcard re-exports. **No** type duplication. **No** shared type extraction package.
- Dependency direction: streaming → substrate (healthy). Substrate → streaming (forbidden).

### 6. Projection Access Contract
```python
def get_projection(self, stream_id: str) -> Optional[RuntimeProjection]:
    """
    Returns the current projection, or None if not yet built or rebuild failed.
    
    NONE IS NOT AN ERROR. Projection absence is a normal operational state.
    
    Callers must handle None. Metadata (exists, stale, rebuild_pending, failed,
    revision, sequence_coverage) should accompany the return.
    """
```

**Do NOT**: Block on projection rebuild. **Do NOT**: Treat stale projections as fatal. Projection freshness is subordinate to runtime stability.

### 7. Observability Boundaries
**Streaming owns**: Emitting canonical operational events via a subscription mechanism.

**Evidence domain owns** (ADR 0007): Persistence, signing, lineage durability, forensic reconstruction, receipt derivation.

**Do NOT**: Couple streaming to evidence persistence. **Do NOT**: Create "evidence-only execution paths."

Canonical event stream consumed by: UI, replay, evidence, telemetry, audit tooling.

Event types (normative):
- `StreamCreated`
- `StreamStarting`
- `StreamStarted`
- `StreamFailed`
- `StreamStopped`
- `ProjectionInvalidated`
- `ProjectionRebuilt`
- `BackpressureDetected`
- `SupervisorExited`

---

## Decision: Deepen Cluster 2 Only

Create a **RuntimeStreaming** deep module that owns the **streaming operational loop** — and **only** this loop.

### Semantic Boundary (Non-Negotiable)
The streaming domain owns:
- Stream lifecycle (create, start, stop, fail)
- Supervision coordination (process monitoring, output collection, timeouts)
- WebSocket propagation as **operational adapter** (stream fanout, subscriber delivery)
- Projection refresh orchestration (invalidation triggering, cadence coordination)

The streaming domain **does NOT own**:
- Replay semantics (Cluster 3: `runtime_replay.py`)
- Event substrate (Cluster 1: `runtime.py`, `runtime_events.py`)
- Topology authority (which agents/providers exist)
- Transport authority (canonical envelope policy, generalized routing, transport normalization)
- Projection semantics (ADR 0002: meaning, composition, lineage, contracts)

**This boundary is the difference between deepening and gravitational collapse.**

WebSocket is an **operational adapter** currently participating in stream propagation, not the defining abstraction. Transport substrate authority remains separate.

### New Interface
```python
# src/rig/domain/runtime_streaming/__init__.py - public interface
class RuntimeStreaming:
    """Single seam for the streaming operational loop."""
    
    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "RuntimeStreaming":
        """Factory - per-repo, deterministic. Returns cold instance."""
    
    def create_stream(self, config: RuntimeConfig) -> StreamHandle:
        """Create and start a runtime stream. Activation boundary. Raises on failure."""
    
    def submit_proposal(self, proposal: RuntimeProposal) -> ProposalDecision:
        """Submit a proposal to the runtime stream."""
    
    def get_projection(self, stream_id: str) -> Optional[RuntimeProjection]:
        """Get current projection. Returns None if unavailable (normal state)."""
    
    def get_events(self, stream_id: str, since_sequence: int = 0) -> List[RuntimeStreamEvent]:
        """Get stream events since sequence number. Uses stream_instance_id."""
    
    def subscribe_events(
        self, 
        event_types: Optional[List[Type[RuntimeStreamEvent]]] = None
    ) -> Subscription:
        """Subscribe to operational event stream. Multiple consumers share same substrate."""
```

### Internal Architecture
- `_types.py` (~1,950 lines) — **Cluster 2-only types**: `StreamHandle`, `StreamState`, `StreamConfig`, `StreamSubscription`, `ProjectionRefreshState`, `StreamBackpressurePolicy`, `StreamLifecyclePhase`
- `_stream.py` (~1,678 lines) — stream lifecycle management
- `_supervisor.py` (~1,690 lines) — process supervision
- `_websocket.py` (~1,435 lines) — WebSocket transport (internal adapter, subordinate to stream activation)
- `_projection.py` (~1,412 lines) — **Refresh orchestration only**: invalidation, scheduling, coalescing. **NOT** projection semantics (which belong to ADR 0002)

> **Note on `_projection.py`**: This file should be split during implementation. Only refresh coordination (invalidation triggering, cadence) moves to streaming. Projection rebuilding semantics remain in the Projection Domain.

### What Stays Outside (Explicitly)
- `runtime.py` types (`RuntimeProvider`, `Capability`, `Proposal`, `Invocation`) — remain in Cluster 1 (Event Substrate)
- Cluster 1 (Event Substrate) — untouched
- Cluster 3 (Operational Tooling) — untouched; must import from streaming's **public interface**, not internal modules
- `rig_tools` modules — updated to import from new package

---

## Consequences

### Leverage
One place for streaming operations. Currently: 4 files with overlapping concerns, cross-dependencies. After: 1 interface with 6 methods. Add new stream feature? One place.

### Locality
All 5,915 lines of streaming knowledge in one deep module. Currently: stream in one file, supervision in another, websocket in another, projection in another. After: clean internal seams with explicit dependency direction.

### Testability
Test streaming through domain interface. Currently: need to mock stream, supervisor, websocket separately. After: mock `RuntimeStreaming` once. Projection absence is a valid test state, not a mocking requirement.

### Semantic Compression
**YES** — this is one operational concept (the streaming loop), not a grab-bag of adjacent concerns.

### Risk
**Medium**. Affects core runtime functionality. But Cluster 2 is self-contained with clear boundaries. Rollback via shims at each phase.

**Critical Risk**: Projection authority leakage. Mitigated by explicit Normative Constraint #1.

---

## Files Involved

### New package: `src/rig/domain/runtime_streaming/`
| File | Source | Ownership |
|------|--------|-----------|
| `__init__.py` | New | Public interface: `RuntimeStreaming` class |
| `_types.py` | `runtime_stream.py` stream-specific types | Cluster 2 only |
| `_stream.py` | `runtime_stream.py` | Cluster 2 |
| `_supervisor.py` | `runtime_supervisor.py` | Cluster 2 |
| `_websocket.py` | `runtime_websocket.py` | Cluster 2 (internal adapter) |
| `_projection.py` | `runtime_projection.py` refresh orchestration only | Split: orchestration → Cluster 2, semantics → ADR 0002 |

> **Type Imports**: Files in this package import Cluster 1 types explicitly from `runtime.py`, not via duplication or shared modules.

### Deprecated files (4 total, 5,915 lines)
- `src/rig/domain/runtime_stream.py` — removed
- `src/rig/domain/runtime_supervisor.py` — removed
- `src/rig/domain/runtime_websocket.py` — removed
- `src/rig/domain/runtime_projection.py` — removed

### Updated consumers
- Any module importing from the 4 deprecated files → update to `runtime_streaming` **public interface**
- `runtime.py` — unchanged (Cluster 1 substrate)
- `runtime_reconciliation.py` — must use public interface, **not** internal streaming modules
- `runtime_replay.py` — must use public interface for any streaming dependencies

---

## Migration Path

### Phase 1: Create package, preserve behavior (week 1)
1. Create `runtime_streaming` package with `__init__.py` stub
2. Copy each file to corresponding `_<name>.py`
3. Create **failing shims** in original files with explicit deprecation metadata
4. Verify all existing tests pass

### Shim Template (Normative)
```python
# runtime_stream.py - Compatibility shim for ADR 0004 migration
"""
Compatibility shim for ADR 0004 migration.

Deprecated:    2026-05
Removal:       Phase 4 of ADR 0004
Canonical:     rig.domain.runtime_streaming
ADR:           0004-runtime-streaming-consolidation.md

DO NOT ADD NEW CODE HERE. This file will be deleted.
"""
import warnings
from rig.domain.runtime_streaming._stream import (
    StreamEvent,
    StreamConfig,
    StreamState,
    # Explicit re-exports - NO wildcards
)

warnings.warn(
    (
        "rig.domain.runtime_stream is deprecated. "
        "Import from rig.domain.runtime_streaming instead. "
        "See ADR 0004."
    ),
    DeprecationWarning,
    stacklevel=2,
)
```

### Phase 2: Create public interface (week 1-2)
5. Define `RuntimeStreaming` class with public methods
6. Wire each method to internal modules
7. Implement `subscribe_events()` for event stream
8. Run comprehensive runtime tests

### Phase 3: Migrate consumers (week 2)
9. Update all imports from deprecated files to `runtime_streaming`
10. CI begins **failing on new shim imports** (existing tolerated, new forbidden)
11. Repository-wide shim import count must **monotonically decrease**
12. Remove shims once all consumers updated

### Phase 4: Cleanup (week 2)
13. Delete deprecated files
14. Final verification

**Rollback strategy**: At any phase, shims allow reverting to original locations.

**Shim Expiration**: Shims contain ADR reference, deprecation date, removal target, and canonical replacement path. They are **temporary lineage**, not permanent sediment.

---

## Future Work

After Cluster 2 is proven stable:
- **Cluster 1 (Event Substrate)**: Consider whether these belong to a broader operational substrate (not runtime-specific). These are infrastructure-level concerns that may serve multiple domains.
- **Cluster 3 (Operational Tooling)**: Each module may need its own deepening:
  - `runtime_replay.py` → ReplayDomain (if replay becomes a first-class concern)
  - `runtime_registry.py` + `runtime_benchmark.py` → remain independent (diverse lifecycles)
  - `runtime_doctor.py` → HealthDomain or DiagnosticsDomain
  - `runtime_tools.py` → ToolExecutionDomain (separate from streaming)
  - `runtime_reconciliation.py` → ReconciliationDomain

**Important**: Do NOT create a `RuntimeDomain` that unifies these. Each cluster has its own semantic center of gravity.

---

## Summary

This ADR represents **architectural maturity**: we started with a broad unification proposal, discovered it was semantically wrong, and refined to a focused deepening of the only cluster that passes the semantic compression test. The streaming loop is the only operational concept currently exhibiting strong enough cohesion and temporal coupling to justify deepening.

**The discipline demonstrated here** — rejecting the tempting giant consolidation in favor of precise, bounded deepening, while explicitly fencing off projection authority, identity semantics, and observability boundaries — is the difference between:
- Architectural evolution
- Architectural sediment

We choose evolution.

---

## Appendix: Why These Constraints Prevent Gravity Wells

1. **Projection Authority Separation** → Prevents streaming from absorbing projection semantics, which would make it the "runtime brain"
2. **Lineage vs Instance Identity** → Prevents replay from being coupled to live orchestration timing
3. **Error Causal Preservation** → Prevents streaming from becoming a black box that hides failure modes
4. **Factory Coldness** → Prevents import-time side effects and resource consumption before explicit intent
5. **Explicit Type Imports** → Prevents streaming from becoming a shadow substrate with duplicated semantics
6. **Optional Projection Return** → Prevents synchronous blocking assumptions that couple UI to runtime cadence
7. **Event Subscription Seam** → Prevents evidence collection from being coupled to streaming internals, enabling a single canonical event substrate for all consumers
