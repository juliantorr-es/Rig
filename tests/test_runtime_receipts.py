"""Tests for Runtime Execution Receipts.

This module provides tests for runtime execution receipts and their integration
with the receipt infrastructure (Phase 3).

Core doctrine validated:
- Receipts are replay-compatible
- Receipts are integrity-compatible
- Receipts are projection-compatible
- Receipts are audit-compatible
- Receipts NEVER indicate direct authority mutation
- Receipts are always advisory only

file: tests/test_runtime_receipts.py
"""

from __future__ import annotations

import json
import pytest
from typing import Any

from rig.domain.runtime import (
    RuntimeProvider,
    RuntimeCapability,
    RuntimeCapabilityKind,
    RuntimeInvocation,
    RuntimeProposal,
    RuntimeExecutionReceipt,
    RuntimeBenchmark,
    RuntimeDecision,
    RuntimeState,
    RuntimeProviderTrustTier,
    RuntimeInvocationStatus,
    RuntimeProposalStatus,
    RuntimeProposalDecision,
)
from rig.domain.runtime_registry import (
    CapabilityRegistry,
    RuntimeRegistry,
    get_runtime_registry,
    reset_default_registries,
)
from rig.domain.receipts import ExecutionReceipt as LegacyExecutionReceipt


# =============================================================================
# RuntimeExecutionReceipt Integration Tests
# ==============================================================================

class TestRuntimeExecutionReceiptIntegration:
    """Test RuntimeExecutionReceipt integration with receipt infrastructure."""

    def test_receipt_kind_distinction(self):
        """Runtime execution receipts have distinct kind."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        
        assert receipt.kind == "runtime_execution"
        # Legacy execution receipts have different kind
        # (They have kind="execution" in the legacy module)

    def test_receipt_includes_provider_metadata(self):
        """Runtime receipts include provider metadata."""
        invocation = RuntimeInvocation.create(
            provider_id="dry_run",
            model_id="dry-run-model",
            request={},
        )
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        
        assert receipt.provider_id == "dry_run"
        assert receipt.model_id == "dry-run-model"

    def test_receipt_includes_capability_metadata(self):
        """Runtime receipts include capability metadata."""
        capability = RuntimeCapability.file_read()
        invocation = RuntimeInvocation.create(
            provider_id="test",
            model_id="test",
            request={},
            capability_ids=frozenset([capability.capability_id]),
        )
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        
        assert capability.capability_id in receipt.capability_ids

    def test_receipt_includes_proposal_metadata(self):
        """Runtime receipts include proposal metadata."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal1 = RuntimeProposal.from_invocation(invocation, "test1", {})
        proposal2 = RuntimeProposal.from_invocation(invocation, "test2", {})
        
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            proposal_ids=frozenset([proposal1.proposal_id, proposal2.proposal_id]),
        )
        
        assert proposal1.proposal_id in receipt.proposal_ids
        assert proposal2.proposal_id in receipt.proposal_ids
        assert receipt.proposal_count == 2

    def test_receipt_includes_token_metadata(self):
        """Runtime receipts include token usage metadata."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            token_metadata={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        )
        
        assert receipt.prompt_tokens == 100
        assert receipt.completion_tokens == 50
        assert receipt.total_tokens == 150

    def test_receipt_includes_duration(self):
        """Runtime receipts include execution duration."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            duration_seconds=2.5,
        )
        
        assert receipt.duration_seconds == 2.5

    def test_receipt_never_authoritative(self):
        """Runtime receipts are NEVER authoritative."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        
        assert receipt.authoritative is False
        assert receipt.advisory_only is True

    def test_receipt_includes_integrity_fields(self):
        """Runtime receipts include integrity flags."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            integrity_flags=frozenset(["replay_compatible", "deterministic"]),
        )
        
        assert "replay_compatible" in receipt.integrity_flags
        assert "deterministic" in receipt.integrity_flags

    def test_receipt_has_replay_refs(self):
        """Runtime receipts have replay reference list."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            replay_refs=["ref1", "ref2"],
        )
        
        assert len(receipt.replay_refs) == 2
        assert "ref1" in receipt.replay_refs
        assert "ref2" in receipt.replay_refs

    def test_receipt_has_parent_receipt_ids(self):
        """Runtime receipts have parent receipt IDs."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            parent_receipt_ids=["parent1", "parent2"],
        )
        
        assert len(receipt.parent_receipt_ids) == 2


# ==============================================================================
# Replay Compatibility Tests
# ==============================================================================

class TestReplayCompatibility:
    """Test that runtime receipts are replay-compatible."""

    def test_receipt_is_deterministic(self):
        """Same invocation produces same receipt."""
        invocation = RuntimeInvocation.create(
            provider_id="test",
            model_id="test",
            request={"deterministic": True},
        )
        
        receipt1 = RuntimeExecutionReceipt.from_invocation(invocation)
        receipt2 = RuntimeExecutionReceipt.from_invocation(invocation)
        
        assert receipt1.receipt_id == receipt2.receipt_id

    def test_receipt_serializes_completely(self):
        """Receipt serializes all necessary data for replay."""
        invocation = RuntimeInvocation.create(
            provider_id="dry_run",
            model_id="model",
            request={"test": "data"},
            workspace_id="ws1",
            actor_id="user1",
        )
        proposal = RuntimeProposal.from_invocation(invocation, "shell", {"argv": ["ls"]})
        
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            proposal_ids=frozenset([proposal.proposal_id]),
            duration_seconds=0.5,
            token_metadata={"prompt_tokens": 10, "completion_tokens": 20},
            replay_refs=["replay_1"],
            integrity_flags=frozenset(["replay_compatible"]),
        )
        
        d = receipt.to_dict()
        
        # All necessary fields for replay should be present
        assert "receipt_id" in d
        assert "kind" in d
        assert "provider_id" in d
        assert "model_id" in d
        assert "invocation_id" in d
        assert "proposal_ids" in d
        assert "proposal_count" in d
        assert "duration_seconds" in d
        assert "prompt_tokens" in d
        assert "completion_tokens" in d
        assert "replay_refs" in d
        assert "integrity_flags" in d

    def test_receipt_roundtrip_preserves_data(self):
        """Receipt serialization roundtrip preserves all data."""
        invocation = RuntimeInvocation.create(
            provider_id="test",
            model_id="test",
            request={"key": "value"},
            workspace_id="ws1",
        )
        
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            proposal_ids=frozenset(["p1", "p2"]),
            duration_seconds=1.0,
            token_metadata={"prompt_tokens": 10, "completion_tokens": 20},
            replay_refs=["r1"],
            parent_receipt_ids=["parent1"],
        )
        
        # Serialize and deserialize
        d = receipt.to_dict()
        restored = RuntimeExecutionReceipt.from_dict(d)
        
        # All fields should match
        assert restored.receipt_id == receipt.receipt_id
        assert restored.provider_id == receipt.provider_id
        assert restored.model_id == receipt.model_id
        assert restored.invocation_id == receipt.invocation_id
        assert restored.proposal_ids == receipt.proposal_ids
        assert restored.proposal_count == receipt.proposal_count
        assert restored.duration_seconds == receipt.duration_seconds
        assert restored.prompt_tokens == receipt.prompt_tokens
        assert restored.replay_refs == receipt.replay_refs


# ==============================================================================
# Registry Receipt Integration Tests
# ==============================================================================

class TestRegistryReceiptIntegration:
    """Test runtime registry integration with receipts."""

    def setup_method(self):
        """Reset registries before each test."""
        reset_default_registries()

    def test_registry_records_receipts(self):
        """RuntimeRegistry records execution receipts."""
        registry = RuntimeRegistry()
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        
        receipt_id = registry.record_execution_receipt(receipt)
        assert receipt_id == receipt.receipt_id
        
        retrieved = registry.get_execution_receipt(receipt_id)
        assert retrieved is not None
        assert retrieved.receipt_id == receipt_id

    def test_registry_state_reflects_receipts(self):
        """Runtime state reflects recorded receipts."""
        registry = RuntimeRegistry()
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        
        registry.record_execution_receipt(receipt)
        
        state = registry.get_runtime_state()
        assert state.total_execution_receipts >= 1

    def test_registry_to_dict_includes_receipts(self):
        """Registry to_dict includes receipts."""
        registry = RuntimeRegistry()
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        registry.record_execution_receipt(receipt)
        
        d = registry.to_dict()
        assert "execution_receipts" in d
        assert len(d["execution_receipts"]) >= 1

    def test_registry_json_includes_receipts(self):
        """Registry JSON serialization includes receipts."""
        registry = RuntimeRegistry()
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        registry.record_execution_receipt(receipt)
        
        json_str = registry.to_json()
        parsed = json.loads(json_str)
        assert "execution_receipts" in parsed


# ==============================================================================
# Benchmark Receipt Tests
# ==============================================================================

class TestBenchmarkReceipts:
    """Test benchmark receipts."""

    def test_benchmark_is_deterministic(self):
        """Benchmark IDs are deterministic."""
        bm1 = RuntimeBenchmark.latency("p1", "m1", 1.0)
        bm2 = RuntimeBenchmark.latency("p1", "m1", 1.0)
        assert bm1.benchmark_id == bm2.benchmark_id

    def test_benchmark_serializes_completely(self):
        """Benchmark serializes all necessary data."""
        benchmark = RuntimeBenchmark.latency("p1", "m1", 1.5)
        d = benchmark.to_dict()
        
        assert "benchmark_id" in d
        assert "provider_id" in d
        assert "model_id" in d
        assert "kind" in d
        assert "value" in d
        assert "unit" in d
        assert "recorded_at" in d

    def test_benchmark_roundtrip(self):
        """Benchmark serialization roundtrip preserves data."""
        benchmark = RuntimeBenchmark.timeout_maximum("p1", "m1", 10.0)
        
        d = benchmark.to_dict()
        restored = RuntimeBenchmark.from_dict(d)
        
        assert restored.benchmark_id == benchmark.benchmark_id
        assert restored.provider_id == benchmark.provider_id
        assert restored.value == benchmark.value
        assert restored.unit == benchmark.unit


# ==============================================================================
# Authority Boundary Tests
# ==============================================================================

class TestAuthorityBoundaries:
    """Test that authority boundaries are explicit and maintained."""

    def test_all_domain_models_are_advisory_only(self):
        """All runtime domain models are advisory only."""
        # Providers
        provider = RuntimeProvider.dry_run()
        assert provider.advisory_only is True
        assert provider.authoritative is False
        
        # Capabilities
        cap = RuntimeCapability.file_read()
        assert cap.advisory_only is True
        
        # Invocations
        inv = RuntimeInvocation.create("test", "test", {})
        assert inv.advisory_only is True
        
        # Proposals
        prop = RuntimeProposal.from_invocation(inv, "test", {})
        assert prop.advisory_only is True
        assert prop.authoritative is False
        
        # Receipts
        receipt = RuntimeExecutionReceipt.from_invocation(inv)
        assert receipt.advisory_only is True
        assert receipt.authoritative is False

    def test_receipts_explicitly_deny_authority(self):
        """Receipts explicitly state they are not authoritative."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        
        # Both direct attributes and serialized form
        assert receipt.authoritative is False
        assert receipt.advisory_only is True
        
        d = receipt.to_dict()
        assert d["authoritative"] is False
        assert d["advisory_only"] is True

    def test_proposals_explicitly_deny_authority(self):
        """Proposals explicitly state they are not authoritative."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.from_invocation(invocation, "test", {})
        
        assert proposal.authoritative is False
        assert proposal.advisory_only is True
        
        d = proposal.to_dict()
        assert d["authoritative"] is False
        assert d["advisory_only"] is True


# ==============================================================================
# Projection Compatibility Tests
# ==============================================================================

class TestProjectionCompatibility:
    """Test that runtime receipts are projection-compatible."""

    def test_receipt_has_json_serializable_dict(self):
        """Receipt to_dict produces JSON-serializable output."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            proposal_ids=frozenset(["p1"]),
            token_metadata={"prompt_tokens": 10},
        )
        
        d = receipt.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_receipt_dict_has_consistent_structure(self):
        """Receipt dict has consistent, predictable structure."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        d = receipt.to_dict()
        
        # Known keys should always be present
        expected_keys = [
            "receipt_id", "kind", "provider_id", "model_id",
            "capability_ids", "invocation_id", "proposal_ids",
            "status", "advisory_only", "authoritative", "timestamp",
        ]
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"

    def test_receipt_fields_are_predictable_types(self):
        """Receipt fields are predictable types for projection."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        d = receipt.to_dict()
        
        # Check types
        assert isinstance(d["receipt_id"], str)
        assert isinstance(d["kind"], str)
        assert isinstance(d["provider_id"], str)
        assert isinstance(d["advisory_only"], bool)
        assert isinstance(d["authoritative"], bool)
        assert isinstance(d["capability_ids"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
