# Workspace Control Plane

## Purpose

Rig treats a **Workspace** as the project authority boundary. A workspace owns the repository root, workspace configuration, base-branch policy, receipts, projections, and future lane registry state. An **AgentLane** is a governed child of a workspace: one worktree path, one branch, one agent/task identity, and one explicit lane history.

Git worktrees are the substrate. Rig wraps them with policy, inspection, checkpointing, validation, receipts, and promotion planning. The current operational MVP is the `scripts/rig_agent_worktree.py` helper. The full workspace runtime is future work.

## Non-goals

- Not an IDE
- Not a Git replacement
- Not remote CI
- Not provider sync
- Not OAuth
- Not automatic push, merge, rebase, or main mutation
- Not a hidden daemon

## Core Objects

### Workspace

The Workspace is the container for governed work. It owns:

- repo root
- workspace config
- base branch policy
- receipts
- projections
- validation gates
- future lane registry state

The workspace is the authority boundary. It can observe lanes, receipts, and projections, but it does not invent lane state.

### AgentLane

An AgentLane is a child of a Workspace. It maps to:

- one worktree path
- one branch
- one agent identity
- one task identity
- one explicit lane state history

Agent lanes may create checkpoint commits on non-main branches under policy. Main remains protected.

### Operation

An Operation is a live command or action performed in a Workspace and optionally on an AgentLane.

Operations:

- stream telemetry
- may emit receipts
- may refresh projections
- are not durable authority by themselves

### Receipt

A Receipt is durable evidence that an operation or validation happened. Receipts belong to a Workspace and may optionally attach to an AgentLane or Operation.

Future receipt kinds include:

- lane_start
- lane_attach
- lane_prompt_generated
- lane_checkpoint_dry_run
- lane_checkpoint_commit
- lane_validation
- lane_remove_refused
- lane_remove
- lane_promote
- lane_recommendation

### Projection

A Projection is a backend-authored snapshot for the frontend. It contains workspace widgets, lane widgets, receipts, and next actions.

The frontend renders what the backend authors. It must not infer governance, checkpointability, file selection, or promotion readiness.

### Frontend

The frontend is dumb by design.

- It renders backend-authored state.
- It emits backend-defined intentions.
- It does not select files.
- It does not decide checkpointability.
- It does not fabricate commands.

## Current State

The workspace control plane is not fully implemented yet.

Current truthful surfaces:

- `scripts/rig_agent_worktree.py` for governed agent lane operations
- `src/rig/domain/projection_builder.py` for backend-authored workspace placeholder widgets
- `src/rig/commands_workspace.py` for read-only workspace planning entrypoints and legacy workspace support

Future workspace runtime work should continue to treat agent lanes as governed children of Workspaces, not as free-floating branch state.

## Doctrine

- Workspace is the container.
- Agent lanes are governed children.
- Progress streams are live telemetry.
- Receipts and projections are durable authority.
- Frontend widgets render backend-authored state only.

## Future Work

- connect lane registry to workspace state
- promote agent lane planning into workspace-aware commands
- wire receipts to workspace and lane operations more explicitly
- make workspace projection the primary authority surface for the UI
