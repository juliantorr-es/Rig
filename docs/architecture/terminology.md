# Rig Canonical Terminology

This document establishes the canonical meaning of terms used across the Rig codebase and documentation. Adherence to this language is mandatory to prevent semantic drift.

---

## 1. Core Domain Terms

| Term | Canonical Meaning |
|------|-------------------|
| **Workspace** | The project authority boundary. Owns the repository root, configuration, base-branch policy, receipts, and projections. |
| **AgentLane** | A governed child of a workspace: one worktree path, one branch, one agent/task identity, and one explicit lane history. |
| **Governance** | The system of rules and engines (e.g., `GovernanceEngine`) that evaluate the legality of proposed actions. |
| **Runtime** | The active execution environment where agents perform tasks and Rig monitors/governs their progress. |
| **Replay** | The deterministic reconstruction of workspace state from immutable evidence (receipts and audit events). |
| **Projection** | A derived, UI-optimized view of domain state. Projections are Trust Level 2 and never authoritative. |
| **Receipt** | An immutable, cryptographically signed record of an action, decision, or state transition. |
| **Audit Event** | An immutable record in the workspace audit trail, forming the basis for replay. |

## 2. Visualization & UX Terms

| Term | Canonical Meaning |
|------|-------------------|
| **Topology** | The geometric arrangement and connectivity of system components (e.g., lanes, nodes, edges) in the UI. |
| **Instrumentation** | The process of capturing and exposing runtime telemetry and state transitions for visualization. |
| **Disclosure** | The progressive reveal of information (e.g., "Widget Disclosure") to manage cognitive load without hiding truth. |
| **DTG** | **Deterministic Topology Graph**. A graph visualization where node IDs and layout are derived deterministically from state. |
| **Truthful Animation** | Motion that is driven strictly by state transitions or sequence progression, never by synthetic timers. |
| **Topology Lane** | A visual representation of an `AgentLane` within the system topology. |

## 3. Operational & Pipeline Terms

| Term | Canonical Meaning |
|------|-------------------|
| **Preproduction** | The stages of validation and governance that occur before a change is applied to the main branch. |
| **Integration Soak** | A period of observation in a governed environment to ensure a change doesn't introduce regressions. |
| **Extension** | A modular addition to Rig's capabilities (e.g., instrumentation extension) that must follow replay-safe constraints. |
| **Replay-Safe** | A property of a system or extension ensuring its state can be perfectly reconstructed from existing receipts. |
| **Trust Level** | A categorization of data authority (0-3). Trust never increases as data moves from receipts (0) to UI (3). |
| **Authority** | The explicit right to make a decision or transition state, typically established via a receipt. |
