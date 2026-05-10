"""Budget types for governed agent orchestration.

ADR 0009: Agentic Workflow Refinement — Slice 0 (types only).

OrchestratorBudget defines resource limits for an agent orchestration session:
maximum steps, maximum wall time, and maximum estimated token consumption.

All types are pure data, frozen, deterministic, and import without side effects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestratorBudget:
    """Resource budget for an agent orchestration session.

    Enforced by the orchestrator at each step. Once any limit is reached,
    the orchestrator refuses further steps and returns budget_exhausted.

    All limits are optional. Omitted limits are unbounded (use with caution).
    """

    # Maximum number of orchestrator steps (intent → execute cycles)
    max_steps: int | None = None

    # Maximum wall-clock time for the entire session (seconds)
    max_wall_time_seconds: float | None = None

    # Maximum estimated token consumption across all observations
    max_tokens: int | None = None

    def remaining(
        self,
        steps_used: int = 0,
        wall_time_used_seconds: float = 0.0,
        tokens_used: int = 0,
    ) -> OrchestratorBudget:
        """Compute remaining budget after consumption.

        Returns a new OrchestratorBudget with remaining values.
        Negative remaining values are clamped to 0.
        """
        return OrchestratorBudget(
            max_steps=(
                max(0, self.max_steps - steps_used)
                if self.max_steps is not None
                else None
            ),
            max_wall_time_seconds=(
                max(0.0, self.max_wall_time_seconds - wall_time_used_seconds)
                if self.max_wall_time_seconds is not None
                else None
            ),
            max_tokens=(
                max(0, self.max_tokens - tokens_used)
                if self.max_tokens is not None
                else None
            ),
        )

    def is_exhausted(
        self,
        steps_used: int = 0,
        wall_time_used_seconds: float = 0.0,
        tokens_used: int = 0,
    ) -> bool:
        """Check if any budget limit has been reached or exceeded."""
        if self.max_steps is not None and steps_used >= self.max_steps:
            return True
        if (
            self.max_wall_time_seconds is not None
            and wall_time_used_seconds >= self.max_wall_time_seconds
        ):
            return True
        if self.max_tokens is not None and tokens_used >= self.max_tokens:
            return True
        return False

    def exhaustion_reason(
        self,
        steps_used: int = 0,
        wall_time_used_seconds: float = 0.0,
        tokens_used: int = 0,
    ) -> str | None:
        """Return human-readable reason if budget is exhausted, else None."""
        if self.max_steps is not None and steps_used >= self.max_steps:
            return f"Step limit reached ({steps_used}/{self.max_steps})"
        if (
            self.max_wall_time_seconds is not None
            and wall_time_used_seconds >= self.max_wall_time_seconds
        ):
            return (
                f"Wall time limit reached "
                f"({wall_time_used_seconds:.1f}s/{self.max_wall_time_seconds:.1f}s)"
            )
        if self.max_tokens is not None and tokens_used >= self.max_tokens:
            return f"Token limit reached ({tokens_used}/{self.max_tokens})"
        return None
