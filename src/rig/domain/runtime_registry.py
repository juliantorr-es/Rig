"""Runtime Capability Registry for Rig.

This module provides the canonical runtime capability registry for Phase 2 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Capabilities DO NOT execute authority directly.
- They authorize proposal generation only.
- Runtime providers are advisory execution providers, not authorities.
- All capability checks are deterministic and replay-safe.
- All models are JSON-serializable.
- No ambient mutation.

file: src/rig/domain/runtime_registry.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime import (
        RuntimeCapability,
        RuntimeCapabilityKind,
        RuntimeCapabilityScope,
        RuntimeConstraint,
        RuntimeProvider,
        RuntimeProviderTrustTier,
    )

from rig.domain.runtime import (
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_NO_PROVIDER,
    PLACEHOLDER_NO_CAPABILITY,
    RuntimeCapabilityKind,
    RuntimeCapabilityScope,
    RuntimeConstraintKind,
    RuntimeConstraintMode,
    RuntimeInvocationStatus,
    RuntimeProviderKind,
    RuntimeProviderTrustTier,
    RuntimeProviderStatus,
)


# =============================================================================
# Helper Functions
# =============================================================================

def _utc_now() -> str:
    """Get current UTC time as ISO format string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# =============================================================================
# Capability Registry
# =============================================================================

@dataclass(frozen=True, slots=True)
class CapabilityRegistry:
    """Immutable registry of runtime capabilities.
    
    Provides:
    - Capability registration and lookup
    - Capability validation
    - Runtime/provider compatibility checks
    - Runtime constraint enforcement
    - Deterministic serialization
    
    Capabilities DO NOT execute authority directly.
    They authorize proposal generation only.
    """
    
    # Capabilities indexed by capability_id
    capabilities: Dict[str, "RuntimeCapability"] = field(default_factory=dict)
    
    # Capabilities indexed by kind
    capabilities_by_kind: Dict[RuntimeCapabilityKind, Set[str]] = field(default_factory=dict)
    
    # Capabilities indexed by workspace_id
    capabilities_by_workspace: Dict[Optional[str], Set[str]] = field(default_factory=dict)
    
    # Capabilities indexed by scope
    capabilities_by_scope: Dict[RuntimeCapabilityScope, Set[str]] = field(default_factory=dict)
    
    # Provider capabilities: provider_id -> set of capability_ids
    provider_capabilities: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    
    # Constraints indexed by constraint_id
    constraints: Dict[str, "RuntimeConstraint"] = field(default_factory=dict)
    
    # Constraints indexed by workspace_id
    constraints_by_workspace: Dict[Optional[str], Set[str]] = field(default_factory=dict)
    
    # Registered providers indexed by provider_id
    providers: Dict[str, "RuntimeProvider"] = field(default_factory=dict)
    
    # Registry metadata
    registry_id: str = field(default_factory=lambda: f"registry_{_utc_now().replace(':', '-').replace('.', '-')}")
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    version: str = "1.0.0"
    
    @classmethod
    def create_empty(cls) -> "CapabilityRegistry":
        """Create an empty capability registry."""
        return cls()
    
    @classmethod
    def create_default(cls) -> "CapabilityRegistry":
        """Create a default capability registry with built-in capabilities and constraints."""
        from rig.domain.runtime import (
            RuntimeCapability,
            RuntimeConstraint,
            RuntimeProvider,
        )
        
        # Create built-in capabilities
        capabilities: Dict[str, RuntimeCapability] = {}
        
        # Global capabilities
        for ws_id in [None, "global"]:
            caps = [
                RuntimeCapability.file_read(ws_id),
                RuntimeCapability.replay_access(),
            ]
            for cap in caps:
                if cap.capability_id not in capabilities:
                    capabilities[cap.capability_id] = cap
        
        # Per-workspace capabilities (template)
        cap_template = RuntimeCapability.file_write_proposal()
        capabilities[cap_template.capability_id] = cap_template
        
        cap_template = RuntimeCapability.shell_proposal()
        capabilities[cap_template.capability_id] = cap_template
        
        cap_template = RuntimeCapability.patch_proposal()
        capabilities[cap_template.capability_id] = cap_template
        
        cap_template = RuntimeCapability.network_fetch_proposal()
        capabilities[cap_template.capability_id] = cap_template
        
        cap_template = RuntimeCapability.docs_fetch_proposal()
        capabilities[cap_template.capability_id] = cap_template
        
        cap_template = RuntimeCapability.telemetry_export_proposal()
        capabilities[cap_template.capability_id] = cap_template
        
        # Create built-in constraints
        constraints: Dict[str, RuntimeConstraint] = {}
        
        # Global constraints
        global_constraints = [
            RuntimeConstraint.no_filesystem_writes(),
            RuntimeConstraint.no_network(),
            RuntimeConstraint.trust_tier_minimum(
                RuntimeProviderTrustTier.PLANNER
            ),
            RuntimeConstraint.timeout_maximum(300.0),  # 5 minutes default
        ]
        for c in global_constraints:
            constraints[c.constraint_id] = c
        
        # Create built-in providers
        providers: Dict[str, RuntimeProvider] = {}
        
        dry_run_provider = RuntimeProvider.dry_run()
        providers[dry_run_provider.provider_id] = dry_run_provider
        
        custom_provider = RuntimeProvider.custom_command()
        providers[custom_provider.provider_id] = custom_provider
        
        # Build indexes
        capabilities_by_kind: Dict[RuntimeCapabilityKind, Set[str]] = {}
        capabilities_by_workspace: Dict[Optional[str], Set[str]] = {}
        capabilities_by_scope: Dict[RuntimeCapabilityScope, Set[str]] = {}
        provider_capabilities: Dict[str, FrozenSet[str]] = {}
        constraints_by_workspace: Dict[Optional[str], Set[str]] = {}
        
        # Index capabilities
        for cap_id, cap in capabilities.items():
            # By kind
            if cap.kind not in capabilities_by_kind:
                capabilities_by_kind[cap.kind] = set()
            capabilities_by_kind[cap.kind].add(cap_id)
            
            # By workspace
            ws = cap.workspace_id
            if ws not in capabilities_by_workspace:
                capabilities_by_workspace[ws] = set()
            capabilities_by_workspace[ws].add(cap_id)
            
            # By scope
            if cap.scope not in capabilities_by_scope:
                capabilities_by_scope[cap.scope] = set()
            capabilities_by_scope[cap.scope].add(cap_id)
        
        # Index constraints
        for constraint_id, constraint in constraints.items():
            ws = constraint.workspace_id
            if ws not in constraints_by_workspace:
                constraints_by_workspace[ws] = set()
            constraints_by_workspace[ws].add(constraint_id)
        
        # Index provider capabilities
        for provider_id, provider in providers.items():
            # For now, all providers have all capabilities
            # This will be refined with actual provider-specific capabilities
            provider_capabilities[provider_id] = frozenset(capabilities.keys())
        
        return cls(
            capabilities=capabilities,
            capabilities_by_kind=capabilities_by_kind,
            capabilities_by_workspace=capabilities_by_workspace,
            capabilities_by_scope=capabilities_by_scope,
            provider_capabilities=provider_capabilities,
            constraints=constraints,
            constraints_by_workspace=constraints_by_workspace,
            providers=providers,
        )
    
    def get_capability(self, capability_id: str) -> Optional["RuntimeCapability"]:
        """Get a capability by ID."""
        return self.capabilities.get(capability_id)
    
    def get_capabilities_by_kind(self, kind: RuntimeCapabilityKind) -> List["RuntimeCapability"]:
        """Get all capabilities of a specific kind."""
        cap_ids = self.capabilities_by_kind.get(kind, set())
        return [self.capabilities[cap_id] for cap_id in cap_ids if cap_id in self.capabilities]
    
    def get_capabilities_for_workspace(self, workspace_id: Optional[str]) -> List["RuntimeCapability"]:
        """Get all capabilities for a specific workspace."""
        cap_ids = self.capabilities_by_workspace.get(workspace_id, set())
        return [self.capabilities[cap_id] for cap_id in cap_ids if cap_id in self.capabilities]
    
    def get_capabilities_by_scope(self, scope: RuntimeCapabilityScope) -> List["RuntimeCapability"]:
        """Get all capabilities with a specific scope."""
        cap_ids = self.capabilities_by_scope.get(scope, set())
        return [self.capabilities[cap_id] for cap_id in cap_ids if cap_id in self.capabilities]
    
    def get_provider(self, provider_id: str) -> Optional["RuntimeProvider"]:
        """Get a provider by ID."""
        return self.providers.get(provider_id)
    
    def get_provider_capabilities(self, provider_id: str) -> FrozenSet[str]:
        """Get all capability IDs for a specific provider."""
        return self.provider_capabilities.get(provider_id, frozenset())
    
    def get_constraint(self, constraint_id: str) -> Optional["RuntimeConstraint"]:
        """Get a constraint by ID."""
        return self.constraints.get(constraint_id)
    
    def get_constraints_for_workspace(self, workspace_id: Optional[str]) -> List["RuntimeConstraint"]:
        """Get all constraints for a specific workspace."""
        constraint_ids = self.constraints_by_workspace.get(workspace_id, set())
        return [self.constraints[cid] for cid in constraint_ids if cid in self.constraints]
    
    def has_capability(self, provider_id: str, capability_id: str) -> bool:
        """Check if a provider has a specific capability."""
        provider_caps = self.provider_capabilities.get(provider_id, frozenset())
        return capability_id in provider_caps
    
    def has_capability_kind(self, provider_id: str, kind: RuntimeCapabilityKind) -> bool:
        """Check if a provider has any capability of a specific kind."""
        provider_caps = self.get_provider_capabilities(provider_id)
        for cap_id in provider_caps:
            cap = self.get_capability(cap_id)
            if cap and cap.kind == kind:
                return True
        return False
    
    def validate_capability(
        self,
        provider_id: str,
        capability_id: str,
        workspace_id: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Validate if a provider can use a capability.
        
        Returns (is_valid, list of error messages).
        """
        errors: List[str] = []
        
        # Check if provider exists
        provider = self.get_provider(provider_id)
        if provider is None:
            errors.append(f"Unknown provider: {provider_id}")
            return False, errors
        
        # Check if capability exists
        capability = self.get_capability(capability_id)
        if capability is None:
            errors.append(f"Unknown capability: {capability_id}")
            return False, errors
        
        # Check if provider has capability
        if not self.has_capability(provider_id, capability_id):
            errors.append(f"Provider {provider_id} does not have capability {capability_id}")
            return False, errors
        
        # Check capability scope
        if capability.scope == RuntimeCapabilityScope.WORKSPACE:
            if capability.workspace_id and workspace_id:
                if capability.workspace_id != workspace_id:
                    errors.append(
                        f"Capability {capability_id} is scoped to workspace "
                        f"{capability.workspace_id}, not {workspace_id}"
                    )
                    return False, errors
        
        # Check constraint enforcement for this capability
        constraint_errors = self.validate_constraints(
            provider_id, capability, workspace_id
        )
        errors.extend(constraint_errors)
        
        if errors:
            return False, errors
        
        return True, []
    
    def validate_constraints(
        self,
        provider_id: str,
        capability: "RuntimeCapability",
        workspace_id: Optional[str] = None,
    ) -> List[str]:
        """Validate constraints for a provider/capability/workspace combination.
        
        Returns list of error messages (empty if all constraints satisfied).
        """
        errors: List[str] = []
        provider = self.get_provider(provider_id)
        if provider is None:
            return [f"Unknown provider: {provider_id}"]
        
        # Get all applicable constraints
        applicable_constraints: List["RuntimeConstraint"] = []
        
        # Global constraints
        for constraint_id, constraint in self.constraints.items():
            if constraint.scope == RuntimeCapabilityScope.GLOBAL:
                applicable_constraints.append(constraint)
        
        # Workspace-specific constraints
        ws_constraints = self.get_constraints_for_workspace(workspace_id)
        applicable_constraints.extend(ws_constraints)
        
        # Check each constraint
        for constraint in applicable_constraints:
            # Check if constraint applies to this capability
            if not constraint.applies_to_capability(capability):
                continue
            
            # Validate constraint
            if constraint.kind == RuntimeConstraintKind.TRUST_TIER:
                if constraint.mode == RuntimeConstraintMode.REQUIRED:
                    required_tier_str = constraint.value
                    try:
                        required_tier = RuntimeProviderTrustTier(required_tier_str)
                    except ValueError:
                        continue
                    
                    if provider.trust_tier.value < required_tier.value:
                        # Compare trust tier levels
                        tier_order = list(RuntimeProviderTrustTier)
                        provider_idx = tier_order.index(provider.trust_tier)
                        required_idx = tier_order.index(required_tier)
                        
                        if provider_idx < required_idx:
                            errors.append(
                                f"Trust tier violation: provider {provider_id} has tier "
                                f"{provider.trust_tier.value}, requires {required_tier.value}"
                            )
            
            elif constraint.kind == RuntimeConstraintKind.TIMEOUT:
                # Timeout constraint - always valid at check time
                # Will be enforced during execution
                pass
            
            elif constraint.kind == RuntimeConstraintKind.NETWORK:
                if constraint.mode == RuntimeConstraintMode.PROHIBITED:
                    if capability.kind == RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL:
                        errors.append(
                            f"Network access prohibited by constraint {constraint.constraint_id}"
                        )
            
            elif constraint.kind == RuntimeConstraintKind.FILESYSTEM:
                if constraint.mode == RuntimeConstraintMode.PROHIBITED:
                    if capability.kind in [
                        RuntimeCapabilityKind.FILE_WRITE_PROPOSAL,
                        RuntimeCapabilityKind.SHELL_PROPOSAL,
                        RuntimeCapabilityKind.PATCH_PROPOSAL,
                    ]:
                        errors.append(
                            f"Filesystem writes prohibited by constraint "
                            f"{constraint.constraint_id}"
                        )
        
        return errors
    
    def check_trust_tier(
        self,
        provider_id: str,
        minimum_tier: RuntimeProviderTrustTier,
    ) -> Tuple[bool, str]:
        """Check if a provider meets a minimum trust tier requirement.
        
        Returns (meets_requirement, reason).
        """
        provider = self.get_provider(provider_id)
        if provider is None:
            return False, f"Unknown provider: {provider_id}"
        
        tier_order = list(RuntimeProviderTrustTier)
        provider_idx = tier_order.index(provider.trust_tier)
        required_idx = tier_order.index(minimum_tier)
        
        if provider_idx >= required_idx:
            return True, f"Provider {provider_id} has trust tier {provider.trust_tier.value}"
        else:
            return False, (
                f"Provider {provider_id} has trust tier {provider.trust_tier.value}, "
                f"requires {minimum_tier.value}"
            )
    
    def get_required_capabilities(
        self,
        capability_kinds: Set[RuntimeCapabilityKind],
        workspace_id: Optional[str] = None,
    ) -> Set[str]:
        """Get all capability IDs required for a set of capability kinds."""
        required: Set[str] = set()
        
        for kind in capability_kinds:
            caps = self.get_capabilities_by_kind(kind)
            for cap in caps:
                # Check workspace scope
                if cap.scope == RuntimeCapabilityScope.WORKSPACE:
                    if cap.workspace_id == workspace_id:
                        required.add(cap.capability_id)
                else:
                    required.add(cap.capability_id)
        
        return required
    
    def get_missing_capabilities(
        self,
        provider_id: str,
        required_capability_kinds: Set[RuntimeCapabilityKind],
        workspace_id: Optional[str] = None,
    ) -> Set[str]:
        """Get capabilities that a provider is missing for required capability kinds."""
        required_ids = self.get_required_capabilities(
            required_capability_kinds, workspace_id
        )
        provider_ids = self.get_provider_capabilities(provider_id)
        return required_ids - provider_ids
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "registry_id": self.registry_id,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "capabilities": {k: v.to_dict() for k, v in self.capabilities.items()},
            "constraints": {k: v.to_dict() for k, v in self.constraints.items()},
            "providers": {k: v.to_dict() for k, v in self.providers.items()},
            "provider_capabilities": {
                k: list(v) for k, v in self.provider_capabilities.items()
            },
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CapabilityRegistry":
        """Deserialize from dictionary."""
        from rig.domain.runtime import (
            RuntimeCapability,
            RuntimeConstraint,
            RuntimeProvider,
        )
        
        # Deserialize capabilities
        capabilities = {}
        for cap_id, cap_data in d.get("capabilities", {}).items():
            try:
                cap = RuntimeCapability.from_dict(cap_data)
                capabilities[cap_id] = cap
            except Exception:
                pass
        
        # Deserialize constraints
        constraints = {}
        for constraint_id, constraint_data in d.get("constraints", {}).items():
            try:
                constraint = RuntimeConstraint.from_dict(constraint_data)
                constraints[constraint_id] = constraint
            except Exception:
                pass
        
        # Deserialize providers
        providers = {}
        for provider_id, provider_data in d.get("providers", {}).items():
            try:
                provider = RuntimeProvider.from_dict(provider_data)
                providers[provider_id] = provider
            except Exception:
                pass
        
        # Build indexes
        capabilities_by_kind: Dict[RuntimeCapabilityKind, Set[str]] = {}
        capabilities_by_workspace: Dict[Optional[str], Set[str]] = {}
        capabilities_by_scope: Dict[RuntimeCapabilityScope, Set[str]] = {}
        provider_capabilities: Dict[str, FrozenSet[str]] = {}
        constraints_by_workspace: Dict[Optional[str], Set[str]] = {}
        
        # Index capabilities
        for cap_id, cap in capabilities.items():
            if cap.kind not in capabilities_by_kind:
                capabilities_by_kind[cap.kind] = set()
            capabilities_by_kind[cap.kind].add(cap_id)
            
            ws = cap.workspace_id
            if ws not in capabilities_by_workspace:
                capabilities_by_workspace[ws] = set()
            capabilities_by_workspace[ws].add(cap_id)
            
            if cap.scope not in capabilities_by_scope:
                capabilities_by_scope[cap.scope] = set()
            capabilities_by_scope[cap.scope].add(cap_id)
        
        # Index constraints
        for constraint_id, constraint in constraints.items():
            ws = constraint.workspace_id
            if ws not in constraints_by_workspace:
                constraints_by_workspace[ws] = set()
            constraints_by_workspace[ws].add(constraint_id)
        
        # Index provider capabilities
        for provider_id, cap_ids in d.get("provider_capabilities", {}).items():
            provider_capabilities[provider_id] = frozenset(cap_ids)
        
        return cls(
            capabilities=capabilities,
            capabilities_by_kind=capabilities_by_kind,
            capabilities_by_workspace=capabilities_by_workspace,
            capabilities_by_scope=capabilities_by_scope,
            provider_capabilities=provider_capabilities,
            constraints=constraints,
            constraints_by_workspace=constraints_by_workspace,
            providers=providers,
            registry_id=d.get("registry_id", f"registry_{_utc_now().replace(':', '-').replace('.', '-')}"),
            created_at=d.get("created_at", _utc_now()),
            updated_at=d.get("updated_at", _utc_now()),
            version=d.get("version", "1.0.0"),
        )


# =============================================================================
# Mutable Runtime Registry (for runtime use)
# =============================================================================

class RuntimeRegistry:
    """Mutable runtime registry for active runtime management.
    
    This class provides the mutable interface for runtime operations:
    - Registering providers at runtime
    - Recording invocations and proposals
    - Tracking runtime state
    - Benchmark recording
    
    Uses an immutable CapabilityRegistry as its backing store for
    capability, constraint, and provider definitions.
    
    Properties:
    - No ambient mutation of authority state
    - Deterministic serialization
    - Replay-safe
    - Projection-safe
    """
    
    def __init__(self, capability_registry: Optional[CapabilityRegistry] = None):
        """Initialize the runtime registry.
        
        Args:
            capability_registry: The backing capability registry.
                                  If None, creates a default one.
        """
        self._capability_registry = capability_registry or CapabilityRegistry.create_default()
        self._invocations: Dict[str, "RuntimeInvocation"] = {}
        self._proposals: Dict[str, "RuntimeProposal"] = {}
        self._execution_receipts: Dict[str, "RuntimeExecutionReceipt"] = {}
        self._benchmarks: Dict[str, "RuntimeBenchmark"] = {}
        self._runtime_state: Optional["RuntimeState"] = None
        self._active_invocations: Set[str] = set()
    
    @property
    def capability_registry(self) -> CapabilityRegistry:
        """Get the backing capability registry."""
        return self._capability_registry
    
    def register_provider(self, provider: "RuntimeProvider") -> None:
        """Register a provider with the registry.
        
        Note: This does NOT mutate the backing capability registry.
        Providers registered here are ephemeral and not persisted.
        """
        # For now, just track in a separate dict
        # This could be extended to support session-scoped providers
        pass
    
    def record_invocation(self, invocation: "RuntimeInvocation") -> str:
        """Record a runtime invocation.
        
        Returns the invocation_id.
        """
        self._invocations[invocation.invocation_id] = invocation
        if invocation.status == RuntimeInvocationStatus.RUNNING:
            self._active_invocations.add(invocation.invocation_id)
        return invocation.invocation_id
    
    def get_invocation(self, invocation_id: str) -> Optional["RuntimeInvocation"]:
        """Get a recorded invocation."""
        return self._invocations.get(invocation_id)
    
    def record_proposal(self, proposal: "RuntimeProposal") -> str:
        """Record a runtime proposal.
        
        Returns the proposal_id.
        """
        self._proposals[proposal.proposal_id] = proposal
        return proposal.proposal_id
    
    def get_proposal(self, proposal_id: str) -> Optional["RuntimeProposal"]:
        """Get a recorded proposal."""
        return self._proposals.get(proposal_id)
    
    def record_execution_receipt(self, receipt: "RuntimeExecutionReceipt") -> str:
        """Record a runtime execution receipt.
        
        Returns the receipt_id.
        """
        self._execution_receipts[receipt.receipt_id] = receipt
        return receipt.receipt_id
    
    def get_execution_receipt(self, receipt_id: str) -> Optional["RuntimeExecutionReceipt"]:
        """Get a recorded execution receipt."""
        return self._execution_receipts.get(receipt_id)
    
    def record_benchmark(self, benchmark: "RuntimeBenchmark") -> str:
        """Record a runtime benchmark.
        
        Returns the benchmark_id.
        """
        self._benchmarks[benchmark.benchmark_id] = benchmark
        return benchmark.benchmark_id
    
    def get_benchmark(self, benchmark_id: str) -> Optional["RuntimeBenchmark"]:
        """Get a recorded benchmark."""
        return self._benchmarks.get(benchmark_id)
    
    def list_benchmarks(
        self,
        provider_id: Optional[str] = None,
        kind: Optional["RuntimeBenchmarkKind"] = None,
    ) -> List["RuntimeBenchmark"]:
        """List benchmarks with optional filters."""
        from rig.domain.runtime import RuntimeBenchmarkKind
        
        results = []
        for benchmark in self._benchmarks.values():
            if provider_id and benchmark.provider_id != provider_id:
                continue
            if kind and benchmark.kind != kind:
                continue
            results.append(benchmark)
        return results
    
    def get_provider_benchmarks(self, provider_id: str) -> List["RuntimeBenchmark"]:
        """Get all benchmarks for a specific provider."""
        return [b for b in self._benchmarks.values() if b.provider_id == provider_id]
    
    def get_runtime_state(self) -> "RuntimeState":
        """Get the current runtime state snapshot."""
        from rig.domain.runtime import RuntimeState, RuntimeStateKind
        
        total_inv = len(self._invocations)
        total_pro = len(self._proposals)
        total_receipts = len(self._execution_receipts)
        active_inv = len(self._active_invocations)
        blocked = sum(
            1 for i in self._invocations.values()
            if i.status == RuntimeInvocationStatus.BLOCKED
        )
        failed = sum(
            1 for i in self._invocations.values()
            if i.status == RuntimeInvocationStatus.FAILED
        )
        
        # Determine overall kind
        if active_inv > 0:
            kind = RuntimeStateKind.ACTIVE
        elif blocked > 0:
            kind = RuntimeStateKind.BLOCKED
        else:
            kind = RuntimeStateKind.IDLE
        
        return RuntimeState(
            state_id=f"state_{_utc_now().replace(':', '-').replace('.', '-')}",
            kind=kind,
            active_invocations=frozenset(self._active_invocations),
            active_providers=frozenset(
                i.provider_id for i in self._invocations.values()
            ),
            total_invocations=total_inv,
            total_proposals=total_pro,
            total_execution_receipts=total_receipts,
            overall_status="healthy" if failed == 0 else "degraded",
            blocked_count=blocked,
            failed_count=failed,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        from rig.domain.runtime import RuntimeExecutionReceipt
        
        return {
            "capability_registry": self._capability_registry.to_dict(),
            "invocations": {k: v.to_dict() for k, v in self._invocations.items()},
            "proposals": {k: v.to_dict() for k, v in self._proposals.items()},
            "execution_receipts": {k: v.to_dict() for k, v in self._execution_receipts.items()},
            "benchmarks": {k: v.to_dict() for k, v in self._benchmarks.items()},
            "runtime_state": self.get_runtime_state().to_dict(),
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


# =============================================================================
# Module-level Default Registry
# =============================================================================

_default_capability_registry: Optional[CapabilityRegistry] = None
_default_runtime_registry: Optional[RuntimeRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    """Get the default capability registry."""
    global _default_capability_registry
    if _default_capability_registry is None:
        _default_capability_registry = CapabilityRegistry.create_default()
    return _default_capability_registry


def get_runtime_registry(repo_root: Optional[Path] = None) -> RuntimeRegistry:
    """Get or create the default runtime registry.
    
    Args:
        repo_root: Repository root path (used for persistence in future).
        
    Note: Currently returns a new registry each time. For production use,
    you should create and manage your own RuntimeRegistry instance.
    """
    global _default_runtime_registry
    if _default_runtime_registry is None:
        _default_runtime_registry = RuntimeRegistry()
    return _default_runtime_registry


def reset_default_registries() -> None:
    """Reset the default registries. Useful for testing."""
    global _default_capability_registry, _default_runtime_registry
    _default_capability_registry = None
    _default_runtime_registry = None


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Functions
    "get_capability_registry",
    "get_runtime_registry",
    "reset_default_registries",
    # Classes
    "CapabilityRegistry",
    "RuntimeRegistry",
]
