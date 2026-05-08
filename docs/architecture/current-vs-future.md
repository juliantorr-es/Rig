# Rig: Current vs. Future Systems

This document clarifies the implementation status of various Rig subsystems. It is intended to prevent contributor confusion by separating active runtime capabilities from planned research and speculative designs.

---

## 1. Classification Definitions

| Classification | Meaning |
|----------------|---------|
| **Implemented** | Active in the runtime, tested, and ready for operational use. |
| **Canonical Doctrine** | Established philosophy and rules that govern existing and future systems. |
| **Experimental** | Partially implemented or available as a prototype/CLI helper. |
| **Planned** | Approved architecture and contracts, but implementation has not started. |
| **Research** | Speculative design or exploration of future capabilities. |
| **Future Capability** | Long-term roadmap items without a fixed architecture yet. |

## 2. System Status Map

### 2.1 Core Governance & Integrity
- **Implemented**: `GovernanceEngine` (basic legality), `IntegrityEngine` (finding generation), `ReceiptEnvelope` (v1), `AuditEvent` logging.
- **Canonical Doctrine**: "Deny by Default", "Everything Leaves a Receipt", "Trust Level Hierarchy".
- **Planned**: Advanced multi-actor signing for receipts, formal gate proofs.

### 2.2 Workspace & Agent Lanes
- **Implemented**: Git worktree isolation (via `rig_agent_worktree.py`), workspace record persistence, basic status transitions.
- **Experimental**: `AgentLane` management (currently handled via CLI script helpers).
- **Planned**: First-class `rig lane` CLI namespace, lane registry state in domain objects.

### 2.3 Replay & Determinism
- **Implemented**: `replay_workspace_from_fs`, deterministic state reconstruction, determinism validation tests.
- **Canonical Doctrine**: "Deterministic Reconstruction from Receipts", "Historical Truth Sovereignty".
- **Planned**: Cross-workspace replay integrity checks.

### 2.4 Visualization & UI
- **Implemented**: Projection-backed rendering, SVG instrumentation (v1), `dtg-svg-bindings.js`, core widgets (status, topology, stream).
- **Experimental**: High-density topology collapsing.
- **Canonical Doctrine**: "Truthful Animation", "Dumb UI renderers", "Advisory-only Visualization".
- **Future Capability**: Advanced interactive topology manipulation (governed).

### 2.5 Operational Trust & Pipeline
- **Implemented**: `preproduction-governance.md` gates (basic), `protected-branch-governance.md`.
- **Planned**: `Integration Soak` automation, formal `Review Bundle` receipts.
- **Future Capability**: `PublicOps` (governed collaboration with external SaaS).

### 2.6 Execution Sandbox
- **Implemented**: Basic process isolation in worktrees.
- **Research**: `execution-sandbox.md` (hardening strategies like gVisor or Firecracker).
- **Planned**: Formal sandbox provider contract.

## 3. Contributor Note

If you are contributing to a system marked **Planned** or **Research**, your focus should be on **refining contracts and architecture** rather than deep runtime implementation. If you are contributing to **Implemented** systems, focus on **robustness, validation, and documentation accuracy**.
