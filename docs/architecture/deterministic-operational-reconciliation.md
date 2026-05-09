# Deterministic Operational Reconciliation

> **Canonical Doctrine**: Rig is a bounded operational reconciliation runtime, NOT an infinitely reactive system.

---

## Overview

This document canonicalizes the Deterministic Operational Reconciliation doctrine for Rig. It defines the boundaries between reconciliation loops (operational convergence mechanisms) and authoritative transactions (explicit irreversible transitions).

**Core Principle**: Events are authoritative facts. Loops are operational convergence mechanisms, NOT authority generators.

---

## Concept Definitions

| Concept | Meaning | Authority Source | Mutability |
|---|---|---|---|
| reconciliation loop | Bounded operational convergence mechanism | Canonical events | Derived state only |
| authoritative state | Canonical operational fact | External authority (human, governance) | Immutable |
| derived state | Continuously synthesized operational state | Reconciliation controllers | Mutable within bounds |
| reconciliation controller | Deterministic drift corrector | Canonical events | Stateful, bounded |
| bounded convergence | Correction within operational ceilings | Governance constraints | Enforced |
| damping | Oscillation prevention mechanism | DampingFactor primitives | Configurable |
| reconciliation cadence | Bounded refresh interval | ReconciliationCadence primitives | Fixed |
| replay-safe reconciliation | Deterministic reconstruction compatibility | Event ordering guarantees | Mandatory |
| transactional authority boundary | Explicit irreversible transition | Human/Git/governance | Immutable |

---

## Architectural Boundaries

### Reconciliation Loop Domain

Reconciliation loops are VALID ONLY WHEN:

- State is operationally derived (not authoritative)
- Authoritative inputs are canonical events
- Reconciliation is deterministic (same inputs → same outputs)
- Replay integrity is preserved (events can be replayed identically)
- Convergence is bounded (ceiling exists)
- Damping exists (oscillation prevention)
- Oscillation prevention exists (convergence guarantees)
- Authority boundaries remain explicit (no hidden mutations)

### Transactional Authority Boundaries (MUST REMAIN EXPLICIT)

The following are **explicit transactional boundaries** and MUST NOT become reconciliation loops:

| Boundary | Authority | Mutability | Reconciliation Allowed |
|---|---|---|---|
| merge approval | Human | Immutable | No |
| Git commits | Human/Git | Immutable | No |
| replay integrity finalization | Governance | Immutable | No |
| forensic snapshots | Governance | Immutable | No |
| artifact publication | Human | Immutable | No |
| governance escalation | Human | Immutable | No |
| schema migration | Governance | Immutable | No |

---

## Reconciliation Loop Validity Matrix

| Loop Type | State Source | Authority | Deterministic | Replay-Safe | Bounded | Valid |
|---|---|---|---|---|---|---|
| Runtime supervision | Operational | No | Yes | Yes | Yes | Yes |
| Projection refresh | Canonical events | No | Yes | Yes | Yes | Yes |
| Telemetry aggregation | Operational metrics | No | Yes | Yes | Yes | Yes |
| Workspace hygiene | Namespace state | No | Yes | Yes | Yes | Yes |
| Topology density | Projection state | No | Yes | Yes | Yes | Yes |
| Transport normalization | Envelope events | No | Yes | Yes | Yes | Yes |
| Merge approval | Human intent | Yes | No | N/A | N/A | **NO** |
| Commit creation | Human intent | Yes | No | N/A | N/A | **NO** |
| Replay mutation | Replay events | Yes | No | N/A | N/A | **NO** |
| Cross-workspace reconciliation | Multiple workspaces | Yes | No | No | N/A | **NO** |

---

## Canonical Event Model

### Event Properties

All reconciliation loops MUST operate on canonical events with the following properties:

1. **Immutable**: Events cannot be modified after creation
2. **Ordered**: Events have deterministic ordering (timestamp + sequence)
3. **Attributed**: Events have explicit source attribution
4. **Typed**: Events have explicit type classification
5. **Serialized**: Events can be deterministically serialized/deserialized

### Event Types

| Type | Purpose | Authority | Reconciliation Safe |
|---|---|---|---|
| RuntimeStatusEvent | Runtime state change | Operational | Yes |
| RuntimeCompletionEvent | Runtime completion | Operational | Yes |
| RuntimeFailureEvent | Runtime failure | Operational | Yes |
| RuntimeHeartbeatEvent | Runtime heartbeat | Operational | Yes |
| RuntimeToolProposalEvent | Tool proposal | Advisory | Yes (advisory only) |
| RuntimePatchProposalEvent | Patch proposal | Advisory | Yes (advisory only) |

---

## Deterministic Reconciliation Requirements

### Input Requirements

1. **Canonical Events Only**: All inputs must be canonical events from the event router
2. **No Implicit Authority**: Controllers must not infer authority from transport or timing
3. **Bounded History**: Controllers must operate on bounded event windows
4. **Ordering Guarantees**: Events must be processed in deterministic order

### Output Requirements

1. **Derived State Only**: Controllers may only produce derived (non-authoritative) state
2. **No Authority Mutation**: Controllers must not mutate canonical events or authoritative state
3. **Replay-Compatible**: All outputs must be replay-safe
4. **Bounded Changes**: Changes to derived state must respect convergence ceilings

### Controller Requirements

1. **Deterministic**: Same inputs → same outputs
2. **Idempotent**: Multiple applications of same input → same result
3. **Bounded**: Convergence must be bounded
4. **Damped**: Oscillation must be prevented
5. **Observable**: Health and state must be visible
6. **Cancellable**: Must support deterministic shutdown

---

## Reconciliation Controller Types

| Controller | Purpose | Input | Output | Cadence | Bounds |
|---|---|---|---|---|---|
| RuntimeSupervisionController | Runtime drift correction | Runtime events | Supervision state | Configurable | Runtime limits |
| ProjectionRefreshController | Projection convergence | Canonical events | Projection state | Event-driven | Projection bounds |
| TelemetryAggregationController | Telemetry synthesis | Telemetry events | Aggregated metrics | Configurable | Telemetry limits |
| WorkspaceHygieneController | Namespace cleanup | Workspace events | Cleanup actions | Configurable | Workspace limits |
| TopologyDensityController | Operational density stabilization | Topology events | Density state | Configurable | Topology limits |

---

## Bounded Convergence Principles

### Convergence Windows

All reconciliation loops must define explicit convergence windows:

```
convergence_window = min(maximum_iterations, time_bound)
```

- **Maximum Iterations**: Hard ceiling on correction attempts
- **Time Bound**: Hard ceiling on convergence duration
- **Convergence Detection**: Loop terminates when state stabilizes

### Damping Mechanisms

Oscillation prevention through damping factors:

| Damping Type | Purpose | Implementation |
|---|---|---|
| Exponential Backoff | Reduce correction magnitude over time | DampingFactor.exponential |
| Linear Attenuation | Linear reduction of correction | DampingFactor.linear |
| Threshold Damping | Minimum change threshold | DampingFactor.threshold |
| Hysteresis | State-dependent damping | DampingFactor.hysteresis |

### Retry Ceilings

All loops must have bounded retry behavior:

- **Maximum Retries**: Hard ceiling on retry attempts
- **Retry Backoff**: Exponential or linear backoff between retries
- **Retry Conditions**: Only retry on transient errors, not on bound violations

---

## Replay-Safe Reconciliation

### Requirements

1. **Deterministic Ordering**: Events must be processed in replay-identical order
2. **No Side Effects**: Reconciliation must not have side effects outside derived state
3. **Replay Detectable**: Controllers must detect and handle replay context
4. **State Reconstruction**: Controllers must support state reconstruction from event history

### Replay Context

Controllers must be aware of replay context:

```python
@dataclass
class ReconciliationContext:
    is_replay: bool
    replay_timestamp: Optional[datetime]
    event_sequence: int
    deterministic_ordering: bool
```

---

## Authority Boundary Enforcement

### Forbidden Operations

Reconciliation controllers MUST NOT:

1. Create Git commits
2. Approve merges
3. Mutate canonical event history
4. Rewrite replay data
5. Infer authority from transport
6. Create self-authorizing loops
7. Perform cross-workspace reconciliation
8. Mutate governance state

### Authority Inheritance

**FORBIDDEN**: No reconciliation loop may inherit authority.

- Controllers operate on derived state only
- Controllers may not elevate their own privileges
- Controllers may not bypass governance checks
- Controllers may not create new authority boundaries

---

## Operational Stability Guarantees

### Stability Properties

| Property | Guarantee | Enforcement |
|---|---|---|
| Deterministic | Same inputs → same outputs | Unit tests + property tests |
| Bounded | Convergence within ceilings | Runtime enforced |
| Replay-Safe | Identical behavior on replay | Event ordering + no side effects |
| Observable | Full visibility into state | Telemetry + health endpoints |
| cancellable | Deterministic shutdown | Cancellation hooks + cleanup |

### Failure Modes

| Failure Mode | Handler | Recovery |
|---|---|---|
| Convergence timeout | Abort loop, report error | Manual retry |
| Authority violation | Abort immediately, audit | Manual intervention |
| Replay conflict | Reject event, report | Replay from clean state |
| Oscillation detected | Apply damping, log | Automatic recovery |
| Bounds violated | Abort loop, report | Manual retry with new bounds |

---

## Non-Goals (Reiterated)

The following are **explicitly NOT goals** of this architecture:

- Everything becomes reactive
- Auto-approval systems
- Auto-commit systems
- Governance automation replacing humans
- Replay mutation loops
- Infinite event recursion
- Speculative distributed consensus
- Electron architecture
- Broad frontend rewrite
- Git replacement
- Destructive Git operations

---

## Summary

Rig implements **bounded operational reconciliation** where:

1. Events are the authoritative source of truth
2. Loops are convergence mechanisms, not authority generators
3. Authority boundaries remain explicit and immutable
4. Reconciliation is deterministic, replay-safe, and bounded
5. All loops have damping, retry ceilings, and convergence windows
6. Frontend is a dumb renderer of backend-authored projections

This architecture ensures Rig behaves as a **bounded operational reconciliation runtime** rather than a collection of disconnected event-capable systems.
