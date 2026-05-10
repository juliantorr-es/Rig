"""Projection Reconciliation for Rig.

This module provides projection reconciliation as defined in PHASE 5 of the
Deterministic Operational Reconciliation Sprint.

Core doctrine:
- Projections are backend-authored truth
- Frontend is a dumb renderer
- All projection updates must be event-driven
- All reconciliation must be replay-safe
- No frontend authority inference

file: src/rig/domain/projection_reconciliation.py
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, FrozenSet, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.reconciliation_governance import (
        ReconciliationCadence,
        DampingFactor,
        RetryCeiling,
        ConvergenceWindow,
        CancellationPolicy,
        EventStormConfig,
        ReconciliationContext,
        LoopHealthState,
        LoopStatus,
        DampingType,
    )
    from rig.domain.runtime_events import RuntimeEvent
    from rig.domain.runtime_event_router import RuntimeEventRouter

from rig.domain.reconciliation_governance import (
    ReconciliationCadence,
    DampingFactor,
    RetryCeiling,
    ConvergenceWindow,
    CancellationPolicy,
    EventStormConfig,
    ReconciliationContext,
    LoopHealthState,
    LoopStatus,
    DampingType,
    DEFAULT_MIN_INTERVAL_SECONDS,
    DEFAULT_MAX_INTERVAL_SECONDS,
    DEFAULT_JITTER_FACTOR,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_RETRY_MAX_DELAY,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_DURATION_SECONDS,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "rig.projection_reconciliation.v1"

# Projection-specific defaults
DEFAULT_PROJECTION_CADENCE_MIN = 0.5  # Minimum 500ms between projection refreshes
DEFAULT_PROJECTION_CADENCE_MAX = 5.0   # Maximum 5s between projection refreshes
DEFAULT_PROJECTION_MAX_ITERATIONS = 50   # Bounded projection convergence


class ProjectionRefreshPriority(Enum):
    """Priority levels for projection refresh."""
    CRITICAL = "critical"      # Must refresh immediately
    HIGH = "high"              # High priority refresh
    NORMAL = "normal"          # Normal priority refresh
    LOW = "low"                # Low priority refresh
    BACKGROUND = "background"  # Background refresh


class ProjectionRefreshTrigger(Enum):
    """Types of projection refresh triggers."""
    EVENT_DRIVEN = "event_driven"          # Triggered by canonical events
    SCHEDULED = "scheduled"                # Scheduled refresh cycle
    ON_DEMAND = "on_demand"                # Manual/on-demand refresh
    FORCED = "forced"                      # Forced full rebuild


@dataclass(frozen=True, slots=True)
class ProjectionRefreshConfig:
    """Configuration for projection refresh scheduling."""
    priority: ProjectionRefreshPriority = ProjectionRefreshPriority.NORMAL
    min_interval_seconds: float = DEFAULT_PROJECTION_CADENCE_MIN
    max_interval_seconds: float = DEFAULT_PROJECTION_CADENCE_MAX
    jitter_factor: float = DEFAULT_JITTER_FACTOR
    max_iterations: int = DEFAULT_PROJECTION_MAX_ITERATIONS
    batch_size: int = 10                       # Max projections per batch
    enabled: bool = True
    workspace_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must be >= 0")
        if self.max_interval_seconds < self.min_interval_seconds:
            raise ValueError("max_interval_seconds must be >= min_interval_seconds")
        if not 0.0 <= self.jitter_factor <= 1.0:
            raise ValueError("jitter_factor must be in [0.0, 1.0]")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")


@dataclass(frozen=True, slots=True)
class ProjectionState:
    """State of a single projection."""
    projection_id: str
    version: int = 0
    last_refresh: Optional[datetime] = None
    last_event_sequence: int = 0
    needs_refresh: bool = True
    pending_events: int = 0
    refresh_priority: ProjectionRefreshPriority = ProjectionRefreshPriority.NORMAL
    is_valid: bool = True
    error: Optional[str] = None
    disabled_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["refresh_priority"] = self.refresh_priority.name
        return result


@dataclass(frozen=True, slots=True)
class ProjectionRefreshStats:
    """Statistics for projection refresh operations."""
    total_refreshes: int = 0
    total_projections: int = 0
    successful_refreshes: int = 0
    failed_refreshes: int = 0
    average_refresh_time: float = 0.0
    last_refresh_time: Optional[datetime] = None
    projections_needing_refresh: int = 0
    high_priority_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProjectionInvalidationReason(Enum):
    """Reasons for projection invalidation."""
    EVENT_RECEIVED = "event_received"          # New canonical event arrived
    STALE = "stale"                            # Projection is stale
    ERROR = "error"                            # Projection error occurred
    SCHEMA_CHANGED = "schema_changed"          # Projection schema changed
    FORCED = "forced"                          # Forced invalidation


@dataclass(frozen=True, slots=True)
class ProjectionInvalidation:
    """Record of a projection invalidation."""
    projection_id: str
    reason: ProjectionInvalidationReason
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_sequence: int = 0
    details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["reason"] = self.reason.value
        return result


class ProjectionRefreshScheduler:
    """Schedules projection refreshes based on event-driven and cadence-based triggers.
    
    Purpose: Implement projection refresh scheduling
    - Canonical event-driven projection updates
    - Replay-safe refresh ordering
    - Topology-safe refresh convergence
    - Bounded projection invalidation
    - Deterministic rebuild triggers
    
    DO NOT:
    - Introduce frontend authority
    - Create imperative rendering commands
    - Bypass canonical envelopes
    """

    def __init__(
        self,
        config: ProjectionRefreshConfig,
        event_router: Optional[Any] = None,  # RuntimeEventRouter
        projection_registry: Optional[Any] = None,
    ) -> None:
        self.config = config
        self._event_router = event_router
        self._projection_registry = projection_registry
        
        # State tracking
        self._projection_states: Dict[str, ProjectionState] = {}
        self._refresh_queue: Deque[str] = deque()
        self._invalidations: Deque[ProjectionInvalidation] = deque(maxlen=1000)
        self._pending_events: Dict[str, List[Any]] = {}  # proj_id -> events
        self._stats = ProjectionRefreshStats()
        self._last_schedule_time: Optional[datetime] = None
        self._sequence = 0

    @property
    def stats(self) -> ProjectionRefreshStats:
        return self._stats

    @property
    def projection_states(self) -> Dict[str, ProjectionState]:
        return dict(self._projection_states)

    def register_projection(self, projection_id: str) -> None:
        """Register a new projection for reconciliation."""
        if projection_id not in self._projection_states:
            self._projection_states[projection_id] = ProjectionState(
                projection_id=projection_id,
                version=0,
                last_refresh=None,
                last_event_sequence=0,
                needs_refresh=True,
                pending_events=0,
            )
            object.__setattr__(self._stats, "total_projections", self._stats.total_projections + 1)
            logger.info(f"Projection registered: {projection_id}")

    def unregister_projection(self, projection_id: str) -> None:
        """Unregister a projection from reconciliation."""
        if projection_id in self._projection_states:
            del self._projection_states[projection_id]
            object.__setattr__(self._stats, "total_projections", max(0, self._stats.total_projections - 1))
            logger.info(f"Projection unregistered: {projection_id}")

    def receive_event(self, event: Any, projection_id: Optional[str] = None) -> bool:
        """Receive a canonical event that may require projection refresh.
        
        Args:
            event: The canonical event
            projection_id: Optional explicit projection ID
            
        Returns:
            True if event triggered a refresh, False otherwise
        """
        # Extract projection ID from event or use provided
        proj_id = self._resolve_projection_id(event, projection_id)
        
        # Track sequence
        event_seq = getattr(event, 'sequence', 0)
        try:
            event_seq = int(event_seq)
        except (TypeError, ValueError):
            event_seq = 0
        self._sequence = max(self._sequence, event_seq)
        
        # Store pending event
        if proj_id not in self._pending_events:
            self._pending_events[proj_id] = []
        self._pending_events[proj_id].append(event)
        
        # Update projection state
        if proj_id not in self._projection_states:
            self.register_projection(proj_id)
        
        state = self._projection_states.get(proj_id)
        if state:
            # Check if this event requires refresh
            event_type = getattr(event, 'event_type', '')
            requires_refresh = self._event_requires_refresh(event_type)
            
            if requires_refresh:
                self._projection_states[proj_id] = ProjectionState(
                    projection_id=proj_id,
                    version=state.version + 1,
                    last_refresh=state.last_refresh,
                    last_event_sequence=max(state.last_event_sequence, event_seq),
                    needs_refresh=True,
                    pending_events=state.pending_events + 1,
                    refresh_priority=self._get_refresh_priority(event),
                )
                
                # Record invalidation
                self._invalidations.append(ProjectionInvalidation(
                    projection_id=proj_id,
                    reason=ProjectionInvalidationReason.EVENT_RECEIVED,
                    event_sequence=event_seq,
                    details=f"Event type: {event_type}",
                ))
                
                # Queue for refresh
                if proj_id not in self._refresh_queue:
                    self._refresh_queue.append(proj_id)
                
                object.__setattr__(
                    self._stats,
                    "projections_needing_refresh",
                    len([pid for pid, ps in self._projection_states.items() if ps.needs_refresh]),
                )

                # Update priority counts
                if state.refresh_priority == ProjectionRefreshPriority.HIGH:
                    object.__setattr__(self._stats, "high_priority_count", max(0, self._stats.high_priority_count - 1))
                new_state = self._projection_states[proj_id]
                if new_state.refresh_priority == ProjectionRefreshPriority.HIGH:
                    object.__setattr__(self._stats, "high_priority_count", self._stats.high_priority_count + 1)

                return True
        
        return False

    def _resolve_projection_id(self, event: Any, projection_id: Optional[str]) -> str:
        for candidate in (projection_id, getattr(event, "workspace_id", None), getattr(event, "projection_id", None)):
            if isinstance(candidate, str) and candidate:
                if candidate not in self._projection_states and len(self._projection_states) == 1:
                    return next(iter(self._projection_states))
                return candidate
        return "default"

    def _event_requires_refresh(self, event_type: str) -> bool:
        """Check if an event type requires projection refresh."""
        refresh_triggers = {
            'completion',
            'failure',
            'status',
            'delta',
            'update',
            'change',
            'create',
            'delete',
            'modify',
            'refresh',
            'rebuild',
        }
        event_type_lower = event_type.lower()
        return any(t in event_type_lower for t in refresh_triggers)

    def _get_refresh_priority(self, event: Any) -> ProjectionRefreshPriority:
        """Get refresh priority based on event."""
        event_type = getattr(event, 'event_type', '')
        
        # Critical events
        if any(t in event_type.lower() for t in ['failure', 'error', 'critical']):
            return ProjectionRefreshPriority.CRITICAL
        
        # High priority events
        if any(t in event_type.lower() for t in ['completion', 'status_change']):
            return ProjectionRefreshPriority.HIGH
        
        # Normal events
        return ProjectionRefreshPriority.NORMAL

    def schedule_refresh(
        self,
        projection_id: str,
        priority: ProjectionRefreshPriority = ProjectionRefreshPriority.NORMAL,
        trigger: ProjectionRefreshTrigger = ProjectionRefreshTrigger.ON_DEMAND,
    ) -> None:
        """Schedule a projection refresh."""
        if projection_id not in self._projection_states:
            self.register_projection(projection_id)
        
        # Update state
        state = self._projection_states[projection_id]
        self._projection_states[projection_id] = ProjectionState(
            projection_id=projection_id,
            version=state.version + 1,
            last_refresh=state.last_refresh,
            last_event_sequence=state.last_event_sequence,
            needs_refresh=True,
            pending_events=state.pending_events,
            refresh_priority=priority,
            is_valid=state.is_valid,
            error=state.error,
            disabled_reason=state.disabled_reason,
        )
        
        # Queue if not already queued
        if projection_id not in self._refresh_queue:
            # Insert at appropriate priority position
            if priority == ProjectionRefreshPriority.CRITICAL:
                self._refresh_queue.appendleft(projection_id)
            elif priority == ProjectionRefreshPriority.HIGH:
                # Insert after critical, before others
                critical_count = sum(
                    1 for pid in self._refresh_queue 
                    if self._projection_states.get(pid, ProjectionState(pid, 0)).refresh_priority 
                       == ProjectionRefreshPriority.CRITICAL
                )
                self._refresh_queue.insert(critical_count, projection_id)
            else:
                self._refresh_queue.append(projection_id)
        
        # Record invalidation
        reason = {
            ProjectionRefreshTrigger.EVENT_DRIVEN: ProjectionInvalidationReason.EVENT_RECEIVED,
            ProjectionRefreshTrigger.SCHEDULED: ProjectionInvalidationReason.STALE,
            ProjectionRefreshTrigger.ON_DEMAND: ProjectionInvalidationReason.FORCED,
            ProjectionRefreshTrigger.FORCED: ProjectionInvalidationReason.FORCED,
        }.get(trigger, ProjectionInvalidationReason.FORCED)
        
        self._invalidations.append(ProjectionInvalidation(
            projection_id=projection_id,
            reason=reason,
            details=f"Trigger: {trigger.value}, Priority: {priority.value}",
        ))
        
        object.__setattr__(
            self._stats,
            "projections_needing_refresh",
            len([pid for pid, ps in self._projection_states.items() if ps.needs_refresh]),
        )
        
        if priority == ProjectionRefreshPriority.HIGH:
            object.__setattr__(self._stats, "high_priority_count", self._stats.high_priority_count + 1)
        
        logger.debug(f"Scheduled refresh for {projection_id}: priority={priority}, trigger={trigger}")

    def get_next_refresh_batch(self, max_batch_size: Optional[int] = None) -> List[str]:
        """Get the next batch of projections to refresh.
        
        Args:
            max_batch_size: Maximum batch size (defaults to config.batch_size)
            
        Returns:
            List of projection IDs to refresh, ordered by priority
        """
        batch_size = max_batch_size or self.config.batch_size
        batch = []
        
        while self._refresh_queue and len(batch) < batch_size:
            proj_id = self._refresh_queue.popleft()
            state = self._projection_states.get(proj_id)
            if state and state.needs_refresh:
                batch.append(proj_id)
        
        return batch

    def mark_refreshed(self, projection_id: str, success: bool = True, error: Optional[str] = None) -> None:
        """Mark a projection as refreshed."""
        if projection_id not in self._projection_states:
            return
        
        state = self._projection_states[projection_id]
        now = datetime.now(timezone.utc)
        
        self._projection_states[projection_id] = ProjectionState(
            projection_id=projection_id,
            version=state.version,
            last_refresh=now,
            last_event_sequence=state.last_event_sequence,
            needs_refresh=False,
            pending_events=0,
            refresh_priority=ProjectionRefreshPriority.BACKGROUND,
            is_valid=success and state.is_valid,
            error=error if not success else state.error,
        )
        
        # Clear pending events
        self._pending_events.pop(projection_id, [])
        
        # Update stats
        object.__setattr__(self._stats, "total_refreshes", self._stats.total_refreshes + 1)
        object.__setattr__(self._stats, "last_refresh_time", now)
        if success:
            object.__setattr__(self._stats, "successful_refreshes", self._stats.successful_refreshes + 1)
        else:
            object.__setattr__(self._stats, "failed_refreshes", self._stats.failed_refreshes + 1)
            if state.refresh_priority == ProjectionRefreshPriority.HIGH:
                object.__setattr__(self._stats, "high_priority_count", max(0, self._stats.high_priority_count - 1))

        object.__setattr__(
            self._stats,
            "projections_needing_refresh",
            len([pid for pid, ps in self._projection_states.items() if ps.needs_refresh]),
        )
        
        logger.info(f"Projection refreshed: {projection_id}, success={success}")

    def mark_error(
        self,
        projection_id: str,
        error: str,
        disabled_reason: Optional[str] = None,
    ) -> None:
        """Mark a projection as having an error."""
        if projection_id not in self._projection_states:
            return
        
        state = self._projection_states[projection_id]
        now = datetime.now(timezone.utc)
        
        self._projection_states[projection_id] = ProjectionState(
            projection_id=projection_id,
            version=state.version,
            last_refresh=now,
            last_event_sequence=state.last_event_sequence,
            needs_refresh=True,  # Error means needs re-attempt
            pending_events=state.pending_events,
            refresh_priority=ProjectionRefreshPriority.HIGH,
            is_valid=False,
            error=error,
            disabled_reason=disabled_reason,
        )
        
        object.__setattr__(self._stats, "failed_refreshes", self._stats.failed_refreshes + 1)
        if state.refresh_priority != ProjectionRefreshPriority.HIGH:
            object.__setattr__(self._stats, "high_priority_count", self._stats.high_priority_count + 1)
        
        logger.error(f"Projection error: {projection_id}, error={error}")

    def invalidate_projection(
        self,
        projection_id: str,
        reason: ProjectionInvalidationReason,
        details: Optional[str] = None,
    ) -> None:
        """Explicitly invalidate a projection."""
        if projection_id not in self._projection_states:
            return
        
        state = self._projection_states[projection_id]
        
        self._projection_states[projection_id] = ProjectionState(
            projection_id=projection_id,
            version=state.version + 1,
            last_refresh=state.last_refresh,
            last_event_sequence=state.last_event_sequence,
            needs_refresh=True,
            pending_events=state.pending_events + 1,
            refresh_priority=self._invalidation_priority(reason),
            is_valid=False,
            error=state.error,
        )
        
        if projection_id not in self._refresh_queue:
            self._refresh_queue.append(projection_id)
        
        self._invalidations.append(ProjectionInvalidation(
            projection_id=projection_id,
            reason=reason,
            details=details,
        ))
        
        object.__setattr__(
            self._stats,
            "projections_needing_refresh",
            len([pid for pid, ps in self._projection_states.items() if ps.needs_refresh]),
        )
        
        logger.info(f"Projection invalidated: {projection_id}, reason={reason}")

    def _invalidation_priority(self, reason: ProjectionInvalidationReason) -> ProjectionRefreshPriority:
        """Get priority for invalidation reason."""
        priority_map = {
            ProjectionInvalidationReason.ERROR: ProjectionRefreshPriority.CRITICAL,
            ProjectionInvalidationReason.SCHEMA_CHANGED: ProjectionRefreshPriority.HIGH,
            ProjectionInvalidationReason.EVENT_RECEIVED: ProjectionRefreshPriority.NORMAL,
            ProjectionInvalidationReason.STALE: ProjectionRefreshPriority.LOW,
            ProjectionInvalidationReason.FORCED: ProjectionRefreshPriority.HIGH,
        }
        return priority_map.get(reason, ProjectionRefreshPriority.NORMAL)

    def get_projections_needing_refresh(self) -> List[str]:
        """Get list of projection IDs that need refresh."""
        return [
            pid for pid in self._refresh_queue
            if self._projection_states.get(pid, ProjectionState(pid)).needs_refresh
        ]

    def get_high_priority_projections(self) -> List[str]:
        """Get list of high priority projection IDs."""
        return [
            pid for pid in self._refresh_queue
            if self._projection_states.get(pid, ProjectionState(pid)).needs_refresh
            and self._projection_states.get(pid, ProjectionState(pid)).refresh_priority in (
                ProjectionRefreshPriority.CRITICAL,
                ProjectionRefreshPriority.HIGH,
            )
        ]

    def reset_stats(self) -> None:
        """Reset statistics."""
        total_projections = len(self._projection_states)
        self._stats = ProjectionRefreshStats(total_projections=total_projections)


class ProjectionRebuildTrigger:
    """Deterministic rebuild trigger for projections.
    
    Purpose: Provide deterministic rebuild triggers that are:
    - Replay-safe
    - Event-driven
    - Bounded
    - Topology-safe
    
    DO NOT:
    - Create imperative rendering commands
    - Bypass canonical envelopes
    - Introduce frontend authority
    """

    def __init__(
        self,
        scheduler: ProjectionRefreshScheduler,
        max_rebuilds_per_hour: int = 24,
    ) -> None:
        self._scheduler = scheduler
        self._max_rebuilds_per_hour = max_rebuilds_per_hour
        self._rebuild_count = 0
        self._last_rebuild_time: Optional[datetime] = None
        self._rebuild_history: Deque[datetime] = deque(maxlen=100)

    def check_rebuild_needed(self, projection_id: str) -> bool:
        """Check if a projection needs a full rebuild.
        
        Args:
            projection_id: The projection ID to check
            
        Returns:
            True if full rebuild is needed
        """
        state = self._scheduler.projection_states.get(projection_id)
        if not state:
            return False
        
        # Check if we're under rate limit
        if not self._can_rebuild():
            return False
        
        # Rebuild needed if:
        # 1. Schema changed (recorded in invalidation reason)
        # 2. Too many errors
        # 3. Forced rebuild requested
        
        return state.error is not None

    def _can_rebuild(self) -> bool:
        """Check if we can perform a rebuild (rate limiting)."""
        now = datetime.now(timezone.utc)
        
        # Clean old rebuilds from history
        while self._rebuild_history and (now - self._rebuild_history[0]).total_seconds() > 3600:
            self._rebuild_history.popleft()
        
        if len(self._rebuild_history) >= self._max_rebuilds_per_hour:
            return False
        
        return True

    def trigger_rebuild(self, projection_id: str) -> bool:
        """Trigger a full rebuild of a projection.
        
        Args:
            projection_id: The projection ID to rebuild
            
        Returns:
            True if rebuild was triggered, False if blocked
        """
        if not self.check_rebuild_needed(projection_id):
            return False
        
        now = datetime.now(timezone.utc)
        self._rebuild_history.append(now)
        self._rebuild_count += 1
        self._last_rebuild_time = now
        
        # Invalidate the projection to trigger refresh
        self._scheduler.invalidate_projection(
            projection_id,
            ProjectionInvalidationReason.FORCED,
            details="Full rebuild triggered",
        )
        
        # Schedule immediate refresh
        self._scheduler.schedule_refresh(
            projection_id,
            priority=ProjectionRefreshPriority.CRITICAL,
            trigger=ProjectionRefreshTrigger.FORCED,
        )
        
        logger.info(f"Full rebuild triggered for {projection_id}")
        return True


class ProjectionReconciliationController:
    """Main controller for projection reconciliation.
    
    Orchestrates:
    - Projection refresh scheduling
    - Canonical event-driven projection updates
    - Replay-safe refresh ordering
    - Topology-safe refresh convergence
    - Bounded projection invalidation
    - Deterministic rebuild triggers
    
    DO NOT:
    - Introduce frontend authority
    - Create imperative rendering commands
    - Bypass canonical envelopes
    """

    def __init__(
        self,
        config: ProjectionRefreshConfig,
        scheduler: Optional[ProjectionRefreshScheduler] = None,
        rebuild_trigger: Optional[ProjectionRebuildTrigger] = None,
        event_router: Optional[Any] = None,
        projection_registry: Optional[Any] = None,
    ) -> None:
        self.config = config
        self._scheduler = scheduler or ProjectionRefreshScheduler(config, event_router, projection_registry)
        self._rebuild_trigger = rebuild_trigger or ProjectionRebuildTrigger(self._scheduler)
        self._running = False

    @property
    def scheduler(self) -> ProjectionRefreshScheduler:
        return self._scheduler

    @property
    def rebuild_trigger(self) -> ProjectionRebuildTrigger:
        return self._rebuild_trigger

    @property
    def stats(self) -> ProjectionRefreshStats:
        return self._scheduler.stats

    def start(self) -> None:
        """Start the projection reconciliation controller."""
        self._running = True
        logger.info("Projection reconciliation controller started")

    def register_projection(self, projection_id: str) -> None:
        self._scheduler.register_projection(str(projection_id))

    def unregister_projection(self, projection_id: str) -> None:
        self._scheduler.unregister_projection(str(projection_id))

    def schedule_refresh(
        self,
        projection_id: str,
        priority: ProjectionRefreshPriority = ProjectionRefreshPriority.NORMAL,
        trigger: ProjectionRefreshTrigger = ProjectionRefreshTrigger.ON_DEMAND,
    ) -> None:
        self._scheduler.schedule_refresh(str(projection_id), priority=priority, trigger=trigger)

    def stop(self) -> None:
        """Stop the projection reconciliation controller."""
        self._running = False
        logger.info("Projection reconciliation controller stopped")

    def process_events(self, events: List[Any]) -> int:
        """Process a batch of canonical events.
        
        Args:
            events: List of canonical events to process
            
        Returns:
            Number of projections that were invalidated
        """
        invalidated = 0
        for event in events:
            if self._scheduler.receive_event(event):
                invalidated += 1
        return invalidated

    def tick(self) -> List[str]:
        """Perform one reconciliation tick.
        
        Returns:
            List of projection IDs that were refreshed in this tick
        """
        # Get next batch
        batch = self._scheduler.get_next_refresh_batch()
        
        # For each projection in batch, trigger refresh
        refreshed = []
        for proj_id in batch:
            # In a real implementation, this would call the projection builder
            # For now, we just mark as refreshed
            self._scheduler.mark_refreshed(proj_id, success=True)
            refreshed.append(proj_id)
        
        return refreshed


__all__ = [
    # Schema
    'SCHEMA_VERSION',
    # Enums
    'ProjectionRefreshPriority',
    'ProjectionRefreshTrigger',
    'ProjectionInvalidationReason',
    # Config
    'ProjectionRefreshConfig',
    # State types
    'ProjectionState',
    'ProjectionRefreshStats',
    'ProjectionInvalidation',
    # Scheduler
    'ProjectionRefreshScheduler',
    # Rebuild
    'ProjectionRebuildTrigger',
    # Controller
    'ProjectionReconciliationController',
    # Constants
    'DEFAULT_PROJECTION_CADENCE_MIN',
    'DEFAULT_PROJECTION_CADENCE_MAX',
    'DEFAULT_PROJECTION_MAX_ITERATIONS',
]
