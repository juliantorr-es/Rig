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

# Stream constants - canonical definitions (migrated from runtime_stream.py)
PLACEHOLDER_STREAM_ID = "not_set"
PLACEHOLDER_SEQUENCE = -1
PLACEHOLDER_CHANNEL = "unknown"
PLACEHOLDER_CONTENT = ""
PLACEHOLDER_PROVIDER = "no_provider"
PLACEHOLDER_INVOCATION = "no_invocation"
PLACEHOLDER_RECEIPT = "no_receipt"
PLACEHOLDER_NO_RECEIPT = "no_receipt"
PLACEHOLDER_TIMESTAMP = "1970-01-01T00:00:00Z"

# Default streaming configuration
DEFAULT_MAX_CHUNK_SIZE = 1024 * 1024  # 1 MB
DEFAULT_MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_SEQUENCE_GAP = 100
DEFAULT_STREAM_TIMEOUT_SECONDS = 300.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 5.0
DEFAULT_STALLED_THRESHOLD_SECONDS = 30.0


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
    # Constants
    "PLACEHOLDER_STREAM_ID",
    "PLACEHOLDER_SEQUENCE",
    "PLACEHOLDER_CHANNEL",
    "PLACEHOLDER_CONTENT",
    "PLACEHOLDER_PROVIDER",
    "PLACEHOLDER_INVOCATION",
    "PLACEHOLDER_RECEIPT",
    "PLACEHOLDER_NO_RECEIPT",
    "PLACEHOLDER_TIMESTAMP",
    "DEFAULT_MAX_CHUNK_SIZE",
    "DEFAULT_MAX_BUFFER_SIZE",
    "DEFAULT_MAX_SEQUENCE_GAP",
    "DEFAULT_STREAM_TIMEOUT_SECONDS",
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "DEFAULT_STALLED_THRESHOLD_SECONDS",
    "ProjectionRefreshState",
    "StreamBackpressurePolicy",
    "StreamLifecyclePhase",
    "StreamHandle",
    "StreamConfig",
]
