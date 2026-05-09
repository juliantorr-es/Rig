# Agentic Workflow Refinement

**ADR 0009**

Rig's agentic workflow infrastructure — the governed pipeline from intent to proposal to evidence — is architecturally sound but operationally shallow in several areas exposed by studying production multi-agent systems at scale. This ADR proposes targeted refinements to deepen Rig's agent orchestration, context retrieval, isolation, and telemetry capabilities **within the established governance narrative**: models propose, Rig disposes.

**Status**: proposed / needs reconciliation

> [!IMPORTANT]
> ADR numbering and cross-references in this document depend on the ADR index being stabilized. Before this ADR can be accepted, verify that the Related ADR numbers below match the canonical index in `docs/adr/README.md`. Known drift exists between ADR 0007/0008 filenames and their cross-references.

**Related ADRs**:
- [0003 Governance Engine Deepening](0003-governance-engine-deepening.md) — agent orchestration feeds governance evaluation
- [0004 Runtime Streaming Consolidation](0004-runtime-streaming-consolidation.md) — Runtime Streaming may transport/propagate orchestration events as an operational stream; it does **not** own agent orchestration semantics (those belong to the execution domain)
- [0007 Workspace Domain Authority](0007-workspace-domain-authority.md) — worktree isolation is the backbone of agent sandboxing; ephemeral worktree lifecycle (Decision 3) is deferred until this ADR is accepted
- [0008 Receipt/Evidence Unification](0008-receipt-evidence-unification.md) — agent trajectory evidence flows through current receipt/evidence mechanisms now, converging into EvidenceDomain when ADR 0008 is resolved

**Explicit non-goal**: Rig does not become an autonomous coding IDE. Rig governs external agent loops. The orchestrator provides governance infrastructure for agent workflows that originate in external tools (Gemini, Cursor, Claude Code, etc.). It does not autonomously plan, reason, or execute.

---

## Context: External Architecture Signals and Inferred Patterns

The following patterns are **inferred from public marketing materials, developer blog posts, and a promotional video transcript** describing Cursor 3's multi-agent system. Implementation details below are editorial interpretation, not verified architecture documentation. They are included as directional signals for where production agentic systems appear to be converging.

> [!NOTE]
> **Provenance**: Patterns in this table are synthesized from a promotional video transcript (no direct engineering documentation). Specific implementation claims (Merkle trees, Tree-sitter chunking, TurboPuffer, sparse MoE routing) are presented as described in that source material and may reflect marketing framing rather than verified architecture.

| Pattern | Inferred Commercial Approach | Rig Status |
|---------|------------------------------|------------|
| **Orchestrator Loop** | ReAct-style pattern: reason → act → observe → rebuild context → repeat | `WorktreeExecutor` is single-shot; no iterative agent loop |
| **Context Retrieval** | Codebase indexing with AST-aware chunking and semantic search | No codebase indexing; agents receive whatever context the external tool provides |
| **Agent Isolation** | Per-agent isolated working directories | `WorkspaceDomain` has worktree primitives, but no per-agent ephemeral lifecycle |
| **Context Compaction** | Algorithmic compression at token threshold — structured summarization, pruning verbose outputs | No context window management; agents own their own context budgets externally |
| **Telemetry Feedback Loop** | Execution telemetry feeding operational improvement | `ExecutionReceipt` exists but has no feedback channel to agent behavior |

### What Rig Already Has (and Must Not Lose)

These are **non-negotiable advantages** that commercial agentic IDEs lack:

1. **Governance Authority** — Rig evaluates legality *before* execution. Commercial agent IDEs typically let agents execute freely; Rig gates every state transition through `GovernanceEngine.evaluate()`.
2. **Evidence Lineage** — Every execution produces a `ReceiptEnvelope` with causal chain. Commercial systems have telemetry but not forensic-grade evidence.
3. **Proposal Lifecycle** — Decoded → Registered → Accepted → Applied. Agents cannot bypass the lifecycle.
4. **Git Guard** — Destructive git operations are blocked at the shell level, not just by prompt engineering.
5. **Gate Policy** — `WorkflowGatePolicy` (Gate A) defines what agents can and cannot do, with advisory escalation path.

**The goal is not to replicate Cursor. The goal is to deepen Rig's existing seams so that governed agents can operate with the same operational efficiency as ungoverned ones — without sacrificing the governance contract.**

---

## Decisions

### Decision 1: Agent Orchestrator Loop (Governed ReAct)

**Problem**: `WorktreeExecutor` treats each execution as an atomic, single-shot operation. Real agent workflows require iterative loops: the agent reasons, acts, observes results, and decides what to do next. Currently, the loop lives entirely outside Rig — in the external AI tool (Gemini, Cursor, Claude Code). This means:
- Rig has no visibility into the *reasoning* steps
- Governance can only gate individual actions, not trajectories
- Evidence captures execution but not decision context

**Decision**: Create an `AgentOrchestrator` that owns the governed iteration loop.

```python
# src/rig/domain/execution/orchestrator.py

class AgentOrchestrator:
    """Governed agent loop: reason → propose → gate → execute → observe → repeat.
    
    The orchestrator does NOT contain AI reasoning. It is a control loop that:
    1. Receives agent intents (from external model or local tool)
    2. Routes each intent through GovernanceEngine.evaluate()
    3. Delegates allowed intents to WorktreeExecutor
    4. Collects observations (execution results, projections)
    5. Emits trajectory events for evidence and telemetry
    6. Enforces loop budget (max steps, max tokens, max wall time)
    
    The orchestrator is the GOVERNED alternative to letting agents
    call tools directly without oversight.
    """
    
    @classmethod
    def from_workspace(
        cls,
        workspace_id: str,
        repo_root: Path,
        gate_policy: WorkflowGatePolicy,
        budget: OrchestratorBudget,
    ) -> "AgentOrchestrator":
        """Factory: workspace-scoped, budget-bounded, governance-wired."""
    
    def step(self, intent: Intent) -> StepResult:
        """Execute one governed step in the agent loop.
        
        1. Evaluate intent against GovernanceEngine
        2. If blocked → return GateDecision with reason
        3. If allowed → acquire lease, execute, collect observation
        4. Emit TrajectoryEvent to evidence stream
        5. Return StepResult (observation + governance metadata)
        """
    
    def get_trajectory(self) -> List[TrajectoryEvent]:
        """Full trajectory of this orchestration session."""
    
    @property
    def budget_remaining(self) -> OrchestratorBudget:
        """Remaining budget (steps, tokens, wall time)."""
```

**Architecture constraints**:
- Orchestrator does NOT own AI model selection or routing — that remains external
- Orchestrator does NOT contain reasoning logic — it is a governed control loop
- Each `step()` produces a `TrajectoryEvent` that is persisted through current receipt/evidence mechanisms (converges into EvidenceDomain when ADR 0008 is resolved)
- Budget enforcement is local and deterministic, not model-dependent
- The orchestrator uses `WorktreeExecutor` internally, not subprocess directly

**What this is NOT**: This is not an "auto-agent" that runs autonomously. It is infrastructure for *governing* agent loops that already exist in external tools (Gemini, Cursor, Claude Code). The external tool calls `step()` instead of executing commands directly.

### Decision 2: Context Retrieval Seam

**Problem**: Agents operating on Rig-managed codebases need surgical context retrieval — not the entire codebase, but the exact functions, classes, and scopes relevant to their current task. Currently, context is whatever the external tool happens to provide. Rig has no opinion on context quality.

**Decision**: Define a `ContextRetrieval` protocol that Rig can use to provide governed context to agents, without owning the indexing infrastructure itself.

```python
# src/rig/domain/execution/context_retrieval.py

@runtime_checkable
class ContextRetriever(Protocol):
    """Protocol for providing surgical context to agent orchestration.
    
    Implementations may use:
    - Local CLI tools (rg, fd, ctags, ast-grep) — preferred per user rules
    - Anigma MCP server's context_search tool
    - External vector databases
    
    Rig does NOT own the retrieval implementation. Rig owns the SEAM.
    """
    
    def retrieve(
        self,
        query: str,
        scope: ContextScope,
        budget_tokens: int,
    ) -> ContextBundle:
        """Retrieve relevant context within token budget.
        
        Returns ranked, deduplicated context chunks with provenance.
        Never exceeds budget_tokens.
        """

class ContextScope:
    """Defines retrieval boundaries — workspace, paths, file patterns."""
    workspace_id: str
    include_paths: List[str]  # Glob patterns
    exclude_paths: List[str]  # Glob patterns
    
class ContextBundle:
    """Retrieved context with provenance metadata."""
    chunks: List[ContextChunk]
    total_tokens: int
    retrieval_method: str  # "rg", "ctags", "ast-grep", "anigma-mcp", etc.
    
class ContextChunk:
    """Single chunk of retrieved context."""
    file_path: str
    start_line: int
    end_line: int
    content: str
    relevance_score: float  # 0.0-1.0, implementation-defined
    chunk_type: str  # "function", "class", "scope", "file", "snippet"
```

**Architecture constraints**:
- Rig owns the protocol; implementations are adapters
- Preferred implementation uses local CLI tools (rg, fd, ctags, ast-grep) per user tooling preferences
- Anigma MCP's `context_search` is a valid adapter
- Context retrieval is **not** required for orchestration — it enhances it
- Retrieval provenance is part of trajectory evidence
- ContextScope respects workspace boundaries — agents cannot retrieve outside their worktree

### Decision 3: Ephemeral Worktree Lifecycle for Agents (Reserved Seam — Deferred)

**Problem**: Rig's `WorkspaceDomain` manages worktrees for human developers. Agent-driven workflows need ephemeral, automatically-managed worktrees that:
- Are created at orchestration session start
- Are scoped to the agent's task
- Are cleaned up after merge-or-discard
- Support sparse checkouts (only the directories the agent needs)

Currently, `workspace.py` has worktree creation but no ephemeral lifecycle semantics.

**Decision**: **Reserve the seam; defer implementation until WorkspaceDomain Authority (ADR 0007) is accepted and stabilized.** The types `EphemeralWorktreeSpec` and `EphemeralWorktree` are defined here as the intended contract but are NOT implemented in the first slice.

> [!WARNING]
> Do NOT implement ephemeral worktree lifecycle until `WorkspaceDomain` (ADR 0007) owns worktree authority. Premature implementation would create a second worktree management surface with unclear ownership.

**Reserved contract** (for future implementation on `WorkspaceDomain`):

```python
# Future extension to WorkspaceDomain (ADR 0007) — NOT implemented now

@dataclass(frozen=True)
class EphemeralWorktreeSpec:
    """Specification for an agent's ephemeral worktree."""
    task_description: str
    sparse_paths: Optional[List[str]]  # If set, sparse checkout these paths only
    base_ref: str  # Git ref to base the worktree on (default: HEAD)
    ttl_seconds: float  # Auto-cleanup after TTL
    agent_id: str  # For audit lineage
    
@dataclass(frozen=True)
class EphemeralWorktree:
    """Managed ephemeral worktree with automatic lifecycle."""
    worktree_path: Path
    branch_name: str  # agent/<task>/<agent> pattern per AGENTS.md
    sparse_paths: Optional[List[str]]
    created_at: str
    expires_at: str
    agent_id: str
```

**Architecture constraints** (apply when implemented):
- Ephemeral worktrees use existing git worktree primitives
- Branch naming enforced by AGENTS.md conventions: `agent/<task>/<agent>`
- Sparse checkout is optional — full worktree is the safe default
- Cleanup is idempotent and non-destructive (marks for cleanup, does not force-delete)
- Worktree creation produces evidence through current receipt/evidence mechanisms
- Agent must never operate on main worktree directly — ephemeral isolation is mandatory for automated execution

**Deferred because**: `WorkspaceDomain` (ADR 0007) is not yet accepted. Implementing ephemeral lifecycle without workspace authority would scatter worktree management across two surfaces.

### Decision 4: Context Compaction Protocol

**Problem**: Long-running agent sessions accumulate massive amounts of tool output, terminal logs, and intermediate observations. Without compaction, the agent's context window fills with stale, redundant information, degrading reasoning quality. Production agentic systems reportedly address this with algorithmic context compaction — structured summarization triggered at a token threshold.

Rig cannot control the external model's context window. But Rig *can* compact the trajectory and observation data that it provides back to the agent through the orchestrator.

**Decision**: Add compaction semantics to the orchestrator's trajectory.

```python
# src/rig/domain/execution/compaction.py

class CompactionPolicy:
    """Policy for trajectory compaction."""
    trigger_threshold_tokens: int  # Compact when trajectory exceeds this
    target_tokens: int  # Target size after compaction
    preserve_recent_steps: int  # Never compact the N most recent steps
    preserve_error_steps: bool  # Always keep error observations in full
    
class CompactedTrajectory:
    """Compacted view of agent trajectory.
    
    Preserves:
    - Recent N steps in full
    - Error steps in full
    - Governance decision points in full
    - Older steps summarized to: intent + outcome + key metadata
    
    Strips:
    - Verbose stdout from successful executions
    - Redundant stderr output
    - Intermediate projection states
    """
    full_steps: List[TrajectoryEvent]  # Recent + errors + governance decisions
    summarized_steps: List[TrajectoryEventSummary]  # Compressed older steps
    total_original_tokens: int
    total_compacted_tokens: int
    compaction_metadata: CompactionMetadata
```

**Architecture constraints**:
- Compaction is deterministic and reproducible given the same trajectory
- Compaction never discards governance events or error observations
- The full, uncompacted trajectory is always preserved through current receipt/evidence mechanisms (converges into EvidenceDomain when ADR 0008 is resolved)
- Compaction output is advisory — agents may or may not use it
- Compaction does NOT use AI summarization (no model dependency). It uses structural rules: keep recent, keep errors, keep governance, summarize the rest

### Decision 5: Execution Telemetry Feedback Seam

**Problem**: `ExecutionTelemetrySample` exists as a data model but has no feedback channel. Agent execution produces rich operational data (which tools succeed/fail, latency, output patterns, governance violations). This data should feed back into agent behavior recommendations — not through RL training (Rig doesn't own models), but through operational statistics that inform gate policy and budget tuning.

**Decision**: Extend the telemetry model into a feedback seam.

```python
# Extension to src/rig/domain/execution_telemetry.py

class AgentSessionTelemetry:
    """Aggregated telemetry for a complete agent orchestration session."""
    session_id: str
    agent_id: str
    workspace_id: str
    
    # Execution metrics
    total_steps: int
    successful_steps: int
    failed_steps: int
    governance_blocked_steps: int
    
    # Resource metrics
    total_wall_time_seconds: float
    total_tokens_consumed: int  # Estimated from trajectory
    context_compactions: int
    
    # Tool usage patterns
    tool_usage: Dict[str, ToolUsageStats]  # tool_name → stats
    
    # Governance metrics
    gate_evaluations: int
    gate_blocks: int
    gate_escalations: int
    
    # Outcome
    session_outcome: str  # "completed", "budget_exhausted", "governance_blocked", "error"
    
class ToolUsageStats:
    """Per-tool usage statistics."""
    invocations: int
    successes: int
    failures: int
    avg_latency_ms: float
    total_output_tokens: int
```

**Architecture constraints**:
- Telemetry is observational only — it does NOT influence governance decisions in real time
- Telemetry is persisted through current receipt/evidence mechanisms as `TelemetrySummaryReceipt` (converges into EvidenceDomain when ADR 0008 is resolved)
- Aggregation happens at session end, not per-step (avoids latency overhead)
- Telemetry data feeds `rig doctor` for agent health recommendations
- No model-specific telemetry — tool-level and governance-level only

---

## Consequences

### What Changes

| Component | Before | After |
|-----------|--------|-------|
| Agent execution | Single-shot `WorktreeExecutor.execute()` | Iterative `AgentOrchestrator.step()` with budget + governance |
| Context provision | External tool's responsibility | `ContextRetriever` protocol with governed scope |
| Agent isolation | Manual worktree management | `EphemeralWorktree` seam reserved (deferred to ADR 0007) |
| Long sessions | Unbounded context growth | `CompactionPolicy` with structural summarization |
| Execution data | Fire-and-forget `ExecutionReceipt` | `AgentSessionTelemetry` with tool-level analytics |

### What Does NOT Change

- **Governance narrative**: Models propose, Rig disposes. Unchanged.
- **Evidence lineage**: All execution produces receipts. Unchanged.
- **Proposal lifecycle**: Decoded → Registered → Accepted → Applied. Unchanged.
- **Git Guard**: Destructive operations blocked at shell level. Unchanged.
- **Authority model**: Rig is authority, agents are advisors. Unchanged.
- **External model selection**: Rig does not route between models. Unchanged.

### Leverage

One orchestrator replaces ad-hoc agent execution patterns. Currently: each agent tool integration manually implements lease → execute → receipt. After: call `orchestrator.step(intent)` and governance + evidence + telemetry happen automatically.

### Locality

All agent workflow concerns concentrated in `execution/` package. Currently: `WorktreeExecutor` (execution), `agent_workflow_gates.py` (policy), `execution_telemetry.py` (metrics) are loosely connected. After: orchestrator wires them into a coherent loop.

### Testability

Test agent workflows through `AgentOrchestrator.step()` interface. Mock `GovernanceEngine` + `WorktreeExecutor` + `ContextRetriever`. Test trajectories as sequences of `(intent, gate_decision, observation)` triples.

### Risk

**Medium**. This creates new infrastructure but does NOT modify existing execution paths. `WorktreeExecutor` remains the low-level execution engine. `AgentOrchestrator` is a new consumer, not a replacement.

---

## Files Involved

### New files
- `src/rig/domain/execution/orchestrator.py` — Agent orchestrator with governed loop (~200 lines)
- `src/rig/domain/execution/context_retrieval.py` — ContextRetriever protocol + types (~80 lines)
- `src/rig/domain/execution/compaction.py` — CompactionPolicy + CompactedTrajectory (~100 lines)
- `src/rig/domain/execution/trajectory.py` — TrajectoryEvent + TrajectoryEventSummary types (~60 lines)
- `src/rig/domain/execution/budget.py` — OrchestratorBudget type (~30 lines)

### Modified files
- `src/rig/domain/execution_telemetry.py` — Add `AgentSessionTelemetry`, `ToolUsageStats` (~50 lines added)
- `src/rig/domain/agent_workflow_gates.py` — No change (Gate A policy consumed as-is by orchestrator)
- `src/rig/domain/workspace.py` — Future: ephemeral worktree methods (deferred to ADR 0007 implementation)

### Unchanged files
- `src/rig/domain/execution/executor.py` — WorktreeExecutor remains the low-level engine
- `src/rig/domain/execution/models.py` — Execution models remain stable
- `src/rig/domain/governance/engine.py` — GovernanceEngine consumed as-is
- `src/rig/domain/runtime_streaming/__init__.py` — Streaming domain unchanged

---

## Migration Path

### Slice 0: Types Only (first implementation — safe to land now)

Create pure data types. No executor wiring. No WorkspaceDomain changes. No RuntimeStreaming changes.

1. Create `src/rig/domain/execution/trajectory.py` — `TrajectoryEvent`, `TrajectoryEventSummary`, `StepResult`
2. Create `src/rig/domain/execution/budget.py` — `OrchestratorBudget`
3. Create `src/rig/domain/execution/context_retrieval.py` — `ContextRetriever` protocol, `ContextScope`, `ContextBundle`, `ContextChunk`
4. Create `src/rig/domain/execution/compaction.py` — `CompactionPolicy`, `CompactedTrajectory`, `CompactionMetadata`
5. All types must be: pure data, frozen/immutable where possible, deterministic, serializable, import without side effects
6. Tests proving: types import cleanly, are constructible, are serializable if relevant, produce no side effects on import

**Do NOT create**: `AgentOrchestrator`, executor wiring, WorkspaceDomain extensions, RuntimeStreaming changes.

### Phase 2: Orchestrator Core (future — after Slice 0 review)
7. Create `orchestrator.py` with `AgentOrchestrator`
8. Wire `step()` to `GovernanceEngine.evaluate()` → `WorktreeExecutor.execute()`
9. Implement budget enforcement (max steps, max wall time)
10. Implement trajectory recording
11. Tests: governed step sequences, budget exhaustion, governance blocks

### Phase 3: Context Retrieval Adapter (future)
12. Create CLI-tools adapter (rg + fd + ctags) as default `ContextRetriever`
13. Create Anigma MCP adapter as optional `ContextRetriever`
14. Wire to orchestrator (optional — orchestrator works without retrieval)
15. Tests: retrieval within scope boundaries, token budget enforcement

### Phase 4: Compaction Implementation (future)
16. Implement structural compaction rules in `compaction.py`
17. Wire to orchestrator trajectory
18. Tests: compaction preserves errors and governance events, meets token target

### Phase 5: Ephemeral Worktrees (blocked on ADR 0007)
19. Requires `WorkspaceDomain` deepening to be accepted and stable
20. Add ephemeral lifecycle methods to deepened workspace module
21. Wire to orchestrator session start/end

### Phase 6: Telemetry Integration (future)
22. Implement `AgentSessionTelemetry` aggregation at session end
23. Wire to current receipt/evidence mechanisms as `TelemetrySummaryReceipt`
24. Add `rig doctor` agent health recommendations
25. Tests: telemetry accuracy, receipt creation

---

## Appendix A: Rig vs. Commercial Agent Systems — Philosophical Divergence

The transcript describes systems that optimize for **speed and autonomy**: "politely ask you to step away from the keyboard." Rig optimizes for **governance and evidence**: "the model proposes, Rig disposes."

This is not a deficiency. It is a design choice that trades maximum agent speed for:

1. **Audit trail** — Every agent action produces forensic-grade evidence
2. **Governance checkpoints** — Agents cannot bypass gate evaluation
3. **Reproducibility** — Trajectory + evidence enables exact replay
4. **Trust boundary** — Ephemeral worktrees ensure agents cannot corrupt main
5. **Budget control** — Resource consumption is bounded and visible

The refinements in this ADR bring Rig's *operational efficiency* closer to commercial systems while **preserving** the governance contract that makes Rig unique.

## Appendix B: Terminology Mapping (Inferred)

> [!NOTE]
> The "Commercial Pattern" column reflects patterns described in promotional materials. Specific implementation claims are editorial interpretation, not verified engineering documentation.

| Commercial Pattern (Inferred) | Rig Equivalent | Relationship |
|------------------------------|----------------|--------------|
| Auto mode / Model router | External — Rig does not own model selection | Explicit non-goal |
| Orchestrator (ReAct loop) | `AgentOrchestrator` | Governed control loop, not autonomous |
| Context retrieval / RAG | `ContextRetriever` protocol | Seam with local-CLI-preferred adapter |
| Per-agent isolated workspaces | `EphemeralWorktree` via `WorkspaceDomain` (deferred) | Reserved seam, per-agent isolation with TTL |
| Context compaction | `CompactionPolicy` | Structural rules, no AI summarization |
| Inference optimization | External — Rig does not own model inference | Explicit non-goal |
| Custom in-house model | External — any model via intake | Models are advisors, not authority |
| Execution telemetry | `AgentSessionTelemetry` → evidence | Observational, feeds `rig doctor` |
| Shadow workspaces | Existing: `WorkspaceDomain` + worktree primitives | Already architectural advantage |
| Async cloud execution | Future: not in scope for this ADR | Potential follow-up |

---

## Summary

This ADR proposes five targeted refinements to Rig's agentic workflow infrastructure:

1. **AgentOrchestrator** — A governed ReAct loop that gates every agent step through governance
2. **ContextRetriever** — A protocol seam for surgical context provision with local-CLI-preferred adapters
3. **EphemeralWorktree** — Reserved seam for agent isolation (deferred to ADR 0007 stabilization)
4. **CompactionPolicy** — Deterministic trajectory compaction for long-running sessions
5. **AgentSessionTelemetry** — Tool-level analytics feeding evidence and operational health

Each refinement deepens an existing Rig seam rather than creating new abstractions. The governance contract — models propose, Rig disposes — remains inviolate.
