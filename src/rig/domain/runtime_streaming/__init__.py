"""Runtime Streaming Domain for Rig.

This package provides the RuntimeStreaming seam for the streaming operational loop.
See ADR 0004: docs/adr/0004-runtime-streaming-consolidation.md

Core doctrine:
- Streaming owns: lifecycle, supervision coordination, WebSocket propagation,
  projection refresh orchestration (invalidation triggering, cadence)
- Streaming does NOT own: projection semantics, event substrate, topology authority,
  transport authority, replay semantics
- from_repo_root() is COLD - no sockets, processes, threads, or I/O
- Activation boundary is create_stream()
- get_projection() returns Optional - projection absence is normal operational state
- Observable via event subscription, not callbacks
- Dependency direction: streaming -> substrate (Cluster 1), never reverse

Phase 1: Thin façade with internal delegation modules as placeholders.
All real implementation remains in legacy Cluster 2 modules (runtime_stream.py,
runtime_supervisor.py, runtime_websocket.py, runtime_projection.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type


# =============================================================================
# Streaming Domain Types (Cluster 2 Authority)
# =============================================================================

# Stream identity types
StreamLineageId = str  # Deterministic: repo_root + semantic_config + workspace_namespace
StreamInstanceId = str  # Operational: monotonic sequence, activation occurrence


class StreamHandle:
    """Opaque handle to an active stream. Owned by streaming domain.
    
    Contains both lineage and instance identifiers.
    """
    
    def __init__(
        self, 
        stream_lineage_id: StreamLineageId,
        stream_instance_id: StreamInstanceId,
    ) -> None:
        self.stream_lineage_id = stream_lineage_id
        self.stream_instance_id = stream_instance_id
    
    def __repr__(self) -> str:
        return (
            f"StreamHandle(lineage={self.stream_lineage_id!r}, "
            f"instance={self.stream_instance_id!r})"
        )


class Subscription:
    """Event subscription handle. Allows unsubscribe."""
    
    def __init__(self, unsubscribe: Callable[[], None]) -> None:
        self._unsubscribe = unsubscribe
        self._active = True
    
    def unsubscribe(self) -> None:
        """Stop receiving events. Idempotent."""
        if self._active:
            self._active = False
            self._unsubscribe()
    
    @property
    def active(self) -> bool:
        return self._active


# =============================================================================
# Event Types (Normative)
# =============================================================================

class StreamCreated:
    """Stream lifecycle event: stream was created."""
    pass


class StreamStarting:
    """Stream lifecycle event: stream is starting."""
    pass


class StreamStarted:
    """Stream lifecycle event: stream started successfully."""
    pass


class StreamFailed:
    """Stream lifecycle event: stream failed."""
    pass


class StreamStopped:
    """Stream lifecycle event: stream stopped."""
    pass


class ProjectionInvalidated:
    """Projection event: projection invalidated, rebuild needed."""
    pass


class ProjectionRebuilt:
    """Projection event: projection rebuild complete."""
    pass


class BackpressureDetected:
    """Operational event: backpressure detected in stream."""
    pass


class SupervisorExited:
    """Operational event: supervisor process exited."""
    pass


# =============================================================================
# RuntimeStreaming Façade
# =============================================================================


class RuntimeStreaming:
    """Single seam for the streaming operational loop.
    
    See ADR 0004 for architectural constraints.
    
    Factory is COLD: from_repo_root() returns dormant instance.
    Activation boundary: create_stream() triggers lazy initialization.
    """
    
    def __init__(self, repo_root: Path) -> None:
        """Internal constructor. Use from_repo_root() for creation."""
        self._repo_root = repo_root
        self._initialized = False
        # Event subscriptions registry
        self._subscriptions: Dict[int, Subscription] = {}
        self._next_sub_id = 0
    
    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "RuntimeStreaming":
        """Factory - per-repo, deterministic. Returns COLD instance.
        
        NO sockets opened, NO processes spawned, NO threads started, NO I/O.
        Just pure data and wiring.
        
        Args:
            repo_root: Repository root path for deterministic configuration.
            
        Returns:
            Dormant RuntimeStreaming instance.
            
        Raises:
            ValueError: If repo_root is not a valid directory.
        """
        # Validate repo_root exists and is a directory
        if not repo_root.is_dir():
            raise ValueError(f"repo_root must be a directory: {repo_root}")
        return cls(repo_root)
    
    def _ensure_initialized(self) -> None:
        """Lazy initialization at activation boundary. Called by create_stream()."""
        if self._initialized:
            return
        # Mark as initialized - real impl will wire to internal modules
        self._initialized = True
    
    def create_stream(self, config: Any) -> StreamHandle:
        """Create and start a runtime stream. ACTIVATION BOUNDARY.
        
        First call triggers lazy initialization of internal adapters.
        Either creates a propagating stream or raises.
        
        Args:
            config: Runtime configuration (type from runtime.py / Cluster 1).
            
        Returns:
            StreamHandle with stream_lineage_id and stream_instance_id.
            
        Raises:
            StreamActivationError: If stream cannot be created.
            SupervisorLaunchError: If process supervision fails.
            TransportInitializationError: If WebSocket transport fails.
        """
        self._ensure_initialized()
        
        # Generate deterministic lineage_id from config and repo_root
        import hashlib
        config_str = str(config) if config else ""
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]
        lineage_id: StreamLineageId = f"{self._repo_root.name}_{config_hash}"
        
        # Instance ID is non-deterministic (operational)
        instance_id: StreamInstanceId = f"inst_{id(config)}"
        
        # Emit StreamCreated event to subscribers
        self._emit_event(StreamCreated())
        
        return StreamHandle(stream_lineage_id=lineage_id, stream_instance_id=instance_id)
    
    def submit_proposal(self, proposal: Any) -> Any:
        """Submit a proposal to the runtime stream.
        
        Args:
            proposal: Proposal to submit (type from runtime.py / Cluster 1).
            
        Returns:
            ProposalDecision from supervision.
        """
        self._ensure_initialized()
        # TODO: Delegate to supervision module
        return None  # Placeholder
    
    def get_projection(self, stream_instance_id: str) -> Optional[Any]:
        """Get current projection for a stream.
        
        NONE IS NOT AN ERROR. Projection absence is a normal operational state.
        Callers must handle None.
        
        Args:
            stream_instance_id: The stream instance identifier.
            
        Returns:
            RuntimeStreamProjection if available, None otherwise.
        """
        self._ensure_initialized()
        # TODO: Delegate to projection module
        # For now, return None (normal state - projection not yet built)
        return None
    
    def get_events(self, stream_instance_id: str, since_sequence: int = 0) -> List[Any]:
        """Get stream events since sequence number.
        
        Uses stream_instance_id for querying.
        
        Args:
            stream_instance_id: The stream instance identifier.
            since_sequence: Sequence number to start from (default 0).
            
        Returns:
            List of RuntimeStreamEvent objects.
        """
        self._ensure_initialized()
        # TODO: Delegate to stream module
        return []
    
    def subscribe_events(
        self, 
        event_types: Optional[List[Type[Any]]] = None,
        callback: Optional[Callable[[Any], None]] = None,
    ) -> Subscription:
        """Subscribe to operational event stream.
        
        Multiple consumers share the same canonical event substrate.
        
        Args:
            event_types: Optional list of event types to filter (default: all).
            callback: Called for each matching event. If None, subscription
                     is registered but events are not delivered (future: iterator pattern).
            
        Returns:
            Subscription handle that can be used to unsubscribe.
        """
        sub_id = self._next_sub_id
        self._next_sub_id += 1
        
        def unsubscribe() -> None:
            self._subscriptions.pop(sub_id, None)
        
        sub = Subscription(unsubscribe=unsubscribe)
        self._subscriptions[sub_id] = sub
        return sub
    
    def _emit_event(self, event: Any) -> None:
        """Internal: emit event to all active subscribers."""
        for sub in self._subscriptions.values():
            if sub.active:
                # In real impl, filter by event_types and call callback
                pass


__all__ = [
    "RuntimeStreaming",
    "StreamHandle",
    "StreamLineageId",
    "StreamInstanceId",
    "Subscription",
    # Event types
    "StreamCreated",
    "StreamStarting",
    "StreamStarted",
    "StreamFailed",
    "StreamStopped",
    "ProjectionInvalidated",
    "ProjectionRebuilt",
    "BackpressureDetected",
    "SupervisorExited",
]
