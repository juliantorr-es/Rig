# Rig Workflow: ADR → Sprint → Mission → Evidence → Review/Promotion

**Canonical Workflow Reference** — This document defines the current Rig narrative for agent workflow.

> **Models propose; Rig disposes.**

## Canonical Workflow Hierarchy

```
ADR (Architectural Decision Record)
  → Sprint(s) (Time/Scope-bounded implementation campaign)
      → Mission(s) (Substantial delegated work packet)
          → Evidence (Append-only progress ledger)
          → Review/Promotion (Governance evaluation)
```

## Definitions

### ADR: Architectural Decision and Authority Boundary

An ADR explains **why** work exists and what constraints govern it. It is the architectural authority for a domain.

- **Purpose**: Define architectural decisions, authority boundaries, and constraints
- **Scope**: Large enough to require multiple implementation sprints
- **Authority**: Architectural decision authority
- **Lifespan**: Endures until superseded by another ADR
- **Relationship**: A massive ADR may require multiple sprints. An ADR maps to one or more sprints, not exactly one.

**Examples**: ADR 0007 (Workspace Domain Authority), ADR 0008 (Receipt/Evidence Unification), ADR 0009 (Agentic Workflow Refinement)

### Sprint: Implementation Campaign

A sprint is a time-bounded or scope-bounded implementation campaign for part of an ADR.

- **Purpose**: Deliver a coherent increment of value for an ADR
- **Scope**: Part or all of an ADR's implementation
- **Duration**: Time-bounded or scope-bounded
- **Authority**: Sprint docs point to ADRs and missions; they do NOT define competing workflow authority
- **Relationship**: A sprint may contain several missions. Multiple sprints may be needed for a large ADR.

**Examples**: governance-replay-phase-5, workspace-authority-auditability-spine, proposal-lifecycle-console

### Mission: Substantial Delegated Work Packet

A mission is a **substantial**, agent-sized work packet inside a sprint. It is the primary unit of delegation.

- **Purpose**: Provide meaningful independent agent work
- **Scope**: Agent-sized, not baby-sized. Large enough for orientation, implementation, validation, and handoff
- **Authority**: Mission-level authority is delegated from sprint/ADR authority
- **Relationship**: Missions are flat. No nested missions, subtasks, or slices.

**Mission Sizing Rules**:
- A mission **must** be big enough for meaningful independent agent work
- A mission **should** include orientation, implementation, validation, and handoff
- A mission **may** contain an internal checklist, but checklist items are NOT first-class tracked tasks
- A mission **should** produce one coherent handoff and, when appropriate, one coherent commit
- If a mission is only "edit one line," "inspect one file," or "run one command," it is **too small**
- If a mission spans unrelated domains or cannot be reviewed as a coherent unit, it is **too large**
- **Do not** create nested missions, subtasks, or slices

### Evidence: Append-Only Progress Ledger

Evidence records what happened during mission execution.

- **Purpose**: Append-only progress ledger entries, heartbeats, tests, handoffs, receipts, commits, and out-of-current-scope findings
- **Authority**: Evidence records observations; it does not define workflow authority
- **Formats**: progress.jsonl (ADR-local), receipts, test results, handoff notes
- **Rules**:
  - `progress.jsonl` is **append-only**. Never delete or edit existing lines
  - Generated projections and generated notes are **NOT authority**
  - Out-of-scope findings do **not** expand the current mission
  - Agents must heartbeat during long work
  - Agents must record out-of-current-scope findings instead of ignoring them

### Review/Promotion: Governance Evaluation

Human/governance evaluation before acceptance, merge, release, or production movement.

- **Purpose**: Evaluate mission completion against acceptance criteria
- **Authority**: Governance/human authority
- **Actions**: Acceptance, merge, release, production movement
- **Rules**: Missions should be reviewable as coherent units of change

## Workflow Rules

### What Agents Must Do

1. **Claim missions, not tiny slices** — Agents claim missions, not micro-tasks
2. **Heartbeat during long work** — Use `scripts/work_heartbeat.py` for active missions
3. **Record out-of-current-scope findings** — Use `scripts/work_note.py --out-of-scope`
4. **Derive internal checklists from mission intent** — Missions may contain internal checklists, but these are not tracked as workflow children
5. **Use tracked scripts for worktree normalization** — Use `scripts/worktree_normalize.py`, never raw folder moves
6. **Never hand-edit generated files** — Generated projections and notes are not authority
7. **Include out-of-scope findings in handoffs** — Always include out-of-scope findings at the end of handoff/final reports

### What Agents Must NOT Do

1. **Do not create recursive hierarchy below Mission** — No nested missions, subtasks, or slices
2. **Do not execute in the main worktree** — Agents execute in `.rig/worktrees/`
3. **Do not use sibling worktrees** — Use `.rig/worktrees/<name>` for linked worktrees
4. **Do not hand-edit generated projections** — They are generated, not authoritative
5. **Do not treat optimized/encoded context as authority** — Canonical representation is the authority
6. **Do not create workstreams or current-work-streams** — These are obsolete concepts

### Worktree Rules

- Rig-owned linked worktrees **must** live under `.rig/worktrees/`
- Do **not** create new sibling worktrees next to the main repo
- Use `git worktree add .rig/worktrees/<name> <branch>` for new tracked work
- If sibling worktrees already exist, normalize them with `scripts/worktree_normalize.py`
- **Never** raw-move worktrees with `mv`. Use `git worktree move` or the normalization script

### ADR-Local State Rules

- ADR work state lives under `.rig/work/adr/<adr-id>/`
- Each ADR has `task.json`, `progress.jsonl`, `projection.json`, and `notes/out-of-scope-findings.md`
- `progress.jsonl` is **append-only**. Never delete or edit existing lines
- `projection.json` and `notes/out-of-scope-findings.md` are **generated**. Do not hand-edit them

## Authority Hierarchy

| Layer | Authority Type | Document Location | Notes |
|-------|---------------|------------------|-------|
| **Operational** | Agent behavior | `AGENTS.md` | Operational authority for agent behavior |
| **Workflow** | Operating procedure | `docs/workflow/adr-sprint-mission-evidence.md` | This document |
| **Architectural** | ADR index | `docs/adr/README.md` | ADR index authority |
| **Architectural** | Individual decisions | `docs/adr/<nnnn>-*.md` | Architectural decision authority |
| **Implementation** | Sprint coordination | `docs/sprints/*.md` | Sprint point to ADRs and missions |
| **Schema** | Data contracts | `docs/schemas/*.json` | Referenced by scripts and docs |
| **Script** | Runtime tools | `scripts/*.py` | Tracked canonical implementations |

## Key Differentiators from Other Systems

### vs GitHub-style Issue Trees
- **Rig**: Flat missions, no recursion, append-only evidence
- **GitHub**: Recursive issues, subtasks, nested hierarchies

### vs Jira-style Epics/Sprints
- **Rig**: ADR (architectural epic) → Sprint (implementation campaign) → Mission (substantial work packet)
- **Jira**: Epic → Sprint → Story → Subtask
- **Difference**: Rig **bottoms out at Mission**. No subtasks beneath missions.

### vs Commercial Agent IDEs
- **Rig**: Governance authority, evidence lineage, proposal lifecycle, Git guard
- **Commercial**: Execution telemetry, but not forensic-grade evidence. Agents execute freely.
- **Rig principle**: Models propose; Rig disposes.

## Terminology: What Terms Mean in Rig

| Term | Rig Meaning | Notes |
|------|-------------|-------|
| **ADR** | Architectural Decision Record | Authority boundary, explains why work exists |
| **Sprint** | Implementation campaign | Time/scope-bounded, part of ADR |
| **Mission** | Substantial delegated work packet | Agent-sized, not micro-tasks |
| **Evidence** | Append-only progress ledger | progress.jsonl, receipts, tests, findings |
| **Slice** | **OBSOLETE** | Historical term for implementation phases; use **Sprint** instead |
| **Subtask** | **FORBIDDEN** | Do not create recursive hierarchy below Mission |
| **Workstream** | **OBSOLETE** | Do not use; workflow is ADR → Sprint → Mission |
| **Slice 0 / 0.5 / 0.8** | Implementation phases | Only valid in ADR 0009 as historical slice references; do not use as workflow model |

## ADR 0009 Special Notes

ADR 0009 (Agentic Workflow Refinement) serves as the **umbrella ADR** for agent workflow refinement. It:
- Maps to the canonical workflow: ADR → Sprint → Mission → Evidence → Review/Promotion
- Defines `AgentOrchestrator`, `ContextPacket`, `SemanticIntent`, `NativeAction` as future types
- Uses "slice" terminology internally to describe **implementation phases only** (Slice 0, Slice 0.5, Slice 0.8, etc.)
- These slices are **NOT** workflow hierarchy levels. They are implementation staging phases.
- The **dogfood bridge** uses ADR-local missions and progress ledgers as bootstrap
- Do not confuse ADR 0009's slice references with workflow hierarchy

## Validation and Verification

### Before Any Commit
- Run `python scripts/work_doctor.py <task_id>` to validate task + ledger
- Run targeted `ruff check` on touched files
- Run `python -m compileall -q src tests` for syntax
- Run `python -m pyright --project pyrightconfig.json` for types (targeted scope)

### Smoke Commands
- `python -m rig doctor`
- `python -m rig ui --help`
- `python -m rig tui` (deprecation shim)
- `python -m rig window open --dry-run`
- `python -m rig --debug ui --browser`

## Summary

Rig's workflow is intentionally **flat below Mission**. This is the anti-bureaucracy guardrail:
- ADRs provide architectural authority
- Sprints organize time-bounded campaigns
- Missions are substantial, agent-sized work packets
- Evidence is append-only
- Review/Promotion is governance evaluation

**No recursive hierarchy. No subtasks. No slices as workflow. No workstreams.**

This hierarchy is simple enough to coordinate agents but structured enough to maintain governance authority.
