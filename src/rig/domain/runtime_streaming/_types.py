"""Runtime Streaming Domain Types.

Cluster 2-only types. Streaming domain authority.

See ADR 0004: docs/adr/0004-runtime-streaming-consolidation.md

**DO NOT** put Cluster 1 (substrate) types here.
**DO** import Cluster 1 types explicitly from runtime.py when needed.

Phase 1: Minimal type definitions. Full type extraction happens in later phases.
"""

from __future__ import annotations

# =============================================================================
# Streaming Domain Types (Cluster 2 Authority)
# =============================================================================

# Stream identity types
StreamLineageId = str  # Deterministic: repo_root + semantic_config + workspace_namespace
StreamInstanceId = str  # Operational: monotonic sequence, activation occurrence

# Projection refresh orchestration types (NOT projection semantics - see ADR 0002)


class ProjectionRefreshState:
    """Refresh orchestration state. Streaming domain authority."""

    pass


class StreamBackpressurePolicy:
    """Backpressure configuration for stream events. Streaming domain authority."""

    pass


class StreamLifecyclePhase:
    """Stream lifecycle enumeration. Streaming domain authority."""

    pass


class StreamHandle:
    """Opaque handle to an active stream. Streaming domain authority.

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


class StreamConfig:
    """Stream configuration. Owned by streaming domain.

    Note: Contains references to Cluster 1 types but does not own them.
    """

    pass


__all__ = [
    # Cluster 2 types
    "StreamLineageId",
    "StreamInstanceId",
    "ProjectionRefreshState",
    "StreamBackpressurePolicy",
    "StreamLifecyclePhase",
    "StreamHandle",
    "StreamConfig",
]
