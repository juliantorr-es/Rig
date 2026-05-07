# Rig Domain Context

## Core Concepts

- **Workspace** — A governed environment for work items.
- **Worktree** — An isolated Git environment for untrusted execution.
- **Proposal** — An advisory set of changes or actions decoded from agent output.
- **Gate** — A governance checkpoint (e.g., validator pass) required before applying changes.
- **Evidence** — Durable proof of an event (Receipts), typically used to satisfy gates.
- **Intent** — A requested action from the user or agent (e.g., "Apply Patch").
- **Projection** — A derived view of the domain state optimized for UI consumption.

## Governance

- **Governance Engine** — The central domain authority for evaluating action legality.
- **GateDecision** — The result of a governance evaluation, determining if an intent is allowed or blocked.
- **DecisionReason** — A structured explanation for a `GateDecision`.

## Lifecycle

- **Decoded** — Raw agent output translated into a structured proposal.
- **Registered** — A proposal persisted and identified within a workspace.
- **Accepted** — A proposal approved as technically valid/advisory.
- **Applied** — A proposal merged into the main branch or final output.
