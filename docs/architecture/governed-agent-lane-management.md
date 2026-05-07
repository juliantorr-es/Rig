# Governed Agent Lane Management

## Purpose

Rig manages isolated agent work through Git worktrees and task branches, then wraps that substrate with policy, inspection, checkpointing, validation, receipts, and explicit promotion into reviewable history.

The current MVP is the `scripts/rig_agent_worktree.py` helper and its tests. It is the operational lane controller today. The future product shape is a Rig CLI namespace that exposes the same ideas as first-class commands.

## Non-goals

- Not an IDE
- Not a Git replacement
- Not remote CI
- Not automatic push or merge
- Not automatic main mutation
- Not provider, OAuth, or PublicOps implementation
- Not a hidden daemon

## Core Objects

### AgentLane

An isolated unit of agent work tied to:

- repo root
- worktree path
- branch
- task identity
- lane state

An `AgentLane` is the governing concept behind a worktree, not the worktree itself.

### LaneCheckpoint

A deliberate checkpoint commit inside a lane. It records:

- the selected dirty files
- the commit message
- before/after HEAD
- the lane branch
- whether the checkpoint was dry-run or real

### LaneReceipt

A machine-readable receipt that records a lane action and its evidence.

### LaneValidation

A validation result for a lane or checkpoint, including tests, smoke commands, and gate status.

### LanePrompt

The guarded prompt handed to an agent before it touches a lane.

### LanePromotion

Future path from a lane branch into reviewable history. Promotion is intentionally separate from checkpointing.

## Current Command Contract

The MVP command surface lives in [`scripts/rig_agent_worktree.py`](/Users/user/Developer/GitHub/Rig/scripts/rig_agent_worktree.py) and is tested in [`tests/test_rig_agent_worktree.py`](/Users/user/Developer/GitHub/Rig/tests/test_rig_agent_worktree.py).

### `start <agent> <task>`

Purpose:
- Create a new isolated agent lane as a sibling worktree.

Inputs:
- agent slug
- task slug

Side effects:
- Creates a new branch from `main` by default.
- Creates a sibling worktree path under `../Rig-worktrees/rig-<agent>-<task>`.

Refusals:
- invalid slugs
- path already exists
- branch already exists

Mutates Git/files:
- yes, when not dry-run

Allowed on main:
- it is a repository-level action, but it still creates a non-main branch; it must not commit to main

Expected output:
- worktree path
- branch
- base
- setup commands
- guarded lane prompt

### `attach <agent> <task> --path <path>`

Purpose:
- Recognize and describe an existing linked worktree without mutating it.

Inputs:
- agent slug
- task slug
- existing worktree path

Side effects:
- none

Refusals:
- invalid slugs
- missing path
- path not in the same repository

Mutates Git/files:
- no

Allowed on main:
- read-only only

Expected output:
- lane summary
- branch convention status
- dirty files
- guarded prompt

### `prompt <agent> <task>`

Purpose:
- Print the guarded handoff prompt for a lane.

Inputs:
- agent slug
- task slug

Side effects:
- none

Mutates Git/files:
- no

Allowed on main:
- yes, read-only only

Expected output:
- guarded prompt header

### `list`

Purpose:
- Show `git worktree list`.

Side effects:
- none

Mutates Git/files:
- no

Allowed on main:
- yes, read-only only

Expected output:
- native worktree list output

### `status`

Purpose:
- Show repo root, branch, HEAD, status, and worktree list.

Side effects:
- none

Mutates Git/files:
- no

Allowed on main:
- yes, read-only only

Expected output:
- repo root
- branch
- short HEAD
- `git status --short --branch`
- `git worktree list`

### `remove <agent> <task>`

Purpose:
- Remove a lane only when it is clean.

Refusals:
- missing path
- dirty worktree

Mutates Git/files:
- yes, only when clean and not dry-run

Allowed on main:
- this is a cleanup operation on a lane; it must not delete branches

Expected output:
- refusal or confirmation

### `checkpoint <agent> <task> --path <path> --message <msg>`

Purpose:
- Turn a lane’s dirty files into a deliberate local commit.

Refusals:
- `main`
- clean worktree
- empty message
- unresolved conflict state
- unknown selection inputs

Mutates Git/files:
- yes, only when not dry-run

Allowed on main:
- no

Expected output:
- lane summary
- dirty files
- selected files
- excluded files, when relevant
- proposed commit message
- dry-run commands or real commit result

### `checkpoint --include`

Purpose:
- Select exactly the listed dirty files.

Rules:
- repeatable
- selected files must be dirty
- explicit staging only

### `checkpoint --exclude`

Purpose:
- Select dirty files minus the listed excluded files.

Rules:
- repeatable
- excluded files must be dirty
- explicit staging only

### `checkpoint --dry-run`

Purpose:
- Print the exact selection and commands without mutating anything.

Guarantee:
- dry-run and real checkpoint use the same selected file list

### `review <agent> <task> --path <path> [--base <ref>]`

Purpose:
- Produce a read-only promotion-readiness report for an existing lane.

Inputs:
- agent slug
- task slug
- existing worktree path
- optional base ref, defaulting to `main`

Side effects:
- none

Refusals:
- invalid slugs
- missing path
- repository mismatch
- unresolved base ref

Mutates Git/files:
- no

Allowed on main:
- yes, read-only only

Expected output:
- lane summary
- cleanliness
- branch convention status
- ahead/behind counts
- changed files vs base
- commits ahead of base
- ready-for-review status
- blockers
- warnings
- recommended next actions

### `promote <agent> <task> --path <path> --dry-run`

Purpose:
- Produce a read-only promotion plan for a review-ready lane.

Inputs:
- agent slug
- task slug
- existing worktree path
- optional base ref, defaulting to `main`
- optional target branch, defaulting to `sprint/<task>`
- optional strategy, defaulting to `manual`

Side effects:
- none

Refusals:
- invalid slugs
- missing path
- missing `--dry-run`
- dirty worktree
- `main` source branch
- zero commits ahead of base
- unresolved base ref
- target branch equals source branch
- unknown strategy

Mutates Git/files:
- no

Allowed on main:
- yes, read-only only

Expected output:
- lane summary
- base/target/strategy
- cleanliness
- ahead/behind counts
- commits ahead of base
- changed files vs base
- required validations
- planned operations
- future command templates
- blockers
- warnings
- ready-to-promote status

Strategy semantics:
- `manual`: human review path, default
- `pr`: future pull request planning only; prints a `gh pr create` template but does not call `gh`
- `squash`: future squash promotion planning only
- `cherry-pick`: future cherry-pick promotion planning only
- `manual` is the safest default unless a caller explicitly selects a strategy

### `recommend <agent> <task> --path <path> [--prefer <path>]`

Purpose:
- Choose the safest next governed path for a clean lane.

Inputs:
- agent slug
- task slug
- existing worktree path
- optional base ref, defaulting to `main`
- optional target branch, defaulting to `sprint/<task>`
- optional preference hint: `review`, `pr`, `squash`, `cherry-pick`, or `hold`

Side effects:
- none

Refusals:
- invalid slugs
- missing path
- repository mismatch

Mutates Git/files:
- no

Allowed on main:
- yes, read-only only

Expected output:
- lane summary
- blockers and warnings
- preferred path
- recommended path
- rationale
- future commands
- validations to run
- ready/hold state
- next safe action

Decision model:
- `hold` when blockers exist or the user preference is invalid / explicitly hold
- `review` when the lane is clean and promotable but warnings make human review the safest next step
- `pr` / `squash` / `cherry-pick` only when explicitly preferred or policy-driven and no blockers exist
- default recommendation is `review`
- warnings do not block recommendation; blockers do

## Future Rig CLI Shape

These are planned product commands, not implemented by the current MVP unless the repo explicitly adds them later.

- `rig agent lane start`
- `rig agent lane attach`
- `rig agent lane prompt`
- `rig agent lane status`
- `rig agent lane checkpoint`
- `rig agent lane validate`
- `rig agent lane promote`
- `rig sprint checkpoint`
- `rig sprint pr`

The product CLI should preserve the same governed semantics as the helper script.
Promotion remains planning-only in the current MVP; actual promotion is future work.

## Safety Invariants

- never commit to main
- never push automatically
- never merge automatically
- never rebase, reset, clean, or stash
- never remove dirty worktrees
- never stage with `git add .`
- never stage with `git add -A`
- stage explicit selected paths only
- dry-run and real checkpoint share the same selected file list
- dirty files detected and files selected for checkpoint are distinct concepts
- branch mismatch may warn but should not force metadata mutation
- suspicious untracked files require explicit include/exclude decisions

## Branch Policy

- `main`: sacred, no agent commits
- `agent/*`: messy checkpoint commits allowed
- `feature/*`: checkpoint commits allowed if assigned to the lane
- `sprint/*`: coherent checkpoint commits allowed
- main history is updated through human review, PR, and squash/merge policy

## Git Parsing Contract

Machine decisions must use `git status --porcelain=v1 -z`.

Human-facing `git status` output must not be parsed for checkpoint selection.

The parser must preserve exact file paths, including:

- spaces
- renames
- untracked files

Conflict states must be refused.

The parser must be covered by tests so it does not regress to line slicing or quote parsing.

## Selection Policy

- `--include` selects exactly the included dirty files
- `--exclude` selects dirty files minus excluded files
- include/exclude mixing is refused unless explicitly specified and tested
- unknown includes/excludes are refused
- zero selected files is refused
- selected paths are staged explicitly with `--` before file paths
- dry-run selected list and real checkpoint selected list must match

## Lifecycle States

The lane lifecycle is:

- created
- attached
- dirty
- checkpoint_planned
- checkpointed
- validated
- ready_for_review
- promoted
- removable
- removed
- abandoned

## Validation Gates

Validation is layered:

- helper tests
- lane-specific tests
- smoke commands
- promotion gates

Known commands:

- `python3.14 -m compileall -q scripts tests`
- `python3.14 -m pytest tests/test_rig_agent_worktree.py -v`
- `python3.14 -m compileall -q src tests`
- `python3.14 -m pytest tests/test_ui_repo_selection.py -v`
- `python3.14 -m pytest tests/test_ui_intent_contract.py -v`
- `python3.14 -m pytest tests/test_ui_frontend_logic.py -v`
- `python3.14 -m rig ui --help`
- `python3.14 -m rig window open --dry-run`

## Receipt Model

Future receipts should exist for:

- `lane_start`
- `lane_attach`
- `lane_prompt_generated`
- `lane_checkpoint_dry_run`
- `lane_checkpoint_commit`
- `lane_validation`
- `lane_remove_refused`
- `lane_remove`
- `lane_promote`
- `lane_recommendation`

Each receipt should include:

- repo root
- worktree path
- branch
- before HEAD
- after HEAD if changed
- dirty files detected
- selected files
- excluded files
- command summary
- result
- timestamp
- warnings
- recommended path
- rationale
- validations to run

## UI Projection Plan

Future projection widgets:

- `AgentLaneCard`
- `LaneStatusTable`
- `CheckpointPreviewCard`
- `DirtyFileList`
- `SelectedFileList`
- `ExcludedFileList`
- `NextSafeActionCard`
- `ValidationReceiptList`

The frontend remains dumb.

- backend authors safety state
- frontend renders it
- frontend emits intentions
- frontend does not infer checkpointability
- frontend does not stage files

## Promotion Path From Script to Rig Command

The script is the MVP lane controller. The product path should eventually promote the same semantics into Rig’s CLI and UI surfaces:

1. keep the helper as the executable substrate
2. expose the same concepts under `rig agent lane ...`
3. keep checkpoint selection explicit and receipted
4. add a promotion flow that turns lane work into reviewable history

Promotion is a separate step from checkpointing. Checkpointing records local, deliberate progress; promotion moves reviewed work toward shared history.

## Open Risks / Future Work

- Selective checkpointing currently solves the suspicious-file problem, but lane policy still depends on human judgment for what to include.
- `main` protection is policy-driven; repo/hosting protection should still back it up.
- `LanePromotion` is not implemented yet.
- The UI projection plan is future work.
- The helper remains a script, not a first-class Rig CLI command.
- Receipts for lane actions are defined here, but the full receipt emission pipeline is future work.
