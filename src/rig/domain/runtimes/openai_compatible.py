"""OpenAI-Compatible Runtime Adapter for Rig.

This module provides an OpenAI-compatible runtime adapter for Phase 5 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Models propose; Rig governs.
- Adapter is a stub for now - no real API calls.
- No real API keys required.
- No production networking.
- No hidden execution.

This adapter simulates OpenAI-compatible API behavior for testing.

file: src/rig/domain/runtimes/openai_compatible.py
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
# OpenAI-Compatible Adapter
# =============================================================================

class OpenAICompatibleAdapter(BaseRuntimeAdapter):
    """OpenAI-compatible runtime adapter.
    
    This adapter simulates OpenAI-compatible API behavior.
    It does NOT make actual API calls or require real API keys.
    
    Properties:
    - Stub implementation only
    - No real API calls
    - No API keys required
    - No production networking
    - No hidden execution
    
    Use cases:
    - Testing OpenAI-compatible behavior
    - Simulating chat/completion APIs
    - Validating OpenAI-compatible proposal generation
    """
    
    def __init__(
        self,
        model_id: str = "openai-compatible-model",
        adapter_id: str = "openai-compatible",
        provider_id: str = "openai-compatible",
        config: Optional[AdapterConfig] = None,
        mock_response: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the OpenAI-compatible adapter.
        
        args:
            model_id: The model identifier
            adapter_id: The adapter identifier
            provider_id: The provider identifier
            config: Optional adapter configuration
            mock_response: Optional mock response to return
        """
        super().__init__(
            adapter_id=adapter_id,
            provider_id=provider_id,
            model_id=model_id,
            config=config,
        )
        self.mock_response = mock_response
    
    def declare_capabilities(self) -> AdapterCapabilities:
        """Declare supported capabilities."""
        return AdapterCapabilities(
            adapter_id=self.adapter_id,
            supported_capability_kinds=frozenset([
                RuntimeCapabilityKind.FILE_READ,
                RuntimeCapabilityKind.FILE_WRITE_PROPOSAL,
                RuntimeCapabilityKind.SHELL_PROPOSAL,
                RuntimeCapabilityKind.PATCH_PROPOSAL,
                RuntimeCapabilityKind.REPLAY_ACCESS,
                RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL,
                RuntimeCapabilityKind.DOCS_FETCH_PROPOSAL,
            ]),
            default_capability_kinds=frozenset([
                RuntimeCapabilityKind.FILE_READ,
                RuntimeCapabilityKind.SHELL_PROPOSAL,
                RuntimeCapabilityKind.REPLAY_ACCESS,
            ]),
        )
    
    def get_provider(self) -> RuntimeProvider:
        """Get the OpenAI-compatible provider."""
        return RuntimeProvider(
            provider_id=self.provider_id,
            kind=RuntimeProviderKind.CLI,
            trust_tier=RuntimeProviderTrustTier.PLANNER,
            version="1.0.0",
            executable="openai-compatible",
            offline_capable=False,
            supports_streaming=True,
            supports_structured_output=True,
            can_modify_files=False,
            rig_allows_file_mutation=False,
            supported_tasks=["chat", "completion", "embedding"],
            status=RuntimeProviderStatus.AVAILABLE,
        )
    
    def invoke(
        self,
        request: Dict[str, Any],
        workspace_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        capability_kinds: Optional[FrozenSet[RuntimeCapabilityKind]] = None,
    ) -> AdapterResult:
        """Invoke the OpenAI-compatible adapter.
        
        This method simulates an OpenAI-compatible API call.
        It does NOT make actual API calls.
        
        args:
            request: The invocation request (should contain messages, model, etc.)
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
            response = self.mock_response
        else:
            response = self._generate_response(request)
        
        # Extract proposals from response
        proposals = self._extract_proposals(response, invocation)
        
        # Format output
        raw_output = json.dumps(response, indent=2) if isinstance(response, dict) else str(response)
        
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
        
        # Create execution receipt with token metadata
        token_metadata = self._estimate_tokens(request, response)
        execution_receipt = self.create_execution_receipt(
            invocation=invocation,
            proposals=proposals,
            duration_seconds=0.5,  # Simulated latency
            token_metadata=token_metadata,
        )
        
        return AdapterResult(
            invocation=invocation,
            proposals=proposals,
            raw_output=raw_output,
            execution_receipt=execution_receipt,
            success=True,
        )
    
    def _generate_response(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a mock OpenAI-compatible response."""
        messages = request.get("messages", [])
        
        # Generate a simple response
        response_message = {
            "role": "assistant",
            "content": "This is a simulated OpenAI-compatible response for testing purposes only.",
        }
        
        # Try to extract tool calls if needed
        tool_calls = []
        if any("tool" in str(m).lower() for m in messages):
            tool_calls = [
                {
                    "id": "tool_call_1",
                    "type": "function",
                    "function": {
                        "name": "simulated_tool",
                        "arguments": "{}",
                    },
                }
            ]
        
        return {
            "id": "chatcmpl_simulated",
            "object": "chat.completion",
            "created": 1700000000,
            "model": self.model_id,
            "choices": [
                {
                    "index": 0,
                    "message": response_message,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 25,
                "completion_tokens": 20,
                "total_tokens": 45,
            },
        }
    
    def _extract_proposals(
        self,
        response: Dict[str, Any],
        invocation: RuntimeInvocation,
    ) -> List[RuntimeProposal]:
        """Extract proposals from a response."""
        proposals: List[RuntimeProposal] = []
        
        # Check for structured output
        choices = response.get("choices", [])
        if choices:
            for choice in choices:
                message = choice.get("message", {})
                content = message.get("content", "")
                
                # Try to parse as JSON
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        # Handle structured proposal
                        proposal = RuntimeProposal.from_invocation(
                            invocation=invocation,
                            proposal_kind=parsed.get("kind", "proposal"),
                            payload=parsed,
                        )
                        proposals.append(proposal)
                    else:
                        # Handle text proposal
                        proposal = RuntimeProposal.from_invocation(
                            invocation=invocation,
                            proposal_kind="text",
                            payload={"content": content},
                        )
                        proposals.append(proposal)
                except (json.JSONDecodeError, TypeError):
                    # Plain text proposal
                    proposal = RuntimeProposal.from_invocation(
                        invocation=invocation,
                        proposal_kind="text",
                        payload={"content": content},
                    )
                    proposals.append(proposal)
        
        # If no proposals extracted, create a default one
        if not proposals:
            proposal = RuntimeProposal.from_invocation(
                invocation=invocation,
                proposal_kind="openai_response",
                payload={
                    "response_id": response.get("id", "unknown"),
                    "model": response.get("model", self.model_id),
                },
            )
            proposals.append(proposal)
        
        return proposals
    
    def _estimate_tokens(
        self,
        request: Dict[str, Any],
        response: Dict[str, Any],
    ) -> Dict[str, int]:
        """Estimate token usage."""
        # Use values from response if available
        usage = response.get("usage", {})
        if usage:
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            }
        
        # Default estimates
        messages = request.get("messages", [])
        prompt_tokens = sum(len(str(m)) // 4 for m in messages)  # Rough estimate
        completion_tokens = 20  # Default
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
    
    def with_mock_response(self, response: Dict[str, Any]) -> "OpenAICompatibleAdapter":
        """Create a new adapter with a mock response."""
        return OpenAICompatibleAdapter(
            adapter_id=self.adapter_id,
            provider_id=self.provider_id,
            model_id=self.model_id,
            mock_response=response,
        )


# =============================================================================
# Factory functions
# =============================================================================

def create_openai_compatible_adapter(
    model_id: str = "gpt-4",
    mock_response: Optional[Dict[str, Any]] = None,
) -> OpenAICompatibleAdapter:
    """Factory function to create an OpenAI-compatible adapter."""
    return OpenAICompatibleAdapter(
        model_id=model_id,
        mock_response=mock_response,
    )


__all__ = [
    "OpenAICompatibleAdapter",
    "create_openai_compatible_adapter",
]
