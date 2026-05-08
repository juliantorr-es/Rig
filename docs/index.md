# Rig

Rig is the cryptographically governed control plane for local AI coding.

It wraps repositories in isolated worktrees, receipts, review bundles, and explicit apply gates.

Phase 6 adds governed orchestration jobs that stop at human gates instead of mutating main automatically. Phase 7 hardens that job store so the queue is durable and repairable.

## Architecture

- [Domain Context](../CONTEXT.md) — Vocabulary and concepts.
- [UI Doctrine](architecture/UI_DOCTRINE.md) — Rig UI strategy and model.
- [Governance Engine](architecture/governance-engine.md) — Central authority for action legality.
- [Governed Agent Lane Management](architecture/governed-agent-lane-management.md) — Worktree-based agent lanes, checkpointing, and promotion path.
- [Workspace Control Plane](architecture/workspace-control-plane.md) — Workspace as the authority boundary for governed lanes.
- [Workspace Status Summary](architecture/workspace-status-summary.md) — Canonical read-only workspace substrate summary.
- [Workspace UI Projection Contract](architecture/workspace-ui-projection-contract.md) — Backend-authored workspace and lane widgets.
- [Workspace Progress Stream](architecture/workspace-progress-stream.md) — Live telemetry for workspace and lane operations.
- [Projection Renderer Frontend](architecture/projection-renderer-frontend.md) — Browser-native ES-module renderer for backend projections.
- [Agent Workflow Gates](dogfood/agent-workflow-gates.md) — Dogfood gate policy for allowed and blocked agent workflows.
- [Proposal Lifecycle Console Sprint](sprints/proposal-lifecycle-console.md) — Sprint charter and backlog for the proposal lifecycle console.
- [Proposal Lifecycle](architecture/proposal-lifecycle.md) — Future plan for proposal state management.
- [PublicOps Architecture](architecture/public-ops.md) — Future public collaboration surface architecture.
- [Execution Sandbox](architecture/execution-sandbox.md) — Managed execution and isolation.
- [UI Projections](architecture/ui-projections.md) — Unidirectional data flow for TUIs and Web UIs.
