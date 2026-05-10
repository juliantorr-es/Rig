"""Projection Refresh Orchestration Delegation for Runtime Streaming Domain.

See ADR 0004: docs/adr/0004-runtime-streaming-consolidation.md

**CRITICAL**: This module owns refresh ORCHESTRATION ONLY.
Projection SEMANTICS (meaning, composition, lineage, contracts) belong to ADR 0002.

Phase 1: This is a thin delegation layer. All real implementation
remains in runtime_projection.py (Cluster 2 legacy module).

Future: Only refresh orchestration (invalidation triggering, cadence, coalescing)
will be extracted here. Projection semantics remain in the Projection Domain.
"""

from __future__ import annotations

# Phase 1: No implementation extraction yet - just documenting the target structure.
# All types remain in runtime_projection.py and are imported through the façade.

# In Phase 2+, this will contain:
# - Projection invalidation triggering
# - Refresh cadence coordination
# - Refresh coalescing
# - Bounded rebuild scheduling

# NOT:
# - Projection building (ADR 0002 authority)
# - Projection semantics (ADR 0002 authority)
# - Lineage correctness (ADR 0002 authority)
# - Deterministic rebuild execution (ADR 0002 authority)

__all__: list[str] = []
