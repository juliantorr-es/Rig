# Loop Governance

> **Canonical Doctrine**: No infinite reconciliation. No self-authorizing loops. No replay mutation. No transport-as-authority semantics.

---

## Overview

This document establishes the governance constraints for all reconciliation loops in Rig. It defines the bounded reconciliation doctrine and the required constraints that must be enforced for all operational loops.

**Core Principle**: Reconciliation loops are operational convergence mechanisms bound by explicit governance constraints.

---

## Bounded Reconciliation Doctrine

Rig implements **bounded reconciliation** where:

1. All loops have explicit cadence limits
2. All loops have damping mechanisms
3. All loops have retry ceilings
4. All loops are replay-compatible
5. No loop may inherit or create authority

---

## Governance Concern Matrix

| Governance Concern | Required Constraint | Enforcement | Violation Handler |
|---|---|---|---|
| loop cadence | bounded intervals | ReconciliationCadence | Abort loop, report |
| damping | required | DampingFactor | Apply damping, log |
| retry ceilings | bounded | RetryCeiling | Abort retries, report |
| event storms | prevented | Event storm detection | Throttle, drop, log |
| oscillation | prevented | DampingFactor + ConvergenceWindow | Apply damping, log |
| convergence windows | explicit | ConvergenceWindow | Abort on timeout, report |
| cancellation | deterministic | CancellationPolicy | Graceful shutdown |
| replay compatibility | mandatory | Replay-safe design | Reject conflicting events |
| authority inheritance | forbidden | Authority boundary checks | Abort immediately, audit |

---

## Loop Cadence Governance

### Cadence Constraints

All reconciliation loops MUST define:

1. **Minimum Interval**: Lower bound on time between loop iterations
2. **Maximum Interval**: Upper bound on time between loop iterations
3. **Jitter Window**: Random jitter to prevent thundering herd

```python
@dataclass
class ReconciliationCadence:
    min_interval_seconds: float  # >= 0.0, typically 0.1-1.0
    max_interval_seconds: float  # >= min_interval_seconds, typically 1.0-60.0
    jitter_factor: float = 0.1    # 0.0-1.0, fraction of interval for jitter
```

### Cadence Profiles

| Profile | Min Interval | Max Interval | Jitter | Use Case |
|---|---|---|---|---|
| Aggressive | 0.1s | 1.0s | 0.2 | High-priority runtime supervision |
| Standard | 1.0s | 10.0s | 0.1 | Telemetry aggregation, projection refresh |
| Lazy | 10.0s | 60.0s | 0.05 | Workspace hygiene, low-priority cleanup |
| Background | 60.0s | 300.0s | 0.01 | Long-running topology convergence |

### Cadence Enforcement

- Loops MUST respect their configured cadence
- Loops MUST NOT run faster than min_interval
- Loops MUST NOT run slower than max_interval (unless blocked)
- Loops MUST apply jitter to prevent synchronization

---

## Damping Governance

### Damping Requirements

All loops MUST have damping mechanisms to prevent oscillation. Damping is **REQUIRED**, not optional.

### Damping Types

| Damping Type | Implementation | Use Case | Oscillation Prevention |
|---|---|---|---|
| Exponential | factor *= base^(iterations) | General purpose | High |
| Linear | factor *= 1 - (rate * iterations) | Predictable behavior | Medium |
| Threshold | Skip if change < threshold | Small corrections | High |
| Hysteresis | State-dependent factor | Mode switching | High |
| Adaptive | Learn from history | Complex systems | Medium |

### Damping Configuration

```python
@dataclass
class DampingFactor:
    damp_type: DampingType  # exponential, linear, threshold, hysteresis, adaptive
    base: float = 0.5        # For exponential: 0.0-1.0
    rate: float = 0.1        # For linear: 0.0-1.0
    threshold: float = 0.01  # For threshold: minimum change
    min_factor: float = 0.01 # Minimum damping factor
    max_factor: float = 1.0  # Maximum damping factor
```

### Damping Enforcement

- Damping MUST be applied on every correction iteration
- Damping factor MUST remain within [min_factor, max_factor]
- Damping MUST prevent oscillation in all configured scenarios

---

## Retry Ceilings

### Retry Constraints

All loops MUST have bounded retry behavior.

```python
@dataclass
class RetryCeiling:
    max_retries: int               # Hard ceiling, typically 3-10
    retry_base_delay: float        # Initial delay in seconds
    retry_max_delay: float         # Maximum delay in seconds
    retry_backoff_type: str        # "exponential", "linear", "constant"
    retryable_errors: FrozenSet[str] # Set of retryable error types
```

### Retry Rules

1. **Retryable Errors**: Only transient errors may be retried
2. **Permanent Errors**: Authority violations, bounds violations must NOT be retried
3. **Backoff**: Must use exponential or linear backoff
4. **Ceiling**: Must respect max_retries

### Retryable vs Non-Retryable Errors

| Error Type | Retryable | Reason |
|---|---|---|
| Network timeout | Yes | Transient |
| Resource unavailable | Yes | Transient |
| Rate limit exceeded | Yes | Retry after delay |
| Authority violation | **NO** | Permanent |
| Bounds violation | **NO** | Permanent |
| Replay conflict | **NO** | Permanent |
| Convergence timeout | **NO** | Permanent |

---

## Event Storm Prevention

### Storm Detection

Loops MUST detect and prevent event storms:

1. **Rate Limiting**: Limit events processed per interval
2. **Burst Detection**: Detect sudden spikes in event volume
3. **Backpressure**: Apply backpressure when overwhelmed
4. **Dropping**: Drop events when queue exceeds threshold

### Storm Configuration

```python
@dataclass
class EventStormConfig:
    max_events_per_second: int    # Rate limit
    burst_threshold: int           # Events that trigger storm mode
    burst_window_seconds: float    # Window for burst detection
    queue_max_size: int            # Max queue size before dropping
    drop_policy: str = "newest"    # "newest", "oldest", "random"
```

### Storm Mitigation

| Condition | Action |
|---|---|
| Rate > max_events_per_second | Throttle input |
| Burst detected | Enter storm mode, increase damping |
| Queue > queue_max_size | Drop events per drop_policy |
| Storm sustained | Log, alert, consider shutdown |

---

## Oscillation Prevention

### Oscillation Detection

Loops MUST detect and prevent oscillation:

1. **State Oscillation**: State alternates between values
2. **Correction Oscillation**: Corrections alternate direction
3. **Convergence Failure**: Loop fails to converge within window

### Oscillation Metrics

```python
@dataclass
class OscillationMetrics:
    state_changes: List[Tuple[datetime, Any]]  # History of state changes
    correction_history: List[Tuple[datetime, float]]  # History of corrections
    oscillation_count: int  # Number of detected oscillations
    last_oscillation_time: Optional[datetime]  # Last oscillation time
```

### Oscillation Response

| Detection | Response |
|---|---|
| Single oscillation | Apply damping, log |
| Repeated oscillation | Increase damping, extend convergence window |
| Sustained oscillation | Abort loop, report critical |

---

## Convergence Windows

### Window Constraints

All loops MUST define explicit convergence windows:

```python
@dataclass
class ConvergenceWindow:
    max_iterations: int            # Maximum correction attempts
    max_duration_seconds: float    # Maximum time for convergence
    stabilisation_threshold: float # Threshold for "converged" detection
    stabilisation_window: float    # Time window for convergence detection
```

### Convergence Detection

Loop is considered converged when:

1. State changes are below stabilisation_threshold for stabilisation_window
2. OR max_iterations reached
3. OR max_duration_seconds reached

### Window Enforcement

- Loop MUST terminate when convergence detected
- Loop MUST terminate when bounds reached
- Loop MUST report convergence status

---

## Cancellation Policy

### Deterministic Shutdown

All loops MUST support deterministic shutdown:

```python
@dataclass
class CancellationPolicy:
    cancellation_timeout: float    # Time to wait for graceful shutdown
    force_shutdown_after: float   # Time to force shutdown
    cleanup_hooks: List[Callable]  # Functions to call on shutdown
```

### Shutdown Sequence

1. **Graceful Request**: Signal loop to stop
2. **Current Iteration**: Complete current iteration
3. **Cleanup**: Execute cleanup hooks
4. **Force Shutdown**: If timeout exceeded, force stop

### Cancellation Guarantees

- Loop MUST be cancellable at any point
- Loop MUST complete current iteration before stopping
- Loop MUST execute cleanup hooks
- Loop MUST report final state

---

## Replay Compatibility

### Mandatory Requirements

All loops MUST be replay-compatible:

1. **Deterministic Processing**: Same events → same results
2. **No Side Effects**: No external mutations during replay
3. **Replay Detection**: Must detect replay context
4. **State Reconstruction**: Must support reconstruction from events

### Replay Context

```python
@dataclass
class ReconciliationContext:
    is_replay: bool
    replay_timestamp: Optional[datetime]
    event_sequence: int
    deterministic_ordering: bool = True
```

### Replay Handling

| Context | Behavior |
|---|---|
| Normal operation | Process events normally |
| Replay detected | Skip side effects, verify determinism |
| Replay with conflicts | Reject conflicting events, report |

---

## Authority Boundary Enforcement

### Forbidden Authority Inheritance

**NO reconciliation loop may inherit authority.**

### Authority Checks

All loops MUST enforce:

1. **No Event Authority**: Events are facts, not authority
2. **No Transport Authority**: Transport does not confer authority
3. **No Timing Authority**: Timing does not confer authority
4. **No Loop Authority**: Loops do not have inherent authority

### Authority Violation Response

| Violation | Response |
|---|---|
| Attempt to create commit | Abort immediately, audit log |
| Attempt to approve merge | Abort immediately, audit log |
| Attempt to mutate governance state | Abort immediately, audit log |
| Attempt to infer authority | Abort immediately, audit log |
| Transport authority inference | Reject event, audit log |

---

## Loop Health State

### Health Metrics

All loops MUST expose health state:

```python
@dataclass
class LoopHealthState:
    loop_id: str
    status: LoopStatus  # running, stopped, error, converged
    iterations: int
    last_iteration_time: Optional[datetime]
    last_error: Optional[str]
    convergence_info: Optional[ConvergenceInfo]
    damping_info: Optional[DampingInfo]
    retry_info: Optional[RetryInfo]
```

### Health Visibility

- Health state MUST be observable via telemetry
- Health state MUST be queryable via API
- Health state MUST be logged at configured intervals

---

## Transport Semantics

### Transport-as-Authority: FORBIDDEN

**Transport mechanisms do NOT confer authority.**

- WebSocket messages are transport, not authority
- HTTP requests are transport, not authority
- Event buses are transport, not authority
- Authoritative decisions must come from governance engine

### Canonical Envelope Requirement

All transport MUST use canonical envelopes:

```python
@dataclass
class CanonicalEnvelope:
    event_id: str
    event_type: str
    timestamp: datetime
    sequence: int
    source: str
    payload: Dict[str, Any]
    authority_hint: Optional[str] = None  # ADVISORY ONLY, not authority
```

---

## Cross-Workspace Constraints

### Cross-Workspace Reconciliation: FORBIDDEN

**NO loop may perform cross-workspace reconciliation.**

### Workspace Isolation

- Each loop operates within a single workspace
- Loops may not access state from other workspaces
- Loops may not mutate state in other workspaces
- Workspace boundaries are explicit and enforced

---

## Summary: Bounded Reconciliation Doctrine

Rig enforces **bounded reconciliation** through:

1. **Bounded cadence**: All loops have explicit interval constraints
2. **Required damping**: All loops have oscillation prevention
3. **Bounded retries**: All loops have retry ceilings
4. **Mandatory replay compatibility**: All loops are replay-safe
5. **Explicit convergence windows**: All loops have convergence bounds
6. **Deterministic cancellation**: All loops support graceful shutdown
7. **Forbidden authority inheritance**: No loop may create or inherit authority
8. **Forbidden cross-workspace**: No loop may span workspaces
9. **Transport-as-authority forbidden**: Transport does not confer authority

This governance ensures Rig behaves as a **bounded operational reconciliation runtime** with explicit authority boundaries and deterministic behavior.
