"""Deterministic context engineering types for governed agent orchestration.

ADR 0009: Agentic Workflow Refinement — Slice 0.5 (types only).

ContextBlock is a typed, hashable, provenance-bearing unit of context.
ContextPacket is a deterministic assembly of blocks for one agent step.
ContextAssemblyPolicy defines rules for packet construction.

Context packets are deterministic: given the same mission, trajectory,
retrieval results, and budget, Rig produces the same ordered packet
with the same block IDs and hashes.

Ordering rule (most stable → most volatile):
  1. Invariant system/governance contract
  2. ADR/task/mission contract
  3. Stable policy and allowed/protected paths
  4. Retrieved code context with provenance
  5. Recent trajectory observations
  6. Current tool result / newest observation
  7. Out-of-scope findings and handoff notes

This ordering maximizes prompt-cache locality when downstream
model APIs support prefix caching.

All types are pure data, frozen, deterministic, and import without side effects.
No assembly implementation is included in this file.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# Context Block
# =============================================================================


@dataclass(frozen=True)
class ContextBlock:
    """A typed, hashable, provenance-bearing unit of context.

    Each block has a kind that determines its position in the
    stable ordering (system < mission < policy < code < observation).
    """

    block_id: str
    kind: str  # "system", "mission", "policy", "adr", "code", "observation",
    #             "error", "finding", "summary"
    content: str
    source: str  # file path, event id, receipt id, generated label
    content_hash: str  # SHA-256 hex digest of content
    token_estimate: int
    priority: int  # Lower = more important, placed earlier

    # If True, this block should appear in the stable prefix region
    stable_prefix: bool = False

    # If set, this block expires after this step index
    expires_after_step: int | None = None

    @staticmethod
    def compute_hash(content: str) -> str:
        """Deterministic SHA-256 hash of content string."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


# =============================================================================
# Context Packet
# =============================================================================


@dataclass(frozen=True)
class ContextPacket:
    """Deterministic context view provided to an agent step.

    A packet is the complete context assembly for one orchestrator step.
    It is reconstructable from durable inputs: task file, progress ledger,
    mission definition, retrieval provenance, receipts, and assembly policy.
    """

    packet_id: str
    session_id: str
    step_index: int
    blocks: tuple[ContextBlock, ...] = ()
    total_tokens: int = 0
    budget_tokens: int = 0
    assembly_policy: str = ""  # Policy name/id used for assembly
    packet_hash: str = ""  # SHA-256 of concatenated block hashes

    @property
    def block_count(self) -> int:
        """Number of blocks in this packet."""
        return len(self.blocks)

    @property
    def is_within_budget(self) -> bool:
        """Whether packet is within its token budget."""
        return self.budget_tokens == 0 or self.total_tokens <= self.budget_tokens

    @property
    def stable_prefix_tokens(self) -> int:
        """Token count of the stable prefix region."""
        return sum(b.token_estimate for b in self.blocks if b.stable_prefix)


# =============================================================================
# Context Assembly Policy
# =============================================================================


# Kind ordering for deterministic block placement.
# Lower number = placed earlier in the packet (more stable).
KIND_PRIORITY: dict[str, int] = {
    "system": 0,
    "mission": 10,
    "policy": 20,
    "adr": 30,
    "code": 40,
    "observation": 50,
    "error": 55,
    "finding": 60,
    "summary": 70,
}


@dataclass(frozen=True)
class ContextAssemblyPolicy:
    """Rules for deterministic context packet assembly.

    Controls what gets included, how much budget each category gets,
    and what preservation rules apply.
    """

    # Total token budget for the assembled packet
    budget_tokens: int = 100_000

    # Ordering: place stable blocks before volatile ones
    preserve_stable_prefix: bool = True

    # How many recent trajectory steps to include as observations
    include_recent_steps: int = 10

    # Always include error steps regardless of recency
    include_error_steps: bool = True

    # Always include governance block events
    include_governance_blocks: bool = True

    # Include out-of-scope findings from ADR work
    include_out_of_scope_findings: bool = True

    # Budget allocation for retrieval within overall budget
    retrieval_budget_tokens: int = 20_000


# =============================================================================
# Canonicalization Helpers (pure, deterministic)
# =============================================================================


def canonicalize_content(content: str) -> str:
    """Normalize content for deterministic hashing.

    - Normalize line endings to LF
    - Strip trailing whitespace per line
    - Ensure single trailing newline
    """
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    stripped = [line.rstrip() for line in lines]
    # Remove trailing empty lines, keep one trailing newline
    while stripped and stripped[-1] == "":
        stripped.pop()
    return "\n".join(stripped) + "\n" if stripped else ""


def compute_packet_hash(blocks: tuple[ContextBlock, ...]) -> str:
    """Deterministic hash of a packet from its block hashes.

    Concatenates block content_hashes in order and hashes the result.
    """
    combined = "|".join(b.content_hash for b in blocks)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
