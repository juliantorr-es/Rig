# Workspace as Substrate

The workspace is the operational environment, not merely a repository checkout. Rig uses the workspace as a governed boundary for execution, replay, telemetry, and promotion.

## Core Ideas

| Concept | Meaning |
|---|---|
| `.rig/` | Governed operational infrastructure owned by Rig |
| Worktree | Operational lane for isolated execution |
| Workspace | Full governed environment containing code, policy, artifacts, and runtime state |
| Replay namespace | Deterministic partition for reconstructing history |
| Artifact segregation | Separation of logs, receipts, summaries, and generated outputs |
| Runtime isolation | Ports, caches, streams, and artifacts stay isolated per lane |
| Integration staging | Promotion boundary before merge authority |

## Workspace Lifecycle

| Stage | Purpose |
|---|---|
| Created | A governed lane is initialized |
| Active | Execution and observation occur inside the lane |
| Staged | Outputs are prepared for validation or review |
| Promoted | A validated result is submitted for integration |
| Archived | The lane is no longer active, but its artifacts remain replayable |

## Operational Rules

- Every workspace has a distinct operational identity.
- Replay artifacts and runtime telemetry remain namespaced to the workspace.
- No lane should assume shared runtime state unless it is explicitly governed.
- The workspace is the unit of isolation for concurrent agent work.

## What This Replaces

- Ad hoc shared working directories.
- Implicit artifact placement.
- Unscoped replay outputs.
- Cross-agent collisions in runtime or cache state.

