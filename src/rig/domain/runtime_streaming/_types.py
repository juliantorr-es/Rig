"""Runtime Streaming Domain Types.

Cluster 2-only types. Streaming domain authority.

See ADR 0004: docs/adr/0004-runtime-streaming-consolidation.md

**DO NOT** put Cluster 1 (substrate) types here.
**DO** import Cluster 1 types explicitly from runtime.py when needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

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
    """Stream configuration.owned by streaming domain.
    
    Note: Contains references to Cluster 1 types but does not own them.
    """
    pass


# =============================================================================
# Re-exports from Cluster 1 (Event Substrate) - explicit, not wildcards
# =============================================================================

# These are imported explicitly to preserve semantic authority direction.
# The types themselves remain owned by Cluster 1 (runtime.py, runtime_stream.py).
# Streaming domain only references them, never redefines them.

# From runtime_stream.py (Cluster 2 but shared with Cluster 1 consumers)
from rig.domain.runtime_stream import (
    RuntimeStreamEvent,
    RuntimeStreamChunk,
    RuntimeStreamBuffer,
    RuntimeSequenceState,
    RuntimeStreamChannel,
    RuntimeStreamStatus,
    RuntimeProposalKind,
    RuntimeWarningCode,
    RuntimeFailureCategory,
    DEFAULT_MAX_CHUNK_SIZE,
    DEFAULT_MAX_BUFFER_SIZE,
    DEFAULT_MAX_SEQUENCE_GAP,
    DEFAULT_STREAM_TIMEOUT_SECONDS,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_STALLED_THRESHOLD_SECONDS,
    PLACEHOLDER_STREAM_ID,
    PLACEHOLDER_SEQUENCE,
    PLACEHOLDER_CHANNEL,
    PLACEHOLDER_CONTENT,
    PLACEHOLDER_PROVIDER,
    PLACEHOLDER_INVOCATION,
    PLACEHOLDER_NO_RECEIPT,
    PLACEHOLDER_TIMESTAMP,
)

# From runtime.py (Cluster 1 substrate) - imported explicitly, not owned here
from rig.domain.runtime import (
    RuntimeProvider,
    RuntimeCapabilityKind,
    RuntimeProposal,
    RuntimeInvocation,
)


__all__ = [
    # Cluster 2 types
    "StreamLineageId",
    "StreamInstanceId",
    "ProjectionRefreshState",
    "StreamBackpressurePolicy",
    "StreamLifecyclePhase",
    "StreamHandle",
    "StreamConfig",
    # Re-exports from runtime_stream.py (Cluster 2 shared)
    "RuntimeStreamEvent",
    "RuntimeStreamChunk",
    "RuntimeStreamBuffer",
    "RuntimeSequenceState",
    "RuntimeStreamChannel",
    "RuntimeStreamStatus",
    "RuntimeProposalKind",
    "RuntimeWarningCode",
    "RuntimeFailureCategory",
    "DEFAULT_MAX_CHUNK_SIZE",
    "DEFAULT_MAX_BUFFER_SIZE",
    "DEFAULT_MAX_SEQUENCE_GAP",
    "DEFAULT_STREAM_TIMEOUT_SECONDS",
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "DEFAULT_STALLED_THRESHOLD_SECONDS",
    "PLACEHOLDER_STREAM_ID",
    "PLACEHOLDER_SEQUENCE",
    "PLACEHOLDER_CHANNEL",
    "PLACEHOLDER_CONTENT",
    "PLACEHOLDER_PROVIDER",
    "PLACEHOLDER_INVOCATION",
    "PLACEHOLDER_NO_RECEIPT",
    "PLACEHOLDER_TIMESTAMP",
    # Re-exports from runtime.py (Cluster 1 substrate)
    "RuntimeProvider",
    "RuntimeCapabilityKind",
    "RuntimeProposal",
    "RuntimeInvocation",
]
