# Rig Workflow: ADR → Sprint → Sprint Research → Mission → Patch Batch → Evidence → Review/Promotion

**Canonical Workflow Reference** — This document defines the current Rig narrative for agent workflow.

> **Models propose; Rig disposes.**

---

## Canonical Workflow Hierarchy

```
ADR (Architectural Decision Record)
  → Sprint(s) (Scope-bounded implementation campaign)
      → Sprint Research (MANDATORY read-only planning phase)
          → Mission(s) (Substantial delegated work packet)
              → Patch Batch(es) (Coherent set of related changes)
                  → Evidence (Append-only progress ledger)
                  → Review/Promotion (Governance evaluation)
```

**Key Rule**: Sprint Research is **mandatory** before any sprint implementation. Agents **must not** jump straight from ADR text to file edits.

---

## Definitions

### ADR: Architectural Decision and Authority Boundary

An ADR explains **why** work exists and what constraints govern it. It is the architectural authority for a domain.

- **Purpose**: Define architectural decisions, authority boundaries, and constraints
- **Scope**: Large enough to require multiple implementation sprints
- **Authority**: Architectural decision authority
- **Lifespan**: Endures until superseded by another ADR
- **Relationship**: A massive ADR may require multiple sprints. An ADR maps to one or more sprints, not exactly one.

**Examples**: ADR 0007 (Workspace Domain Authority), ADR 0008 (Receipt/Evidence Unification), ADR 0009 (Agentic Workflow Refinement)

### Sprint: Scope-Bounded Implementation Campaign

A sprint is a scope-bounded implementation campaign for part of an ADR.

- **Purpose**: Deliver a coherent increment of value for an ADR
- **Scope**: Part or all of an ADR's implementation
- **Duration**: Scope-bounded or time-bounded
- **Authority**: Sprint docs point to ADRs and missions; they do NOT define competing workflow authority
- **Relationship**: A sprint **must** have completed research before implementation. A sprint may contain several missions. Multiple sprints may be needed for a large ADR.

**Examples**: governance-replay-phase-5, workspace-authority-auditability-spine, proposal-lifecycle-console

### Sprint Research: Mandatory Read-Only Planning Phase

**Sprint Research is MANDATORY before any sprint implementation.**

- **Purpose**: Inspect the repo, understand current state, propose missions, plan coherent patch batches
- **Read-Only**: NO file edits during research except writing local sprint research artifacts under `.rig/work/adr/<adr-id>/sprints/<sprint-id>/`
- **Tooling**: Use installed Python tooling (pathlib, json, ast, difflib, subprocess, tokenize) and local CLI tools (rg, fd, git diff, git status --porcelain=v1)
- **Output**: Must produce all required research artifacts before implementation begins

#### Research Phase Rules

1. **Research is mandatory** before sprint implementation
2. **Research is read-only** — no file edits except sprint research artifacts
3. **No file edits** during research except writing artifacts under `.rig/work/adr/<adr-id>/sprints/<sprint-id>/`
4. **Use installed Python tooling** and local CLI tools to inspect the repo
5. **Must produce**:
   - `research_summary` — overview of findings
   - `repo_inventory` — list of relevant files and their purposes
   - `relevant_files` — files that will be affected by this sprint
   - `current_state` — current state of the codebase relevant to the sprint
   - `risk_notes` — potential risks and mitigations
   - `mission_plan` — proposed missions for this sprint
   - `patch_batches` — planned coherent change batches
   - `validation_plan` — validation commands and criteria
   - `out_of_scope_findings` — observations outside sprint scope
6. **Must identify expected files** before mutation begins
7. **Must define validation commands** before mutation begins
8. **Must record out-of-current-scope findings** instead of ignoring them

#### Research Artifacts Location

Sprint research artifacts live under:
```
.rig/work/adr/<adr-id>/sprints/<sprint-id>/
  research_summary.md
  repo_inventory.md or repo_inventory.json
  relevant_files.txt or relevant_files.json
  current_state.md
  risk_notes.md
  mission_plan.json
  patch_batches/
    <batch-id>.patch or <batch-id>.diff
    <batch-id>_plan.json
  validation_plan.md
  out_of_scope_findings.md
```

### Mission: Substantial Delegated Work Packet

A mission is a **substantial**, agent-sized work packet inside a sprint. It is the primary unit of delegation.

- **Purpose**: Provide meaningful independent agent work
- **Scope**: Agent-sized, not baby-sized. Large enough for orientation, implementation, validation, and handoff
- **Authority**: Mission-level authority is delegated from sprint/ADR authority
- **Relationship**: Missions are flat. No nested missions, subtasks, or slices.
- **Execution**: Missions should be executed as patch batches where practical

**Mission Sizing Rules**:
- A mission **must** be big enough for meaningful independent agent work
- A mission **should** include orientation, implementation, validation, and handoff
- A mission **may** contain an internal checklist, but checklist items are NOT first-class tracked tasks
- A mission **should** produce one coherent handoff and, when appropriate, one coherent commit
- If a mission is only "edit one line," "inspect one file," or "run one command," it is **too small**
- If a mission spans unrelated domains or cannot be reviewed as a coherent unit, it is **too large**
- **Do not** create nested missions, subtasks, or slices

### Patch Batch: Coherent Set of Related Changes

A patch batch is a coherent set of related changes that should be applied together.

- **Purpose**: Prefer batch application over repeated fine-grained edits to reduce failure and noise
- **Coherence**: Changes in a batch must be related and reviewable as a single unit
- **Do not** batch unrelated domains together
- **Precheck**: Always run `git apply --check <patch>` before applying unified diff patches
- **Validation**: Always validate after each batch is applied

#### Patch Batch Rules

1. **Prefer patch batches** over repeated fine-grained edits
2. A patch batch **must** be coherent and reviewable
3. **Do not** batch unrelated domains together
4. Use **unified diff patches** when practical
5. Use **deterministic Python codemod/AST scripts** for repetitive Python edits when safer than line edits
6. Run `git apply --check <patch>` **before** applying a patch file when using unified diffs
7. Apply patch batches **only** after precheck passes
8. **Validate after each batch**
9. **Stop if actual changed files exceed** the planned files
10. **Stop if protected paths are touched**
11. **Stop if unexpected dirty files appear**
12. **Do not use** `git reset`/`restore`/`stash`/`checkout`/`clean` for rollback. Report and await direction.

#### Patch Batch Location

Keep generated patch files under the ADR sprint workspace:
```
.rig/work/adr/<adr-id>/sprints/<sprint-id>/patch-batches/
  <batch-id>.patch
  <batch-id>_plan.json
  <batch-id>_precheck.json
  <batch-id>_apply_receipt.json
  <batch-id>_validation.json
```

### Evidence: Append-Only Progress Ledger

Evidence records what happened during mission and patch batch execution.

- **Purpose**: Append-only progress ledger entries, heartbeats, tests, handoffs, receipts, commits, and out-of-current-scope findings
- **Authority**: Evidence records observations; it does not define workflow authority
- **Formats**: progress.jsonl (ADR-local), receipts, test results, handoff notes

#### Evidence Rules:
- `progress.jsonl` is **append-only**. Never delete or edit existing lines
- Generated projections and generated notes are **NOT authority**
- Out-of-scope findings do **not** expand the current mission or sprint
- Agents must heartbeat during long work
- Agents must record out-of-current-scope findings instead of ignoring them

#### Visual Evidence Protocol (UI/Visualization):
For missions affecting the User Interface or Visualization substrate, evidence must be **multimodal**:
- **Verification**: Capture screenshots or video recordings using the `browser_subagent`.
- **Causality**: Evidence must demonstrate that the change preserves **Object Constancy** (Heer & Robertson, 2007) and uses **Signaling** (Mayer & Moreno, 2003) to guide cognition.
- **Artifacts**: Store media files in the artifacts directory and link them in the handoff.

### Review/Promotion: Governance Evaluation

Human/governance evaluation before acceptance, merge, release, or production movement.

- **Purpose**: Evaluate mission/sprint completion against acceptance criteria
- **Authority**: Governance/human authority
- **Actions**: Acceptance, merge, release, production movement
- **Rules**: Missions and patch batches should be reviewable as coherent units of change

---

## Rite of Deterministic Passage (Preproduction Promotion)

**Preproduction promotion is script-gated only.** Agents **must not** merge directly. Agents **may only** invoke `scripts/work_promote.py --target preproduction` to promote.

### Overview

The **Rite of Deterministic Passage** is a sequence of 13 deterministic gates that must all pass before agent work may be merged into the local `preproduction` branch. This ensures that promotion is fully auditable, safe, and governed.

**Key Principles**:
- Agents **must not** run `git merge` directly under any circumstances
- Agents **may only** invoke `scripts/work_promote.py` for promotion
- Promotion script verifies all 13 gates pass before executing merge
- Failed gates append `preproduction_promotion_blocked` event to ledger and **must not** mutate branches
- Promotion is fully auditable through ADR-local progress ledger events
- **Preproduction is integration/local only** — production/main remains human-governed and out of scope

### The 13 Gates

All 13 gates must pass before promotion execution. Gates are checked in dependency order:

| # | Gate | Blocking | Description |
|---|------|----------|-------------|
| 1 | **Sprint research completed** | Yes | Sprint research must be completed (event `sprint_research_completed` exists) |
| 2 | **Mission handoff completed** | Yes | Mission must have a handoff event with required fields (tests, dirty_files_after, completion_summary, out_of_scope_findings) |
| 3 | **Patch batches prechecked** | Yes | All planned patch batches must have precheck events (`patch_batch_prechecked`) |
| 4 | **Patch batches applied and validated** | No (warning) | Patch batches should be applied and validated |
| 5 | **Merge-friendliness pass completed** | Yes | Applied patch batches must have passed merge-friendliness check (`patch_batch_merge_friendly_checked` with `safe_to_apply: true`) |
| 6 | **work_doctor.py passed** | Yes | `work_doctor.py` must pass for the task (run as subprocess) |
| 7 | **Required tests/checks passed** | Yes | Required checks must pass or be explicitly justified |
| 8 | **Out-of-current-scope findings recorded** | Yes | Out-of-scope findings must be recorded, even if empty |
| 9 | **Candidate source branch is clean** | Yes | Source branch worktree must be clean (no dirty files) |
| 10 | **Candidate source branch HEAD is recorded** | Yes | Source branch HEAD commit must be available |
| 11 | **Preproduction branch exists locally** | Yes | Preproduction branch must exist locally (`git branch --list preproduction`) |
| 12 | **Merge simulation against preproduction passes** | Yes | `git merge-tree` simulation must pass without conflicts |
| 13 | **Preproduction working tree is clean before merge** | Yes | Preproduction branch worktree must be clean before merge |

### Promotion Workflow

```
1. Check all 13 gates → All pass?
   ├─ NO: Append preproduction_promotion_blocked event to ledger
   │       Exit non-zero, do NOT mutate branches
   │
   YES: Proceed to merge execution
   │
2. Execute promotion merge (Internal implementation detail of work_promote.py):
   ├─ Switch to preproduction branch
   ├─ Verify preproduction worktree is clean
   ├─ Run internal merge operation
   │
   ├─ If merge fails:
   │   ├─ Abort internal merge
   │   ├─ Switch back to source branch
   │   └─ Append preproduction_promotion_blocked event
   │
   └─ If merge succeeds:
       ├─ Switch back to source branch
       └─ Append preproduction_promotion_completed event
3. Record event to ADR-local progress.jsonl ledger
```

### Additional Safety Checks

The promotion script also enforces these constraints:
- **Not on main**: Cannot promote from main branch
- **Target is preproduction**: Only `preproduction` target is supported; main/production are blocked
- **Not on target**: Cannot promote while on the target (preproduction) branch
- **Source != target**: Source and target branches must be different

### Script Usage

```bash
# Dry-run: Check gates without executing promotion
python3 scripts/work_promote.py <task_id> \
    --mission <mission_id> \
    --target preproduction \
    --worker <worker> \
    --dry-run

# Execute promotion (only if all gates pass)
python3 scripts/work_promote.py <task_id> \
    --mission <mission_id> \
    --sprint <sprint_id> \
    --target preproduction \
    --worker <worker>
```

### Event Types

| Event Type | When Emitted | Key Fields |
|------------|--------------|------------|
| `preproduction_promotion_completed` | All gates passed, merge executed successfully | `target`, `source_branch`, `source_head`, `gate_results`, `all_gates_passed: true` |
| `preproduction_promotion_blocked` | Any blocking gate failed | `target`, `source_branch`, `source_head`, `gate_results`, `blocking_gates_failures`, `all_gates_passed: false` |
| `preproduction_merge_completed` | Merge execution completed | Same as promotion_completed |
| `preproduction_validation_passed` | Post-promotion validation passed | - |
| `preproduction_validation_failed` | Post-promotion validation failed | - |

### Post-Promotion Validation

After successful promotion, agents should run validation:
```bash
python3 scripts/work_doctor.py <task_id>
# Note: Agents must not checkout the preproduction branch directly.
# Run validation from the current worktree or use governed tools.
```

---

## Workflow Rules

### What Agents Must Do

1. **Complete Sprint Research first** — Research is mandatory before any implementation
2. **Research is read-only** — No file edits except sprint research artifacts
3. **Claim missions, not tiny slices** — Agents claim missions, not micro-tasks
4. **Heartbeat during long work** — Use `scripts/work_heartbeat.py` for active missions
5. **Record out-of-current-scope findings** — Use `scripts/work_note.py --out-of-scope`
6. **Derive internal checklists from mission intent** — Missions may contain internal checklists, but these are not tracked as workflow children
7. **Use tracked scripts for worktree normalization** — Use `scripts/worktree_normalize.py`, never raw folder moves
8. **Prefer patch batches** — Use `scripts/work_patch_batch.py` for coherent change sets
9. **Precheck patches** — Run `git apply --check` before applying unified diffs
10. **Check merge-friendliness** — Run `scripts/work_merge_friendly.py` before applying any patch batch to check against active worktrees
11. **Never hand-edit generated files** — Generated projections and notes are not authority
12. **Include out-of-scope findings in handoffs** — Always include out-of-scope findings at the end of handoff/final reports
13. **Include patch batches applied in handoffs** — Always record which patch batches were applied

### What Agents Must NOT Do

1. **Do not skip Sprint Research** — Research is mandatory before implementation
2. **Do not edit files during research** — Research is read-only
3. **Do not create recursive hierarchy below Mission** — No nested missions, subtasks, or slices
4. **Do not execute in the main worktree** — Agents execute in `.rig/worktrees/`
5. **Do not use sibling worktrees** — Use `.rig/worktrees/<name>` for linked worktrees
6. **Do not hand-edit generated projections** — They are generated, not authoritative
7. **Do not treat optimized/encoded context as authority** — Canonical representation is the authority
8. **Do not create workstreams or current-work-streams** — These are obsolete concepts
9. **Do not apply patches without precheck** — Always run `git apply --check` first
10. **Do not apply patches without merge-friendliness check** — Always run `scripts/work_merge_friendly.py` before apply
11. **Do not apply patches with failed merge-friendliness** — If merge-friendliness reports blocked, resolve issues first
12. **Do not use git reset/restore/stash/checkout/clean for rollback** — Report and await direction
13. **Do not merge directly** — Agents must NOT run `git merge`. Use `scripts/work_promote.py` for preproduction promotion only
14. **Do not promote to main/production** — Only preproduction target is supported via `work_promote.py`. main/production remain human-governed
15. **Do not mark ready_for_review without forge gate success** — Agents must run `rig forge doctor` and `rig forge promote --dry-run` before marking handoff as `ready_for_review`. Reviewability budget is enforced by Rig, not human memory

---

### ADR 0010: Forge Promotion Gates

**Agents must run forge readiness checks before handoff.**

The `rig forge` command provides forge-neutral readiness validation:
- `rig forge doctor --json` — Validates forge configuration and reports reviewability
- `rig forge promote --dry-run --json` — Plans promotion and reports blockers

**Requirements:**
- Agents **must** run forge gates before marking a mission as `ready_for_review`
- Agents **must** record forge evidence in handoff events via `scripts/work_handoff.py`
- `work_handoff.py` automatically runs `rig forge doctor` and `rig forge promote --dry-run` for `ready_for_review` status
- If forge gates fail, `work_handoff.py` **blocks** the handoff and reports blockers
- Reviewability budget (default: 300 files) is enforced — over-budget missions must split or provide explicit override evidence
- No direct push/merge to protected integration branches (`preproduction`, `main`)

**Forge Gate Evidence Fields in Handoff Events:**
- `forge_gates_checked` — Whether forge gates were run
- `forge_evidence` — Full evidence dict with: doctor status, promotion ready, blockers, reviewability info
- `forge_gate_skip_explicit` — Whether `--skip-forge-gates` was used (NOT RECOMMENDED)

**Workflow Command Chains (ADR 0009 / ADR 0010):**

Agents run **workflow contexts** instead of manual command checklists. Workflow command chains provide deterministic validation sequences that replace ad-hoc validation command enumeration.

- **Core principle**: Agents run workflow contexts (e.g., `mission_handoff`, `promotion_dry_run`), not manual command checklists
- **CLI**: `rig workflow run <context_id>` executes the canonical validation chain
- **Built-in contexts**:
  - `mission_handoff` — Pre-check before `ready_for_review`: compileall, pytest_collect, check_fast, forge_doctor, forge_promote_dry_run
  - `promotion_dry_run` — Pre-check before promotion: forge_doctor, forge_promote_dry_run
- **Safety**: All commands use `subprocess.run` with explicit argument arrays, NEVER `shell=True`
- **Evidence**: Written to `.rig/work/validation/<context_id>-<timestamp>.json` with truncation at 10,000 characters
- **No secrets**: No tokens/credentials in evidence; no personal names in generated evidence
- **Agent enforcement**: All initial contexts are non-mutating and agent-allowed; `--allow-mutating` flag required for mutating contexts (not implemented in Phase 1)
- **Execution behavior**: Stop early on first required command failure; continue on optional command failure

**CLI Usage:**
```bash
# List available workflow contexts
python -m rig workflow list
python -m rig workflow list --json

# Run mission_handoff workflow
python -m rig workflow run mission_handoff
python -m rig workflow run mission_handoff --json
python -m rig workflow run mission_handoff --no-evidence

# Run promotion_dry_run workflow  
python -m rig workflow run promotion_dry_run

# Agent mode (enforces agent_allowed check)
python -m rig workflow run mission_handoff --agent
```

**Integration with work_handoff.py:**
- `scripts/_work_lib.py` provides `check_mission_handoff_readiness()` and `run_workflow_context_chain()` functions
- These functions use the `rig workflow run` CLI internally
- Compatible with existing `check_forge_readiness()` for backward compatibility
- Future: `work_handoff.py` can use `check_mission_handoff_readiness()` directly

**Bypass Policy:**
- Use `--skip-forge-gates` **only for testing** — explicit bypass is recorded and reported
- `work_doctor.py` flags bypassed handoffs as warnings
- No silent bypasses allowed

**Validation:**
- `work_doctor.py` validates that `ready_for_review` handoffs have forge gate evidence
- `work_status.py` displays forge readiness from projection
- Forge gate failures block commit readiness

---

### Worktree Rules

- Rig-owned linked worktrees **must** live under `.rig/worktrees/`
- Do **not** create new sibling worktrees next to the main repo
- Use `git worktree add .rig/worktrees/<name> <branch>` for new tracked work
- If sibling worktrees already exist, normalize them with `scripts/worktree_normalize.py`
- **Never** raw-move worktrees with `mv`. Use `git worktree move` or the normalization script

### Worktree Naming Policy

**Canonical worktree names are based on ADR titles, not arbitrary branch names.**
This ensures consistent, human-readable operating spaces that map directly to architectural decisions.

#### Distinction: Worktree Names vs Branch Names vs ADR Ledger Paths

| Concept | Purpose | Location | Example |
|---------|---------|----------|---------|
| **Worktree directory name** | Human-readable operating space | Filesystem under `.rig/worktrees/` | `.rig/worktrees/adr0009-agentic-workflow-refinement/` |
| **Branch name** | Git ref | Git namespace | `sprint/adr0009-agentic-workflow-refinement` |
| **ADR ledger path** | Machine-readable evidence store | `.rig/work/adr/` | `.rig/work/adr/adr0009-agentic-workflow-refinement/` |

**Critical rule**: Worktree directory names and branch names are **independent**.
A worktree can be on any branch. A branch can be checked out in any worktree.
The naming conventions are separate but complementary.

#### Canonical Worktree Naming Conventions

##### ADR Implementation Worktree

```
.rig/worktrees/<adr-id>-<adr-title-slug>/
```

Derived from the ADR's canonical ID and title. Use the `canonical_slug()` function from `scripts/_work_lib.py` to derive the slug.

**Examples:**
- `.rig/worktrees/adr0007-workspace-domain-authority/`
- `.rig/worktrees/adr0008-receipt-evidence-unification/`
- `.rig/worktrees/adr0009-agentic-workflow-refinement/`

##### Mission-Specific Worktree (Optional)

For missions that need isolated worktrees within an ADR implementation:

```
.rig/worktrees/<adr-id>-<adr-title-slug>--<mission-slug>/
```

**Examples:**
- `.rig/worktrees/adr0009-agentic-workflow-refinement--worktree-naming/`
- `.rig/worktrees/adr0009-agentic-workflow-refinement--slug-functions/`

##### Reserved Integration Worktrees

These names are **reserved** and must not be used for ADR implementation worktrees:

```
.rig/worktrees/preproduction/
.rig/worktrees/main/
```

These worktrees are for integration purposes only.

##### Legacy Worktree Names

The following worktree names are **legacy/ambiguous** and should be migrated:
- `Rig-consolidation` — should be `preproduction` (reserved)
- `Rig-main-merge` — should map to appropriate ADR
- `ui-cockpit` — should map to appropriate ADR

Use `scripts/worktree_normalize.py` to detect and propose canonical names.

#### Canonical Slug Derivation

The `canonical_slug()` function enforces these rules:
1. Lowercase all characters
2. Trim leading/trailing whitespace
3. Replace non-alphanumeric runs with single hyphen
4. Remove leading/trailing hyphens
5. Deterministic: same input always produces same output

**Examples:**
| Input | Output |
|-------|--------|
| `Agentic Workflow Refinement` | `agentic-workflow-refinement` |
| `ADR 0009: Agentic Workflow Refinement` | `adr-0009-agentic-workflow-refinement` |
| `Receipt/Evidence Unification` | `receipt-evidence-unification` |
| `Workspace Domain Authority` | `workspace-domain-authority` |
| `ui_cockpit` | `ui-cockpit` |

#### Branch Naming Conventions

Branches remain Git refs, separate from worktree paths:

| Branch Type | Pattern | Example |
|-------------|---------|---------|
| Sprint branch | `sprint/<adr-id>-<adr-title-slug>` | `sprint/adr0009-agentic-workflow-refinement` |
| Agent/mission branch | `agent/<adr-id>-<mission-slug>` | `agent/adr0009-worktree-naming` |
| Promotion branch | `promotion/<adr-id>-<adr-title-slug>` | `promotion/adr0009-agentic-workflow-refinement` |

#### Helper Functions

The following functions are available in `scripts/_work_lib.py`:

- `canonical_slug(text: str) -> str` — Convert text to canonical slug
- `derive_adr_directory_slug(adr_path | adr_id + adr_title) -> str` — Derive ADR directory slug
- `get_adr_worktree_path(...)` — Get ADR implementation worktree path
- `get_mission_worktree_path(...)` — Get mission-specific worktree path
- `get_sprint_branch_name(...)` — Get sprint branch name
- `get_mission_branch_name(adr_id, mission_slug)` — Get mission branch name
- `get_promotion_branch_name(...)` — Get promotion branch name
- `is_reserved_worktree_name(name)` — Check if name is reserved
- `validate_worktree_name(name)` — Validate against naming policy

#### Implementation Guidance

**DO:**
- Always pass the branch explicitly to `git worktree add <path> <branch>`. Do **not** rely on implicit branch creation from the final path component.
- Use canonical naming for new worktrees.
- Use the helper functions for derivation to ensure consistency.

**DO NOT:**
- Create worktrees with arbitrary names like `test`, `temp`, `my-work`.
- Use reserved names (`preproduction`, `main`) for ADR implementation worktrees.
- Rely on implicit branch creation from worktree path names.
- Use sibling worktrees (outside `.rig/worktrees/`).

### ADR-Local State Rules

- ADR work state lives under `.rig/work/adr/<adr-id>/`
- Each ADR has `task.json`, `progress.jsonl`, `projection.json`, and `notes/out-of-scope-findings.md`
- Each sprint under an ADR has `.rig/work/adr/<adr-id>/sprints/<sprint-id>/` with research artifacts and patch batches
- `progress.jsonl` is **append-only**. Never delete or edit existing lines
- `projection.json` and `notes/out-of-scope-findings.md` are **generated**. Do not hand-edit them

#### ADR Workspace Structure

```
.rig/work/adr/<adr-id>/
  task.json                    # ADR implementation task
  progress.jsonl               # Append-only ledger events
  projection.json              # Generated state snapshot
  exports/                     # Generated dataset exports (optional)
    events.csv                # All work events
    missions.csv              # Mission definitions
    patch_batches.csv          # Patch batch tracking
    validations.csv            # Validation results
    findings.csv               # Out-of-scope findings
    events.parquet             # Parquet format (if pyarrow/pandas/polars installed)
    schema.json                # Table schemas and metadata
    dataset_card.md            # Dataset documentation
  notes/
    out-of-scope-findings.md   # Observations outside scope
  sprints/
    <sprint-id>/
      research_summary.md      # Research phase summary
      repo_inventory.md         # Relevant files and their purposes
      relevant_files.txt        # Files to be affected
      current_state.md          # Current codebase state
      risk_notes.md             # Risks and mitigations
      mission_plan.json         # Proposed missions
      patch_batches/            # Planned coherent changes
        <batch-id>.patch        # Unified diff patch
        <batch-id>_plan.json    # Patch batch plan
        <batch-id>_precheck.json # Precheck results
        <batch-id>_validation.json # Validation results
      validation_plan.md        # Validation commands and criteria
      out_of_scope_findings.md  # Out-of-scope observations
```

### Dataset Exports

Generated dataset exports provide rebuildable analysis artifacts derived from task.json, progress.jsonl, patch batch metadata, validation events, and out-of-scope findings.

**Rules**:
- progress.jsonl remains canonical authority
- CSV/Parquet exports are generated and must not be hand-edited
- Large stdout/stderr must not be stored inline; store hashes and artifact paths
- Do not store secrets or private chain-of-thought
- Record semantic intent, native action, validation outcome, patch batch metadata, and review outcome as structured fields
- Export should be deterministic for the same ledger state
- Use stable column names and include schema_version in exports

**Required generated files** (created by `scripts/work_export_dataset.py`):
- `events.csv` - All work events
- `missions.csv` - Mission definitions  
- `patch_batches.csv` - Patch batch tracking
- `validations.csv` - Validation results
- `findings.csv` - Out-of-scope findings
- `dataset_card.md` - Dataset documentation
- `schema.json` - Table schemas and metadata
- `events.parquet` - Parquet format (written if pyarrow/pandas/polars is installed)

---

## Tooling Guidance

### Python Stdlib Tools

Use Python stdlib tools where appropriate:
- `pathlib` — Path manipulation
- `json` — JSON serialization
- `ast` — Python AST parsing for codemod scripts
- `difflib` — Diff generation and comparison
- `subprocess` — Running CLI commands
- `tokenize` — Python token inspection

### Local CLI Tools

Use local CLI tools where appropriate:
- `rg` — Recursive grep for code search
- `fd` — Fast file finder
- `git diff` — View changes
- `git status --porcelain=v1` — Parseable git state (stable for scripts)
- `git apply --check` — Precheck patches before applying
- `git apply` — Apply unified diff patches

### Patch Strategy

- For **broad Python refactors**: Use AST/codemod-style scripts when safer than manual line edits
- For **coherent multi-file changes**: Use unified diff patches
- For **single-file edits**: Direct edits may be appropriate

**Preferred patch workflow**:
1. Generate patch file
2. Run `git apply --check <patch>`
3. If precheck passes, run `git apply <patch>`
4. Run validation
5. Record evidence

---

## Authority Hierarchy

| Layer | Authority Type | Document Location | Notes |
|-------|---------------|------------------|-------|
| **Operational** | Agent behavior | `AGENTS.md` | Operational authority for agent behavior |
| **Workflow** | Operating procedure | `docs/workflow/adr-sprint-mission-evidence.md` | This document |
| **Architectural** | ADR index | `docs/adr/README.md` | ADR index authority |
| **Architectural** | Individual decisions | `docs/adr/<nnnn>-*.md` | Architectural decision authority |
| **Implementation** | Sprint coordination | `docs/sprints/*.md` | Sprint point to ADRs and missions |
| **Schema** | Data contracts | `docs/schemas/rig-work-*.json` | Referenced by scripts and docs |
| **Script** | Runtime tools | `scripts/work_*.py` | Tracked canonical implementations |

---

## Key Differentiators from Other Systems

### vs GitHub-style Issue Trees
- **Rig**: Flat missions, no recursion, append-only evidence
- **GitHub**: Recursive issues, subtasks, nested hierarchies

### vs Jira-style Epics/Sprints
- **Rig**: ADR (architectural epic) → Sprint (scope-bounded campaign) → **Sprint Research** (mandatory read-only planning) → Mission (substantial work packet) → **Patch Batch** (coherent changes)
- **Jira**: Epic → Sprint → Story → Subtask
- **Difference**: Rig **bottoms out at Mission** with mandatory research and batch execution. No subtasks beneath missions.

### vs Commercial Agent IDEs
- **Rig**: Governance authority, evidence lineage, proposal lifecycle, Git guard, **mandatory research**, **patch batches**
- **Commercial**: Execution telemetry, but not forensic-grade evidence. Agents execute freely.
- **Rig principle**: Models propose; Rig disposes.

---

## Terminology: What Terms Mean in Rig

| Term | Rig Meaning | Notes |
|------|-------------|-------|
| **ADR** | Architectural Decision Record | Authority boundary, explains why work exists |
| **Sprint** | Scope-bounded implementation campaign | Part of ADR; requires mandatory research |
| **Sprint Research** | Mandatory read-only planning phase | Must complete before implementation |
| **Mission** | Substantial delegated work packet | Agent-sized, not micro-tasks |
| **Patch Batch** | Coherent set of related changes | Applied together, prechecked, validated |
| **Evidence** | Append-only progress ledger | progress.jsonl, receipts, tests, findings |
| **Slice** | **OBSOLETE** | Historical term for implementation phases; use **Sprint** instead |
| **Subtask** | **FORBIDDEN** | Do not create recursive hierarchy below Mission |
| **Workstream** | **OBSOLETE** | Do not use; workflow is ADR → Sprint → Sprint Research → Mission → Patch Batch |
| **Slice 0 / 0.5 / 0.8** | Implementation phases | Only valid in ADR 0009 as historical slice references; do not use as workflow model |

---

## Workflow-Specific Rules

### Sprint Research Phase

**Mandatory. Read-only. Before any implementation.**

Each sprint must begin with a research phase that:
1. Inspects the repository using installed Python tooling and CLI tools
2. Identifies relevant files and their current state
3. Assesses risks and defines mitigations
4. Proposes coherent missions
5. Plans patch batches for each mission
6. Defines validation commands and acceptance criteria
7. Records out-of-scope findings

**No file edits are permitted during research** except writing artifacts to `.rig/work/adr/<adr-id>/sprints/<sprint-id>/`.

### Patch Batch Execution

**Prefer batch application over repeated fine-grained edits.**

When executing missions:
1. Group related changes into coherent patch batches
2. For unified diff patches: always run `git apply --check` first
3. Apply only after precheck passes
4. Validate immediately after each batch
5. Stop and report if:
   - Actual changed files exceed planned files
   - Protected paths are touched
   - Unexpected dirty files appear
6. Never use destructive git commands for rollback

### Script Requirements

- `scripts/work_research.py` — Start/complete sprint research, write research artifacts
- `scripts/work_patch_batch.py` — Manage patch batch planning, precheck, apply, validation
- `scripts/work_merge_friendly.py` — Run merge-friendliness preflight before applying patch batches
- `scripts/work_doctor.py` — Must warn/fail if sprint has missions but no completed research
- `scripts/work_doctor.py` — Must fail commit readiness if patch batch evidence required but missing
- `scripts/work_status.py` — Must show sprint research status and patch batch status
- `scripts/work_handoff.py` — Must include patch batches applied and out-of-scope findings
- `scripts/work_promote.py` — Governed promotion to preproduction via Rite of Deterministic Passage; agents must NOT merge directly

---

## ADR 0009 Special Notes

ADR 0009 (Agentic Workflow Refinement) serves as the **umbrella ADR** for agent workflow refinement. It:
- Maps to the canonical workflow: ADR → Sprint → **Sprint Research** → Mission → **Patch Batch** → Evidence → Review/Promotion
- Defines `AgentOrchestrator`, `ContextPacket`, `SemanticIntent`, `NativeAction` as future types
- Uses "slice" terminology internally to describe **implementation phases only** (Slice 0, Slice 0.5, Slice 0.8, etc.)
- These slices are **NOT** workflow hierarchy levels. They are implementation staging phases.
- The **dogfood bridge** uses ADR-local missions and progress ledgers as bootstrap
- Do not confuse ADR 0009's slice references with workflow hierarchy

---

## Validation and Verification

### Before Any Commit

- Run `python scripts/work_doctor.py <task_id>` to validate task + ledger
- Run `python scripts/work_patch_batch.py --validate <task_id>` if patch batches were applied
- Run targeted `ruff check` on touched files
- Run `python -m compileall -q src tests` for syntax
- Run `python -m pyright --project pyrightconfig.json` for types (targeted scope)

### Smoke Commands

- `python -m rig doctor`
- `python -m rig ui --help`
- `python -m rig tui` (deprecation shim)
- `python -m rig window open --dry-run`
- `python -m rig --debug ui --browser`

---

## Summary

Rig's workflow enforces **deliberate planning before execution**:

- **ADRs** provide architectural authority
- **Sprints** organize scope-bounded campaigns
- **Sprint Research** is **mandatory** read-only planning before implementation
- **Missions** are substantial, agent-sized work packets
- **Patch Batches** group coherent changes for reliable application
- **Evidence** is append-only
- **Review/Promotion** is governance evaluation

**Key guardrails**:
- No skipping research
- No file edits during research (except research artifacts)
- No tiny slice edits — use patch batches
- No recursive hierarchy below Mission
- No workstreams

This hierarchy coordinate agents effectively while maintaining governance authority and reducing failure from fragile fine-grained edits.
