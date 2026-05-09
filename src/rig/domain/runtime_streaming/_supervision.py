"""Supervision Coordination Delegation for Runtime Streaming Domain.

See ADR 0004: docs/adr/0004-runtime-streaming-consolidation.md

Phase 1: This is a thin delegation layer. All real implementation
remains in runtime_supervisor.py (Cluster 2 legacy module).

Future: Supervision coordination logic will be extracted here.
"""

from __future__ import annotations

# Phase 1: No implementation extraction yet - just documenting the target structure.
# All types remain in runtime_supervisor.py and are imported through the façade.

# In Phase 2+, this will contain:
# - Process supervision coordination
# - Output collection
# - Timeout management
# - Subprocess lifecycle

__all__: list[str] = []
