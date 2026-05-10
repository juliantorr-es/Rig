# Agentic Workflow Refinement

**ADR 0009**

Rig's agentic workflow infrastructure — the governed pipeline from intent to proposal to evidence — is architecturally sound but operationally shallow in several areas exposed by studying production multi-agent systems at scale. This ADR proposes targeted refinements to deepen Rig's agent orchestration, context retrieval, isolation, telemetry, and computable reasoning capabilities **within the established governance narrative**: models propose, Rig disposes.

**Status**: proposed / concept accepted pending ADR index reconciliation; implementation limited to declared slices

> [!IMPORTANT]
> ADR numbering and cross-references in this document depend on the ADR index being stabilized. Before this ADR can be accepted, verify that the Related ADR numbers below match the canonical index in `docs/adr/README.md`. Known drift exists between ADR 0007/0008 filenames and their cross-references.

> [!NOTE]
> **Workflow Narrative**: This ADR is the umbrella for agent workflow refinement. The canonical workflow is: **ADR → Sprint → Sprint Research → Mission → Merge-Friendliness Check → Patch Batch → Evidence → Review → Preproduction Promotion**. Sprint Research is mandatory read-only planning before implementation. Patch batches group coherent changes for reliable application. Patch batches require merge-friendliness preflight check before apply. Preproduction promotion is governed by the **Rite of Deterministic Passage** — a sequence of 13 deterministic gates that must all pass before agent work may be merged into the local `preproduction` branch. Missions are substantial, agent-sized work packets. Do not create nested subtasks or recursive missions. See `docs/workflow/adr-sprint-mission-evidence.md` for the authoritative operational narrative and the full Rite of Deterministic Passage specification.

**Related ADRs**:
- [0003 Governance Engine Deepening](0003-governance-engine-deepening.md) — agent orchestration feeds governance evaluation
- [0004 Runtime Streaming Consolidation](0004-runtime-streaming-consolidation.md) — Runtime Streaming may transport/propagate orchestration events as an operational stream; it does **not** own agent orchestration semantics (those belong to the execution domain)
- [0007 Workspace Domain Authority](0007-workspace-domain-authority.md) — worktree isolation is the backbone of agent sandboxing; ephemeral worktree lifecycle (Decision 4) is deferred until this ADR is accepted
- [0008 Receipt/Evidence Unification](0008-receipt-evidence-unification.md) — agent trajectory evidence flows through current receipt/evidence mechanisms now, converging into EvidenceDomain when ADR 0008 is resolved

**Explicit non-goals**:
1. **Rig does not become an autonomous coding IDE.** Rig governs external agent loops. The orchestrator provides governance infrastructure for agent workflows that originate in external tools (Gemini, Cursor, Claude Code, etc.). It does not autonomously plan, reason, or execute.
2. **No recursive subtasks.** Rig's agent workflow uses bounded missions and append-only progress evidence. We explicitly reject GitHub-style recursive issue trees and nested missions.
3. **Rig does not use optimized/encoded context as governance authority.** Governance decisions always use canonical paths, native actions, policies, and evidence.
4. **Rig does not embed opaque hidden memory.** Facts in this ADR are durable, typed, and reconstructable from observable sources. They are not chatbot context caches or private embedding stores.

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

## Computable Substrate: Local Reasoning Without Authority Drift

Rig is moving toward a local computable knowledge substrate for governed software work. This substrate is not "memory" and not a chatbot context cache. It is a portable, model-agnostic layer that turns operational reality into typed facts that Rig can validate, compute over, constrain, and record before authority is granted to execute or promote.

The key architectural claim is simple:

**LLM layer proposes and explores. Computable substrate validates and normalizes. Rig authority decides and gates.**

### Layer Split

- **LLM layer**
  - proposes
  - summarizes
  - translates
  - prioritizes
  - explores

- **Computable substrate**
  - validates
  - computes
  - proves
  - constrains
  - classifies
  - normalizes

- **Rig authority layer**
  - decides
  - gates
  - records
  - promotes
  - rejects

### Typed Facts

The substrate is composed of typed facts derived from observable sources:

- repository state
- worktree state
- validator outputs
- proposal traces
- tool executions
- receipts
- governance events

Facts are normalized into deterministic graph, rule, and constraint representations before promotion or execution authority is granted.

### Examples of Computable Work

The substrate should make these classes of reasoning first-class:

- dependency graph cycle analysis
- validator authority classification
- worktree safety reasoning
- proposal admissibility checks
- statistical benchmark interpretation
- deterministic repair suggestions
- graph and topology projections

### Candidate Backends

The substrate is backend-agnostic. Potential implementations may include:

- graph engines
- symbolic math systems
- constraint solvers
- deterministic rule engines
- repository topology analyzers
- structured evidence stores

These backends are implementation options, not authority sources. Authority remains inside Rig governance.

**Merge-Friendliness Rules**:
- Patch batches require merge-friendliness preflight before apply.
- Agents must not apply patches blindly while other worktrees are active.
- Dirty same-file overlap in another worktree blocks by default.
- Same-directory overlap warns.
- Merge simulation is advisory/preflight only and does not mutate worktrees.

**Preproduction Promotion Rules (Rite of Deterministic Passage)**:
- **Agents must NOT run `git merge` directly** — Direct git merge is forbidden under all circumstances.
- **Agents may ONLY promote through `scripts/work_promote.py`** — This is the sole authorized path for preproduction promotion.
- **Target is restricted to `preproduction` only** — main/production remain human-governed and out of scope.
- **All 13 deterministic gates must pass** before promotion executes. Gates: sprint research, mission handoff, patch batches prechecked, merge-friendliness, work_doctor, required tests, out-of-scope findings, clean source branch, HEAD recorded, preproduction exists, merge simulation passes, clean preproduction worktree.
- **Failed gates append `preproduction_promotion_blocked` event** to the ledger and **must not mutate branches**.
- **Promotion is fully auditable** through ADR-local progress ledger events.
- **Merge simulation uses `git merge-tree`** for non-mutating preflight check.
- **`--dry-run` mode** shows gate results without executing promotion.
- **Preproduction is integration/local only** — production/main remains human-governed and out of scope.

**Note on "Slice" terminology**: This ADR uses "Slice 0", "Slice 0.5", "Slice 0.8", etc. to describe implementation phases only. These are NOT workflow hierarchy levels. Slices are internal staging for ADR 0009 implementation. The workflow hierarchy stops at Mission. Do not use "slice" as a workflow concept.

**ADR Workspace Structure (Dogfood Bridge)** with Rite of Deterministic Passage promotion:
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

### Decision 2.5: Computable Reasoning Substrate

**Problem**: Agent proposals, validator output, worktree topology, and receipt evidence already contain enough structure to support deterministic reasoning. Today that structure is scattered across logs and ad hoc interpretation. Rig needs a governed substrate that can normalize these observations into computable forms before execution or promotion authority is granted.

**Decision**: Introduce a computable reasoning substrate that sits below orchestration and above authority. It receives typed operational facts, normalizes them into deterministic representations, and produces evidence-backed projections that Rig can use for gating, remediation, and review.

This substrate is explicitly:

1. **Portable** — no single backend is mandatory.
2. **Model-agnostic** — orchestration models are replaceable.
3. **Deterministic-first** — prefer computation, rules, and constraints over probabilistic inference whenever feasible.
4. **Governed** — Rig remains the authority for all decisions that change state or grant execution rights.

**Examples**:
- Build a dependency graph from repository metadata and reject promotions that introduce cycles.
- Classify validator output into admissible, advisory, blocked, or requires-human-review states.
- Reason about worktree safety from branch, HEAD, dirty-state, and allowed-path facts.
- Check proposal admissibility against mission scope, gate policy, and evidence lineage.
- Interpret benchmark results deterministically before any model summary is accepted.
- Generate repair suggestions from constraints and topology instead of from free-form agent guesswork.
- Project graph/topology facts into reviewable evidence snapshots.

**Remediation rule**:
When the substrate can derive a safe deterministic repair, Rig may surface it as a constrained suggestion. The suggestion is still advisory until Rig authority accepts it.

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
- **Reasoning substrate**: Typed facts, deterministic projections, and constrained remediation become first-class governance inputs.

### What Does NOT Change
- **Governance narrative**: Models propose, Rig disposes. Unchanged.
- **Evidence lineage**: All execution produces receipts. Unchanged.
- **Git Guard**: Destructive operations blocked at shell level. Unchanged.
- **External model selection**: Rig does not route between models. Unchanged.
- **Authority location**: Deterministic computation informs Rig, but never replaces Rig's authority layer. Unchanged.

### Leverage
One orchestrator and substrate replaces ad-hoc agent execution patterns. Governance, evidence, context optimization, telemetry, and computable reasoning happen automatically inside the loop without elevating the model to authority.

---

## Machine-Readable Contract

**This ADR has a machine-readable JSON companion at `docs/adr/0009-agentic-workflow-refinement.json`.**

| Aspect | Human-Readable (Markdown) | Machine-Readable (JSON) |
|--------|-------------------------|-------------------------|
| **Purpose** | Explains the WHY: rationale, context, architectural decisions | Tells Rig WHAT to do: contracts, workflows, constraints |
| **Authority** | Rationale authority — the source of truth for understanding | Contract authority — the source of truth for automation |
| **Format** | Free-form Markdown prose | Structured JSON validated against `docs/schemas/rig-adr.schema.json` |

**Key Principle**: The Markdown explains the architectural rationale and must remain human-readable. The JSON contract enables Rig and external tools to parse, validate, and execute against this ADR programmatically. The JSON must conform to the schema; the Markdown must explain the thinking.

**Contract Fields:**
- `adr_id`: `adr0009` — canonical identifier
- `slug`: `agentic-workflow-refinement` — derived from title
- `workflow.worktree_name`: `adr0009-agentic-workflow-refinement` — canonical worktree directory
- `workflow.ledger_path`: `.rig/work/adr/adr0009-agentic-workflow-refinement` — ADR-local ledger
- `workflow.sprint_branch`: `sprint/adr0009-agentic-workflow-refinement` — default sprint branch
- `workflow.promotion_branch`: `promotion/adr0009-agentic-workflow-refinement` — promotion target
- `workflow.mission_branch_prefix`: `agent/adr0009-` — prefix for mission branches
- `authority_boundaries` — constraints agents must not cross
- `sprints` — implementation sprints with missions
- `validation_gates` — the 13 gates of the Rite of Deterministic Passage
- `related_adrs` — dependencies and relationships

**Validation**: Run `python3 -m jsonschema -i docs/adr/0009-agentic-workflow-refinement.json docs/schemas/rig-adr.schema.json` (requires jsonschema CLI) or use the test suite in `tests/test_rig_adr_contracts.py`.

**For new ADRs**: Create both `.md` and `.json` companions. The Markdown is for humans; the JSON is for machines. Do not delete the Markdown. Do not make tests depend on Markdown prose (except for existence checks).

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

## Workflow Command Chains

Agents run **workflow contexts** instead of manual command checklists. This section defines the workflow command chain system implemented in Sprint Workflow Command Chains.

### Domain Types

| Type | Purpose | Fields |
|------|---------|--------|
| `WorkflowCommand` | Single command in a workflow chain | `id`, `command` (tuple), `required`, `mutates_state`, `agent_allowed`, `description` |
| `WorkflowContext` | Named validation workflow | `id`, `description`, `commands` (tuple of WorkflowCommand), `agent_allowed`, `mutates_state` |
| `WorkflowCommandResult` | Result of executing a command | `id`, `command`, `returncode`, `stdout`, `stderr`, `passed`, `required` |
| `WorkflowRunResult` | Result of running a complete context | `context_id`, `passed`, `results` (tuple of WorkflowCommandResult), `blockers` (tuple of str), `evidence_path` |

All types are frozen dataclasses with slots for immutability and memory efficiency.

### Built-in Contexts

| Context ID | Description | Commands | Agent Allowed | Mutates State |
|------------|-------------|----------|---------------|---------------|
| `mission_handoff` | Mission handoff validation chain — pre-check before ready_for_review | 5: compileall, pytest_collect, check_fast, forge_doctor, forge_promote_dry_run | Yes | No |
| `promotion_dry_run` | Promotion dry-run validation chain — pre-check before promotion | 2: forge_doctor, forge_promote_dry_run | Yes | No |

### Command Chain Execution Rules

1. **Explicit argument arrays**: All commands use `subprocess.run` with explicit tuple arguments. NEVER use `shell=True`.
2. **Output capture**: stdout and stderr are captured as text.
3. **Truncation**: Output is truncated to `MAX_OUTPUT_CHARS` (10,000) with `...` suffix.
4. **Required vs Optional**: Required commands block on failure; optional commands fail but continue.
5. **Early termination**: The chain stops at the first required command failure.
6. **Evidence writing**: Results are written to `.rig/work/validation/<context_id>-<timestamp>.json`.
7. **Safety**: No tokens/secrets in evidence. No personal names in generated evidence.

### CLI Interface

```bash
# List all workflow contexts
rig workflow list
rig workflow list --json

# Run a workflow context
rig workflow run mission_handoff
rig workflow run promotion_dry_run

# Options
--json          Output JSON instead of human-readable text
--no-evidence   Don't write evidence file
--agent         Enforce agent_allowed check (default: enforce)
--allow-mutating Allow running mutating contexts (default: false, user must consent)
```

### Python API

```python
from rig.domain.workflow_chains import (
    list_builtin_workflow_contexts,
    get_builtin_workflow_context,
    run_workflow_context,
    MISSION_HANDOFF_CONTEXT,
    PROMOTION_DRY_RUN_CONTEXT,
)

# List all contexts
contexts = list_builtin_workflow_contexts()

# Get a specific context
ctx = get_builtin_workflow_context("mission_handoff")

# Run a context
result = run_workflow_context("mission_handoff", repo_path=".", write_evidence=True)
```

### Integration Points

- `scripts/_work_lib.py` provides `check_mission_handoff_readiness()` and `run_workflow_context_chain()` for integration with existing scripts
- These functions use `rig workflow run` CLI internally
- Compatible with existing `check_forge_readiness()` in `work_handoff.py`
- Future work: Update `work_handoff.py` to use `check_mission_handoff_readiness()` directly

### Schema Validation

See `docs/schemas/rig-workflow-chain.schema.json` for JSON Schema definitions of all workflow chain types.

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
