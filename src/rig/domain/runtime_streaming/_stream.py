"""Stream Lifecycle Delegation for Runtime Streaming Domain.

See ADR 0004: docs/adr/0004-runtime-streaming-consolidation.md

Phase 1: This is a thin delegation layer. All real implementation
remains in runtime_stream.py (Cluster 2 legacy module).

Future: Streaming-specific orchestration logic will be extracted here.
"""

from __future__ import annotations

from typing import Any
from rig.domain.runtime_streaming._types import StreamInstanceId, StreamLineageId


def generate_stream_lineage_id(repo_root_name: str, config: Any) -> StreamLineageId:
    """Generate deterministic stream lineage ID."""
    import hashlib
    config_str = str(config) if config else ""
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]
    return f"{repo_root_name}_{config_hash}"


def generate_stream_instance_id(config: Any) -> StreamInstanceId:
    """Generate non-deterministic stream instance ID."""
    return f"inst_{id(config)}"


# In Phase 2+, this will contain:
# - Stream lifecycle management
# - Stream identity generation (lineage_id, instance_id)
# - Stream event sequencing

# For now, this is a placeholder documenting the architectural intent.

__all__: list[str] = []
