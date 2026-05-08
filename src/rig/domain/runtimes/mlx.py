"""MLX Runtime Adapter for Rig.

This module provides an MLX (Apple Metal) runtime adapter for Phase 5 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Models propose; Rig governs.
- Adapter is a local stub for now - no real MLX calls.
- No real model files required.
- No production execution.
- No hidden execution.
- Apple Silicon only (in metadata).

This adapter simulates MLX behavior for testing.

file: src/rig/domain/runtimes/mlx.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime import (
        RuntimeCapabilityKind,
        RuntimeInvocation,
        RuntimeProposal,
        RuntimeProvider,
    )

from rig.domain.runtimes.base import BaseRuntimeAdapter, AdapterResult, AdapterConfig, AdapterCapabilities
from rig.domain.runtime import (
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_NO_PROVIDER,
    RuntimeCapabilityKind,
    RuntimeProvider,
    RuntimeProviderKind,
    RuntimeProviderTrustTier,
    RuntimeProviderStatus,
    RuntimeInvocation,
    RuntimeProposal,
    RuntimeExecutionReceipt,
    RuntimeInvocationStatus,
)


# =============================================================================
# MLX Adapter
# =============================================================================

class MLXAdapter(BaseRuntimeAdapter):
    """MLX runtime adapter.
    
    This adapter simulates MLX (Apple Metal) local model inference.
    It does NOT require real model files or make actual calls.
    
    Properties:
    - Apple Silicon / macOS only (in metadata)
    - Local process execution simulation
    - No real model files required
    - No actual MLX library calls
    - No hidden execution
    - Offline-capable in simulation
    
    Use cases:
    - Testing Apple Silicon model inference
    - Validating MLX-compatible proposal generation
    - Simulating macOS-local model execution
    """
    
    def __init__(
        self,
        model_id: str = "mlx-llama-7b",
        adapter_id: str = "mlx",
        provider_id: str = "mlx",
        config: Optional[AdapterConfig] = None,
        mock_response: Optional[str] = None,
        model_path: Optional[str] = None,
        device: str = "mps",
    ):
        """Initialize the MLX adapter.
        
        args:
            model_id: The model identifier
            adapter_id: The adapter identifier
            provider_id: The provider identifier
            config: Optional adapter configuration
            mock_response: Optional mock text response to return
            model_path: Optional simulated model file path
            device: The device to use (mps, cpu, etc.)
        """
        super().__init__(
            adapter_id=adapter_id,
            provider_id=provider_id,
            model_id=model_id,
            config=config,
        )
        self.mock_response = mock_response
        self.model_path = model_path or f"/path/to/mlx-models/{model_id}.safetensors"
        self.device = device
    
    def declare_capabilities(self) -> AdapterCapabilities:
        """Declare supported capabilities."""
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            supported_capability_kinds=frozenset([
                RuntimeCapabilityKind.FILE_READ,
                RuntimeCapabilityKind.SHELL_PROPOSAL,
                RuntimeCapabilityKind.PATCH_PROPOSAL,
                RuntimeCapabilityKind.REPLAY_ACCESS,
                RuntimeCapabilityKind.DOCS_FETCH_PROPOSAL,
            ]),
            default_capability_kinds=frozenset([
                RuntimeCapabilityKind.FILE_READ,
                RuntimeCapabilityKind.SHELL_PROPOSAL,
            ]),
        )
    
    def get_provider(self) -> RuntimeProvider:
        """Get the MLX provider."""
        return RuntimeProvider(
            provider_id=self.provider_id,
            kind=RuntimeProviderKind.LOCAL,
            trust_tier=RuntimeProviderTrustTier.PLANNER,
            version="1.0.0",
            executable="mlx",
            offline_capable=True,
            supports_streaming=True,
            supports_structured_output=True,
            can_modify_files=False,
            rig_allows_file_mutation=False,
            supported_tasks=["inference", "embedding", "chat", "generate"],
            status=RuntimeProviderStatus.AVAILABLE,
        )
    
    def invoke(
        self,
        request: Dict[str, Any],
        workspace_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        capability_kinds: Optional[FrozenSet[RuntimeCapabilityKind]] = None,
    ) -> AdapterResult:
        """Invoke the MLX adapter.
        
        This method simulates an MLX inference call.
        It does NOT make actual MLX calls or require real model files.
        
        args:
            request: The invocation request (should contain prompt, etc.)
            workspace_id: Optional workspace context
            actor_id: Optional actor context
            capability_kinds: Optional set of capability kinds to use
        
        Returns:
            AdapterResult with invocation, proposals, and receipt
        """
        # Create invocation
        invocation = self.create_invocation(request, workspace_id, actor_id)
        
        # Generate response
        if self.mock_response:
            response_text = self.mock_response
        else:
            response_text = self._generate_response(request)
        
        # Extract proposals from response
        proposals = self._extract_proposals(response_text, invocation)
        
        # Format output
        raw_output = response_text
        
        # Mark invocation as succeeded
        invocation = RuntimeInvocation(
            invocation_id=invocation.invocation_id,
            provider_id=invocation.provider_id,
            model_id=invocation.model_id,
            capability_ids=invocation.capability_ids,
            request=invocation.request,
            status=RuntimeInvocationStatus.SUCCEEDED,
            started_at=invocation.started_at,
            completed_at=invocation.started_at,
            exit_code=0,
            raw_output=raw_output,
            workspace_id=invocation.workspace_id,
            actor_id=invocation.actor_id,
        )
        
        # Estimate token count (rough estimate)
        prompt = request.get("prompt", "")
        prompt_tokens = len(prompt) // 4 if prompt else 0
        completion_tokens = len(response_text) // 4 if response_text else 0
        
        # Create execution receipt with MLX-specific metadata
        execution_receipt = self.create_execution_receipt(
            invocation=invocation,
            proposals=proposals,
            duration_seconds=0.8,  # Simulated MLX latency (optimized for Apple Silicon)
            token_metadata={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        )
        
        return AdapterResult(
            invocation=invocation,
            proposals=proposals,
            raw_output=raw_output,
            execution_receipt=execution_receipt,
            success=True,
        )
    
    def _generate_response(self, request: Dict[str, Any]) -> str:
        """Generate a mock MLX response."""
        prompt = request.get("prompt", "")
        
        # Simple response based on prompt
        if "analyze" in prompt.lower():
            return "I am an MLX-powered model on Apple Silicon. I can analyze code and provide insights. What would you like me to analyze?"
        
        if "generate" in prompt.lower():
            return "I can generate code, text, or other content. What would you like me to generate?"
        
        if "explain" in prompt.lower():
            return "I can explain concepts, code, or documentation. What would you like me to explain?"
        
        return f"I am an MLX model ({self.model_id}) running on Apple Silicon with device '{self.device}'. How can I help you?"
    
    def _extract_proposals(
        self,
        response_text: str,
        invocation: RuntimeInvocation,
    ) -> List[RuntimeProposal]:
        """Extract proposals from a text response."""
        proposals: List[RuntimeProposal] = []
        
        # Try to parse as JSON first
        try:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict):
                proposal = RuntimeProposal.from_invocation(
                    invocation=invocation,
                    proposal_kind=parsed.get("kind", "mlx_proposal"),
                    payload=parsed,
                )
                proposals.append(proposal)
                return proposals
        except (json.JSONDecodeError, TypeError):
            pass
        
        # For plain text, create a text proposal with MLX metadata
        proposal = RuntimeProposal.from_invocation(
            invocation=invocation,
            proposal_kind="text",
            payload={
                "content": response_text,
                "model": self.model_id,
                "model_path": self.model_path,
                "device": self.device,
                "framework": "mlx",
            },
        )
        proposals.append(proposal)
        
        return proposals
    
    def with_mock_response(self, response: str) -> "MLXAdapter":
        """Create a new adapter with a mock response."""
        return MLXAdapter(
            adapter_id=self.adapter_id,
            provider_id=self.provider_id,
            model_id=self.model_id,
            mock_response=response,
        )
    
    def with_model_path(self, path: str) -> "MLXAdapter":
        """Create a new adapter with a model path."""
        return MLXAdapter(
            adapter_id=self.adapter_id,
            provider_id=self.provider_id,
            model_id=self.model_id,
            model_path=path,
        )
    
    def with_device(self, device: str) -> "MLXAdapter":
        """Create a new adapter with a device."""
        return MLXAdapter(
            adapter_id=self.adapter_id,
            provider_id=self.provider_id,
            model_id=self.model_id,
            device=device,
        )


# =============================================================================
# Factory functions
# =============================================================================

def create_mlx_adapter(
    model_id: str = "mlx-llama-7b",
    model_path: Optional[str] = None,
    mock_response: Optional[str] = None,
    device: str = "mps",
) -> MLXAdapter:
    """Factory function to create an MLX adapter."""
    return MLXAdapter(
        model_id=model_id,
        model_path=model_path,
        mock_response=mock_response,
        device=device,
    )


__all__ = [
    "MLXAdapter",
    "create_mlx_adapter",
]
