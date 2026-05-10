"""Context retrieval protocol and types for governed agent orchestration.

ADR 0009: Agentic Workflow Refinement — Slice 0 (types only).

Defines the ContextRetriever protocol (seam) and supporting types for
surgical codebase context provision to agent orchestration sessions.

Rig owns the protocol; implementations are adapters:
- Preferred: local CLI tools (rg, fd, ctags, ast-grep)
- Optional: Anigma MCP server's context_search tool

All types are pure data, frozen where possible, and import without side effects.
No adapter implementations are included in this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# =============================================================================
# Context Scope
# =============================================================================


@dataclass(frozen=True)
class ContextScope:
    """Defines retrieval boundaries — workspace, paths, file patterns.

    Retrieval must respect scope boundaries. Agents cannot retrieve
    context outside their worktree or excluded paths.
    """

    workspace_id: str
    include_paths: tuple[str, ...] = ()  # Glob patterns for inclusion
    exclude_paths: tuple[str, ...] = ()  # Glob patterns for exclusion


# =============================================================================
# Context Chunk
# =============================================================================


@dataclass(frozen=True)
class ContextChunk:
    """Single chunk of retrieved context with provenance.

    Provenance (file_path, start_line, end_line) enables the orchestrator
    to record exactly what context was provided to the agent.
    """

    file_path: str
    start_line: int
    end_line: int
    content: str
    relevance_score: float  # 0.0–1.0, implementation-defined
    chunk_type: str  # "function", "class", "scope", "file", "snippet"


# =============================================================================
# Context Bundle
# =============================================================================


@dataclass(frozen=True)
class ContextBundle:
    """Retrieved context with provenance metadata.

    A bundle is the result of a single retrieval operation.
    It must never exceed the requested token budget.
    """

    chunks: tuple[ContextChunk, ...] = ()
    total_tokens: int = 0
    retrieval_method: str = ""  # "rg", "ctags", "ast-grep", "anigma-mcp", etc.
    scope: ContextScope | None = None  # The scope used for retrieval

    @property
    def chunk_count(self) -> int:
        """Number of chunks in this bundle."""
        return len(self.chunks)

    @property
    def is_empty(self) -> bool:
        """Whether this bundle contains no context."""
        return len(self.chunks) == 0


# =============================================================================
# Context Retriever Protocol (Seam)
# =============================================================================


@runtime_checkable
class ContextRetriever(Protocol):
    """Protocol for providing surgical context to agent orchestration.

    Implementations may use:
    - Local CLI tools (rg, fd, ctags, ast-grep) — preferred per user rules
    - Anigma MCP server's context_search tool
    - External vector databases

    Rig does NOT own the retrieval implementation. Rig owns the SEAM.

    Implementations must:
    - Respect scope boundaries (never retrieve outside workspace/worktree)
    - Never exceed budget_tokens in the returned ContextBundle
    - Return an empty ContextBundle on failure (not raise)
    - Set retrieval_method to identify the adapter used
    """

    def retrieve(
        self,
        query: str,
        scope: ContextScope,
        budget_tokens: int,
    ) -> ContextBundle:
        """Retrieve relevant context within token budget.

        Args:
            query: Natural language or keyword query.
            scope: Workspace and path boundaries for retrieval.
            budget_tokens: Maximum token count for returned context.

        Returns:
            ContextBundle with ranked, deduplicated chunks.
            Never exceeds budget_tokens.
            Returns empty bundle on failure.
        """
        ...
