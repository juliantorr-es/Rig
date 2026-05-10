"""Runtime Adapters for Rig.

This module provides local runtime adapters for Phase 5 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Models propose; Rig governs.
- Adapters are local-only stubs for now.
- No real API keys required.
- No production networking.
- No hidden execution.
- No background daemons.

These adapters shape the runtime substrate cleanly before real integrations.

file: src/rig/domain/runtimes/__init__.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime import RuntimeProvider, RuntimeInvocation, RuntimeProposal

from rig.domain.runtimes.base import BaseRuntimeAdapter
from rig.domain.runtimes.openai_compatible import OpenAICompatibleAdapter
from rig.domain.runtimes.llama_cpp import LlamaCppAdapter
from rig.domain.runtimes.mlx import MLXAdapter
from rig.domain.runtimes.dry_run import DryRunAdapter

__all__ = [
    "BaseRuntimeAdapter",
    "OpenAICompatibleAdapter",
    "LlamaCppAdapter",
    "MLXAdapter",
    "DryRunAdapter",
    # Factory function
    "get_adapter",
]


def get_adapter(adapter_id: str, **kwargs: object) -> BaseRuntimeAdapter:
    """Get a runtime adapter by ID.
    
    args:
        adapter_id: The adapter identifier
        **kwargs: Adapter-specific configuration
    
    Returns:
        A BaseRuntimeAdapter instance
    """
    adapters = {
        "openai-compatible": OpenAICompatibleAdapter,
        "llama-cpp": LlamaCppAdapter,
        "mlx": MLXAdapter,
        "dry-run": DryRunAdapter,
    }
    
    adapter_class = adapters.get(adapter_id)
    if adapter_class is None:
        raise ValueError(f"Unknown adapter: {adapter_id}")
    
    return adapter_class(**kwargs)
