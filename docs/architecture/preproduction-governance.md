# Preproduction Governance Model

## Purpose

Rig uses `preproduction` as the governed integration branch between individual agent proposals and the stable `main` branch.

This branch exists to absorb concurrent agent work, validate deterministic behavior, and provide a human-controlled convergence point before promotion to `main`.

Core doctrine:

- Models propose
- Governed infrastructure validates
- Humans decide

## Branch Topology

### `main`

- Stable trusted runtime
- Protected branch
- No direct pushes
- No direct agent merges
- Requires validation and review before merge

### `preproduction`

- Integration and convergence branch
- Protected branch
- Receives approved agent proposal branches
- Runs mandatory validation before promotion to `main`
- Serves as the canonical preproduction soak surface

### `agent/*`

- Agent proposal branches
- Used for isolated, bounded submissions from automated or semi-automated agents
- Must merge by pull request into `preproduction`
- Must not be pushed directly into `main`

### `feature/*`

- Human-directed feature branches
- Used for changes led by a human maintainer or contributor
- May target `preproduction` when they participate in the integration lane

### `experiment/*`

- Unsafe exploratory work
- May be used for local experimentation or disposable prototyping
- Must not be treated as trusted integration input

## Merge Flow

1. An agent produces a proposal on an `agent/*` branch.
2. The proposal is submitted as a pull request targeting `preproduction`.
3. Governed validation runs on the pull request.
4. Reviewers inspect the proposal and its artifacts.
5. The branch soaks in `preproduction` if additional integration confidence is required.
6. A human reviewer approves promotion from `preproduction` to `main`.
7. `main` receives only reviewed, validated, integration-safe changes.

## Explicit Prohibitions

- No direct agent merge to `main`
- No direct push to protected branches
- No bypass of replay validation
- No bypass of frontend contract validation
- No autonomous merge-to-main flow
- No AI self-approval loop
- No automatic rebase system
- No force-push workflow for governed branches
- No destructive Git operations as part of integration governance

## Branch Lifecycle

### Agent proposal lifecycle

- Create `agent/<scope>` from the current governed base branch
- Make the smallest coherent change set
- Validate locally when possible
- Open a PR against `preproduction`
- Submit artifacts and validation evidence with the PR

### Preproduction lifecycle

- Collect approved agent and human feature submissions
- Validate the integrated branch deterministically
- Hold the branch during soak until the current validation window is clean
- Promote only after human approval

### Promotion lifecycle

- `preproduction` is the only branch allowed to converge multiple concurrent sprints/ADRs
- Promotion to `main` is a deliberate human action
- Promotion requires the branch to remain stable under replay, projection, and frontend contract checks

## Integration Expectations

### Replay validation

Integration work on `preproduction` must remain replay-safe. Any change that affects event ordering, receipts, or deterministic reconstruction must be treated as replay-sensitive.

### UI validation

Changes that affect the browser or projection surfaces must preserve frontend contract integrity and startup behavior.

### Topology stability

Changes that affect workspace, runtime, or agent topology must not silently rename, remove, or rewire governed nodes without an explicit review trail.

## Branch Creation Guidance

This model expects branch creation to be explicit and auditable.

Recommended conventions:

- `agent/<task>` for submitted proposals
- `feature/<task>` for human-directed work
- `experiment/<topic>` for disposable exploration

The helper used to create branches should always make the target branch explicit and never imply protected-branch bypass.

## Governance Outcome

`preproduction` exists so Rig can safely scale to multiple concurrent agents without losing deterministic replay guarantees, frontend contract integrity, or human authority over merge decisions.
