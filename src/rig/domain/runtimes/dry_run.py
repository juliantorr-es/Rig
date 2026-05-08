"""Dry-Run Runtime Adapter for Rig.

This module provides a dry-run runtime adapter for Phase 5 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Models propose; Rig governs.
- Dry-run adapter does NO actual execution.
- All outputs are mock proposals for testing.
- No API keys required.
- No networking.
- No hidden execution.

This adapter is for testing and validation purposes only.

file: src/rig/domain/runtimes/dry_run.py
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
# Dry-Run Adapter
# =============================================================================

class DryRunAdapter(BaseRuntimeAdapter):
    """Dry-run runtime adapter.
    
    This adapter simulates runtime execution without actually executing anything.
    It generates mock proposals for testing and validation.
    
    Properties:
    - No actual execution
    - All outputs are mock proposals
    - No API keys required
    - No networking
    - No hidden execution
    
    Use cases:
    - Testing runtime infrastructure
    - Validating proposal generation
    - Dry-run mode for CI/integration testing
    """
    
    def __init__(
        self,
        model_id: str = "dry-run-model",
        adapter_id: str = "dry-run",
        provider_id: str = "dry-run",
        config: Optional[AdapterConfig] = None,
        deterministic_output: Optional[str] = None,
        mock_proposals: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize the dry-run adapter.
        
        args:
            model_id: The model identifier
            adapter_id: The adapter identifier
            provider_id: The provider identifier
            config: Optional adapter configuration
            deterministic_output: Optional fixed output for deterministic testing
            mock_proposals: Optional list of mock proposals to return
        """
        super().__init__(
            adapter_id=adapter_id,
            provider_id=provider_id,
            model_id=model_id,
            config=config,
        )
        self.deterministic_output = deterministic_output
        self.mock_proposals = mock_proposals or []
    
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
                RuntimeCapabilityKind.TELEMETRY_EXPORT_PROPOSAL,
            ]),
            default_capability_kinds=frozenset([
                RuntimeCapabilityKind.FILE_READ,
                RuntimeCapabilityKind.REPLAY_ACCESS,
            ]),
        )
    
    def get_provider(self) -> RuntimeProvider:
        """Get the dry-run provider."""
        return RuntimeProvider(
            provider_id=self.provider_id,
            kind=RuntimeProviderKind.DRY_RUN,
            trust_tier=RuntimeProviderTrustTier.ADVISORY,
            version="1.0.0",
            executable="dry-run",
            offline_capable=True,
            supports_streaming=False,
            supports_structured_output=True,
            can_modify_files=False,
            rig_allows_file_mutation=False,
            supported_tasks=["dry_run", "validate", "test"],
            status=RuntimeProviderStatus.AVAILABLE,
        )
    
    def invoke(
        self,
        request: Dict[str, Any],
        workspace_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        capability_kinds: Optional[FrozenSet[RuntimeCapabilityKind]] = None,
    ) -> AdapterResult:
        """Invoke the dry-run adapter.
        
        This method generates mock proposals without actual execution.
        
        args:
            request: The invocation request
            workspace_id: Optional workspace context
            actor_id: Optional actor context
            capability_kinds: Optional set of capability kinds to use
        
        Returns:
            AdapterResult with mock invocation, proposals, and receipt
        """
        # Create invocation
        invocation = self.create_invocation(request, workspace_id, actor_id)
        
        # Generate proposals based on request or use mock proposals
        proposals = self._generate_proposals(request, invocation, capability_kinds)
        
        # Determine output
        if self.deterministic_output:
            raw_output = self.deterministic_output
        else:
            raw_output = self._generate_output(request)
        
        # Mark invocation as succeeded (dry-run always succeeds)
        invocation = RuntimeInvocation(
            invocation_id=invocation.invocation_id,
            provider_id=invocation.provider_id,
            model_id=invocation.model_id,
            capability_ids=invocation.capability_ids,
            request=invocation.request,
            status=RuntimeInvocationStatus.SUCCEEDED,
            started_at=invocation.started_at,
            completed_at=invocation.started_at,  # Instant completion for dry-run
            exit_code=0,
            raw_output=raw_output,
            workspace_id=invocation.workspace_id,
            actor_id=invocation.actor_id,
        )
        
        # Create execution receipt
        execution_receipt = self.create_execution_receipt(
            invocation=invocation,
            proposals=proposals,
            duration_seconds=0.0,  # Instant for dry-run
        )
        
        return AdapterResult(
            invocation=invocation,
            proposals=proposals,
            raw_output=raw_output,
            execution_receipt=execution_receipt,
            success=True,
        )
    
    def _generate_proposals(
        self,
        request: Dict[str, Any],
        invocation: RuntimeInvocation,
        capability_kinds: Optional[FrozenSet[RuntimeCapabilityKind]],
    ) -> List[RuntimeProposal]:
        """Generate mock proposals based on the request."""
        proposals: List[RuntimeProposal] = []
        
        # Use mock proposals if provided
        if self.mock_proposals:
            for i, proposal_data in enumerate(self.mock_proposals):
                proposal = RuntimeProposal.from_invocation(
                    invocation=invocation,
                    proposal_kind=proposal_data.get("kind", "mock"),
                    payload=proposal_data.get("payload", {}),
                )
                proposals.append(proposal)
            return proposals
        
        # Auto-generate proposals based on request
        task = request.get("task", "").lower()
        static_output = request.get("static_output", "")
        
        # Try to parse static_output as JSON for structured proposals
        if static_output:
            try:
                parsed = json.loads(static_output)
                if isinstance(parsed, dict):
                    # Generate proposal from parsed data
                    proposal = RuntimeProposal.from_invocation(
                        invocation=invocation,
                        proposal_kind=parsed.get("kind", "proposal"),
                        payload=parsed,
                    )
                    proposals.append(proposal)
                    return proposals
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Default: generate a generic proposal
        proposal = RuntimeProposal.from_invocation(
            invocation=invocation,
            proposal_kind="dry_run",
            payload={
                "message": "Dry-run execution completed",
                "request": request,
            },
        )
        proposals.append(proposal)
        
        return proposals
    
    def _generate_output(self, request: Dict[str, Any]) -> str:
        """Generate mock output."""
        task = request.get("task", "dry_run")
        return f"Dry-run adapter executed task: {task}"
    
    def with_deterministic_output(self, output: str) -> "DryRunAdapter":
        """Create a new adapter with deterministic output."""
        return DryRunAdapter(
            adapter_id=self.adapter_id,
            provider_id=self.provider_id,
            model_id=self.model_id,
            deterministic_output=output,
        )
    
    def with_mock_proposals(self, proposals: List[Dict[str, Any]]) -> "DryRunAdapter":
        """Create a new adapter with mock proposals."""
        return DryRunAdapter(
            adapter_id=self.adapter_id,
            provider_id=self.provider_id,
            model_id=self.model_id,
            mock_proposals=proposals,
        )


# =============================================================================
# factory functions
# =============================================================================

def create_dry_run_adapter(
    model_id: str = "dry-run-model",
    deterministic_output: Optional[str] = None,
) -> DryRunAdapter:
    """Factory function to create a dry-run adapter."""
    return DryRunAdapter(
        model_id=model_id,
        deterministic_output=deterministic_output,
    )


__all__ = [
    "DryRunAdapter",
    "create_dry_run_adapter",
]
