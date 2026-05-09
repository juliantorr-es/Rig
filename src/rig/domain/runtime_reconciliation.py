"""Runtime Reconciliation Controllers for Rig.

This module provides deterministic operational reconciliation controllers for Phase 3
of the Deterministic Operational Reconciliation Sprint.

Core doctrine:
- Controllers are operational convergence mechanisms, NOT authority generators
- All reconciliation is deterministic, replay-safe, and bounded
- Authority boundaries remain explicit
- Events are authoritative facts; loops consume and derive from them
- No controller may mutate canonical event history or governance state
- Frontend is a dumb renderer of backend-authored projections

file: src/rig/domain/runtime_reconciliation.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Deque,
    Dict,
    FrozenSet,
    List,
    Optional,
    Set,
    Tuple,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from rig.domain.runtime_events import RuntimeEvent
    from rig.domain.runtime_event_router import RuntimeEventRouter

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

SCHEMA_VERSION = "rig.reconciliation.v1"

# Default bounds
DEFAULT_MAX_ITERATIONS = 100
DEFAULT_MAX_DURATION_SECONDS = 60.0
DEFAULT_STABILISATION_THRESHOLD = 0.001
DEFAULT_STABILISATION_WINDOW_SECONDS = 2.0
DEFAULT_MIN_INTERVAL_SECONDS = 0.1
DEFAULT_MAX_INTERVAL_SECONDS = 10.0
DEFAULT_JITTER_FACTOR = 0.1
DEFAULT_MAX_RETRIES = 5
DEFAULT_RETRY_BASE_DELAY = 0.1
DEFAULT_RETRY_MAX_DELAY = 10.0
DEFAULT_MAX_EVENTS_PER_SECOND = 100
DEFAULT_BURST_THRESHOLD = 50
DEFAULT_BURST_WINDOW_SECONDS = 1.0
DEFAULT_QUEUE_MAX_SIZE = 1000

# Authority violation strings
AUTHORITY_VIOLATION_COMMIT = "attempted_commit_creation"
AUTHORITY_VIOLATION_MERGE = "attempted_merge_approval"
AUTHORITY_VIOLATION_GOVERNANCE = "attempted_governance_mutation"
AUTHORITY_VIOLATION_REPLAY = "attempted_replay_mutation"
AUTHORITY_VIOLATION_AUTHORITY = "attempted_authority_inference"


# =============================================================================
# Enums
# =============================================================================

class LoopStatus(Enum):
    """Status of a reconciliation loop."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"
    CONVERGED = "converged"


class ControllerType(Enum):
    """Types of reconciliation controllers."""
    RUNTIME_SUPERVISION = "runtime_supervision"
    PROJECTION_REFRESH = "projection_refresh"
    TELEMETRY_AGGREGATION = "telemetry_aggregation"
    WORKSPACE_HYGIENE = "workspace_hygiene"
    TOPOLOGY_DENSITY = "topology_density"


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


# =============================================================================
# Governance Primitives (from PHASE 4)
# =============================================================================

@dataclass(frozen=True, slots=True)
class ReconciliationCadence:
    """Bounded refresh interval for reconciliation loops."""
    min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS
    max_interval_seconds: float = DEFAULT_MAX_INTERVAL_SECONDS
    jitter_factor: float = DEFAULT_JITTER_FACTOR

    def __init__(
        self,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        max_interval_seconds: float = DEFAULT_MAX_INTERVAL_SECONDS,
        jitter_factor: float = DEFAULT_JITTER_FACTOR,
        **aliases: Any,
    ) -> None:
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"unexpected keyword arguments: {unexpected}")
        object.__setattr__(self, "min_interval_seconds", min_interval_seconds)
        object.__setattr__(self, "max_interval_seconds", max_interval_seconds)
        object.__setattr__(self, "jitter_factor", jitter_factor)
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be >= 0")
        if self.max_interval_seconds < self.min_interval_seconds:
            raise ValueError("max_interval_seconds must be >= min_interval_seconds")
        if not 0.0 <= self.jitter_factor <= 1.0:
            raise ValueError("jitter_factor must be in [0.0, 1.0]")

    def calculate_next_interval(self) -> float:
        """Calculate the next interval with jitter."""
        base = random.uniform(self.min_interval_seconds, self.max_interval_seconds)
        jitter = base * self.jitter_factor * random.uniform(-1, 1)
        return max(self.min_interval_seconds, base + jitter)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DampingFactor:
    """Oscillation prevention mechanism."""
    damp_type: DampingType = DampingType.EXPONENTIAL
    base: float = 0.5
    rate: float = 0.1
    threshold: float = 0.01
    min_factor: float = 0.01
    max_factor: float = 1.0

    def __init__(
        self,
        damp_type: DampingType = DampingType.EXPONENTIAL,
        base: float = 0.5,
        rate: float = 0.1,
        threshold: float = 0.01,
        min_factor: float = 0.01,
        max_factor: float = 1.0,
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
        """Apply damping to a value based on iteration count."""
        if self.damp_type == DampingType.EXPONENTIAL:
            factor = self.base ** (iteration + 1)
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

        effective_min = max(self.min_factor, 0.01)
        return max(effective_min, min(self.max_factor, factor)) * current_value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RetryCeiling:
    """Bounded retry configuration."""
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
        """Calculate delay for a retry attempt."""
        if self.retry_backoff_type == RetryBackoffType.EXPONENTIAL:
            delay = self.retry_base_delay * (2 ** retry_count)
        elif self.retry_backoff_type == RetryBackoffType.LINEAR:
            delay = self.retry_base_delay * (retry_count + 1)
        else:  # CONSTANT
            delay = self.retry_base_delay
        return round(min(delay, self.retry_max_delay), 10)

    def is_retryable(self, error_type: str) -> bool:
        """Check if an error is retryable."""
        return error_type in self.retryable_errors

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ConvergenceWindow:
    """Bounded correction window for convergence."""
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
        if iterations >= self.max_iterations:
            return True
        if duration >= self.max_duration_seconds:
            return True
        return stabilisation_threshold_met

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CancellationPolicy:
    """Deterministic shutdown configuration."""
    cancellation_timeout: float = 5.0
    force_shutdown_after: float = 10.0
    cleanup_hooks: List[Callable[[], Coroutine[Any, Any, None]]] = field(default_factory=list)

    def __init__(
        self,
        cancellation_timeout: float = 5.0,
        force_shutdown_after: float = 10.0,
        cleanup_hooks: Optional[List[Callable[[], Coroutine[Any, Any, None]]]] = None,
        **aliases: Any,
    ) -> None:
        if "cleanup_hook_keys" in aliases:
            cleanup_hooks = aliases.pop("cleanup_hook_keys")
        if aliases:
            unexpected = ", ".join(sorted(aliases))
            raise TypeError(f"unexpected keyword arguments: {unexpected}")
        object.__setattr__(self, "cancellation_timeout", cancellation_timeout)
        object.__setattr__(self, "force_shutdown_after", force_shutdown_after)
        object.__setattr__(self, "cleanup_hooks", list(cleanup_hooks or []))
        self.__post_init__()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __post_init__(self) -> None:
        if self.cancellation_timeout < 0:
            raise ValueError("cancellation_timeout must be >= 0")
        if self.force_shutdown_after < self.cancellation_timeout:
            raise ValueError("force_shutdown_after must be >= cancellation_timeout")


@dataclass(frozen=True, slots=True)
class EventStormConfig:
    """Event storm detection and prevention configuration."""
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

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
        result = asdict(self)
        result["drop_policy"] = self.drop_policy.name
        return result


@dataclass(frozen=True, slots=True)
class ReconciliationContext:
    """Context for reconciliation operations."""
    is_replay: bool = False
    replay_timestamp: Optional[datetime] = None
    event_sequence: int = 0
    deterministic_ordering: bool = True
    workspace_id: Optional[str] = None


# =============================================================================
# Health and Info Types
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
    """Health state of a reconciliation loop."""
    loop_id: str
    controller_type: ControllerType
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
            result["convergence_info"] = asdict(self.convergence_info)
        if self.damping_info:
            result["damping_info"] = asdict(self.damping_info)
        if self.retry_info:
            result["retry_info"] = asdict(self.retry_info)
        return result


# =============================================================================
# Oscillation Detection
# =============================================================================

@dataclass(slots=True)
class OscillationMetrics:
    """Metrics for detecting oscillation."""
    state_changes: Deque[Tuple[datetime, Any]] = field(default_factory=deque)
    correction_history: Deque[Tuple[datetime, float]] = field(default_factory=deque)
    oscillation_count: int = 0
    last_oscillation_time: Optional[datetime] = None
    max_history: int = 100

    def record_state_change(self, timestamp: datetime, state: Any) -> None:
        """Record a state change."""
        self.state_changes.append((timestamp, state))
        while len(self.state_changes) > self.max_history:
            self.state_changes.popleft()

    def record_correction(self, timestamp: datetime, correction: float) -> None:
        """Record a correction."""
        self.correction_history.append((timestamp, correction))
        while len(self.correction_history) > self.max_history:
            self.correction_history.popleft()

    def detect_oscillation(self, threshold: float = 0.5, window_size: int = 3) -> bool:
        """Detect oscillation in state changes.
        
        Args:
            threshold: Minimum ratio of alternating changes to detect oscillation
            window_size: Number of recent changes to check
            
        Returns:
            True if oscillation detected
        """
        if len(self.state_changes) < window_size * 2:
            return False
        
        # Check if state is alternating in the recent window
        recent = list(self.state_changes)[-window_size:]
        if len(recent) < 2:
            return False
        
        # Simple oscillation detection: check if values alternate
        alternating = True
        for i in range(1, len(recent)):
            if recent[i][1] == recent[i-1][1]:
                alternating = False
                break
        
        if alternating:
            self.oscillation_count += 1
            self.last_oscillation_time = datetime.now(timezone.utc)
            return True
        
        return False


# =============================================================================
# Base Reconciliation Controller
# =============================================================================

class ReconciliationController(ABC):
    """Abstract base class for reconciliation controllers.
    
    All reconciliation controllers must:
    - Be deterministic (same inputs -> same outputs)
    - Be replay-safe (can reconstruct state from events)
    - Have bounded cadence
    - Support damping
    - Have bounded retries
    - Be cancellable
    - Not mutate authority boundaries
    """

    @dataclass
    class Config:
        """Configuration for a reconciliation controller."""
        controller_id: str
        controller_type: ControllerType
        cadence: ReconciliationCadence = field(default_factory=ReconciliationCadence)
        damping: DampingFactor = field(default_factory=DampingFactor)
        retry: RetryCeiling = field(default_factory=RetryCeiling)
        convergence: ConvergenceWindow = field(default_factory=ConvergenceWindow)
        cancellation: CancellationPolicy = field(default_factory=CancellationPolicy)
        event_storm: EventStormConfig = field(default_factory=EventStormConfig)
        enabled: bool = True
        workspace_id: Optional[str] = None

    def __init__(self, config: Config) -> None:
        self.config = config
        self._status: LoopStatus = LoopStatus.PENDING
        self._iterations: int = 0
        self._last_iteration_time: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._context: ReconciliationContext = ReconciliationContext()
        self._oscillation: OscillationMetrics = OscillationMetrics()
        self._event_buffer: Deque[Any] = deque()
        self._storm_mode: bool = False
        self._converged: bool = False

    @property
    def controller_id(self) -> str:
        return self.config.controller_id

    @property
    def controller_type(self) -> ControllerType:
        return self.config.controller_type

    @property
    def status(self) -> LoopStatus:
        return self._status

    @property
    def iterations(self) -> int:
        return self._iterations

    @property
    def running(self) -> bool:
        return self._running

    @property
    def context(self) -> ReconciliationContext:
        return self._context

    @context.setter
    def context(self, value: ReconciliationContext) -> None:
        self._context = value

    @property
    def health_state(self) -> LoopHealthState:
        """Get current health state."""
        convergence_info = None
        if self._status in (LoopStatus.RUNNING, LoopStatus.CONVERGED):
            convergence_info = ConvergenceInfo(
                current_iteration=self._iterations,
                total_iterations=self.config.convergence.max_iterations,
                current_duration=0.0,  # Simplified for now
                max_duration=self.config.convergence.max_duration_seconds,
                stabilisation_threshold=self.config.convergence.stabilisation_threshold,
                converged=self._converged,
            )
        
        return LoopHealthState(
            loop_id=self.controller_id,
            controller_type=self.controller_type,
            status=self._status,
            iterations=self._iterations,
            last_iteration_time=self._last_iteration_time,
            last_error=self._last_error,
            convergence_info=convergence_info,
            damping_info=DampingInfo(
                current_factor=1.0,  # Simplified
                damp_type=self.config.damping.damp_type,
                iterations_applied=self._iterations,
                oscillation_detected=self._oscillation.detect_oscillation(),
            ),
            retry_info=RetryInfo(
                retry_count=0,  # Simplified
                total_retries=self.config.retry.max_retries,
                last_error=self._last_error,
                next_delay=None,
            ),
        )

    def _check_authority_violation(self, action: str, target: Any) -> bool:
        """Check for authority violations. Returns True if violation detected.
        
        This method enforces the rule that reconciliation controllers MUST NOT
        mutate authoritative state or create authority.
        """
        forbidden_actions = {
            "commit", "merge", "approve", "publish", "authorize",
            "governance_mutation", "replay_mutation", "authority_inference",
            "schema_migration", "finalize", "snapshot",
        }

        action_lower = action.lower()
        for allowed in ("refresh_projection", "reconcile_state", "damp_correction"):
            if allowed in action_lower:
                return False
        forbidden_actions = forbidden_actions | {
            "governance",
            "replay",
            "authority",
        }
        for forbidden in forbidden_actions:
            if forbidden in action_lower:
                return True
        
        # Check for cross-workspace operations
        if self.config.workspace_id and hasattr(target, 'workspace_id'):
            target_ws = getattr(target, 'workspace_id', None)
            if target_ws and target_ws != self.config.workspace_id:
                return True
        
        return False

    def _authority_violation_response(self, violation_type: str) -> None:
        """Handle authority violation - abort and log."""
        self._last_error = f"AUTHORITY VIOLATION: {violation_type}"
        self._status = LoopStatus.ERROR
        logger.error(f"[{self.controller_id}] AUTHORITY VIOLATION: {violation_type}")
        self._running = False
        if self._task:
            self._task.cancel()
        raise RuntimeError(f"Authority violation: {violation_type}")

    def _check_event_storm(self) -> bool:
        """Check for event storm conditions and apply mitigation."""
        if len(self._event_buffer) > self.config.event_storm.queue_max_size:
            # Drop events per policy
            if self.config.event_storm.drop_policy == DropPolicy.NEWEST:
                # Drop from the right (newest)
                while len(self._event_buffer) > self.config.event_storm.queue_max_size:
                    self._event_buffer.pop()
            elif self.config.event_storm.drop_policy == DropPolicy.OLDEST:
                # Drop from the left (oldest)
                while len(self._event_buffer) > self.config.event_storm.queue_max_size:
                    self._event_buffer.popleft()
            else:  # RANDOM
                while len(self._event_buffer) > self.config.event_storm.queue_max_size:
                    idx = random.randint(0, len(self._event_buffer) - 1)
                    del self._event_buffer[idx]
            
            self._storm_mode = True
            logger.warning(f"[{self.controller_id}] Event storm detected, dropped events")
            return True
        return False

    def _check_convergence(self) -> bool:
        """Check if convergence has been reached."""
        if self._iterations >= self.config.convergence.max_iterations:
            self._converged = True
            return True
        return False

    def _apply_damping(self, value: float, iteration: int) -> float:
        """Apply damping to a value."""
        return self.config.damping.apply(iteration, value)

    @abstractmethod
    async def reconcile_once(self) -> None:
        """Perform a single reconciliation iteration.
        
        This method must be implemented by subclasses and must:
        - Be deterministic
        - Be replay-safe
        - Not mutate authoritative state
        - Respect all governance constraints
        """
        raise NotImplementedError

    @abstractmethod
    def get_events(self) -> List[Any]:
        """Get events to process. Must return canonical events."""
        raise NotImplementedError

    @abstractmethod
    def derive_state(self, events: List[Any]) -> Any:
        """Derive state from events. Must be deterministic."""
        raise NotImplementedError

    @abstractmethod
    def calculate_correction(self, current_state: Any, desired_state: Any) -> Any:
        """Calculate correction. Must be deterministic and bounded."""
        raise NotImplementedError

    @abstractmethod
    def apply_correction(self, correction: Any) -> None:
        """Apply correction. Must not mutate authoritative state."""
        raise NotImplementedError

    async def _run_iteration(self) -> None:
        """Run a single reconciliation iteration with all governance checks."""
        try:
            # Check if we should run
            if not self.config.enabled or not self._running:
                return

            # Get and buffer events
            events = self.get_events()
            self._event_buffer.extend(events)
            
            # Check for event storm
            self._check_event_storm()
            
            # Process buffered events
            if self._event_buffer:
                processed_events = list(self._event_buffer)
                self._event_buffer.clear()
                
                # Derive state from events (deterministic)
                current_state = self.derive_state(processed_events)
                
                # Record state for oscillation detection
                self._oscillation.record_state_change(
                    datetime.now(timezone.utc), 
                    current_state
                )
                
                # Calculate desired state (deterministic)
                desired_state = self.calculate_desired_state(current_state)
                
                # Calculate correction (deterministic, bounded)
                correction = self.calculate_correction(current_state, desired_state)
                
                # Record correction for oscillation detection
                correction_magnitude = self._calculate_correction_magnitude(correction)
                self._oscillation.record_correction(
                    datetime.now(timezone.utc),
                    correction_magnitude
                )
                
                # Apply damping
                damped_correction = self._apply_correction_with_damping(
                    correction, 
                    self._iterations
                )
                
                # Check authority
                if self._check_authority_violation(
                    str(type(damped_correction).__name__), 
                    damped_correction
                ):
                    self._authority_violation_response(AUTHORITY_VIOLATION_AUTHORITY)
                    return
                
                # Apply correction
                self.apply_correction(damped_correction)
                
                # Check convergence
                if self._check_convergence():
                    self._status = LoopStatus.CONVERGED
                    self._running = False
                    return
            
            self._iterations += 1
            self._last_iteration_time = datetime.now(timezone.utc)
            
        except asyncio.CancelledError:
            logger.info(f"[{self.controller_id}] Iteration cancelled")
            raise
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"[{self.controller_id}] Iteration error: {e}")
            self._status = LoopStatus.ERROR

    def _calculate_correction_magnitude(self, correction: Any) -> float:
        """Calculate magnitude of a correction for oscillation detection."""
        if correction is None:
            return 0.0
        if isinstance(correction, (int, float)):
            return abs(float(correction))
        if hasattr(correction, '__len__'):
            return float(len(correction))
        return 1.0

    def _apply_correction_with_damping(self, correction: Any, iteration: int) -> Any:
        """Apply damping to correction based on iteration."""
        if correction is None:
            return None
        if isinstance(correction, (int, float)):
            return self._apply_damping(float(correction), iteration)
        if isinstance(correction, dict):
            return {k: self._apply_correction_with_damping(v, iteration) 
                    for k, v in correction.items()}
        if isinstance(correction, list):
            return [self._apply_correction_with_damping(v, iteration) 
                    for v in correction]
        return correction

    def calculate_desired_state(self, current_state: Any) -> Any:
        """Calculate desired state from current state.
        
        Subclasses should override this for specific desired state logic.
        Default implementation returns current state (no change desired).
        """
        return current_state

    async def start(self) -> None:
        """Start the reconciliation loop."""
        if self._running:
            return
        
        self._running = True
        self._status = LoopStatus.RUNNING
        self._iterations = 0
        self._last_error = None
        self._converged = False
        self._storm_mode = False
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the reconciliation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._status = LoopStatus.STOPPED

    async def pause(self) -> None:
        """Pause the reconciliation loop."""
        self._status = LoopStatus.PAUSED

    async def resume(self) -> None:
        """Resume the reconciliation loop."""
        if self._status == LoopStatus.PAUSED:
            self._status = LoopStatus.RUNNING

    async def _run_loop(self) -> None:
        """Main reconciliation loop."""
        while self._running and self._status not in (
            LoopStatus.ERROR, 
            LoopStatus.CONVERGED,
            LoopStatus.STOPPED
        ):
            # Calculate next iteration delay based on cadence
            next_interval = self.config.cadence.calculate_next_interval()
            
            # Run iteration
            await self._run_iteration()
            
            # Respect cadence
            await asyncio.sleep(next_interval)


# =============================================================================
# Runtime Supervision Controller
# =============================================================================

class RuntimeSupervisionController(ReconciliationController):
    """Controller for runtime drift correction.
    
    Purpose: Continuously monitor runtime state and correct drift.
    Input: Runtime events (status, heartbeat, completion, failure)
    Output: Supervision state updates
    Cadence: Configurable (typically aggressive: 0.1-1.0s)
    Bounds: Runtime-specific limits
    
    DO NOT:
    - Mutate governance state
    - Create commits
    - Auto-approve merges
    - Rewrite replay
    - Mutate canonical event history
    """

    def __init__(self, config: ReconciliationController.Config) -> None:
        super().__init__(config)
        self._runtime_states: Dict[str, Any] = {}
        self._last_heartbeat: Dict[str, datetime] = {}

    def get_events(self) -> List[Any]:
        """Get runtime events from the event router."""
        # This would be connected to the actual event router
        # For now, return empty list - will be wired in integration
        return []

    def derive_state(self, events: List[Any]) -> Dict[str, Any]:
        """Derive runtime supervision state from events."""
        state = {}
        for event in events:
            # Process each event type
            event_type = getattr(event, 'event_type', None) or type(event).__name__
            stream_id = getattr(event, 'stream_id', 'unknown')
            
            if 'Status' in event_type:
                state[stream_id] = {
                    'status': getattr(event, 'status', str(event)),
                    'timestamp': getattr(event, 'timestamp', None),
                    'stream_id': stream_id,
                }
            elif 'Heartbeat' in event_type:
                self._last_heartbeat[stream_id] = datetime.now(timezone.utc)
                if stream_id in state:
                    state[stream_id]['last_heartbeat'] = self._last_heartbeat[stream_id]
            elif 'Completion' in event_type or 'Failure' in event_type:
                if stream_id in state:
                    state[stream_id]['status'] = event_type
                    state[stream_id]['finalized'] = True
        
        return state

    def calculate_desired_state(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate desired runtime state (all runtimes should be healthy)."""
        desired = {}
        for stream_id, runtime_state in current_state.items():
            desired[stream_id] = {
                'status': 'ACTIVE',
                'healthy': True,
                'last_heartbeat_recent': True,
            }
        return desired

    def calculate_correction(self, current_state: Dict[str, Any], desired_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate correction for runtime drift.
        
        This calculates what needs to change to correct drift.
        """
        correction = {}
        now = datetime.now(timezone.utc)
        
        for stream_id, desired in desired_state.items():
            current = current_state.get(stream_id, {})
            
            # Check for stalled runtimes (no heartbeat)
            last_hb = self._last_heartbeat.get(stream_id)
            if last_hb:
                stale = (now - last_hb).total_seconds() > 30.0  # 30s stale threshold
            else:
                stale = False
            
            current_status = current.get('status', 'UNKNOWN')
            
            # Identify drift
            drift = {}
            if current_status != desired.get('status'):
                drift['status'] = desired['status']
            if stale:
                drift['action'] = 'restart'
                drift['reason'] = 'stalled'
            if current.get('error'):
                drift['action'] = 'cleanup'
                drift['reason'] = 'error'
            
            if drift:
                correction[stream_id] = drift
        
        return correction

    def apply_correction(self, correction: Dict[str, Any]) -> None:
        """Apply runtime corrections.
        
        This sends signals/advisory actions to the runtime system.
        It does NOT directly mutate runtime state.
        """
        for stream_id, actions in correction.items():
            action = actions.get('action')
            reason = actions.get('reason')
            status = actions.get('status')
            
            # Authority check: ensure we're not trying to do forbidden operations
            if self._check_authority_violation(f"runtime_{action}", stream_id):
                self._authority_violation_response(
                    f"runtime_authority_violation: {action}"
                )
                continue
            
            # Log the advisory action
            logger.info(
                f"[{self.controller_id}] Advisory action for {stream_id}: "
                f"action={action}, reason={reason}, status={status}"
            )
            
            # In a real implementation, this would send advisory signals
            # to the runtime supervisor, which would then take appropriate action
            # through proper governance channels.

    async def reconcile_once(self) -> None:
        """Perform a single reconciliation iteration for runtime supervision."""
        events = self.get_events()
        current_state = self.derive_state(events)
        desired_state = self.calculate_desired_state(current_state)
        correction = self.calculate_correction(current_state, desired_state)
        self.apply_correction(correction)


# =============================================================================
# Projection Refresh Controller
# =============================================================================

class ProjectionRefreshController(ReconciliationController):
    """Controller for projection convergence.
    
    Purpose: Ensure projections are up-to-date with canonical events
    Input: Canonical events (from event router)
    Output: Projection refresh triggers
    Cadence: Event-driven with configurable bounds
    Bounds: Projection-specific limits
    
    DO NOT:
    - Introduce frontend authority
    - Create imperative rendering commands
    - Bypass canonical envelopes
    """

    def __init__(
        self, 
        config: ReconciliationController.Config,
        projection_registry: Optional[Any] = None,
    ) -> None:
        super().__init__(config)
        self._projection_registry = projection_registry
        self._last_refresh: Dict[str, datetime] = {}
        self._projection_versions: Dict[str, int] = {}

    def get_events(self) -> List[Any]:
        """Get projection-relevant events."""
        return []  # Will be wired to event router

    def derive_state(self, events: List[Any]) -> Dict[str, Any]:
        """Derive projection state from events."""
        state = {
            'projections': {},
            'events_by_projection': {},
        }
        
        for event in events:
            # Extract projection ID from event
            proj_id = getattr(event, 'projection_id', None) or \
                     getattr(event, 'workspace_id', 'default')
            
            if proj_id not in state['projections']:
                state['projections'][proj_id] = {
                    'version': 0,
                    'events': [],
                    'needs_refresh': False,
                }
            
            # Check if this event requires a projection update
            event_type = getattr(event, 'event_type', '')
            needs_update = any(
                t in event_type for t in 
                ['completion', 'failure', 'status', 'delta', 'update']
            )
            
            if needs_update:
                state['projections'][proj_id]['needs_refresh'] = True
                state['projections'][proj_id]['version'] += 1
            
            state['projections'][proj_id]['events'].append(event)
        
        return state

    def calculate_desired_state(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate desired projection state (all projections current)."""
        desired = {}
        for proj_id, proj_state in current_state.get('projections', {}).items():
            desired[proj_id] = {
                'version': proj_state.get('version', 0),
                'needs_refresh': False,
                'last_refresh_recent': True,
            }
        return desired

    def calculate_correction(self, current_state: Dict[str, Any], desired_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate which projections need refresh."""
        correction = {}
        
        for proj_id, desired in desired_state.items():
            current = current_state.get('projections', {}).get(proj_id, {})
            
            if current.get('needs_refresh') or current.get('version', 0) < desired.get('version', 0):
                correction[proj_id] = {
                    'action': 'refresh',
                    'target_version': desired.get('version', 0),
                    'priority': 'high' if current.get('needs_refresh') else 'normal',
                }
        
        return correction

    def apply_correction(self, correction: Dict[str, Any]) -> None:
        """Apply projection refresh corrections."""
        for proj_id, actions in correction.items():
            action = actions.get('action')
            
            if self._check_authority_violation(f"projection_{action}", proj_id):
                self._authority_violation_response(
                    f"projection_authority_violation: {action}"
                )
                continue
            
            # Log refresh trigger
            logger.info(
                f"[{self.controller_id}] Projection refresh trigger: "
                f"projection={proj_id}, action={action}"
            )
            
            # Mark as refreshed
            self._last_refresh[proj_id] = datetime.now(timezone.utc)
            self._projection_versions[proj_id] = actions.get('target_version', 0)

    async def reconcile_once(self) -> None:
        """Perform a single reconciliation iteration for projection refresh."""
        events = self.get_events()
        current_state = self.derive_state(events)
        desired_state = self.calculate_desired_state(current_state)
        correction = self.calculate_correction(current_state, desired_state)
        self.apply_correction(correction)


# =============================================================================
# Telemetry Aggregation Controller
# =============================================================================

class TelemetryAggregationController(ReconciliationController):
    """Controller for telemetry synthesis.
    
    Purpose: Continuous operational synthesis from normalized telemetry
    Input: Telemetry events
    Output: Aggregated metrics
    Cadence: Configurable (typically standard: 1.0-10.0s)
    Bounds: Telemetry-specific limits
    
    Requirements:
    - Backend-agnostic
    - Normalized telemetry
    - Replay-safe
    - Bounded oscillation
    - Topology-aware
    """

    def __init__(self, config: ReconciliationController.Config) -> None:
        super().__init__(config)
        self._metrics: Dict[str, Any] = {}
        self._aggregation_windows: Dict[str, float] = {}

    def get_events(self) -> List[Any]:
        """Get telemetry events."""
        return []  # Will be wired to event router

    def derive_state(self, events: List[Any]) -> Dict[str, Any]:
        """Derive telemetry state from events."""
        state = {
            'throughput': 0.0,
            'queue_depth': 0,
            'runtime_saturation': 0.0,
            'cadence': 0.0,
            'density': 0.0,
            'raw_events': events,
        }
        
        for event in events:
            event_type = getattr(event, 'event_type', '')
            
            if 'throughput' in event_type.lower() or 'rate' in event_type.lower():
                state['throughput'] += float(getattr(event, 'value', 0))
            elif 'queue' in event_type.lower():
                state['queue_depth'] = max(state['queue_depth'], int(getattr(event, 'depth', 0)))
            elif 'saturation' in event_type.lower():
                state['runtime_saturation'] = max(
                    state['runtime_saturation'],
                    float(getattr(event, 'saturation', 0))
                )
            elif 'cadence' in event_type.lower():
                state['cadence'] = float(getattr(event, 'cadence', 0))
            elif 'density' in event_type.lower():
                state['density'] = float(getattr(event, 'density', 0))
        
        # Normalize values
        state['throughput'] = min(state['throughput'], 1000.0)  # Cap at 1000
        state['queue_depth'] = min(state['queue_depth'], 10000)  # Cap at 10000
        state['runtime_saturation'] = min(state['runtime_saturation'], 1.0)  # Cap at 1.0
        state['density'] = min(state['density'], 1.0)  # Cap at 1.0
        
        return state

    def calculate_desired_state(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate desired telemetry state (stable, bounded values)."""
        return {
            'throughput_stable': True,
            'queue_depth_bounded': True,
            'runtime_saturation_bounded': True,
            'cadence_stable': True,
            'density_converged': True,
        }

    def calculate_correction(self, current_state: Dict[str, Any], desired_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate telemetry stabilization corrections."""
        correction = {}
        
        # Throughput stabilization
        throughput = current_state.get('throughput', 0)
        if throughput > 100.0:  # High throughput needs stabilization
            correction['throughput'] = {
                'action': 'stabilize',
                'target_value': 100.0,
                'damping': 'exponential',
            }
        
        # Queue depth convergence
        queue_depth = current_state.get('queue_depth', 0)
        if queue_depth > 100:
            correction['queue_depth'] = {
                'action': 'reduce',
                'target_value': 100,
                'damping': 'linear',
            }
        
        # Runtime cooling
        saturation = current_state.get('runtime_saturation', 0)
        if saturation > 0.8:
            correction['runtime_saturation'] = {
                'action': 'cool',
                'target_value': 0.8,
                'damping': 'exponential',
            }
        
        # Cadence stabilization
        cadence = current_state.get('cadence', 0)
        if cadence > 10.0:
            correction['cadence'] = {
                'action': 'smooth',
                'target_value': 10.0,
                'damping': 'threshold',
            }
        
        # Density convergence
        density = current_state.get('density', 0)
        if density > 0.9:
            correction['density'] = {
                'action': 'reduce',
                'target_value': 0.9,
                'damping': 'hysteresis',
            }
        
        return correction

    def apply_correction(self, correction: Dict[str, Any]) -> None:
        """Apply telemetry corrections (advisory signals)."""
        for metric, actions in correction.items():
            action = actions.get('action')
            
            if self._check_authority_violation(f"telemetry_{action}", metric):
                self._authority_violation_response(
                    f"telemetry_authority_violation: {action}"
                )
                continue
            
            logger.info(
                f"[{self.controller_id}] Telemetry advisory: "
                f"metric={metric}, action={action}, target={actions.get('target_value')}"
            )
            
            # Update metrics (derived state only)
            if metric in self._metrics:
                # Apply damping to the correction
                current = self._metrics[metric]
                target = actions.get('target_value', current)
                damped = self._apply_damping(target - current, self._iterations)
                self._metrics[metric] = current + damped

    async def reconcile_once(self) -> None:
        """Perform a single reconciliation iteration for telemetry aggregation."""
        events = self.get_events()
        current_state = self.derive_state(events)
        desired_state = self.calculate_desired_state(current_state)
        correction = self.calculate_correction(current_state, desired_state)
        self.apply_correction(correction)


# =============================================================================
# Workspace Hygiene Controller
# =============================================================================

class WorkspaceHygieneController(ReconciliationController):
    """Controller for workspace namespace cleanup.
    
    Purpose: Clean up stale artifacts, verify namespace hygiene
    Input: Workspace events
    Output: Cleanup actions
    Cadence: Configurable (typically lazy: 10.0-60.0s)
    Bounds: Workspace-specific limits
    
    ALLOWED Workspace Loops:
    - Stale artifact cleanup
    - Namespace hygiene
    - Temp-state cleanup
    - Runtime health verification
    - Isolation verification
    
    FORBIDDEN Workspace Loops:
    - Cross-lane reconciliation
    - Auto-routing authority
    - Replay mutation
    - Implicit merges
    - Artifact authority inference
    """

    def __init__(
        self,
        config: ReconciliationController.Config,
        workspace_id: str,
    ) -> None:
        # Override workspace_id in config
        config = ReconciliationController.Config(
            **{**asdict(config), 'workspace_id': workspace_id}
        )
        super().__init__(config)
        self._stale_artifacts: Dict[str, datetime] = {}
        self._temp_states: Dict[str, datetime] = {}
        self._namespace_states: Dict[str, Dict[str, Any]] = {}

    def get_events(self) -> List[Any]:
        """Get workspace events."""
        return []  # Will be wired to event router

    def derive_state(self, events: List[Any]) -> Dict[str, Any]:
        """Derive workspace hygiene state from events."""
        state = {
            'stale_artifacts': {},
            'temp_states': {},
            'namespace_health': {},
            'isolation_status': 'verified',
            'runtime_health': {},
        }
        
        for event in events:
            event_type = getattr(event, 'event_type', '')
            artifact_id = getattr(event, 'artifact_id', None) or \
                         getattr(event, 'path', 'unknown')
            
            if 'artifact' in event_type.lower() and 'stale' in event_type.lower():
                state['stale_artifacts'][artifact_id] = {
                    'last_accessed': getattr(event, 'timestamp', None),
                    'stale': True,
                }
            elif 'temp' in event_type.lower():
                state['temp_states'][artifact_id] = {
                    'created': getattr(event, 'timestamp', None),
                    'expires': getattr(event, 'expires', None),
                }
            elif 'namespace' in event_type.lower():
                ns_id = getattr(event, 'namespace_id', 'default')
                state['namespace_health'][ns_id] = {
                    'status': getattr(event, 'status', 'unknown'),
                    'issues': getattr(event, 'issues', []),
                }
            elif 'isolation' in event_type.lower():
                if 'violation' in event_type.lower():
                    state['isolation_status'] = 'violated'
            elif 'runtime' in event_type.lower() and 'health' in event_type.lower():
                rt_id = getattr(event, 'runtime_id', 'unknown')
                state['runtime_health'][rt_id] = {
                    'status': getattr(event, 'status', 'unknown'),
                    'healthy': getattr(event, 'healthy', False),
                }
        
        return state

    def calculate_desired_state(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate desired workspace hygiene state."""
        return {
            'stale_artifacts': {},
            'temp_states': {},
            'namespace_health': {ns: {'status': 'healthy'} for ns in current_state.get('namespace_health', {})},
            'isolation_status': 'verified',
            'runtime_health': {rt: {'healthy': True} for rt in current_state.get('runtime_health', {})},
        }

    def calculate_correction(self, current_state: Dict[str, Any], desired_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate workspace cleanup corrections."""
        correction = {}
        now = datetime.now(timezone.utc)
        
        # Stale artifact cleanup
        for artifact_id, artifact_info in current_state.get('stale_artifacts', {}).items():
            last_accessed = artifact_info.get('last_accessed')
            if last_accessed:
                age = (now - last_accessed).total_seconds()
                if age > 86400:  # 24 hours
                    correction[f'cleanup_stale_{artifact_id}'] = {
                        'action': 'remove',
                        'target': artifact_id,
                        'reason': 'stale_artifact',
                        'age_seconds': age,
                    }
        
        # Temp state cleanup
        for temp_id, temp_info in current_state.get('temp_states', {}).items():
            expires = temp_info.get('expires')
            if expires and expires < now:
                correction[f'cleanup_temp_{temp_id}'] = {
                    'action': 'remove',
                    'target': temp_id,
                    'reason': 'expired_temp',
                }
        
        # Namespace hygiene
        for ns_id, ns_info in current_state.get('namespace_health', {}).items():
            if ns_info.get('status') != 'healthy':
                correction[f'namespace_{ns_id}'] = {
                    'action': 'VerifyAndRepair',
                    'target': ns_id,
                    'reason': 'namespace_unhealthy',
                    'issues': ns_info.get('issues', []),
                }
        
        # Isolation verification
        if current_state.get('isolation_status') != 'verified':
            correction['isolation'] = {
                'action': 'verify',
                'reason': 'isolation_violation_detected',
            }
        
        # Runtime health verification
        for rt_id, rt_info in current_state.get('runtime_health', {}).items():
            if not rt_info.get('healthy'):
                correction[f'runtime_{rt_id}'] = {
                    'action': 'health_check',
                    'target': rt_id,
                    'reason': 'runtime_unhealthy',
                }
        
        return correction

    def apply_correction(self, correction: Dict[str, Any]) -> None:
        """Apply workspace hygiene corrections."""
        for action_id, actions in correction.items():
            action = actions.get('action')
            target = actions.get('target')
            
            # CRITICAL: Check for forbidden workspace operations
            forbidden_patterns = [
                'reconcile_cross',
                'auto_route',
                'replay_mutate',
                'implicit_merge',
                'authority_infer',
            ]
            
            action_lower = action.lower()
            for forbidden in forbidden_patterns:
                if forbidden in action_lower:
                    self._authority_violation_response(
                        f"forbidden_workspace_operation: {action}"
                    )
                    continue
            
            # Only allow workspace-scoped operations
            if self.config.workspace_id and target:
                # Verify target is in this workspace
                # In real implementation, this would check workspace boundaries
                pass
            
            logger.info(
                f"[{self.controller_id}] Workspace hygiene action: "
                f"action={action}, target={target}, reason={actions.get('reason')}"
            )
            
            # Mark as cleaned up (derived state update only)
            if action == 'remove':
                self._stale_artifacts.pop(target, None)
                self._temp_states.pop(target, None)

    async def reconcile_once(self) -> None:
        """Perform a single reconciliation iteration for workspace hygiene."""
        events = self.get_events()
        current_state = self.derive_state(events)
        desired_state = self.calculate_desired_state(current_state)
        correction = self.calculate_correction(current_state, desired_state)
        self.apply_correction(correction)


# =============================================================================
# Topology Density Controller
# =============================================================================

class TopologyDensityController(ReconciliationController):
    """Controller for operational density stabilization.
    
    Purpose: Stabilize topology density for calm dashboards
    Input: Topology delta events
    Output: Density state updates
    Cadence: Configurable (typically background: 60.0-300.0s)
    Bounds: Topology-specific limits
    
    Frontend doctrine: dashboards become calmer as reconciliation pressure increases
    """

    def __init__(self, config: ReconciliationController.Config) -> None:
        super().__init__(config)
        self._density_metrics: Dict[str, float] = {}

    def get_events(self) -> List[Any]:
        """Get topology delta events."""
        return []  # Will be wired to event router

    def derive_state(self, events: List[Any]) -> Dict[str, Any]:
        """Derive topology density state from events."""
        state = {
            'node_density': 0.0,
            'edge_density': 0.0,
            'visual_complexity': 0.0,
        }
        
        for event in events:
            event_type = getattr(event, 'event_type', '')
            density_value = float(getattr(event, 'density', 0)) or \
                           float(getattr(event, 'value', 0))
            
            if 'node' in event_type.lower():
                state['node_density'] = max(state['node_density'], density_value)
            elif 'edge' in event_type.lower():
                state['edge_density'] = max(state['edge_density'], density_value)
            elif 'complexity' in event_type.lower():
                state['visual_complexity'] = max(state['visual_complexity'], density_value)
        
        return state

    def calculate_desired_state(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate desired topology density (lower is calmer)."""
        return {
            'node_density': 0.0,
            'edge_density': 0.0,
            'visual_complexity': 0.0,
        }

    def calculate_correction(self, current_state: Dict[str, Any], desired_state: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate density stabilization corrections."""
        correction = {}
        
        # Node density stabilization
        node_density = current_state.get('node_density', 0)
        if node_density > 0.7:
            correction['node_density'] = {
                'action': 'simplify',
                'target': 0.7,
                'damping': 'exponential',
            }
        
        # Edge density stabilization
        edge_density = current_state.get('edge_density', 0)
        if edge_density > 0.5:
            correction['edge_density'] = {
                'action': 'prune',
                'target': 0.5,
                'damping': 'linear',
            }
        
        # Visual complexity reduction
        complexity = current_state.get('visual_complexity', 0)
        if complexity > 0.8:
            correction['visual_complexity'] = {
                'action': 'flatten',
                'target': 0.8,
                'damping': 'hysteresis',
            }
        
        return correction

    def apply_correction(self, correction: Dict[str, Any]) -> None:
        """Apply topology density corrections."""
        for metric, actions in correction.items():
            action = actions.get('action')
            target = actions.get('target')
            
            if self._check_authority_violation(f"topology_{action}", metric):
                self._authority_violation_response(
                    f"topology_authority_violation: {action}"
                )
                continue
            
            logger.info(
                f"[{self.controller_id}] Topology density action: "
                f"metric={metric}, action={action}, target={target}"
            )
            
            # Update density metrics
            self._density_metrics[metric] = target

    async def reconcile_once(self) -> None:
        """Perform a single reconciliation iteration for topology density."""
        events = self.get_events()
        current_state = self.derive_state(events)
        desired_state = self.calculate_desired_state(current_state)
        correction = self.calculate_correction(current_state, desired_state)
        self.apply_correction(correction)


# =============================================================================
# exports
# =============================================================================

__all__ = [
    # Enums
    'LoopStatus',
    'ControllerType',
    'DampingType',
    'RetryBackoffType',
    'DropPolicy',
    # Governance primitives
    'ReconciliationCadence',
    'DampingFactor',
    'RetryCeiling',
    'ConvergenceWindow',
    'CancellationPolicy',
    'EventStormConfig',
    'ReconciliationContext',
    # Info types
    'ConvergenceInfo',
    'DampingInfo',
    'RetryInfo',
    'LoopHealthState',
    # Detection
    'OscillationMetrics',
    # Base controller
    'ReconciliationController',
    # Specific controllers
    'RuntimeSupervisionController',
    'ProjectionRefreshController',
    'TelemetryAggregationController',
    'WorkspaceHygieneController',
    'TopologyDensityController',
    # Constants
    'SCHEMA_VERSION',
    'DEFAULT_MAX_ITERATIONS',
    'DEFAULT_MAX_DURATION_SECONDS',
]
