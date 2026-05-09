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
PLACEHOLDER_PROVIDER_ID = "no_provider"  # Compatibility alias for tests
PLACEHOLDER_MODEL_ID = "no_model"  # Compatibility alias for tests
PLACEHOLDER_INVOCATION = "no_invocation"
PLACEHOLDER_INVOKE_ID = "INVOKE_ID_PLACEHOLDER"  # Canonical constant, matches runtime_replay.py
PLACEHOLDER_RECEIPT = "no_receipt"
PLACEHOLDER_NO_RECEIPT = "no_receipt"
PLACEHOLDER_TIMESTAMP = "1970-01-01T00:00:00Z"
PLACEHOLDER_CHECKSUM = ""  # Compatibility alias for tests
PLACEHOLDER_HASH = ""  # Compatibility alias for tests

# Default streaming configuration
DEFAULT_MAX_CHUNK_SIZE = 1024 * 1024  # 1 MB
DEFAULT_MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_CHUNK_BYTES = DEFAULT_MAX_CHUNK_SIZE  # Compatibility alias for tests
DEFAULT_MAX_BUFFER_BYTES = DEFAULT_MAX_BUFFER_SIZE  # Compatibility alias for tests
DEFAULT_MAX_SEQUENCE_GAP = 100
DEFAULT_STREAM_TIMEOUT_SECONDS = 300.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 5.0
DEFAULT_STALLED_THRESHOLD_SECONDS = 30.0


# =============================================================================
# Re-exports from runtime_stream.py for compatibility during migration
# These types still live in runtime_stream.py which is deprecated per ADR 0004.
# They are re-exported here so that runtime_projection.py and runtime_supervisor.py
# can import from the canonical runtime_streaming package.
# NOTE: runtime_stream.py does NOT import from this module, so no circular dependency.
# =============================================================================

from rig.domain.runtime_stream import (
    RuntimeStreamChunk,
    RuntimeStreamBuffer,
    RuntimeSequenceState,
    RuntimeStatusEvent,
    RuntimeHeartbeatEvent,
    RuntimeToolProposalEvent,
    RuntimePatchProposalEvent,
    RuntimeWarningEvent,
    RuntimeCompletionEvent,
    RuntimeFailureEvent,
    RuntimeStreamChannel,
    RuntimeStreamEventKind,
    RuntimeStreamStatus,
    RuntimeStreamStateKind,
    RuntimeProposalKind,
    RuntimeWarningCode,
    RuntimeFailureCategory,
    RuntimeStreamEvent,
)


# =============================================================================
# Original Cluster 2 Types (Streaming domain authority)
# =============================================================================

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
    "PLACEHOLDER_PROVIDER_ID",
    "PLACEHOLDER_MODEL_ID",
    "PLACEHOLDER_INVOCATION",
    "PLACEHOLDER_INVOKE_ID",
    "PLACEHOLDER_RECEIPT",
    "PLACEHOLDER_NO_RECEIPT",
    "PLACEHOLDER_TIMESTAMP",
    "PLACEHOLDER_CHECKSUM",
    "PLACEHOLDER_HASH",
    "DEFAULT_MAX_CHUNK_SIZE",
    "DEFAULT_MAX_BUFFER_SIZE",
    "DEFAULT_MAX_CHUNK_BYTES",
    "DEFAULT_MAX_BUFFER_BYTES",
    "DEFAULT_MAX_SEQUENCE_GAP",
    "DEFAULT_STREAM_TIMEOUT_SECONDS",
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "DEFAULT_STALLED_THRESHOLD_SECONDS",
    # Re-exported from runtime_stream.py
    "RuntimeStreamChunk",
    "RuntimeStreamBuffer",
    "RuntimeSequenceState",
    "RuntimeStatusEvent",
    "RuntimeHeartbeatEvent",
    "RuntimeToolProposalEvent",
    "RuntimePatchProposalEvent",
    "RuntimeWarningEvent",
    "RuntimeCompletionEvent",
    "RuntimeFailureEvent",
    "RuntimeStreamEvent",
    "RuntimeStreamChannel",
    "RuntimeStreamEventKind",
    "RuntimeStreamStatus",
    "RuntimeStreamStateKind",
    "RuntimeProposalKind",
    "RuntimeWarningCode",
    "RuntimeFailureCategory",
    # Original _types.py classes
    "ProjectionRefreshState",
    "StreamBackpressurePolicy",
    "StreamLifecyclePhase",
    "StreamHandle",
    "StreamConfig",
]
