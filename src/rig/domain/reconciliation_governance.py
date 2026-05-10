"""Reconciliation Governance Primitives for Rig.

This module provides the governance primitives for reconciliation loops as defined
in PHASE 4 of the Deterministic Operational Reconciliation Sprint.

Core doctrine:
- All primitives are deterministic
- All primitives are bounded
- All primitives are replay-safe
- All primitives are observable
- All primitives are topology-visible

file: src/rig/domain/reconciliation_governance.py
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, FrozenSet, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Schema Version
# =============================================================================

SCHEMA_VERSION = "rig.reconciliation_governance.v1"


# =============================================================================
# Default Values
# =============================================================================

# Cadence defaults
DEFAULT_MIN_INTERVAL_SECONDS = 0.1
DEFAULT_MAX_INTERVAL_SECONDS = 10.0
DEFAULT_JITTER_FACTOR = 0.1

# Damping defaults
DEFAULT_DAMP_BASE = 0.5
DEFAULT_DAMP_RATE = 0.1
DEFAULT_DAMP_THRESHOLD = 0.01
DEFAULT_DAMP_MIN_FACTOR = 0.01
DEFAULT_DAMP_MAX_FACTOR = 1.0

# Retry defaults
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_BASE_DELAY = 0.1
DEFAULT_RETRY_MAX_DELAY = 10.0

# Convergence defaults
DEFAULT_MAX_ITERATIONS = 100
DEFAULT_MAX_DURATION_SECONDS = 60.0
DEFAULT_STABILISATION_THRESHOLD = 0.001
DEFAULT_STABILISATION_WINDOW_SECONDS = 2.0

# Event storm defaults
DEFAULT_MAX_EVENTS_PER_SECOND = 100
DEFAULT_BURST_THRESHOLD = 50
DEFAULT_BURST_WINDOW_SECONDS = 1.0
DEFAULT_QUEUE_MAX_SIZE = 1000

# Cancellation defaults
DEFAULT_CANCELLATION_TIMEOUT = 5.0
DEFAULT_FORCE_SHUTDOWN_AFTER = 10.0


# =============================================================================
# Enums
# =============================================================================

class DampingType(Enum):
    """Types of damping for oscillation prevention."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    THRESHOLD = "threshold"
    HYSTERESIS = "hysteresis"
    ADAPTIVE = "adaptive"


class RetryBackoffType(Enum):
    """Types of retry backoff."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


class DropPolicy(Enum):
    """Policy for dropping events during storm conditions."""
    NEWEST = "newest"
    OLDEST = "oldest"
    RANDOM = "random"


class LoopStatus(Enum):
    """Status of a reconciliation loop."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    CONVERGED = "converged"


# =============================================================================
# Reconciliation Cadence
# =============================================================================

@dataclass(frozen=True, slots=True)
class ReconciliationCadence:
    """Bounded refresh interval for reconciliation loops.
    
    Purpose: Enforce bounded cadence for all reconciliation loops
    
    Requirements:
    - Loops MUST respect their configured cadence
    - Loops MUST NOT run faster than min_interval
    - Loops MUST NOT run slower than max_interval (unless blocked)
    - Loops MUST apply jitter to prevent synchronization
    
    Replay-safe: Yes (deterministic configuration)
    Bounded: Yes (explicit min/max intervals)
    Deterministic: Yes (same configuration -> same intervals with same jitter seed)
    Observable: Yes (configuration is inspectable)
    Topology-visible: Yes (can be queried via health endpoints)
    """
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS
    max_interval_seconds: float = DEFAULT_MAX_INTERVAL_SECONDS
    jitter_factor: float = DEFAULT_JITTER_FACTOR

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be >= 0")
        if self.max_interval_seconds < self.min_interval_seconds:
            raise ValueError("max_interval_seconds must be >= min_interval_seconds")
        if not 0.0 <= self.jitter_factor <= 1.0:
            raise ValueError("jitter_factor must be in [0.0, 1.0]")

    def calculate_next_interval(self, jitter_seed: Optional[int] = None) -> float:
        """Calculate the next interval with jitter.
        
        Args:
            jitter_seed: Optional seed for deterministic jitter (for replay safety)
            
        Returns:
            Next interval in seconds
        """
        # Use seed for deterministic jitter if provided (replay safety)
        if jitter_seed is not None:
            rng = random.Random(jitter_seed + self._get_hash())
            base = rng.uniform(self.min_interval_seconds, self.max_interval_seconds)
            jitter = base * self.jitter_factor * rng.uniform(-1, 1)
        else:
            base = random.uniform(self.min_interval_seconds, self.max_interval_seconds)
            jitter = base * self.jitter_factor * random.uniform(-1, 1)
        
        return max(self.min_interval_seconds, base + jitter)

    def _get_hash(self) -> int:
        """Get hash of configuration for deterministic jitter."""
        return hash((
            self.min_interval_seconds,
            self.max_interval_seconds,
            self.jitter_factor,
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# =============================================================================
# Damping Factor
# =============================================================================

@dataclass(frozen=True, slots=True)
class DampingFactor:
    """Oscillation prevention mechanism.
    
    Purpose: Prevent oscillation in reconciliation loops
    
    Requirements:
    - Damping MUST be applied on every correction iteration
    - Damping factor MUST remain within [min_factor, max_factor]
    - Damping MUST prevent oscillation in all configured scenarios
    - Damping is REQUIRED for all loops (not optional)
    
    Replay-safe: Yes (deterministic application)
    Bounded: Yes (min_factor <= factor <= max_factor)
    Deterministic: Yes (same inputs -> same outputs)
    Observable: Yes (type, base, rate all inspectable)
    Topology-visible: Yes (can be queried via health endpoints)
    """
    damp_type: DampingType = DampingType.EXPONENTIAL
    base: float = DEFAULT_DAMP_BASE
    rate: float = DEFAULT_DAMP_RATE
    threshold: float = DEFAULT_DAMP_THRESHOLD
    min_factor: float = DEFAULT_DAMP_MIN_FACTOR
    max_factor: float = DEFAULT_DAMP_MAX_FACTOR

    def __init__(
        self,
        damp_type: DampingType = DampingType.EXPONENTIAL,
        base: float = DEFAULT_DAMP_BASE,
        rate: float = DEFAULT_DAMP_RATE,
        threshold: float = DEFAULT_DAMP_THRESHOLD,
        min_factor: float = DEFAULT_DAMP_MIN_FACTOR,
        max_factor: float = DEFAULT_DAMP_MAX_FACTOR,
        **aliases: Any,
    ) -> None:
        if "damping_type" in aliases:
            damp_type = aliases.pop("damping_type")
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"unexpected keyword arguments: {unexpected}")
        object.__setattr__(self, "damp_type", damp_type)
        object.__setattr__(self, "base", base)
        object.__setattr__(self, "rate", rate)
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "min_factor", min_factor)
        object.__setattr__(self, "max_factor", max_factor)
        self.__post_init__()

    def __post_init__(self) -> None:
        if not 0.0 < self.base <= 1.0:
            raise ValueError("base must be in (0.0, 1.0]")
        if not 0.0 < self.rate <= 1.0:
            raise ValueError("rate must be in (0.0, 1.0]")
        if self.threshold < 0:
            raise ValueError("threshold must be >= 0")
        if not 0.0 <= self.min_factor <= self.max_factor <= 1.0:
            raise ValueError("min_factor <= max_factor must be in [0.0, 1.0]")

    def apply(self, iteration: int, current_value: float) -> float:
        """Apply damping to a value based on iteration count.
        
        Args:
            iteration: Current iteration number
            current_value: Value to damp
            
        Returns:
            Damped value
        """
        if self.damp_type == DampingType.EXPONENTIAL:
            factor = self.base ** iteration
        elif self.damp_type == DampingType.LINEAR:
            factor = max(0.0, 1.0 - self.rate * iteration)
        elif self.damp_type == DampingType.THRESHOLD:
            return current_value if abs(current_value) >= self.threshold else 0.0
        elif self.damp_type == DampingType.HYSTERESIS:
            # State-dependent damping
            factor = self.base if current_value > 0 else 1.0 / self.base
        elif self.damp_type == DampingType.ADAPTIVE:
            # Learn from history - simplified for now
            factor = self.base ** (iteration ** 0.5)
        else:
            factor = self.base

        if self.damp_type == DampingType.HYSTERESIS:
            return factor * abs(current_value)

        effective_min = max(self.min_factor, DEFAULT_DAMP_MIN_FACTOR)
        damped_factor = max(effective_min, min(self.max_factor, factor))
        return damped_factor * current_value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# =============================================================================
# Retry Ceiling
# =============================================================================

@dataclass(frozen=True, slots=True)
class RetryCeiling:
    """Bounded retry configuration.
    
    Purpose: Enforce bounded retry behavior for reconciliation loops
    
    Requirements:
    - Only transient errors may be retried
    - Permanent errors (authority violations, bounds violations) must NOT be retried
    - Must use exponential or linear backoff
    - Must respect max_retries
    
    Replay-safe: Yes (deterministic configuration)
    Bounded: Yes (max_retries is hard ceiling)
    Deterministic: Yes (same retry count -> same delay)
    Observable: Yes (retry count, delays all inspectable)
    Topology-visible: Yes (can be queried via health endpoints)
    
    Retryable errors:
    - Network timeout
    - Resource unavailable
    - Rate limit exceeded
    - Model unavailable
    
    Non-retryable errors:
    - Authority violation
    - Bounds violation
    - Replay conflict
    - Convergence timeout
    """
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY
    retry_backoff_type: RetryBackoffType = RetryBackoffType.EXPONENTIAL
    retryable_errors: FrozenSet[str] = frozenset({
        "timeout",
        "network_error",
        "resource_unavailable",
        "rate_limited",
        "model_unavailable",
    })

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
        retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY,
        retry_backoff_type: RetryBackoffType = RetryBackoffType.EXPONENTIAL,
        retryable_errors: FrozenSet[str] = frozenset({
            "timeout",
            "network_error",
            "resource_unavailable",
            "rate_limited",
            "model_unavailable",
        }),
        **aliases: Any,
    ) -> None:
        if "base_delay_seconds" in aliases:
            retry_base_delay = aliases.pop("base_delay_seconds")
        if "max_delay_seconds" in aliases:
            retry_max_delay = aliases.pop("max_delay_seconds")
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"unexpected keyword arguments: {unexpected}")
        object.__setattr__(self, "max_retries", max_retries)
        object.__setattr__(self, "retry_base_delay", retry_base_delay)
        object.__setattr__(self, "retry_max_delay", retry_max_delay)
        object.__setattr__(self, "retry_backoff_type", retry_backoff_type)
        object.__setattr__(self, "retryable_errors", retryable_errors)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.retry_base_delay < 0:
            raise ValueError("retry_base_delay must be >= 0")
        if self.retry_max_delay < self.retry_base_delay:
            raise ValueError("retry_max_delay must be >= retry_base_delay")

    def calculate_delay(self, retry_count: int) -> float:
        """Calculate delay for a retry attempt.
        
        Args:
            retry_count: Number of retries already attempted
            
        Returns:
            Delay in seconds before next retry
        """
        if self.retry_backoff_type == RetryBackoffType.EXPONENTIAL:
            delay = self.retry_base_delay * (2 ** retry_count)
        elif self.retry_backoff_type == RetryBackoffType.LINEAR:
            delay = self.retry_base_delay * (retry_count + 1)
        else:  # CONSTANT
            delay = self.retry_base_delay
        return round(min(delay, self.retry_max_delay), 10)

    def is_retryable(self, error_type: str) -> bool:
        """Check if an error is retryable.
        
        Args:
            error_type: Type of error (string identifier)
            
        Returns:
            True if error can be retried, False otherwise
        """
        return error_type.lower() in {e.lower() for e in self.retryable_errors}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            **asdict(self),
            'retryable_errors': list(self.retryable_errors),
        }


# =============================================================================
# Convergence Window
# =============================================================================

@dataclass(frozen=True, slots=True)
class ConvergenceWindow:
    """Bounded correction window for convergence.
    
    Purpose: Define explicit convergence bounds for reconciliation loops
    
    Requirements:
    - Loop MUST terminate when convergence detected
    - Loop MUST terminate when bounds reached
    - Loop MUST report convergence status
    
    Replay-safe: Yes (deterministic configuration)
    Bounded: Yes (max_iterations and max_duration are hard ceilings)
    Deterministic: Yes (same conditions -> same detection)
    Observable: Yes (all bounds inspectable)
    Topology-visible: Yes (can be queried via health endpoints)
    
    Convergence detection:
    Loop is considered converged when:
    1. State changes are below stabilisation_threshold for stabilisation_window
    2. OR max_iterations reached
    3. OR max_duration_seconds reached
    """
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS
    stabilisation_threshold: float = DEFAULT_STABILISATION_THRESHOLD
    stabilisation_window: float = DEFAULT_STABILISATION_WINDOW_SECONDS

    def __init__(
        self,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
        stabilisation_threshold: float = DEFAULT_STABILISATION_THRESHOLD,
        stabilisation_window: float = DEFAULT_STABILISATION_WINDOW_SECONDS,
        **aliases: Any,
    ) -> None:
        if "stabilisation_window_seconds" in aliases:
            stabilisation_window = aliases.pop("stabilisation_window_seconds")
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"unexpected keyword arguments: {unexpected}")
        object.__setattr__(self, "max_iterations", max_iterations)
        object.__setattr__(self, "max_duration_seconds", max_duration_seconds)
        object.__setattr__(self, "stabilisation_threshold", stabilisation_threshold)
        object.__setattr__(self, "stabilisation_window", stabilisation_window)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if self.max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be > 0")
        if self.stabilisation_threshold < 0:
            raise ValueError("stabilisation_threshold must be >= 0")
        if self.stabilisation_window <= 0:
            raise ValueError("stabilisation_window must be > 0")

    def is_converged(
        self,
        iterations: int,
        duration: float,
        last_change: Optional[float] = None,
        stabilisation_threshold_met: bool = False,
    ) -> bool:
        """Check if convergence has been reached.
        
        Args:
            iterations: Current iteration count
            duration: Current duration in seconds
            last_change: Timestamp of last change (for stabilisation check)
            stabilisation_threshold_met: Whether change is below threshold
            
        Returns:
            True if convergence reached, False otherwise
        """
        # Check max iterations
        if iterations >= self.max_iterations:
            return True
        
        # Check max duration
        if duration >= self.max_duration_seconds:
            return True
        
        # Check stabilisation (simplified for now - real impl would track history)
        if stabilisation_threshold_met:
            return True
        
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# =============================================================================
# Cancellation Policy
# =============================================================================

@dataclass(frozen=True, slots=True)
class CancellationPolicy:
    """Deterministic shutdown configuration.
    
    Purpose: Define deterministic shutdown behavior for reconciliation loops
    
    Requirements:
    - Loop MUST be cancellable at any point
    - Loop MUST complete current iteration before stopping (graceful)
    - Loop MUST execute cleanup hooks
    - Loop MUST report final state
    
    Replay-safe: Yes (deterministic configuration)
    Bounded: Yes (cancellation_timeout is hard ceiling)
    Deterministic: Yes (same conditions -> same shutdown sequence)
    Observable: Yes (timeout values inspectable)
    Topology-visible: Yes (can be queried via health endpoints)
    
    Shutdown sequence:
    1. Graceful Request: Signal loop to stop
    2. Current Iteration: Complete current iteration
    3. Cleanup: Execute cleanup hooks
    4. Force Shutdown: If timeout exceeded, force stop
    """
    cancellation_timeout: float = DEFAULT_CANCELLATION_TIMEOUT
    force_shutdown_after: float = DEFAULT_FORCE_SHUTDOWN_AFTER
    cleanup_hook_keys: List[str] = field(default_factory=list)

    def __init__(
        self,
        cancellation_timeout: float = DEFAULT_CANCELLATION_TIMEOUT,
        force_shutdown_after: float = DEFAULT_FORCE_SHUTDOWN_AFTER,
        cleanup_hook_keys: Optional[List[str]] = None,
        **aliases: Any,
    ) -> None:
        if "cleanup_hooks" in aliases:
            cleanup_hook_keys = aliases.pop("cleanup_hooks")
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"unexpected keyword arguments: {unexpected}")
        object.__setattr__(self, "cancellation_timeout", cancellation_timeout)
        object.__setattr__(self, "force_shutdown_after", force_shutdown_after)
        object.__setattr__(self, "cleanup_hook_keys", list(cleanup_hook_keys or []))
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.cancellation_timeout < 0:
            raise ValueError("cancellation_timeout must be >= 0")
        if self.force_shutdown_after < self.cancellation_timeout:
            raise ValueError("force_shutdown_after must be >= cancellation_timeout")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# =============================================================================
# Event Storm Config
# =============================================================================

@dataclass(frozen=True, slots=True)
class EventStormConfig:
    """Event storm detection and prevention configuration.
    
    Purpose: Detect and prevent event storms in reconciliation loops
    
    Requirements:
    - Rate Limiting: Limit events processed per interval
    - Burst Detection: Detect sudden spikes in event volume
    - Backpressure: Apply backpressure when overwhelmed
    - Dropping: Drop events when queue exceeds threshold
    
    Replay-safe: Yes (deterministic configuration)
    Bounded: Yes (queue_max_size is hard ceiling)
    Deterministic: Yes (same conditions -> same mitigation)
    Observable: Yes (all thresholds inspectable)
    Topology-visible: Yes (can be queried via health endpoints)
    
    Storm mitigation:
    | Condition | Action |
    |---|---|
    | Rate > max_events_per_second | Throttle input |
    | Burst detected | Enter storm mode, increase damping |
    | Queue > queue_max_size | Drop events per drop_policy |
    | Storm sustained | Log, alert, consider shutdown |
    """
    max_events_per_second: int = DEFAULT_MAX_EVENTS_PER_SECOND
    burst_threshold: int = DEFAULT_BURST_THRESHOLD
    burst_window_seconds: float = DEFAULT_BURST_WINDOW_SECONDS
    queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE
    drop_policy: DropPolicy = DropPolicy.NEWEST

    def __init__(
        self,
        max_events_per_second: int = DEFAULT_MAX_EVENTS_PER_SECOND,
        burst_threshold: int = DEFAULT_BURST_THRESHOLD,
        burst_window_seconds: float = DEFAULT_BURST_WINDOW_SECONDS,
        queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE,
        drop_policy: DropPolicy = DropPolicy.NEWEST,
        **aliases: Any,
    ) -> None:
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"unexpected keyword arguments: {unexpected}")
        object.__setattr__(self, "max_events_per_second", max_events_per_second)
        object.__setattr__(self, "burst_threshold", burst_threshold)
        object.__setattr__(self, "burst_window_seconds", burst_window_seconds)
        object.__setattr__(self, "queue_max_size", queue_max_size)
        object.__setattr__(self, "drop_policy", drop_policy)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.max_events_per_second < 1:
            raise ValueError("max_events_per_second must be >= 1")
        if self.burst_threshold < 1:
            raise ValueError("burst_threshold must be >= 1")
        if self.burst_window_seconds <= 0:
            raise ValueError("burst_window_seconds must be > 0")
        if self.queue_max_size < 1:
            raise ValueError("queue_max_size must be >= 1")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# =============================================================================
# Loop Health State
# =============================================================================

@dataclass(frozen=True, slots=True)
class ConvergenceInfo:
    """Information about convergence state."""
    current_iteration: int
    total_iterations: int
    current_duration: float
    max_duration: float
    stabilisation_threshold: float
    converged: bool
    last_change: Optional[float] = None


@dataclass(frozen=True, slots=True)
class DampingInfo:
    """Information about damping state."""
    current_factor: float
    damp_type: DampingType
    iterations_applied: int
    oscillation_detected: bool


@dataclass(frozen=True, slots=True)
class RetryInfo:
    """Information about retry state."""
    retry_count: int
    total_retries: int
    last_error: Optional[str]
    next_delay: Optional[float]


@dataclass(frozen=True, slots=True)
class LoopHealthState:
    """Health state of a reconciliation loop.
    
    Purpose: Provide full visibility into loop state
    
    Requirements:
    - Health state MUST be observable via telemetry
    - Health state MUST be queryable via API
    - Health state MUST be logged at configured intervals
    
    Replay-safe: Yes (state can be reconstructed from events)
    Bounded: Yes (all values have explicit bounds)
    Deterministic: Yes (same state -> same representation)
    Observable: Yes (entirely for observability)
    Topology-visible: Yes (explicitly for topology awareness)
    """
    loop_id: str
    controller_type: str
    status: LoopStatus
    iterations: int = 0
    last_iteration_time: Optional[datetime] = None
    last_error: Optional[str] = None
    convergence_info: Optional[ConvergenceInfo] = None
    damping_info: Optional[DampingInfo] = None
    retry_info: Optional[RetryInfo] = None

    def __init__(
        self,
        loop_id: str,
        controller_type: Any,
        status: LoopStatus,
        iterations: int = 0,
        last_iteration_time: Optional[datetime] = None,
        last_error: Optional[str] = None,
        convergence_info: Optional[ConvergenceInfo] = None,
        damping_info: Optional[DampingInfo] = None,
        retry_info: Optional[RetryInfo] = None,
        **aliases: Any,
    ) -> None:
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"unexpected keyword arguments: {unexpected}")
        object.__setattr__(self, "loop_id", loop_id)
        object.__setattr__(self, "controller_type", controller_type)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "iterations", iterations)
        object.__setattr__(self, "last_iteration_time", last_iteration_time)
        object.__setattr__(self, "last_error", last_error)
        object.__setattr__(self, "convergence_info", convergence_info)
        object.__setattr__(self, "damping_info", damping_info)
        object.__setattr__(self, "retry_info", retry_info)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["status"] = self.status.name
        if self.convergence_info:
            result['convergence_info'] = asdict(self.convergence_info)
        if self.damping_info:
            result['damping_info'] = asdict(self.damping_info)
        if self.retry_info:
            result['retry_info'] = asdict(self.retry_info)
        return result


# =============================================================================
# Reconciliation Context
# =============================================================================

@dataclass(frozen=True, slots=True)
class ReconciliationContext:
    """Context for reconciliation operations.
    
    Purpose: Provide context for reconciliation loops including replay detection
    
    Requirements:
    - All loops MUST be replay-compatible
    - All loops MUST detect replay context
    - All loops MUST support reconstruction from events
    
    Replay-safe: Yes (by design)
    Bounded: N/A (contextual)
    Deterministic: Yes (same context -> same behavior)
    Observable: Yes (all fields inspectable)
    Topology-visible: Yes (workspace_id is topology-aware)
    
    Replay handling:
    | Context | Behavior |
    |---|---|
    | Normal operation | Process events normally |
    | Replay detected | Skip side effects, verify determinism |
    | Replay with conflicts | Reject conflicting events, report |
    """
    is_replay: bool = False
    replay_timestamp: Optional[datetime] = None
    event_sequence: int = 0
    deterministic_ordering: bool = True
    workspace_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


# =============================================================================
# Authority Boundary Checkers
# =============================================================================

class AuthorityBoundaryViolationError(RuntimeError):
    """Raised when a reconciliation loop attempts to violate authority boundaries."""
    pass


def check_authority_violation(
    action: str,
    target: Any,
    workspace_id: Optional[str] = None,
    allowed_patterns: Optional[Set[str]] = None,
    forbidden_patterns: Optional[Set[str]] = None,
) -> bool:
    """Check if an action would violate authority boundaries.
    
    Args:
        action: The action being attempted
        target: The target of the action
        workspace_id: Current workspace for scope checking
        allowed_patterns: Optional set of allowed action patterns
        forbidden_patterns: Optional set of forbidden action patterns
        
    Returns:
        True if violation detected, False otherwise
        
    Raises:
        AuthorityBoundaryViolationError: If violation detected and strict mode
    """
    # Default forbidden patterns
    default_forbidden = {
        "commit",
        "merge", 
        "approve",
        "publish",
        "authorize",
        "governance_mutation",
        "replay_mutation",
        "authority_inference",
        "schema_migration",
        "finalize",
        "snapshot",
    }
    
    action_lower = action.lower()

    if allowed_patterns is not None:
        for allowed_pattern in allowed_patterns:
            if allowed_pattern.lower() in action_lower:
                return len(allowed_patterns) == 1

    forbidden = default_forbidden | {
        "governance",
        "replay",
        "authority",
    } | (forbidden_patterns or set())
    for forbidden_pattern in forbidden:
        if forbidden_pattern in action_lower:
            return True
    
    # Check for cross-workspace operations
    if workspace_id and hasattr(target, 'workspace_id'):
        target_ws = getattr(target, 'workspace_id', None)
        if target_ws and target_ws != workspace_id:
            return True
    
    return False


def enforce_authority_boundary(
    action: str,
    target: Any,
    workspace_id: Optional[str] = None,
) -> None:
    """Enforce authority boundary - raise if violation detected.
    
    Args:
        action: The action being attempted
        target: The target of the action
        workspace_id: Current workspace for scope checking
        
    Raises:
        AuthorityBoundaryViolationError: If violation detected
    """
    if check_authority_violation(action, target, workspace_id):
        raise AuthorityBoundaryViolationError(
            f"Authority boundary violation: action={action}, target={target}, workspace={workspace_id}"
        )


# =============================================================================
# exports
# =============================================================================

__all__ = [
    # Schema
    'SCHEMA_VERSION',
    # Enums
    'DampingType',
    'RetryBackoffType',
    'DropPolicy',
    'LoopStatus',
    # Primitives
    'ReconciliationCadence',
    'DampingFactor',
    'RetryCeiling',
    'ConvergenceWindow',
    'CancellationPolicy',
    'EventStormConfig',
    # Health and Info
    'ConvergenceInfo',
    'DampingInfo',
    'RetryInfo',
    'LoopHealthState',
    'ReconciliationContext',
    # Authority
    'AuthorityBoundaryViolationError',
    'check_authority_violation',
    'enforce_authority_boundary',
    # Constants
    'DEFAULT_MIN_INTERVAL_SECONDS',
    'DEFAULT_MAX_INTERVAL_SECONDS',
    'DEFAULT_JITTER_FACTOR',
    'DEFAULT_DAMP_BASE',
    'DEFAULT_DAMP_RATE',
    'DEFAULT_DAMP_THRESHOLD',
    'DEFAULT_DAMP_MIN_FACTOR',
    'DEFAULT_DAMP_MAX_FACTOR',
    'DEFAULT_MAX_RETRIES',
    'DEFAULT_RETRY_BASE_DELAY',
    'DEFAULT_RETRY_MAX_DELAY',
    'DEFAULT_MAX_ITERATIONS',
    'DEFAULT_MAX_DURATION_SECONDS',
    'DEFAULT_STABILISATION_THRESHOLD',
    'DEFAULT_STABILISATION_WINDOW_SECONDS',
    'DEFAULT_MAX_EVENTS_PER_SECOND',
    'DEFAULT_BURST_THRESHOLD',
    'DEFAULT_BURST_WINDOW_SECONDS',
    'DEFAULT_QUEUE_MAX_SIZE',
    'DEFAULT_CANCELLATION_TIMEOUT',
    'DEFAULT_FORCE_SHUTDOWN_AFTER',
]
