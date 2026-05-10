"""Compaction types for governed agent orchestration.

ADR 0009: Agentic Workflow Refinement — Slice 0 (types only).

CompactionPolicy defines rules for compacting agent trajectories.
CompactedTrajectory is the result of applying a policy to a trajectory.
CompactionMetadata records what was compacted and why.

Compaction is deterministic and structural — no AI summarization.
Rules: keep recent steps, keep errors, keep governance decisions,
summarize the rest.

All types are pure data, frozen, deterministic, and import without side effects.
No compaction implementation is included in this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Compaction Policy
# =============================================================================


@dataclass(frozen=True)
class CompactionPolicy:
    """Policy for trajectory compaction.

    Defines when compaction triggers and what it preserves.

    Compaction is deterministic: given the same trajectory and policy,
    the same compacted result is produced. No model dependency.
    """

    # Trigger: compact when trajectory exceeds this token estimate
    trigger_threshold_tokens: int = 100_000

    # Target: aim to reduce compacted trajectory to this size
    target_tokens: int = 50_000

    # Preservation rules
    preserve_recent_steps: int = 10  # Never compact the N most recent steps
    preserve_error_steps: bool = True  # Always keep error observations in full
    preserve_governance_blocks: bool = True  # Always keep governance block events


# =============================================================================
# Compaction Metadata
# =============================================================================


@dataclass(frozen=True)
class CompactionMetadata:
    """Records what was compacted and the result.

    Provides transparency into the compaction process for audit
    and debugging purposes.
    """

    # Input metrics
    original_step_count: int = 0
    original_token_estimate: int = 0

    # Output metrics
    compacted_step_count: int = 0  # Steps kept in full
    summarized_step_count: int = 0  # Steps reduced to summaries
    discarded_step_count: int = 0  # Steps fully removed (should be 0 normally)
    compacted_token_estimate: int = 0

    # Compression ratio (0.0–1.0, lower = more compression)
    @property
    def compression_ratio(self) -> float:
        """Ratio of compacted to original tokens. Lower = more compression."""
        if self.original_token_estimate == 0:
            return 1.0
        return self.compacted_token_estimate / self.original_token_estimate

    # Preservation counts
    preserved_error_steps: int = 0
    preserved_governance_steps: int = 0
    preserved_recent_steps: int = 0


# =============================================================================
# Compacted Trajectory
# =============================================================================


@dataclass(frozen=True)
class CompactedTrajectory:
    """Compacted view of an agent trajectory.

    Preserves:
    - Recent N steps in full (per policy.preserve_recent_steps)
    - Error steps in full (if policy.preserve_error_steps)
    - Governance block events in full (if policy.preserve_governance_blocks)
    - Older steps summarized to: intent + outcome + key metadata

    Strips:
    - Verbose stdout from successful executions
    - Redundant stderr output
    - Intermediate projection states

    The full, uncompacted trajectory is always preserved separately
    through receipt/evidence mechanisms.

    Note: field types use strings for step indices to avoid circular imports
    at the type level. TrajectoryEvent and TrajectoryEventSummary references
    are in TYPE_CHECKING only.
    """

    # Steps preserved in full (recent + errors + governance decisions)
    full_step_indices: tuple[int, ...] = ()

    # Steps reduced to summaries
    summarized_step_indices: tuple[int, ...] = ()

    # Compaction metrics
    metadata: CompactionMetadata = field(default_factory=CompactionMetadata)

    @property
    def total_steps(self) -> int:
        """Total steps represented (full + summarized)."""
        return len(self.full_step_indices) + len(self.summarized_step_indices)
