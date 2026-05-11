# Shared Workspace Projection Transport

**ADR 0012 — Proposed**

This ADR defines the architectural transition of Rig from a single-user local tool into a **collaborative cognitive environment**. It establishes the transport and synchronization substrate required for multiple participants (humans and agents) to observe and interact with a shared governed workspace.

**Status**: proposed

**Related ADRs**:
- [0002 Projection Domain Consolidation](0002-projection-domain-consolidation.md) — shared state is derived from authoritative projections.
- [0004 Runtime Streaming Consolidation](0004-runtime-streaming-consolidation.md) — the transport substrate for real-time telemetry.
- [0009 Agentic Workflow Refinement](0009-agentic-workflow-refinement.md) — mutation authority remains governed by missions and claims.
- [0011 Runtime Visualization Substrate](0011-runtime-visualization-substrate.md) — the rendering engine for shared visual state.

---

## 1. Context & Problem Statement

As Rig expands from individual developer automation to team-based "governed agent pipelines," the need for **Shared Workspace Observability** becomes critical. Reviewers, developers, and autonomous agents need a common operating picture of the project state, active missions, and pending proposals.

Existing collaborative models (OT, CRDT) often optimize for **multi-writer concurrent editing**, which introduces significant complexity and potential for state divergence. For Rig, the primary value is in **coordinated visibility and governed intent**, not necessarily simultaneous free-form code editing.

---

## 2. Core Doctrine: Shared Visibility before Shared Mutation

Rig prioritizes **real-time shared visibility** as the foundational layer of collaboration. Shared mutation is deferred until the visibility and transport substrate is stable.

### 2.1. The Multiplayer Authority Model
- **One Governed Authority**: A single authoritative workspace projection builder maintains the "Ground Truth."
- **Many Live Observers**: Multiple participants receive the same projection deltas in real-time.
- **Many Proposed Intents**: Participants can submit intents (proposals), but these do not mutate the project state until promoted.
- **Explicit Ownership/Locks**: Mutation is guarded by the mission claim and worktree locking system (ADR 0009).

---

## 3. Proposed Architecture

The transport architecture follows a strict unidirectional flow from authority to observers.

### 3.1. The Sync Pipeline
1. **Event Log / Receipts**: The durable record of all workspace mutations and agent actions.
2. **Authoritative Projection Builder**: Consumes the event log to build the current project state snapshot.
3. **Projection Snapshot + Delta Stream**: Serializes the snapshot and emits incremental deltas (JSON-patch or similar) to participants.
4. **Shared Runtime UI**: Observers render the projection deltas into the local `SceneGraph`.

### 3.2. Presence vs. Mutation
Rig distinguishes between **Presence** (transient, eventually consistent) and **Mutation** (durable, authoritative).

| Layer | Consistency | Examples | Technology |
|---|---|---|---|
| **Presence** | Eventual | Cursors, Selections, Viewport, Active Layer | CRDT-lite / Pub-Sub |
| **Mutation** | Strong (Governed) | Mission Claims, Worktree Locks, Promotion | Rig Governance Engine |

---

## 4. Implementation Strategy (The Multiplayer Sprints)

### 4.1. Sprint MS-R1: Shared Visibility
- Implement the **Projection Delta Stream** (Server-Sent Events or WebSockets).
- Build the **Read-Only Observer** mode for the Rig UI.
- Establish the **Delta Compression** seam to minimize transport overhead.

### 4.2. Sprint MS-R2: Shared Presence
- Implement **Viewer Cursors** and **Spatial Selection Sync**.
- Build the **"Follow User"** capability to synchronize viewports for collaborative review.
- Visualize **Agent Activity Lanes** across all connected clients.

### 4.3. Sprint MS-R3: Governed Multiplayer
- Implement **Shared Claim Visualization** (who owns which worktree).
- Build the **Proposal Overlay Visualization** for shared review of agent patches.
- Support **Collaborative Promotion Gates** (multi-human sign-off).

---

## 5. Non-Goals

- ADR 0012 does **not** implement real-time collaborative code editing (e.g., Google Docs for code).
- ADR 0012 does **not** allow multi-writer mutation without explicit governance locks.
- ADR 0012 does **not** introduce a cloud-hosted authoritative state; authority remains local or repo-bound.
- ADR 0012 does **not** optimize for low-latency gaming-style synchronization.

---

## 6. Architectural Consequences

### 6.1. Leverage
- **Shared Context**: Teams can review agent behavior in the exact same spatial frame.
- **Reduced Friction**: Promotion and review become synchronous collaborative acts rather than asynchronous PR cycles.

### 6.2. Risks
- **Network Partitioning**: Handling observers who drop out of the delta stream.
- **Projection Complexity**: Delta generation for complex execution graphs may become compute-intensive.

### 6.3. Locality
Transport logic is encapsulated in a new `TransportAdapter`, preserving the isolation of the `RenderGraph` and `ProjectionBuilder`.

---

## 7. Summary

ADR 0012 establishes the "Multiplayer Rig" foundation by focusing on **shared visibility**. By splitting presence from mutation and maintaining a single authoritative projection builder, we provide a collaborative environment that scales to teams without the consistency risks of distributed editing.
