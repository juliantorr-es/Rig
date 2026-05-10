# Worktrees

Execution uses isolated external worktrees by default.

## Branch Creation Helper

Use [`scripts/rig_agent_worktree.py`](../scripts/rig_agent_worktree.py) to create and manage governed `agent/*` lanes.

Expected behavior:

- create an `agent/<task>/<agent>` branch
- create a sibling worktree under `../Rig-worktrees/`
- keep branch creation explicit
- refuse invalid slugs or conflicting branches

This helper is the operational lane controller for agent proposal work. It is the current source of truth for isolated worktree setup and should be used instead of ad hoc branch creation for governed agent lanes.

## Integration Expectations

Integration work should be routed through `preproduction`, not merged directly into `main`.

Artifacts expected from governed integration runs include:

- replay bundles or replay timelines
- topology or workspace snapshots
- frontend diagnostics
- validation summaries

## Operator Guidance

- Use `agent/*` branches for proposal work
- Use `feature/*` branches for human-directed changes
- Keep `main` protected
- Treat `preproduction` as the convergence surface
