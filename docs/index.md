# Rig

Rig is the cryptographically governed control plane for local AI coding.

It wraps repositories in isolated worktrees, receipts, review bundles, and explicit apply gates.

Phase 6 adds governed orchestration jobs that stop at human gates instead of mutating main automatically. Phase 7 hardens that job store so the queue is durable and repairable.

## Architecture

- [Domain Context](../CONTEXT.md) — Vocabulary and concepts.
- [UI Doctrine](architecture/UI_DOCTRINE.md) — Rig UI strategy and model.
- [Governance Engine](architecture/governance-engine.md) — Central authority for action legality.
- [Governed Agent Lane Management](architecture/governed-agent-lane-management.md) — Worktree-based agent lanes, checkpointing, and promotion path.
- [Proposal Lifecycle](architecture/proposal-lifecycle.md) — Future plan for proposal state management.
- [PublicOps Architecture](architecture/public-ops.md) — Future public collaboration surface architecture.
- [Execution Sandbox](architecture/execution-sandbox.md) — Managed execution and isolation.
- [UI Projections](architecture/ui-projections.md) — Unidirectional data flow for TUIs and Web UIs.
