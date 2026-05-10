"""Tests for Runtime Domain Models.

This module provides comprehensive tests for the runtime domain models
introduced in Phase 1 of the Runtime & Agent Execution Plane.

Core doctrine validated:
- Models propose; Rig governs.
- Runtimes are advisory execution providers, not authorities.
- All models are frozen dataclasses where appropriate.
- All models are deterministic serialization.
- All models are replay-safe.
- All models are projection-safe.
- Explicit authority classification.
- NO direct authority mutation from runtimes.

file: tests/test_runtime.py
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime
from pathlib import Path
from typing import Any, FrozenSet

from rig.domain.runtime import (
    # Placeholders
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_UNAVAILABLE,
    PLACEHOLDER_NOT_CREATED,
    PLACEHOLDER_NOT_RUN,
    PLACEHOLDER_NOT_PROOF,
    PLACEHOLDER_ADVISORY_ONLY,
    PLACEHOLDER_NOT_AUTHORITATIVE,
    PLACEHOLDER_NO_RECEIPT,
    PLACEHOLDER_NO_CAPABILITY,
    PLACEHOLDER_NO_PROVIDER,
    REQUIRED_RUNTIME_PLACEHOLDERS,
    # Enums
    RuntimeProviderKind,
    RuntimeProviderTrustTier,
    RuntimeProviderStatus,
    RuntimeCapabilityKind,
    RuntimeCapabilityScope,
    RuntimeInvocationStatus,
    RuntimeProposalStatus,
    RuntimeProposalDecision,
    RuntimeConstraintKind,
    RuntimeConstraintMode,
    RuntimeDecisionKind,
    RuntimeStateKind,
    RuntimeBenchmarkKind,
    RuntimeFailureCategory,
    # Models
    RuntimeProvider,
    RuntimeCapability,
    RuntimeConstraint,
    RuntimeInvocation,
    RuntimeProposal,
    RuntimeExecutionReceipt,
    RuntimeDecision,
    RuntimeBenchmark,
    RuntimeState,
)


# =============================================================================
# Placeholder Constant Tests
# =============================================================================

class TestPlaceholderConstants:
    """Test placeholder constant definitions."""

    def test_all_required_placeholders_defined(self):
        """All required runtime placeholders are defined."""
        for placeholder in REQUIRED_RUNTIME_PLACEHOLDERS:
            assert isinstance(placeholder, str)
            assert len(placeholder) > 0

    def test_placeholder_unique(self):
        """Placeholder constants are unique."""
        assert len(set(REQUIRED_RUNTIME_PLACEHOLDERS)) == len(REQUIRED_RUNTIME_PLACEHOLDERS)

    def test_placeholder_values_match(self):
        """Placeholder values match expected strings."""
        assert PLACEHOLDER_UNKNOWN == "unknown"
        assert PLACEHOLDER_ADVISORY_ONLY == "advisory_only"
        assert PLACEHOLDER_NOT_AUTHORITATIVE == "not_authoritative"
        assert PLACEHOLDER_NO_RECEIPT == "no_receipt"
        assert PLACEHOLDER_NO_PROVIDER == "no_provider"


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Test enum definitions."""

    def test_provider_kind_values(self):
        """RuntimeProviderKind has expected values."""
        assert RuntimeProviderKind.LOCAL.value == "local"
        assert RuntimeProviderKind.CLI.value == "cli"
        assert RuntimeProviderKind.CUSTOM.value == "custom"
        assert RuntimeProviderKind.DRY_RUN.value == "dry_run"
        assert RuntimeProviderKind.STUB.value == "stub"

    def test_provider_trust_tier_order(self):
        """RuntimeProviderTrustTier has correct ordering."""
        tiers = list(RuntimeProviderTrustTier)
        assert len(tiers) >= 6
        # Verify BLOCKED is lowest
        assert tiers[0] == RuntimeProviderTrustTier.BLOCKED
        # Verify VALIDATOR is highest
        assert tiers[-1] == RuntimeProviderTrustTier.VALIDATOR

    def test_provider_status_values(self):
        """RuntimeProviderStatus has expected values."""
        assert RuntimeProviderStatus.AVAILABLE.value == "available"
        assert RuntimeProviderStatus.UNAVAILABLE.value == "unavailable"
        assert RuntimeProviderStatus.DEGRADED.value == "degraded"
        assert RuntimeProviderStatus.BLOCKED.value == "blocked"
        assert RuntimeProviderStatus.ERROR.value == "error"

    def test_capability_kind_values(self):
        """RuntimeCapabilityKind has expected values."""
        assert RuntimeCapabilityKind.FILE_READ.value == "file_read"
        assert RuntimeCapabilityKind.FILE_WRITE_PROPOSAL.value == "file_write_proposal"
        assert RuntimeCapabilityKind.SHELL_PROPOSAL.value == "shell_proposal"
        assert RuntimeCapabilityKind.PATCH_PROPOSAL.value == "patch_proposal"
        assert RuntimeCapabilityKind.REPLAY_ACCESS.value == "replay_access"
        assert RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL.value == "network_fetch_proposal"
        assert RuntimeCapabilityKind.DOCS_FETCH_PROPOSAL.value == "docs_fetch_proposal"
        assert RuntimeCapabilityKind.TELEMETRY_EXPORT_PROPOSAL.value == "telemetry_export_proposal"

    def test_capability_scope_values(self):
        """RuntimeCapabilityScope has expected values."""
        assert RuntimeCapabilityScope.GLOBAL.value == "global"
        assert RuntimeCapabilityScope.WORKSPACE.value == "workspace"
        assert RuntimeCapabilityScope.SESSION.value == "session"
        assert RuntimeCapabilityScope.REQUEST.value == "request"

    def test_invocation_status_values(self):
        """RuntimeInvocationStatus has expected values."""
        assert RuntimeInvocationStatus.PENDING.value == "pending"
        assert RuntimeInvocationStatus.STARTING.value == "starting"
        assert RuntimeInvocationStatus.RUNNING.value == "running"
        assert RuntimeInvocationStatus.SUCCEEDED.value == "succeeded"
        assert RuntimeInvocationStatus.FAILED.value == "failed"
        assert RuntimeInvocationStatus.TIMED_OUT.value == "timed_out"
        assert RuntimeInvocationStatus.CANCELLED.value == "cancelled"
        assert RuntimeInvocationStatus.BLOCKED.value == "blocked"

    def test_proposal_status_values(self):
        """RuntimeProposalStatus has expected values."""
        assert RuntimeProposalStatus.DRAFT.value == "draft"
        assert RuntimeProposalStatus.SUBMITTED.value == "submitted"
        assert RuntimeProposalStatus.VALIDATED.value == "validated"
        assert RuntimeProposalStatus.REJECTED.value == "rejected"
        assert RuntimeProposalStatus.BLOCKED.value == "blocked"
        assert RuntimeProposalStatus.EXPIRED.value == "expired"

    def test_proposal_decision_values(self):
        """RuntimeProposalDecision has expected values."""
        assert RuntimeProposalDecision.ALLOW.value == "allow"
        assert RuntimeProposalDecision.DENY.value == "deny"
        assert RuntimeProposalDecision.REVIEW.value == "review"
        assert RuntimeProposalDecision.PENDING.value == "pending"
        assert RuntimeProposalDecision.ADVISORY.value == "advisory"

    def test_constraint_kind_values(self):
        """RuntimeConstraintKind has expected values."""
        assert RuntimeConstraintKind.TRUST_TIER.value == "trust_tier"
        assert RuntimeConstraintKind.CAPABILITY.value == "capability"
        assert RuntimeConstraintKind.WORKSPACE.value == "workspace"
        assert RuntimeConstraintKind.TIMEOUT.value == "timeout"
        assert RuntimeConstraintKind.MEMORY.value == "memory"
        assert RuntimeConstraintKind.CPU.value == "cpu"
        assert RuntimeConstraintKind.NETWORK.value == "network"
        assert RuntimeConstraintKind.FILESYSTEM.value == "filesystem"

    def test_constraint_mode_values(self):
        """RuntimeConstraintMode has expected values."""
        assert RuntimeConstraintMode.REQUIRED.value == "required"
        assert RuntimeConstraintMode.OPTIONAL.value == "optional"
        assert RuntimeConstraintMode.PROHIBITED.value == "prohibited"

    def test_decision_kind_values(self):
        """RuntimeDecisionKind has expected values."""
        assert RuntimeDecisionKind.CAPABILITY_CHECK.value == "capability_check"
        assert RuntimeDecisionKind.TRUST_VALIDATION.value == "trust_validation"
        assert RuntimeDecisionKind.CONSTRAINT_ENFORCEMENT.value == "constraint_enforcement"
        assert RuntimeDecisionKind.PROPOSAL_APPROVAL.value == "proposal_approval"
        assert RuntimeDecisionKind.EXECUTION_AUTHORIZATION.value == "execution_authorization"

    def test_benchmark_kind_values(self):
        """RuntimeBenchmarkKind has expected values."""
        assert RuntimeBenchmarkKind.LATENCY.value == "latency"
        assert RuntimeBenchmarkKind.TOKEN_THROUGHPUT.value == "token_throughput"
        assert RuntimeBenchmarkKind.PROPOSAL_SUCCESS.value == "proposal_success"
        assert RuntimeBenchmarkKind.VALIDATION_PASS.value == "validation_pass"
        assert RuntimeBenchmarkKind.REPLAY_INTEGRITY.value == "replay_integrity"

    def test_failure_category_values(self):
        """RuntimeFailureCategory has expected values."""
        assert RuntimeFailureCategory.CAPABILITY_MISMATCH.value == "capability_mismatch"
        assert RuntimeFailureCategory.TRUST_VIOLATION.value == "trust_violation"
        assert RuntimeFailureCategory.CONSTRAINT_VIOLATION.value == "constraint_violation"
        assert RuntimeFailureCategory.AUTHORITY_VIOLATION.value == "authority_violation"


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    def test_generate_deterministic_id(self):
        """Deterministic ID generation produces consistent results."""
        from rig.domain.runtime import _generate_deterministic_id
        
        # Same inputs produce same output
        id1 = _generate_deterministic_id("test", "a", "b")
        id2 = _generate_deterministic_id("test", "a", "b")
        assert id1 == id2
        
        # Different inputs produce different output
        id3 = _generate_deterministic_id("test", "a", "c")
        assert id1 != id3
        
        # Starts with prefix
        assert id1.startswith("test_")
        
        # Has consistent length (prefix + 16 hex chars)
        assert len(id1) == 21  # "test_" + 16 = 21


# =============================================================================
# RuntimeProvider Tests
# =============================================================================

class TestRuntimeProvider:
    """Test RuntimeProvider model."""

    def test_frozen_dataclass(self):
        """RuntimeProvider is a frozen dataclass."""
        provider = RuntimeProvider.dry_run()
        with pytest.raises((AttributeError, TypeError)):
            provider.provider_id = "new_id"

    def test_slots(self):
        """RuntimeProvider uses slots."""
        provider = RuntimeProvider.dry_run()
        with pytest.raises((AttributeError, TypeError)):
            provider.nonexistent_attr = "value"

    def test_never_authoritative(self):
        """RuntimeProvider is NEVER authoritative."""
        provider = RuntimeProvider.dry_run()
        assert provider.authoritative is False
        
        # Even when trying to create with authoritative=True
        provider2 = RuntimeProvider(
            provider_id="test",
            authoritative=True,  # Should be overridden
        )
        assert provider2.authoritative is False

    def test_always_advisory_only(self):
        """RuntimeProvider is ALWAYS advisory only."""
        provider = RuntimeProvider.dry_run()
        assert provider.advisory_only is True
        
        provider2 = RuntimeProvider(
            provider_id="test",
            advisory_only=False,  # Should be overridden
        )
        assert provider2.advisory_only is True

    def test_never_allows_file_mutation(self):
        """Rig NEVER allows file mutation from providers."""
        provider = RuntimeProvider(
            provider_id="test",
            rig_allows_file_mutation=True,  # Should be overridden
        )
        assert provider.rig_allows_file_mutation is False

    def test_dry_run_factory(self):
        """Dry-run provider factory creates correct provider."""
        provider = RuntimeProvider.dry_run()
        assert provider.provider_id == "dry_run"
        assert provider.kind == RuntimeProviderKind.DRY_RUN
        assert provider.trust_tier == RuntimeProviderTrustTier.ADVISORY
        assert provider.status == RuntimeProviderStatus.AVAILABLE

    def test_custom_command_factory(self):
        """Custom command provider factory creates correct provider."""
        provider = RuntimeProvider.custom_command()
        assert provider.provider_id == "custom-command"
        assert provider.kind == RuntimeProviderKind.CUSTOM
        assert provider.trust_tier == RuntimeProviderTrustTier.PLANNER

    def test_from_manifest(self):
        """Create provider from manifest dictionary."""
        manifest = {
            "provider_id": "test-provider",
            "kind": "local",
            "trust_tier": "planner",
            "version": "2.0.0",
            "executable": "test-exec",
            "offline_capable": True,
            "supports_streaming": True,
            "supported_tasks": ["test"],
        }
        provider = RuntimeProvider.from_manifest(manifest)
        assert provider.provider_id == "test-provider"
        assert provider.kind == RuntimeProviderKind.LOCAL
        assert provider.trust_tier == RuntimeProviderTrustTier.PLANNER
        assert provider.version == "2.0.0"
        assert provider.executable == "test-exec"
        assert provider.offline_capable is True

    def test_to_dict(self):
        """Provider serialization to dictionary."""
        provider = RuntimeProvider.dry_run()
        d = provider.to_dict()
        
        assert d["provider_id"] == "dry_run"
        assert d["kind"] == "dry_run"
        assert d["trust_tier"] == "advisory"
        assert d["authoritative"] is False
        assert d["advisory_only"] is True

    def test_to_json(self):
        """Provider serialization to JSON."""
        provider = RuntimeProvider.dry_run()
        json_str = provider.to_json()
        
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["provider_id"] == "dry_run"

    def test_from_dict(self):
        """Provider deserialization from dictionary."""
        d = {
            "provider_id": "test-provider",
            "kind": "custom",
            "trust_tier": "reviewer",
            "version": "3.0.0",
            "executable": "test",
        }
        provider = RuntimeProvider.from_dict(d)
        assert provider.provider_id == "test-provider"
        assert provider.kind == RuntimeProviderKind.CUSTOM
        assert provider.trust_tier == RuntimeProviderTrustTier.REVIEWER


# =============================================================================
# RuntimeCapability Tests
# =============================================================================

class TestRuntimeCapability:
    """Test RuntimeCapability model."""

    def test_frozen_dataclass(self):
        """RuntimeCapability is a frozen dataclass."""
        cap = RuntimeCapability.file_read()
        with pytest.raises((AttributeError, TypeError)):
            cap.capability_id = "new_id"

    def test_slots(self):
        """RuntimeCapability uses slots."""
        cap = RuntimeCapability.file_read()
        with pytest.raises((AttributeError, TypeError)):
            cap.nonexistent_attr = "value"

    def test_always_advisory_only(self):
        """Capabilities are always advisory only."""
        cap = RuntimeCapability.file_write_proposal()
        assert cap.advisory_only is True

    def test_file_read_factory(self):
        """File read capability factory."""
        cap = RuntimeCapability.file_read(workspace_id="ws1")
        assert cap.kind == RuntimeCapabilityKind.FILE_READ
        assert cap.workspace_id == "ws1"
        assert cap.scope == RuntimeCapabilityScope.WORKSPACE

    def test_file_write_proposal_factory(self):
        """File write proposal capability factory."""
        cap = RuntimeCapability.file_write_proposal()
        assert cap.kind == RuntimeCapabilityKind.FILE_WRITE_PROPOSAL
        assert cap.requires_validation is True
        assert cap.requires_review is True

    def test_shell_proposal_factory(self):
        """Shell command proposal capability factory."""
        cap = RuntimeCapability.shell_proposal()
        assert cap.kind == RuntimeCapabilityKind.SHELL_PROPOSAL
        assert cap.advisory_only is True

    def test_all_capability_factories(self):
        """All capability factory methods work."""
        factories = [
            RuntimeCapability.file_read,
            RuntimeCapability.file_write_proposal,
            RuntimeCapability.shell_proposal,
            RuntimeCapability.patch_proposal,
            RuntimeCapability.replay_access,
            RuntimeCapability.network_fetch_proposal,
            RuntimeCapability.docs_fetch_proposal,
            RuntimeCapability.telemetry_export_proposal,
        ]
        for factory in factories:
            cap = factory()
            assert cap is not None
            assert isinstance(cap, RuntimeCapability)

    def test_to_dict(self):
        """Capability serialization to dictionary."""
        cap = RuntimeCapability.file_read()
        d = cap.to_dict()
        
        assert "capability_id" in d
        assert "kind" in d
        assert d["kind"] == "file_read"

    def test_from_dict(self):
        """Capability deserialization from dictionary."""
        d = {
            "capability_id": "test-cap",
            "kind": "file_read",
            "scope": "global",
            "description": "Test capability",
        }
        cap = RuntimeCapability.from_dict(d)
        assert cap.capability_id == "test-cap"
        assert cap.kind == RuntimeCapabilityKind.FILE_READ


# =============================================================================
# RuntimeConstraint Tests
# =============================================================================

class TestRuntimeConstraint:
    """Test RuntimeConstraint model."""

    def test_frozen_dataclass(self):
        """RuntimeConstraint is a frozen dataclass."""
        constraint = RuntimeConstraint.no_network()
        with pytest.raises((AttributeError, TypeError)):
            constraint.constraint_id = "new_id"

    def test_slots(self):
        """RuntimeConstraint uses slots."""
        constraint = RuntimeConstraint.no_network()
        with pytest.raises((AttributeError, TypeError)):
            constraint.nonexistent_attr = "value"

    def test_trust_tier_minimum_factory(self):
        """Trust tier minimum constraint factory."""
        constraint = RuntimeConstraint.trust_tier_minimum(
            RuntimeProviderTrustTier.PLANNER
        )
        assert constraint.kind == RuntimeConstraintKind.TRUST_TIER
        assert constraint.value == "planner"
        assert constraint.mode == RuntimeConstraintMode.REQUIRED

    def test_timeout_maximum_factory(self):
        """Timeout maximum constraint factory."""
        constraint = RuntimeConstraint.timeout_maximum(300.0)
        assert constraint.kind == RuntimeConstraintKind.TIMEOUT
        assert constraint.value == 300.0

    def test_no_network_factory(self):
        """No network constraint factory."""
        constraint = RuntimeConstraint.no_network()
        assert constraint.kind == RuntimeConstraintKind.NETWORK
        assert constraint.mode == RuntimeConstraintMode.PROHIBITED
        assert RuntimeCapabilityKind.NETWORK_FETCH_PROPOSAL in constraint.applies_to

    def test_no_filesystem_writes_factory(self):
        """No filesystem writes constraint factory."""
        constraint = RuntimeConstraint.no_filesystem_writes()
        assert constraint.kind == RuntimeConstraintKind.FILESYSTEM
        assert constraint.mode == RuntimeConstraintMode.PROHIBITED

    def test_applies_to_capability(self):
        """Constraint applies_to_capability method."""
        constraint = RuntimeConstraint.no_network()
        
        # Should apply to network fetch capability
        network_cap = RuntimeCapability.network_fetch_proposal()
        assert constraint.applies_to_capability(network_cap) is True
        
        # Should not apply to file read capability
        file_cap = RuntimeCapability.file_read()
        assert constraint.applies_to_capability(file_cap) is False

    def test_to_dict(self):
        """Constraint serialization to dictionary."""
        constraint = RuntimeConstraint.no_network()
        d = constraint.to_dict()
        
        assert "constraint_id" in d
        assert "kind" in d
        assert d["kind"] == "network"

    def test_from_dict(self):
        """Constraint deserialization from dictionary."""
        d = {
            "constraint_id": "test-constraint",
            "kind": "trust_tier",
            "mode": "required",
            "value": "planner",
        }
        constraint = RuntimeConstraint.from_dict(d)
        assert constraint.constraint_id == "test-constraint"
        assert constraint.kind == RuntimeConstraintKind.TRUST_TIER
        assert constraint.mode == RuntimeConstraintMode.REQUIRED


# =============================================================================
# RuntimeInvocation Tests
# =============================================================================

class TestRuntimeInvocation:
    """Test RuntimeInvocation model."""

    def test_frozen_dataclass(self):
        """RuntimeInvocation is a frozen dataclass."""
        invocation = RuntimeInvocation.create(
            provider_id="test-provider",
            model_id="test-model",
            request={"test": "request"},
        )
        with pytest.raises((AttributeError, TypeError)):
            invocation.invocation_id = "new_id"

    def test_slots(self):
        """RuntimeInvocation uses slots."""
        invocation = RuntimeInvocation.create(
            provider_id="test-provider",
            model_id="test-model",
            request={},
        )
        with pytest.raises((AttributeError, TypeError)):
            invocation.nonexistent_attr = "value"

    def test_always_advisory_only(self):
        """Invocations are always advisory only."""
        invocation = RuntimeInvocation.create(
            provider_id="test",
            model_id="test",
            request={},
        )
        assert invocation.advisory_only is True

    def test_create_method(self):
        """Create method generates correct invocation."""
        invocation = RuntimeInvocation.create(
            provider_id="test-provider",
            model_id="test-model",
            request={"task": "test"},
            workspace_id="ws1",
            actor_id="user1",
        )
        assert invocation.provider_id == "test-provider"
        assert invocation.model_id == "test-model"
        assert invocation.request == {"task": "test"}
        assert invocation.workspace_id == "ws1"
        assert invocation.actor_id == "user1"
        assert invocation.status == RuntimeInvocationStatus.STARTING

    def test_invocation_id_deterministic(self):
        """Invocation IDs are deterministic for same inputs."""
        inv1 = RuntimeInvocation.create(
            provider_id="test",
            model_id="test",
            request={"a": 1},
        )
        inv2 = RuntimeInvocation.create(
            provider_id="test",
            model_id="test",
            request={"a": 1},
        )
        assert inv1.invocation_id == inv2.invocation_id

    def test_to_dict(self):
        """Invocation serialization to dictionary."""
        invocation = RuntimeInvocation.create(
            provider_id="test",
            model_id="test",
            request={},
        )
        d = invocation.to_dict()
        
        assert "invocation_id" in d
        assert "provider_id" in d
        assert "model_id" in d
        assert d["provider_id"] == "test"

    def test_from_dict(self):
        """Invocation deserialization from dictionary."""
        import json
        from datetime import datetime, timezone
        
        d = {
            "invocation_id": "test-invocation",
            "provider_id": "test-provider",
            "model_id": "test-model",
            "request": {"test": "value"},
            "status": "succeeded",
            "started_at": "2024-01-01T00:00:00Z",
        }
        invocation = RuntimeInvocation.from_dict(d)
        assert invocation.invocation_id == "test-invocation"
        assert invocation.provider_id == "test-provider"
        assert invocation.status == RuntimeInvocationStatus.SUCCEEDED


# =============================================================================
# RuntimeProposal Tests
# =============================================================================

class TestRuntimeProposal:
    """Test RuntimeProposal model."""

    def test_frozen_dataclass(self):
        """RuntimeProposal is a frozen dataclass."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.from_invocation(
            invocation, "test_kind", {}
        )
        with pytest.raises((AttributeError, TypeError)):
            proposal.proposal_id = "new_id"

    def test_slots(self):
        """RuntimeProposal uses slots."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.from_invocation(invocation, "test", {})
        with pytest.raises((AttributeError, TypeError)):
            proposal.nonexistent_attr = "value"

    def test_always_advisory_only(self):
        """Proposals are always advisory only."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.from_invocation(invocation, "test", {})
        assert proposal.advisory_only is True

    def test_never_authoritative(self):
        """Proposals are never authoritative."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.from_invocation(invocation, "test", {})
        assert proposal.authoritative is False

    def test_from_invocation(self):
        """Create proposal from invocation."""
        invocation = RuntimeInvocation.create(
            provider_id="test-provider",
            model_id="test-model",
            request={},
        )
        proposal = RuntimeProposal.from_invocation(
            invocation=invocation,
            proposal_kind="test",
            payload={"key": "value"},
        )
        assert proposal.invocation_id == invocation.invocation_id
        assert proposal.provider_id == "test-provider"
        assert proposal.model_id == "test-model"
        assert proposal.proposal_kind == "test"
        assert proposal.payload == {"key": "value"}

    def test_file_write_factory(self):
        """File write proposal factory."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.file_write(
            invocation=invocation,
            file_path="/path/to/file",
            content="test content",
        )
        assert proposal.proposal_kind == "file_write"
        assert proposal.payload["file_path"] == "/path/to/file"
        assert proposal.payload["content"] == "test content"

    def test_shell_command_factory(self):
        """Shell command proposal factory."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.shell_command(
            invocation=invocation,
            argv=["ls", "-la"],
            cwd="/test",
        )
        assert proposal.proposal_kind == "shell"
        assert proposal.payload["argv"] == ["ls", "-la"]
        assert proposal.payload["cwd"] == "/test"

    def test_patch_factory(self):
        """Patch proposal factory."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.patch(
            invocation=invocation,
            file_path="/path/to/file",
            diff="test diff",
        )
        assert proposal.proposal_kind == "patch"
        assert proposal.payload["file_path"] == "/path/to/file"
        assert proposal.payload["diff"] == "test diff"

    def test_to_dict(self):
        """Proposal serialization to dictionary."""
        invocation = RuntimeInvocation.create("test", "test", {})
        proposal = RuntimeProposal.from_invocation(invocation, "test", {})
        d = proposal.to_dict()
        
        assert "proposal_id" in d
        assert "invocation_id" in d
        assert "proposal_kind" in d

    def test_from_dict(self):
        """Proposal deserialization from dictionary."""
        d = {
            "proposal_id": "test-proposal",
            "invocation_id": "test-invocation",
            "provider_id": "test-provider",
            "model_id": "test-model",
            "proposal_kind": "test",
            "payload": {"key": "value"},
            "status": "submitted",
        }
        proposal = RuntimeProposal.from_dict(d)
        assert proposal.proposal_id == "test-proposal"
        assert proposal.proposal_kind == "test"
        assert proposal.status == RuntimeProposalStatus.SUBMITTED


# =============================================================================
# RuntimeExecutionReceipt Tests
# =============================================================================

class TestRuntimeExecutionReceipt:
    """Test RuntimeExecutionReceipt model."""

    def test_frozen_dataclass(self):
        """RuntimeExecutionReceipt is a frozen dataclass."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        with pytest.raises((AttributeError, TypeError)):
            receipt.receipt_id = "new_id"

    def test_slots(self):
        """RuntimeExecutionReceipt uses slots."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        with pytest.raises((AttributeError, TypeError)):
            receipt.nonexistent_attr = "value"

    def test_always_advisory_only(self):
        """Execution receipts are always advisory only."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        assert receipt.advisory_only is True

    def test_never_authoritative(self):
        """Execution receipts are never authoritative."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        assert receipt.authoritative is False

    def test_from_invocation(self):
        """Create receipt from invocation."""
        invocation = RuntimeInvocation.create(
            provider_id="test-provider",
            model_id="test-model",
            request={},
            status=RuntimeInvocationStatus.SUCCEEDED,
        )
        receipt = RuntimeExecutionReceipt.from_invocation(
            invocation=invocation,
            duration_seconds=1.5,
            proposal_ids=frozenset(["prop1", "prop2"]),
            token_metadata={"prompt_tokens": 10, "completion_tokens": 20},
        )
        assert receipt.invocation_id == invocation.invocation_id
        assert receipt.provider_id == "test-provider"
        assert receipt.model_id == "test-model"
        assert receipt.proposal_count == 2
        assert receipt.prompt_tokens == 10
        assert receipt.completion_tokens == 20
        assert receipt.total_tokens == 30
        assert receipt.duration_seconds == 1.5

    def test_receipt_id_deterministic(self):
        """Receipt IDs are deterministic for same inputs."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt1 = RuntimeExecutionReceipt.from_invocation(invocation)
        receipt2 = RuntimeExecutionReceipt.from_invocation(invocation)
        assert receipt1.receipt_id == receipt2.receipt_id

    def test_to_dict(self):
        """Receipt serialization to dictionary."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        d = receipt.to_dict()
        
        assert "receipt_id" in d
        assert "kind" in d
        assert d["kind"] == "runtime_execution"
        assert "advisory_only" in d
        assert d["advisory_only"] is True

    def test_to_json(self):
        """Receipt serialization to JSON."""
        invocation = RuntimeInvocation.create("test", "test", {})
        receipt = RuntimeExecutionReceipt.from_invocation(invocation)
        json_str = receipt.to_json()
        
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["kind"] == "runtime_execution"

    def test_from_dict(self):
        """Receipt deserialization from dictionary."""
        d = {
            "receipt_id": "test-receipt",
            "kind": "runtime_execution",
            "provider_id": "test-provider",
            "model_id": "test-model",
            "status": "success",
            "advisory_only": True,
            "authoritative": False,
        }
        receipt = RuntimeExecutionReceipt.from_dict(d)
        assert receipt.receipt_id == "test-receipt"
        assert receipt.provider_id == "test-provider"
        assert receipt.advisory_only is True
        assert receipt.authoritative is False


# =============================================================================
# RuntimeDecision Tests
# =============================================================================

class TestRuntimeDecision:
    """Test RuntimeDecision model."""

    def test_frozen_dataclass(self):
        """RuntimeDecision is a frozen dataclass."""
        decision = RuntimeDecision.allow(
            RuntimeDecisionKind.CAPABILITY_CHECK,
            invocation_id="test",
        )
        with pytest.raises((AttributeError, TypeError)):
            decision.decision_id = "new_id"

    def test_allow_factory(self):
        """Allow decision factory."""
        decision = RuntimeDecision.allow(
            RuntimeDecisionKind.CAPABILITY_CHECK,
            invocation_id="test-invocation",
            proposal_id="test-proposal",
            reason="Test allow",
        )
        assert decision.allowed is True
        assert decision.kind == RuntimeDecisionKind.CAPABILITY_CHECK
        assert decision.invocation_id == "test-invocation"
        assert decision.reason == "Test allow"

    def test_deny_factory(self):
        """Deny decision factory."""
        decision = RuntimeDecision.deny(
            RuntimeDecisionKind.TRUST_VALIDATION,
            invocation_id="test-invocation",
            reason="Trust tier too low",
            trust_violations=["tier_too_low"],
            capability_misses=["required_cap"],
        )
        assert decision.allowed is False
        assert decision.kind == RuntimeDecisionKind.TRUST_VALIDATION
        assert "tier_too_low" in decision.trust_violations
        assert "required_cap" in decision.capability_misses

    def test_deny_factory_empty_lists(self):
        """Deny factory handles None list arguments."""
        decision = RuntimeDecision.deny(
            RuntimeDecisionKind.CAPABILITY_CHECK,
        )
        assert decision.constraint_violations == []
        assert decision.trust_violations == []
        assert decision.capability_misses == []

    def test_to_dict(self):
        """Decision serialization to dictionary."""
        decision = RuntimeDecision.allow(RuntimeDecisionKind.CAPABILITY_CHECK)
        d = decision.to_dict()
        
        assert "decision_id" in d
        assert "kind" in d
        assert "allowed" in d
        assert d["allowed"] is True

    def test_from_dict(self):
        """Decision deserialization from dictionary."""
        d = {
            "decision_id": "test-decision",
            "kind": "capability_check",
            "allowed": True,
            "reason": "Test",
        }
        decision = RuntimeDecision.from_dict(d)
        assert decision.decision_id == "test-decision"
        assert decision.kind == RuntimeDecisionKind.CAPABILITY_CHECK
        assert decision.allowed is True


# =============================================================================
# RuntimeBenchmark Tests
# =============================================================================

class TestRuntimeBenchmark:
    """Test RuntimeBenchmark model."""

    def test_frozen_dataclass(self):
        """RuntimeBenchmark is a frozen dataclass."""
        benchmark = RuntimeBenchmark.latency(
            "test-provider", "test-model", 1.5
        )
        with pytest.raises((AttributeError, TypeError)):
            benchmark.benchmark_id = "new_id"

    def test_latency_factory(self):
        """Latency benchmark factory."""
        benchmark = RuntimeBenchmark.latency(
            "test-provider", "test-model", 1.5
        )
        assert benchmark.kind == RuntimeBenchmarkKind.LATENCY
        assert benchmark.provider_id == "test-provider"
        assert benchmark.value == 1.5
        assert benchmark.unit == "seconds"

    def test_token_throughput_factory(self):
        """Token throughput benchmark factory."""
        benchmark = RuntimeBenchmark.token_throughput(
            "test-provider", "test-model", 50.0
        )
        assert benchmark.kind == RuntimeBenchmarkKind.TOKEN_THROUGHPUT
        assert benchmark.value == 50.0
        assert benchmark.unit == "tokens_per_second"

    def test_proposal_success_rate_factory(self):
        """Proposal success rate benchmark factory."""
        benchmark = RuntimeBenchmark.proposal_success_rate(
            "test-provider", "test-model", 0.95
        )
        assert benchmark.kind == RuntimeBenchmarkKind.PROPOSAL_SUCCESS
        assert benchmark.value == 0.95
        assert benchmark.unit == "ratio"

    def test_benchmark_id_deterministic(self):
        """Benchmark IDs are deterministic for same inputs."""
        bm1 = RuntimeBenchmark.latency("p1", "m1", 1.0)
        bm2 = RuntimeBenchmark.latency("p1", "m1", 1.0)
        assert bm1.benchmark_id == bm2.benchmark_id

    def test_to_dict(self):
        """Benchmark serialization to dictionary."""
        benchmark = RuntimeBenchmark.latency("p1", "m1", 1.0)
        d = benchmark.to_dict()
        
        assert "benchmark_id" in d
        assert "provider_id" in d
        assert "kind" in d
        assert d["kind"] == "latency"

    def test_from_dict(self):
        """Benchmark deserialization from dictionary."""
        d = {
            "benchmark_id": "test-benchmark",
            "provider_id": "test-provider",
            "model_id": "test-model",
            "kind": "latency",
            "value": 1.0,
        }
        benchmark = RuntimeBenchmark.from_dict(d)
        assert benchmark.benchmark_id == "test-benchmark"
        assert benchmark.kind == RuntimeBenchmarkKind.LATENCY


# =============================================================================
# RuntimeState Tests
# =============================================================================

class TestRuntimeState:
    """Test RuntimeState model."""

    def test_frozen_dataclass(self):
        """RuntimeState is a frozen dataclass."""
        state = RuntimeState.initial()
        with pytest.raises((AttributeError, TypeError)):
            state.state_id = "new_id"

    def test_initial_factory(self):
        """Initial state factory."""
        state = RuntimeState.initial(workspace_id="ws1")
        assert state.kind == RuntimeStateKind.IDLE
        assert state.workspace_id == "ws1"
        assert state.total_invocations == 0
        assert state.total_proposals == 0

    def test_to_dict(self):
        """State serialization to dictionary."""
        state = RuntimeState.initial()
        d = state.to_dict()
        
        assert "state_id" in d
        assert "kind" in d
        assert d["kind"] == "idle"

    def test_from_dict(self):
        """State deserialization from dictionary."""
        d = {
            "state_id": "test-state",
            "kind": "idle",
            "total_invocations": 5,
            "total_proposals": 10,
        }
        state = RuntimeState.from_dict(d)
        assert state.state_id == "test-state"
        assert state.kind == RuntimeStateKind.IDLE
        assert state.total_invocations == 5


# =============================================================================
# Authority Invariants Tests
# =============================================================================

class TestAuthorityInvariants:
    """Test that authority invariants are maintained."""

    def test_all_providers_are_advisory_only(self):
        """All runtime providers are advisory only."""
        providers = [
            RuntimeProvider.dry_run(),
            RuntimeProvider.custom_command(),
            RuntimeProvider.from_manifest({
                "provider_id": "test",
                "authoritative": True,  # Should be overridden
            }),
        ]
        for provider in providers:
            assert provider.advisory_only is True
            assert provider.authoritative is False

    def test_all_capabilities_are_advisory_only(self):
        """All runtime capabilities are advisory only."""
        capabilities = [
            RuntimeCapability.file_read(),
            RuntimeCapability.file_write_proposal(),
            RuntimeCapability.shell_proposal(),
            RuntimeCapability.patch_proposal(),
        ]
        for cap in capabilities:
            assert cap.advisory_only is True

    def test_all_invocations_are_advisory_only(self):
        """All runtime invocations are advisory only."""
        invocations = [
            RuntimeInvocation.create("p1", "m1", {}),
            RuntimeInvocation(
                invocation_id="test",
                provider_id="p1",
                advisory_only=False,  # Should be True
            ),
        ]
        # The second one will be overridden by __post_init__
        for invocation in invocations:
            assert invocation.advisory_only is True

    def test_all_proposals_are_advisory_and_not_authoritative(self):
        """All runtime proposals are advisory and not authoritative."""
        invocation = RuntimeInvocation.create("p1", "m1", {})
        proposals = [
            RuntimeProposal.from_invocation(invocation, "test", {}),
            RuntimeProposal(
                proposal_id="test",
                invocation_id="i1",
                advisory_only=False,  # Should be overridden
                authoritative=True,  # Should be overridden
            ),
        ]
        for proposal in proposals:
            assert proposal.advisory_only is True
            assert proposal.authoritative is False

    def test_all_receipts_are_advisory_and_not_authoritative(self):
        """All execution receipts are advisory and not authoritative."""
        invocation = RuntimeInvocation.create("p1", "m1", {})
        receipts = [
            RuntimeExecutionReceipt.from_invocation(invocation),
            RuntimeExecutionReceipt(
                receipt_id="test",
                advisory_only=False,  # Should be overridden
                authoritative=True,  # Should be overridden
            ),
        ]
        for receipt in receipts:
            assert receipt.advisory_only is True
            assert receipt.authoritative is False

    def test_no_direct_file_mutation(self):
        """No runtime provider allows direct file mutation."""
        providers = [
            RuntimeProvider.dry_run(),
            RuntimeProvider.custom_command(),
            RuntimeProvider(
                provider_id="test",
                rig_allows_file_mutation=True,  # Should be overridden
            ),
        ]
        for provider in providers:
            assert provider.rig_allows_file_mutation is False


# =============================================================================
# Deterministic Serialization Tests
# =============================================================================

class TestDeterministicSerialization:
    """Test deterministic serialization."""

    def test_provider_deterministic_json(self):
        """Provider JSON serialization is deterministic."""
        provider = RuntimeProvider.dry_run()
        json1 = provider.to_json()
        json2 = provider.to_json()
        # Note: timestamps may differ, so we check structure
        assert json.loads(json1) == json.loads(json2)

    def test_receipt_deterministic_json_structure(self):
        """Receipt JSON has deterministic structure (ignoring timestamps)."""
        invocation = RuntimeInvocation.create("p1", "m1", {})
        # Use a fixed invocation for testing
        receipt1 = RuntimeExecutionReceipt.from_invocation(invocation)
        receipt2 = RuntimeExecutionReceipt.from_invocation(invocation)
        
        d1 = receipt1.to_dict()
        d2 = receipt2.to_dict()
        
        # Receipt IDs should be the same for same invocation
        assert d1["receipt_id"] == d2["receipt_id"]

    def test_benchmark_deterministic_id(self):
        """Benchmark IDs are deterministic."""
        bm1 = RuntimeBenchmark.latency("p1", "m1", 1.0)
        bm2 = RuntimeBenchmark.latency("p1", "m1", 1.0)
        assert bm1.benchmark_id == bm2.benchmark_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
