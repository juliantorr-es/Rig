"""Tests for ADR 0009 Slice 0 types.

Proves:
- All types import cleanly without side effects
- Types are constructible with expected defaults
- Frozen types are immutable
- Budget arithmetic is deterministic
- No external dependencies beyond stdlib
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

# =============================================================================
# Import purity tests — types import without side effects
# =============================================================================


class TestImportPurity:
    """Verify all Slice 0 modules import cleanly."""

    def test_trajectory_imports(self) -> None:
        from rig.domain.execution.trajectory import (
            SessionOutcome,
            StepOutcome,
            StepResult,
            TrajectoryEvent,
            TrajectoryEventSummary,
        )
        # Verify module loaded
        assert TrajectoryEvent is not None
        assert TrajectoryEventSummary is not None
        assert StepResult is not None
        assert StepOutcome is not None
        assert SessionOutcome is not None

    def test_budget_imports(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        assert OrchestratorBudget is not None

    def test_context_retrieval_imports(self) -> None:
        from rig.domain.execution.context_retrieval import (
            ContextBundle,
            ContextChunk,
            ContextRetriever,
            ContextScope,
        )
        assert ContextRetriever is not None
        assert ContextScope is not None
        assert ContextBundle is not None
        assert ContextChunk is not None

    def test_compaction_imports(self) -> None:
        from rig.domain.execution.compaction import (
            CompactedTrajectory,
            CompactionMetadata,
            CompactionPolicy,
        )
        assert CompactionPolicy is not None
        assert CompactedTrajectory is not None
        assert CompactionMetadata is not None


# =============================================================================
# TrajectoryEvent tests
# =============================================================================


class TestTrajectoryEvent:
    """Verify TrajectoryEvent construction and immutability."""

    def test_construction_with_defaults(self) -> None:
        from rig.domain.execution.trajectory import TrajectoryEvent

        event = TrajectoryEvent(
            step_index=0,
            session_id="sess_abc",
            intent_type="intent.run_validators",
            intent_summary="Run validators on proposal",
            governance_decision="allowed",
            governance_gate="rig.gate.apply",
        )
        assert event.step_index == 0
        assert event.session_id == "sess_abc"
        assert event.intent_type == "intent.run_validators"
        assert event.governance_decision == "allowed"
        assert event.outcome == "executed"
        assert event.execution_id is None
        assert event.exit_code is None
        assert event.estimated_tokens == 0
        assert isinstance(event.metadata, dict)
        assert len(event.metadata) == 0

    def test_frozen_immutability(self) -> None:
        from rig.domain.execution.trajectory import TrajectoryEvent

        event = TrajectoryEvent(
            step_index=0,
            session_id="sess_abc",
            intent_type="intent.run_validators",
            intent_summary="Run validators",
            governance_decision="allowed",
            governance_gate="rig.gate.apply",
        )
        with pytest.raises(AttributeError):
            event.step_index = 1  # type: ignore[misc]

    def test_timestamp_auto_populated(self) -> None:
        from rig.domain.execution.trajectory import TrajectoryEvent

        event = TrajectoryEvent(
            step_index=0,
            session_id="sess_abc",
            intent_type="intent.run_validators",
            intent_summary="Run validators",
            governance_decision="allowed",
            governance_gate="rig.gate.apply",
        )
        # Timestamp should be a valid ISO format string
        parsed = datetime.fromisoformat(event.timestamp)
        assert parsed.tzinfo is not None


class TestTrajectoryEventSummary:
    """Verify TrajectoryEventSummary construction."""

    def test_construction(self) -> None:
        from rig.domain.execution.trajectory import TrajectoryEventSummary

        summary = TrajectoryEventSummary(
            step_index=3,
            session_id="sess_abc",
            intent_type="intent.apply_patch",
            intent_summary="Apply patch to main",
            outcome="governance_blocked",
            governance_decision="blocked",
            observation_summary="Validators must run first",
            timestamp=datetime.now(UTC).isoformat(),
        )
        assert summary.step_index == 3
        assert summary.outcome == "governance_blocked"
        assert summary.estimated_tokens == 0


class TestStepResult:
    """Verify StepResult construction and properties."""

    def test_allowed_step(self) -> None:
        from rig.domain.execution.trajectory import (
            StepOutcome,
            StepResult,
            TrajectoryEvent,
        )

        event = TrajectoryEvent(
            step_index=0,
            session_id="sess_abc",
            intent_type="intent.run_validators",
            intent_summary="Run validators",
            governance_decision="allowed",
            governance_gate="rig.gate.apply",
            outcome=StepOutcome.EXECUTED.value,
            exit_code=0,
        )
        result = StepResult(event=event, budget_remaining_steps=9)
        assert result.was_allowed is True
        assert result.was_blocked is False
        assert result.succeeded is True
        assert result.budget_exhausted is False

    def test_blocked_step(self) -> None:
        from rig.domain.execution.trajectory import (
            StepOutcome,
            StepResult,
            TrajectoryEvent,
        )

        event = TrajectoryEvent(
            step_index=1,
            session_id="sess_abc",
            intent_type="intent.apply_patch",
            intent_summary="Apply patch",
            governance_decision="blocked",
            governance_gate="rig.gate.apply",
            outcome=StepOutcome.GOVERNANCE_BLOCKED.value,
        )
        result = StepResult(event=event)
        assert result.was_allowed is False
        assert result.was_blocked is True
        assert result.succeeded is False


# =============================================================================
# Budget tests
# =============================================================================


class TestOrchestratorBudget:
    """Verify OrchestratorBudget arithmetic and exhaustion checks."""

    def test_defaults_are_unbounded(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        budget = OrchestratorBudget()
        assert budget.max_steps is None
        assert budget.max_wall_time_seconds is None
        assert budget.max_tokens is None
        assert budget.is_exhausted() is False

    def test_step_exhaustion(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        budget = OrchestratorBudget(max_steps=5)
        assert budget.is_exhausted(steps_used=4) is False
        assert budget.is_exhausted(steps_used=5) is True
        assert budget.is_exhausted(steps_used=6) is True

    def test_wall_time_exhaustion(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        budget = OrchestratorBudget(max_wall_time_seconds=60.0)
        assert budget.is_exhausted(wall_time_used_seconds=59.9) is False
        assert budget.is_exhausted(wall_time_used_seconds=60.0) is True

    def test_token_exhaustion(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        budget = OrchestratorBudget(max_tokens=100_000)
        assert budget.is_exhausted(tokens_used=99_999) is False
        assert budget.is_exhausted(tokens_used=100_000) is True

    def test_remaining_computation(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        budget = OrchestratorBudget(
            max_steps=10,
            max_wall_time_seconds=120.0,
            max_tokens=50_000,
        )
        remaining = budget.remaining(
            steps_used=3,
            wall_time_used_seconds=45.0,
            tokens_used=12_000,
        )
        assert remaining.max_steps == 7
        assert remaining.max_wall_time_seconds == 75.0
        assert remaining.max_tokens == 38_000

    def test_remaining_clamps_to_zero(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        budget = OrchestratorBudget(max_steps=5)
        remaining = budget.remaining(steps_used=10)
        assert remaining.max_steps == 0

    def test_exhaustion_reason(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        budget = OrchestratorBudget(max_steps=5, max_tokens=1000)
        assert budget.exhaustion_reason(steps_used=3) is None
        reason = budget.exhaustion_reason(steps_used=5)
        assert reason is not None
        assert "5/5" in reason

    def test_frozen_immutability(self) -> None:
        from rig.domain.execution.budget import OrchestratorBudget

        budget = OrchestratorBudget(max_steps=10)
        with pytest.raises(AttributeError):
            budget.max_steps = 20  # type: ignore[misc]


# =============================================================================
# Context retrieval tests
# =============================================================================


class TestContextTypes:
    """Verify context retrieval types construction."""

    def test_context_scope(self) -> None:
        from rig.domain.execution.context_retrieval import ContextScope

        scope = ContextScope(
            workspace_id="ws_123",
            include_paths=("src/**/*.py",),
            exclude_paths=("**/test_*",),
        )
        assert scope.workspace_id == "ws_123"
        assert len(scope.include_paths) == 1

    def test_context_chunk(self) -> None:
        from rig.domain.execution.context_retrieval import ContextChunk

        chunk = ContextChunk(
            file_path="src/rig/domain/workspace.py",
            start_line=10,
            end_line=25,
            content="def create_workspace():\n    ...",
            relevance_score=0.85,
            chunk_type="function",
        )
        assert chunk.file_path == "src/rig/domain/workspace.py"
        assert chunk.relevance_score == 0.85

    def test_context_bundle_empty(self) -> None:
        from rig.domain.execution.context_retrieval import ContextBundle

        bundle = ContextBundle()
        assert bundle.is_empty is True
        assert bundle.chunk_count == 0
        assert bundle.total_tokens == 0

    def test_context_bundle_with_chunks(self) -> None:
        from rig.domain.execution.context_retrieval import (
            ContextBundle,
            ContextChunk,
        )

        chunk = ContextChunk(
            file_path="src/rig/domain/workspace.py",
            start_line=10,
            end_line=25,
            content="def create_workspace():\n    ...",
            relevance_score=0.85,
            chunk_type="function",
        )
        bundle = ContextBundle(
            chunks=(chunk,),
            total_tokens=50,
            retrieval_method="rg",
        )
        assert bundle.is_empty is False
        assert bundle.chunk_count == 1
        assert bundle.retrieval_method == "rg"

    def test_context_retriever_is_protocol(self) -> None:
        from rig.domain.execution.context_retrieval import ContextRetriever

        # ContextRetriever is a runtime_checkable Protocol
        assert hasattr(ContextRetriever, "retrieve")


# =============================================================================
# Compaction tests
# =============================================================================


class TestCompactionTypes:
    """Verify compaction types construction."""

    def test_compaction_policy_defaults(self) -> None:
        from rig.domain.execution.compaction import CompactionPolicy

        policy = CompactionPolicy()
        assert policy.trigger_threshold_tokens == 100_000
        assert policy.target_tokens == 50_000
        assert policy.preserve_recent_steps == 10
        assert policy.preserve_error_steps is True
        assert policy.preserve_governance_blocks is True

    def test_compaction_policy_custom(self) -> None:
        from rig.domain.execution.compaction import CompactionPolicy

        policy = CompactionPolicy(
            trigger_threshold_tokens=50_000,
            target_tokens=25_000,
            preserve_recent_steps=5,
        )
        assert policy.trigger_threshold_tokens == 50_000
        assert policy.preserve_recent_steps == 5

    def test_compaction_metadata(self) -> None:
        from rig.domain.execution.compaction import CompactionMetadata

        meta = CompactionMetadata(
            original_step_count=20,
            original_token_estimate=80_000,
            compacted_step_count=10,
            summarized_step_count=10,
            compacted_token_estimate=40_000,
        )
        assert meta.compression_ratio == 0.5

    def test_compaction_metadata_zero_division(self) -> None:
        from rig.domain.execution.compaction import CompactionMetadata

        meta = CompactionMetadata()
        assert meta.compression_ratio == 1.0  # No division by zero

    def test_compacted_trajectory(self) -> None:
        from rig.domain.execution.compaction import (
            CompactedTrajectory,
            CompactionMetadata,
        )

        trajectory = CompactedTrajectory(
            full_step_indices=(8, 9, 10, 11, 12),
            summarized_step_indices=(0, 1, 2, 3, 4, 5, 6, 7),
            metadata=CompactionMetadata(
                original_step_count=13,
                compacted_step_count=5,
                summarized_step_count=8,
            ),
        )
        assert trajectory.total_steps == 13
