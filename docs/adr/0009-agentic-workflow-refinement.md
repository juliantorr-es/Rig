# Agentic Workflow Refinement

**ADR 0009**

Rig's agentic workflow infrastructure — the governed pipeline from intent to proposal to evidence — is architecturally sound but operationally shallow in several areas exposed by studying production multi-agent systems at scale. This ADR proposes targeted refinements to deepen Rig's agent orchestration, context retrieval, isolation, and telemetry capabilities **within the established governance narrative**: models propose, Rig disposes.

**Status**: proposed / concept accepted pending ADR index reconciliation; implementation limited to declared slices

> [!IMPORTANT]
> ADR numbering and cross-references in this document depend on the ADR index being stabilized. Before this ADR can be accepted, verify that the Related ADR numbers below match the canonical index in `docs/adr/README.md`. Known drift exists between ADR 0007/0008 filenames and their cross-references.

> [!NOTE]
> **Workflow Narrative**: This ADR is the umbrella for agent workflow refinement. The canonical workflow is: **ADR → Sprint → Sprint Research → Mission → Merge-Friendliness Check → Patch Batch → Evidence → Review/Promotion**. Sprint Research is mandatory read-only planning before implementation. Patch batches group coherent changes for reliable application. Patch batches require merge-friendliness preflight check before apply. Missions are substantial, agent-sized work packets. Do not create nested subtasks or recursive missions. See `docs/workflow/adr-sprint-mission-evidence.md` for the authoritative operational narrative.

**Related ADRs**:
- [0003 Governance Engine Deepening](0003-governance-engine-deepening.md) — agent orchestration feeds governance evaluation
- [0004 Runtime Streaming Consolidation](0004-runtime-streaming-consolidation.md) — Runtime Streaming may transport/propagate orchestration events as an operational stream; it does **not** own agent orchestration semantics (those belong to the execution domain)
- [0007 Workspace Domain Authority](0007-workspace-domain-authority.md) — worktree isolation is the backbone of agent sandboxing; ephemeral worktree lifecycle (Decision 4) is deferred until this ADR is accepted
- [0008 Receipt/Evidence Unification](0008-receipt-evidence-unification.md) — agent trajectory evidence flows through current receipt/evidence mechanisms now, converging into EvidenceDomain when ADR 0008 is resolved

**Explicit non-goals**:
1. **Rig does not become an autonomous coding IDE.** Rig governs external agent loops. The orchestrator provides governance infrastructure for agent workflows that originate in external tools (Gemini, Cursor, Claude Code, etc.). It does not autonomously plan, reason, or execute.
2. **No recursive subtasks.** Rig's agent workflow uses bounded missions and append-only progress evidence. We explicitly reject GitHub-style recursive issue trees and nested missions.
3. **Rig does not use optimized/encoded context as governance authority.** Governance decisions always use canonical paths, native actions, policies, and evidence.

---

## Dogfood Bridge: Sprint Research, Missions, and Patch Batches

Before `AgentOrchestrator` owns executable trajectories, ADR implementation work uses ADR-local progress ledgers (`.rig/work/adr/<adr-id>/progress.jsonl`) and sprint research artifacts. These ledgers and artifacts are append-only operational evidence for human/agent workflow coordination. They are the bootstrap migration path into formal TrajectoryEvents and receipts.

**The Boundary**:
- **Sprint Research** = Mandatory read-only planning phase. Identifies files, assesses state, proposes missions, plans patch batches.
- **Mission** = Delegated work contract (human-facing scope). Substantial, agent-sized work packet. Not a micro-task or subtask.
- **Patch Batch** = Coherent set of related changes applied together. Prechecked and validated.
- **Intent** = Proposed action inside a mission.
- **TrajectoryEvent** = Evidence of a governed execution step.
- **Receipt** = Durable governance/evidence artifact.
- **Merge-Friendliness** = Preflight check that a patch batch is safe to apply relative to active worktrees.

Sprint Research defines the scope; missions provide execution contracts; merge-friendliness checks prevent conflicts with active worktrees; patch batches group reliable changes; trajectory events record what happened; receipts provide durable evidence. Do not collapse these concepts.

**Merge-Friendliness Rules**:
- Patch batches require merge-friendliness preflight before apply.
- Agents must not apply patches blindly while other worktrees are active.
- Dirty same-file overlap in another worktree blocks by default.
- Same-directory overlap warns.
- Merge simulation is advisory/preflight only and does not mutate worktrees.

**Note on "Slice" terminology**: This ADR uses "Slice 0", "Slice 0.5", "Slice 0.8", etc. to describe implementation phases only. These are NOT workflow hierarchy levels. Slices are internal staging for ADR 0009 implementation. The workflow hierarchy stops at Mission. Do not use "slice" as a workflow concept.

**ADR Workspace Structure (Dogfood Bridge)**:
```
.rig/work/adr/<adr-id>/
  task.json
  progress.jsonl
  projection.json
  exports/                    # Optional dataset exports
    events.csv
    missions.csv
    patch_batches.csv
    validations.csv
    findings.csv
    schema.json
    dataset_card.md
  notes/
    out-of-scope-findings.md
  sprints/
    <sprint-id>/
      research_summary.md
      repo_inventory.md
      mission_plan.json
      patch_batches/
        <batch-id>.patch
        <batch-id>_plan.json
```

**Merge-Friendliness Discovery**:
- Worktrees are discovered using `git worktree list --porcelain -z`
- Additional worktrees under `.rig/worktrees/` are also checked
- Dirty worktree state is detected using `git status --porcelain=v1`
- Patch file contents are parsed for touched files (diff --git headers)
- `git apply --check` is used for precheck
- `git merge-tree` is used for merge simulation when available

---

## Context: External Architecture Signals and Inferred Patterns

The following patterns are **inferred from public marketing materials, developer blog posts, and a promotional video transcript** describing Cursor 3's multi-agent system. Implementation details below are editorial interpretation, not verified architecture documentation. They are included as directional signals for where production agentic systems appear to be converging.

> [!NOTE]
> **Provenance**: Patterns in this table are synthesized from promotional materials (no direct engineering documentation). Specific implementation claims are presented as described in those sources and may reflect marketing framing rather than verified architecture.

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

---

## Decisions

### Decision 1: Governed Agent Orchestrator

**Problem**: `WorktreeExecutor` treats each execution as an atomic, single-shot operation. Real agent workflows require iterative loops: the agent reasons, acts, observes results, and decides what to do next. Currently, the loop lives entirely outside Rig, meaning Rig has no visibility into reasoning steps, governance only gates individual actions, and evidence captures execution but not decision context.

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
    """
    
    def step(self, intent: SemanticIntent) -> StepResult:
        """Execute one governed step in the agent loop."""
```

**Architecture constraints**:
- Orchestrator does NOT own AI model selection or routing — that remains external.
- Orchestrator does NOT contain reasoning logic — it is a governed control loop.
- Each `step()` produces a `TrajectoryEvent` that is persisted through current receipt mechanisms.
- Budget enforcement is local and deterministic, not model-dependent.

### Decision 2: Deterministic Agent Substrate

**Problem**: External coding agents vary in how they call tools and handle context. Smaller models may be unreliable at exact tool-call syntax. If Rig exposes raw tools directly, every agent integration must solve its own routing, validation, and sandboxing.

**Decision**: Rig introduces a deterministic agent substrate between external agents and local execution.
Agents submit semantic intents. Rig normalizes those intents into native governed actions, routes them through a constrained tool registry, executes them inside approved sandboxes, and returns normalized observations with provenance.

This substrate has three core parts:
1. `SemanticIntent`: Agent-proposed semantic action, not yet authorized.
2. `NativeAction`: Rig-normalized action after deterministic routing.
3. `ToolRouteDecision`: Explains how Rig mapped semantic intent to native action.

Sandbox execution is consumed by the substrate but implemented later under the Worktree/Sandbox Boundary. Slice 1 defines routing types only; it does not execute actions.

**Routing Rule**:
If routing is ambiguous, Rig must not let the agent improvise. It must return a structured block explaining the ambiguity. The safe default is: *if ambiguous, choose read-only orientation when possible. Never choose mutation by inference.*

### Decision 3: Context Retrieval and Context Engineering

**Problem**: Long-running agent workflows need stable, reusable, bounded, and reconstructable context. If every step rebuilds context differently, Rig loses cache locality, auditability, and deterministic replay.

**Decision**: Define a deterministic context engineering protocol and retrieval seam.

1. **Context Retrieval Seam**: A protocol (`ContextRetriever`) for surgical codebase context. Rig owns the protocol, implementations are adapters.
   - **v0 Implementation**: Local CLI tools only (`rg`, `fd`). No persistent index, daemon, vector store, or semantic cache is introduced in v0. `Anigma MCP` is an optional adapter.
   - Respects workspace boundaries.

2. **Deterministic Context Engineering Protocol**: Rig represents agent context as ordered, typed `ContextBlock` values assembled into a `ContextPacket`. Packets are deterministic given the same inputs and budget.

```python
# Type sketch for Context Engineering
class ContextBlock:
    kind: str # system | adr | policy | retrieved | observation
    content: str
    metadata: dict

class ContextPacket:
    blocks: list[ContextBlock]
    budget_used: int
    alias_table: dict[str, str]

class ContextAliasTable:
    # Deterministic mapping logic
    pass

class ContextAssemblyPolicy:
    # Rules for assembling and compacting packets
    pass
```

   - **Ordering Rule** (most stable to most volatile): System/Governance → ADR/Mission → Policy → Retrieved Code → Recent Observations → Current Result → Out-of-scope Findings. This maximizes prompt-cache locality.
   - **Canonicalization Rule**: Normalized line endings, stable JSON keys, stable path sorting, no random retrieval order.
   - **Reconstruction Rule**: Every packet must be reconstructable from durable inputs.

3. **Context Alias Table**: Rig may replace repeated repo-specific strings with deterministic aliases inside context packets (e.g., `@ADR` → `docs/adr/0004.md`). Aliases are session-local, deterministic, and reversible.

4. **Structural Trajectory Compaction**: Rig may compact older observations into deterministic summaries that preserve intent, command, status, governance, and changed files. **No AI summarization** in v0. Compaction is structural and deterministic.

5. **Experimental Dense Encoding**: Rig may evaluate dense context encodings (including bilingual or non-English recoding) only as an experimental optimization layer.
   - **The canonical representation is the authority. The optimized representation is never the authority.**
   - Evidence uses canonical context. Lossy encodings must be marked advisory.

### Decision 4: Worktree/Sandbox Boundary (Reserved Seam)

**Problem**: Agents need isolated environments.

**Decision**: Reserve the seam for ephemeral worktree lifecycle management; **defer implementation until WorkspaceDomain Authority (ADR 0007) is accepted and stabilized.**

**Sandboxing rule**: Agents do not execute in the main worktree. Agents execute in existing approved worktrees under `.rig/worktrees/`. The substrate records the worktree path, branch, HEAD, allowed paths, and mission authority for every native action.

### Decision 5: Telemetry and Evidence Feedback

**Problem**: Agent execution produces rich operational data that currently has no feedback channel to inform gate policy and budget tuning.

**Decision**: Extend the telemetry model into a feedback seam (`AgentSessionTelemetry`).
- Telemetry is observational only; it does NOT influence governance decisions in real time. It may inform human-reviewed gate policy and budget tuning recommendations.
- Telemetry is persisted through current receipt/evidence mechanisms as `TelemetrySummaryReceipt`.
- **Note**: Health recommendations feeding `rig doctor` should be deferred until the orchestrator actually produces enough sessions to measure reliably.

---

## Consequences

### What Changes
- **Agent execution**: Moves from single-shot `WorktreeExecutor` to iterative `AgentOrchestrator.step()` atop a deterministic agent substrate.
- **Context provision**: External tool's responsibility → Deterministic context engineering with stable aliases, strict cache ordering, and structural compaction.
- **Context retrieval**: Rig provides a governed scope seam via local CLI tools.

### What Does NOT Change
- **Governance narrative**: Models propose, Rig disposes. Unchanged.
- **Evidence lineage**: All execution produces receipts. Unchanged.
- **Git Guard**: Destructive operations blocked at shell level. Unchanged.
- **External model selection**: Rig does not route between models. Unchanged.

### Leverage
One orchestrator and substrate replaces ad-hoc agent execution patterns. Governance, evidence, context optimization, and telemetry happen automatically inside the loop.

---

## Files Involved

*New files to be created, staged by slice:*

**Slice 0 files:**
- `src/rig/domain/execution/trajectory.py`
- `src/rig/domain/execution/budget.py`
- `src/rig/domain/execution/context_retrieval.py`
- `src/rig/domain/execution/compaction.py`

**Slice 0.5 files:**
- `src/rig/domain/execution/context_engineering.py`

**Slice 0.8 dogfood bridge files:**
- `scripts/work_status.py`
- `scripts/work_claim.py`
- `scripts/work_heartbeat.py`
- `scripts/work_note.py`
- `scripts/work_handoff.py`
- `scripts/work_doctor.py`
- `.rig/work/adr/<adr-id>/task.json`
- `.rig/work/adr/<adr-id>/progress.jsonl`

**Slice 1 files:**
- `src/rig/domain/execution/substrate.py`

**Slice 6 files:**
- `src/rig/domain/execution/orchestrator.py`

---

## Migration Path

### Slice 0: Pure Types (Implemented in eb65520)
Create pure data types. No executor wiring.
1. `trajectory.py`, `budget.py`, `context_retrieval.py`, `compaction.py`.

### Slice 0.5: Deterministic Context Engineering Types (in progress; untracked prototype exists)
1. `context_engineering.py` with `ContextBlock`, `ContextPacket`, `ContextAssemblyPolicy`.

### Slice 0.8: Dogfood Bridge (Current Phase)
1. ADR-local missions and progress ledgers as the bootstrap operational layer before AgentOrchestrator trajectories become first-class.

### Slice 1: Substrate Types (Future)
1. `SemanticIntent`, `NativeAction`, `ToolRouteDecision` types only.

### Slice 2: Tool Router (Future)
1. Tool router with read-only actions only (`file.search`, `file.read`).

### Slice 3: Context Assembly (Future)
1. Context alias table and ContextPacket hashing.
2. Structural compaction logic.

### Slice 4: Sandbox Execution (Future)
1. SandboxExecutor wrapper for approved worktrees.

### Slice 5: Mutation Gates (Future)
1. Mutation actions gated by `work_doctor` / governance.

### Slice 6: Orchestrator Loop (Future)
1. `AgentOrchestrator.step()` implementation and loop enforcement.

### Slice 7: Telemetry (Future)
1. `AgentSessionTelemetry` aggregation at session end.

### Blocked: Ephemeral Worktrees
- Blocked on ADR 0007 stabilization.

---

## Appendix: Terminology Mapping (Inferred)

| Commercial Pattern (Inferred) | Rig Equivalent | Relationship |
|------------------------------|----------------|--------------|
| Auto mode / Model router | External — Rig does not own model selection | Explicit non-goal |
| Orchestrator (ReAct loop) | `AgentOrchestrator` | Governed control loop, not autonomous |
| Context retrieval / RAG | `ContextRetriever` protocol | Seam with local-CLI-preferred adapter |
| Per-agent isolated workspaces | `EphemeralWorktree` via `WorkspaceDomain` | Reserved seam (deferred) |
| Context compaction | `CompactionPolicy` | Structural rules, no AI summarization |
| Inference optimization | Deterministic Context Engineering | Prefix stability, aliasing |
| Custom in-house model | External — any model via intake | Models are advisors, not authority |
| Execution telemetry | `AgentSessionTelemetry` → evidence | Observational |
| Shadow workspaces | Existing: `WorkspaceDomain` + worktree primitives | Already architectural advantage |
| Async cloud execution | Future: not in scope for this ADR | Potential follow-up |
