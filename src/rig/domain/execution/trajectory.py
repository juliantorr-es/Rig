"""Trajectory types for governed agent orchestration.

ADR 0009: Agentic Workflow Refinement — Slice 0 (types only).

TrajectoryEvent captures a single governed step in an agent orchestration
session: the intent, governance decision, execution observation, and metadata.
TrajectoryEventSummary is a compacted representation for long sessions.
StepResult is the return type from a single orchestrator step.

All types are pure data, frozen, deterministic, and import without side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

# =============================================================================
# Enums
# =============================================================================


class StepOutcome(Enum):
    """Outcome of a single orchestrator step."""

    EXECUTED = "executed"  # Intent was allowed and executed
    GOVERNANCE_BLOCKED = "governance_blocked"  # Intent was blocked by governance
    BUDGET_EXHAUSTED = "budget_exhausted"  # Budget limit reached before execution
    EXECUTION_FAILED = "execution_failed"  # Execution attempted but failed
    EXECUTION_TIMEOUT = "execution_timeout"  # Execution timed out
    SKIPPED = "skipped"  # Intent was skipped (e.g., duplicate, no-op)


class SessionOutcome(Enum):
    """Outcome of a complete orchestration session."""

    COMPLETED = "completed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    GOVERNANCE_BLOCKED = "governance_blocked"
    ERROR = "error"
    CANCELLED = "cancelled"


# =============================================================================
# Trajectory Event
# =============================================================================


@dataclass(frozen=True)
class TrajectoryEvent:
    """A single governed step in an agent orchestration session.

    Captures the full lifecycle of one step:
      intent → governance decision → execution → observation

    Immutable once created. Flows into receipt/evidence mechanisms.
    """

    # Identity
    step_index: int  # Monotonic within session
    session_id: str

    # What was requested
    intent_type: str  # e.g., "intent.run_validators", "intent.apply_patch"
    intent_summary: str  # Human-readable description

    # Governance result
    governance_decision: str  # "allowed", "blocked", "not_applicable"
    governance_gate: str  # Which gate evaluated this
    governance_reasons: tuple[str, ...] = ()  # DecisionReason summaries

    # Execution result (only populated if governance allowed execution)
    outcome: str = StepOutcome.EXECUTED.value
    execution_id: str | None = None
    exit_code: int | None = None
    observation_summary: str = ""  # Compact observation for context

    # Timing
    timestamp: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    wall_time_ms: float | None = None  # Step wall time in milliseconds

    # Estimated token cost of this step's observation
    estimated_tokens: int = 0

    # Arbitrary metadata (tool name, file paths touched, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Trajectory Event Summary (for compaction)
# =============================================================================


@dataclass(frozen=True)
class TrajectoryEventSummary:
    """Compacted representation of a trajectory event.

    Used by CompactionPolicy to reduce older steps to essential metadata
    while preserving intent, outcome, and governance information.

    Does NOT preserve full observation text — only the summary line.
    """

    step_index: int
    session_id: str
    intent_type: str
    intent_summary: str
    outcome: str
    governance_decision: str
    observation_summary: str  # One-line summary, not full output
    timestamp: str
    estimated_tokens: int = 0


# =============================================================================
# Step Result
# =============================================================================


@dataclass(frozen=True)
class StepResult:
    """Return type from a single orchestrator step.

    Contains the trajectory event plus operational metadata
    that the caller (external agent tool) may need to decide
    what to do next.
    """

    event: TrajectoryEvent

    # Whether the orchestrator can accept more steps
    budget_exhausted: bool = False
    budget_remaining_steps: int | None = None
    budget_remaining_wall_time_seconds: float | None = None

    @property
    def was_allowed(self) -> bool:
        """Whether governance allowed this step to execute."""
        return self.event.governance_decision == "allowed"

    @property
    def was_blocked(self) -> bool:
        """Whether governance blocked this step."""
        return self.event.governance_decision == "blocked"

    @property
    def succeeded(self) -> bool:
        """Whether execution succeeded (exit code 0)."""
        return (
            self.event.outcome == StepOutcome.EXECUTED.value
            and self.event.exit_code == 0
        )
