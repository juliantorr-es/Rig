"""Tests for Runtime Registry.

This module provides tests for the runtime capability registry and runtime registry
introduced in Phase 2 of the Runtime & Agent Execution Plane.

Core doctrine validated:
- Capabilities DO NOT execute authority directly.
- They authorize proposal generation only.
- All capability checks are deterministic and replay-safe.
- All models are JSON-serializable.
- No ambient mutation.

file: tests/test_runtime_registry.py
"""

from __future__ import annotations

import json
import pytest
from typing import Any

from rig.domain.runtime import (
    RuntimeProvider,
    RuntimeCapability,
    RuntimeCapabilityKind,
    RuntimeCapabilityScope,
    RuntimeConstraint,
    RuntimeConstraintKind,
    RuntimeConstraintMode,
    RuntimeProviderKind,
    RuntimeProviderTrustTier,
    RuntimeProviderStatus,
)
from rig.domain.runtime_registry import (
    CapabilityRegistry,
    RuntimeRegistry,
    get_capability_registry,
    get_runtime_registry,
    reset_default_registries,
)


# =============================================================================
# CapabilityRegistry Tests
# =============================================================================

class TestCapabilityRegistry:
    """Test CapabilityRegistry."""

    def setup_method(self):
        """Reset registries before each test."""
        reset_default_registries()

    def test_create_empty(self):
        """Create empty capability registry."""
        registry = CapabilityRegistry.create_empty()
        assert len(registry.capabilities) == 0
        assert len(registry.constraints) == 0
        assert len(registry.providers) == 0

    def test_create_default(self):
        """Create default capability registry with built-in items."""
        registry = CapabilityRegistry.create_default()
        
        # Should have built-in capabilities
        assert len(registry.capabilities) > 0
        
        # Should have built-in constraints
        assert len(registry.constraints) > 0
        
        # Should have built-in providers
        assert len(registry.providers) > 0

    def test_default_has_file_read_capability(self):
        """Default registry has file read capability."""
        registry = CapabilityRegistry.create_default()
        
        caps = registry.get_capabilities_by_kind(RuntimeCapabilityKind.FILE_READ)
        assert len(caps) > 0

    def test_default_has_dry_run_provider(self):
        """Default registry has dry-run provider."""
        registry = CapabilityRegistry.create_default()
        
        provider = registry.get_provider("dry_run")
        assert provider is not None
        assert provider.provider_id == "dry_run"

    def test_default_has_custom_command_provider(self):
        """Default registry has custom command provider."""
        registry = CapabilityRegistry.create_default()
        
        provider = registry.get_provider("custom-command")
        assert provider is not None
        assert provider.provider_id == "custom-command"

    def test_get_capability(self):
        """Get capability by ID."""
        registry = CapabilityRegistry.create_default()
        
        # Get first capability
        all_caps = list(registry.capabilities.values())
        if all_caps:
            cap = registry.get_capability(all_caps[0].capability_id)
            assert cap is not None
            assert cap.capability_id == all_caps[0].capability_id

    def test_get_capability_not_found(self):
        """Get non-existent capability returns None."""
        registry = CapabilityRegistry.create_default()
        assert registry.get_capability("nonexistent") is None

    def test_get_capabilities_by_kind(self):
        """Get capabilities by kind."""
        registry = CapabilityRegistry.create_default()
        
        file_read_caps = registry.get_capabilities_by_kind(
            RuntimeCapabilityKind.FILE_READ
        )
        assert len(file_read_caps) > 0
        for cap in file_read_caps:
            assert cap.kind == RuntimeCapabilityKind.FILE_READ

    def test_get_capabilities_for_workspace(self):
        """Get capabilities for workspace."""
        registry = CapabilityRegistry.create_default()
        
        # Get global capabilities (workspace_id=None)
        global_caps = registry.get_capabilities_for_workspace(None)
        assert len(global_caps) > 0

    def test_get_provider_capabilities(self):
        """Get provider capabilities."""
        registry = CapabilityRegistry.create_default()
        
        caps = registry.get_provider_capabilities("dry_run")
        assert isinstance(caps, frozenset)
        assert len(caps) > 0

    def test_has_capability(self):
        """Check if provider has capability."""
        registry = CapabilityRegistry.create_default()
        
        # dry_run should have some capabilities
        assert registry.has_capability("dry_run", list(registry.capabilities.keys())[0])

    def test_validate_capability_success(self):
        """Validate capability successfully."""
        registry = CapabilityRegistry.create_default()
        
        # Use file_read capability which should work with dry_run provider
        # dry_run has ADVISORY trust tier, file_read doesn't require high trust
        provider_id = "dry_run"
        cap = RuntimeCapability.file_read()
        cap_id = cap.capability_id
        
        validated, errors = registry.validate_capability(
            provider_id, cap_id
        )
        # Should validate successfully
        assert validated or len(errors) == 0

    def test_validate_capability_unknown_provider(self):
        """Validate with unknown provider fails."""
        registry = CapabilityRegistry.create_default()
        
        validated, errors = registry.validate_capability(
            "unknown-provider", "some-capability"
        )
        assert validated is False
        assert len(errors) > 0
        assert any("unknown-provider" in e.lower() for e in errors)

    def test_validate_capability_unknown_capability(self):
        """Validate with unknown capability fails."""
        registry = CapabilityRegistry.create_default()
        
        validated, errors = registry.validate_capability(
            "dry_run", "unknown-capability"
        )
        assert validated is False
        assert len(errors) > 0

    def test_check_trust_tier(self):
        """Check provider trust tier."""
        registry = CapabilityRegistry.create_default()
        
        # dry_run has ADVISORY tier
        meets, reason = registry.check_trust_tier(
            "dry_run", RuntimeProviderTrustTier.ADVISORY
        )
        assert meets is True
        
        # dry_run should not meet PLANNER tier
        meets, reason = registry.check_trust_tier(
            "dry_run", RuntimeProviderTrustTier.PLANNER
        )
        assert meets is False

    def test_constraints_loaded(self):
        """Default registry has constraints loaded."""
        registry = CapabilityRegistry.create_default()
        
        # Should have no-network constraint
        no_network = next(
            (c for c in registry.constraints.values()
             if c.kind == RuntimeConstraintKind.NETWORK),
            None
        )
        assert no_network is not None
        assert no_network.mode == RuntimeConstraintMode.PROHIBITED

    def test_constraints_by_workspace(self):
        """Get constraints for workspace."""
        registry = CapabilityRegistry.create_default()
        
        global_constraints = registry.get_constraints_for_workspace(None)
        assert len(global_constraints) > 0

    def test_to_dict(self):
        """Serialize registry to dictionary."""
        registry = CapabilityRegistry.create_default()
        d = registry.to_dict()
        
        assert "registry_id" in d
        assert "capabilities" in d
        assert "constraints" in d
        assert "providers" in d

    def test_to_json(self):
        """Serialize registry to JSON."""
        registry = CapabilityRegistry.create_default()
        json_str = registry.to_json()
        
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert "capabilities" in parsed

    def test_from_dict(self):
        """Deserialize registry from dictionary."""
        original = CapabilityRegistry.create_default()
        d = original.to_dict()
        
        restored = CapabilityRegistry.from_dict(d)
        
        # Check that capabilities were restored
        assert len(restored.capabilities) == len(original.capabilities)
        assert len(restored.constraints) == len(original.constraints)
        assert len(restored.providers) == len(original.providers)

    def test_serialization_roundtrip(self):
        """Serialization roundtrip preserves data."""
        original = CapabilityRegistry.create_default()
        json_str = original.to_json()
        parsed = json.loads(json_str)
        restored = CapabilityRegistry.from_dict(parsed)
        
        # All IDs should match
        assert set(restored.capabilities.keys()) == set(original.capabilities.keys())
        assert set(restored.constraints.keys()) == set(original.constraints.keys())
        assert set(restored.providers.keys()) == set(original.providers.keys())


# =============================================================================
# RuntimeRegistry Tests
# =============================================================================

class TestRuntimeRegistry:
    """Test RuntimeRegistry."""

    def setup_method(self):
        """Reset registries before each test."""
        reset_default_registries()

    def test_initial_state(self):
        """RuntimeRegistry starts with empty state."""
        registry = RuntimeRegistry()
        state = registry.get_runtime_state()
        
        assert state.total_invocations == 0
        assert state.total_proposals == 0
        assert state.total_execution_receipts == 0

    def test_record_invocation(self):
        """Record an invocation."""
        registry = RuntimeRegistry()
        from rig.domain.runtime import RuntimeInvocation
        
        invocation = RuntimeInvocation.create(
            provider_id="test",
            model_id="test",
            request={},
        )
        
        invocation_id = registry.record_invocation(invocation)
        assert invocation_id == invocation.invocation_id
        
        retrieved = registry.get_invocation(invocation_id)
        assert retrieved is not None
        assert retrieved.invocation_id == invocation_id

    def test_get_invocation_not_found(self):
        """Get non-existent invocation returns None."""
        registry = RuntimeRegistry()
        assert registry.get_invocation("nonexistent") is None

    def test_record_proposal(self):
        """Record a proposal."""
        registry = RuntimeRegistry()
        from rig.domain.runtime import RuntimeInvocation, RuntimeProposal
        
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.from_invocation(invocation, "test", {})
        
        proposal_id = registry.record_proposal(proposal)
        assert proposal_id == proposal.proposal_id
        
        retrieved = registry.get_proposal(proposal_id)
        assert retrieved is not None
        assert retrieved.proposal_id == proposal_id

    def test_record_execution_receipt(self):
        """Record an execution receipt."""
        registry = RuntimeRegistry()
        from rig.domain.runtime import RuntimeInvocation, RuntimeExecutionReceipt
        
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        
        receipt_id = registry.record_execution_receipt(receipt)
        assert receipt_id == receipt.receipt_id
        
        retrieved = registry.get_execution_receipt(receipt_id)
        assert retrieved is not None
        assert retrieved.receipt_id == receipt_id

    def test_record_benchmark(self):
        """Record a benchmark."""
        registry = RuntimeRegistry()
        from rig.domain.runtime import RuntimeBenchmark
        
        benchmark = RuntimeBenchmark.latency("test", "test", 1.0)
        benchmark_id = registry.record_benchmark(benchmark)
        assert benchmark_id == benchmark.benchmark_id
        
        retrieved = registry.get_benchmark(benchmark_id)
        assert retrieved is not None
        assert retrieved.benchmark_id == benchmark_id

    def test_list_benchmarks(self):
        """List benchmarks with filters."""
        registry = RuntimeRegistry()
        from rig.domain.runtime import RuntimeBenchmark, RuntimeBenchmarkKind
        
        # Record some benchmarks
        bm1 = RuntimeBenchmark.latency("provider1", "model1", 1.0)
        bm2 = RuntimeBenchmark.token_throughput("provider1", "model1", 50.0)
        bm3 = RuntimeBenchmark.latency("provider2", "model2", 2.0)
        
        registry.record_benchmark(bm1)
        registry.record_benchmark(bm2)
        registry.record_benchmark(bm3)
        
        # List all
        all_bench = registry.list_benchmarks()
        assert len(all_bench) == 3
        
        # Filter by provider
        provider1_bench = registry.list_benchmarks(provider_id="provider1")
        assert len(provider1_bench) == 2
        
        # Filter by kind
        latency_bench = registry.list_benchmarks(kind=RuntimeBenchmarkKind.LATENCY)
        assert len(latency_bench) == 2

    def test_get_provider_benchmarks(self):
        """Get benchmarks for a specific provider."""
        registry = RuntimeRegistry()
        from rig.domain.runtime import RuntimeBenchmark
        
        bm1 = RuntimeBenchmark.latency("provider1", "model1", 1.0)
        bm2 = RuntimeBenchmark.latency("provider2", "model2", 2.0)
        
        registry.record_benchmark(bm1)
        registry.record_benchmark(bm2)
        
        provider1_bench = registry.get_provider_benchmarks("provider1")
        assert len(provider1_bench) == 1
        assert provider1_bench[0].provider_id == "provider1"

    def test_state_updates_on_record(self):
        """Runtime state updates when recording items."""
        registry = RuntimeRegistry()
        from rig.domain.runtime import RuntimeInvocation, RuntimeProposal, RuntimeExecutionReceipt
        
        # Record some items
        invocation = RuntimeInvocation.create("test", "test", {})
        registry.record_invocation(invocation)
        
        proposal = RuntimeProposal.from_invocation(invocation, "test", {})
        registry.record_proposal(proposal)
        
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        registry.record_execution_receipt(receipt)
        
        state = registry.get_runtime_state()
        assert state.total_invocations >= 1
        assert state.total_proposals >= 1
        assert state.total_execution_receipts >= 1

    def test_to_dict(self):
        """Serialize runtime registry to dictionary."""
        registry = RuntimeRegistry()
        d = registry.to_dict()
        
        assert "capability_registry" in d
        assert "invocations" in d
        assert "proposals" in d
        assert "execution_receipts" in d
        assert "benchmarks" in d
        assert "runtime_state" in d

    def test_to_json(self):
        """Serialize runtime registry to JSON."""
        registry = RuntimeRegistry()
        json_str = registry.to_json()
        
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert "invocations" in parsed

    def test_capability_registry_access(self):
        """Access backing capability registry."""
        registry = RuntimeRegistry()
        cap_registry = registry.capability_registry
        
        assert isinstance(cap_registry, CapabilityRegistry)
        assert len(cap_registry.capabilities) > 0


# =============================================================================
# Default Registry Tests
# =============================================================================

class TestDefaultRegistries:
    """Test module-level default registries."""

    def setup_method(self):
        """Reset registries before each test."""
        reset_default_registries()

    def test_get_capability_registry(self):
        """Get default capability registry."""
        registry = get_capability_registry()
        assert isinstance(registry, CapabilityRegistry)
        assert len(registry.capabilities) > 0

    def test_get_runtime_registry(self):
        """Get default runtime registry."""
        registry = get_runtime_registry()
        assert isinstance(registry, RuntimeRegistry)

    def test_reset_default_registries(self):
        """Reset clears default registries."""
        registry1 = get_capability_registry()
        reset_default_registries()
        registry2 = get_capability_registry()
        
        # Should get a fresh registry
        assert registry1.registry_id != registry2.registry_id


# =============================================================================
# Constraint Enforcement Tests
# =============================================================================

class TestConstraintEnforcement:
    """Test constraint enforcement logic."""

    def test_no_network_constraint_blocks_proposals(self):
        """No network constraint blocks network fetch proposals."""
        registry = CapabilityRegistry.create_default()
        
        # Find the no-network constraint
        no_network = next(
            (c for c in registry.constraints.values()
             if c.kind == RuntimeConstraintKind.NETWORK),
            None
        )
        assert no_network is not None
        
        # Get network fetch capability
        network_cap = next(
            (c for c in registry.capabilities.values()
             if c.kind == RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL),
            None
        )
        assert network_cap is not None
        
        # Constraint should apply to network capability
        assert no_network.applies_to_capability(network_cap) is True

    def test_filesystem_constraint_blocks_writes(self):
        """No filesystem writes constraint blocks write proposals."""
        registry = CapabilityRegistry.create_default()
        
        # Find the no-filesystem-writes constraint
        no_fs = next(
            (c for c in registry.constraints.values()
             if c.kind == RuntimeConstraintKind.FILESYSTEM),
            None
        )
        assert no_fs is not None
        
        # Get file write capability
        file_write_cap = next(
            (c for c in registry.capabilities.values()
             if c.kind == RuntimeCapabilityKind.FILE_WRITE_PROPOSAL),
            None
        )
        assert file_write_cap is not None
        
        # Constraint should apply to file write capability
        assert no_fs.applies_to_capability(file_write_cap) is True

    def test_validate_constraints_trust_tier(self):
        """Validate trust tier constraints."""
        registry = CapabilityRegistry.create_default()
        
        # Get dry_run provider (ADVISORY tier)
        provider = registry.get_provider("dry_run")
        assert provider is not None
        assert provider.trust_tier == RuntimeProviderTrustTier.ADVISORY
        
        # Find trust tier constraint
        trust_constraint = next(
            (c for c in registry.constraints.values()
             if c.kind == RuntimeConstraintKind.TRUST_TIER),
            None
        )
        
        if trust_constraint:
            # dry_run should not meet PLANNER requirement
            file_write_cap = next(
                (c for c in registry.capabilities.values()
                 if c.kind == RuntimeCapabilityKind.FILE_WRITE_PROPOSAL),
                None
            )
            
            if file_write_cap:
                errors = registry.validate_constraints(
                    "dry_run", file_write_cap
                )
                # Should have at least one error for trust tier
                assert any("tier" in e.lower() for e in errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
