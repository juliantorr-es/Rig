"""llama.cpp Runtime Adapter for Rig.

This module provides a llama.cpp runtime adapter for Phase 5 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Models propose; Rig governs.
- Adapter is a local stub for now - no real library calls.
- No real model files required.
- No production execution.
- No hidden execution.

This adapter simulates llama.cpp behavior for testing.

file: src/rig/domain/runtimes/llama_cpp.py
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
# Llama.cpp Adapter
# =============================================================================

class LlamaCppAdapter(BaseRuntimeAdapter):
    """llama.cpp runtime adapter.
    
    This adapter simulates llama.cpp local model inference.
    It does NOT require real model files or make actual calls.
    
    Properties:
    - Local process execution simulation
    - No real model files required
    - No actual library calls
    - No hidden execution
    - Offline-capable in simulation
    
    Use cases:
    - Testing local model inference
    - Validating llama.cpp-compatible proposal generation
    - Simulating offline model execution
    """
    
    def __init__(
        self,
        model_id: str = "llama-7b",
        adapter_id: str = "llama-cpp",
        provider_id: str = "llama-cpp",
        config: Optional[AdapterConfig] = None,
        mock_response: Optional[str] = None,
        model_path: Optional[str] = None,
    ):
        """Initialize the llama.cpp adapter.
        
        args:
            model_id: The model identifier
            adapter_id: The adapter identifier
            provider_id: The provider identifier
            config: Optional adapter configuration
            mock_response: Optional mock text response to return
            model_path: Optional simulated model file path
        """
        super().__init__(
            adapter_id=adapter_id,
            provider_id=provider_id,
            model_id=model_id,
            config=config,
        )
        self.mock_response = mock_response
        self.model_path = model_path or f"/path/to/models/{model_id}.gguf"
    
    def declare_capabilities(self) -> AdapterCapabilities:
        """Declare supported capabilities."""
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            supported_capability_kinds=frozenset([
                RuntimeCapabilityKind.FILE_READ,
                RuntimeCapabilityKind.SHELL_PROPOSAL,
                RuntimeCapabilityKind.PATCH_PROPOSAL,
                RuntimeCapabilityKind.REPLAY_ACCESS,
            ]),
            default_capability_kinds=frozenset([
                RuntimeCapabilityKind.FILE_READ,
                RuntimeCapabilityKind.SHELL_PROPOSAL,
            ]),
        )
    
    def get_provider(self) -> RuntimeProvider:
        """Get the llama.cpp provider."""
        return RuntimeProvider(
            provider_id=self.provider_id,
            kind=RuntimeProviderKind.LOCAL,
            trust_tier=RuntimeProviderTrustTier.REVIEWER,
            version="1.0.0",
            executable="llama-cpp",
            offline_capable=True,
            supports_streaming=True,
            supports_structured_output=True,
            can_modify_files=False,
            rig_allows_file_mutation=False,
            supported_tasks=["inference", "embedding", "chat"],
            status=RuntimeProviderStatus.AVAILABLE,
        )
    
    def invoke(
        self,
        request: Dict[str, Any],
        workspace_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        capability_kinds: Optional[FrozenSet[RuntimeCapabilityKind]] = None,
    ) -> AdapterResult:
        """Invoke the llama.cpp adapter.
        
        This method simulates a llama.cpp inference call.
        It does NOT make actual calls or require real model files.
        
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
        
        # Create execution receipt
        execution_receipt = self.create_execution_receipt(
            invocation=invocation,
            proposals=proposals,
            duration_seconds=1.5,  # Simulated local inference latency
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
        """Generate a mock llama.cpp response."""
        prompt = request.get("prompt", "")
        
        # Simple response based on prompt
        if "file" in prompt.lower():
            return "I can read files and help you analyze them. What file would you like me to look at?"
        
        if "command" in prompt.lower() or "run" in prompt.lower():
            return "I can suggest shell commands for you to review and run. What would you like to do?"
        
        if "patch" in prompt.lower():
            return "I can suggest code changes as patches for you to review. What needs to be changed?"
        
        return "I am a local language model running via llama.cpp. How can I help you?"
    
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
                    proposal_kind=parsed.get("kind", "llama_proposal"),
                    payload=parsed,
                )
                proposals.append(proposal)
                return proposals
        except (json.JSONDecodeError, TypeError):
            pass
        
        # For plain text, create a text proposal
        proposal = RuntimeProposal.from_invocation(
            invocation=invocation,
            proposal_kind="text",
            payload={
                "content": response_text,
                "model": self.model_id,
                "model_path": self.model_path,
            },
        )
        proposals.append(proposal)
        
        return proposals
    
    def with_mock_response(self, response: str) -> "LlamaCppAdapter":
        """Create a new adapter with a mock response."""
        return LlamaCppAdapter(
            adapter_id=self.adapter_id,
            provider_id=self.provider_id,
            model_id=self.model_id,
            mock_response=response,
        )
    
    def with_model_path(self, path: str) -> "LlamaCppAdapter":
        """Create a new adapter with a model path."""
        return LlamaCppAdapter(
            adapter_id=self.adapter_id,
            provider_id=self.provider_id,
            model_id=self.model_id,
            model_path=path,
        )


# =============================================================================
# Factory functions
# =============================================================================

def create_llama_cpp_adapter(
    model_id: str = "llama-7b",
    model_path: Optional[str] = None,
    mock_response: Optional[str] = None,
) -> LlamaCppAdapter:
    """Factory function to create a llama.cpp adapter."""
    return LlamaCppAdapter(
        model_id=model_id,
        model_path=model_path,
        mock_response=mock_response,
    )


__all__ = [
    "LlamaCppAdapter",
    "create_llama_cpp_adapter",
]
