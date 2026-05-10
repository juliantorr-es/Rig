# Rig Doctrine Map

This document defines the layers of responsibility and authority within Rig's documentation and implementation. It establishes the boundaries between different subsystems to prevent architectural confusion.

---

## 1. Doctrine Layers

| Layer | Responsibility | Authority |
|-------|----------------|-----------|
| **Governance Doctrine** | Defines what is *allowed*. Evaluates legality, handles policy, and manages the decision engine. | Primary Authority |
| **Workspace Doctrine** | Defines the *boundary*. Manages lifecycle, worktrees, lanes, and the persistence of receipts/audit events. | Foundation |
| **Runtime Doctrine** | Defines how things *execute*. Manages agent monitoring, stream handling, and execution state. | Operational |
| **Replay Doctrine** | Defines how things are *reconstructed*. Ensures determinism, handles history, and provides the "Source of Truth" for derived views. | Historical Truth |
| **Visualization Doctrine** | Defines how things are *seen*. Manages projections, widgets, and the mapping of state to geometry. | Advisory |
| **Motion Doctrine** | Defines how things *move*. Ensures truthful animation, manages cadence, and enforces state-driven timing. | Aesthetic Truth |
| **Integration Doctrine** | Defines how things *connect*. Manages preproduction gates, CI/CD interfaces, and external tool coordination. | Coordination |
| **Extensibility Doctrine** | Defines how things *expand*. Sets constraints for plugins, instrumentation, and custom widgets to ensure they remain replay-safe. | Constraints |

## 2. Relationships and Authority

- **Governance → Runtime**: The Governance Doctrine provides the constraints within which the Runtime must operate.
- **Workspace → Replay**: The Workspace Doctrine provides the immutable evidence (receipts/audit events) that the Replay Doctrine uses to reconstruct state.
- **Replay → Visualization**: The Replay Doctrine provides the deterministic state frames that the Visualization Doctrine projects into the UI.
- **Visualization → Motion**: The Visualization Doctrine provides the geometric changes that the Motion Doctrine animates truthfully.

## 3. Boundary Guarantees

1. **Advisory Neutrality**: Visualization and Motion doctrines MUST NOT infer authority or mutate domain state.
2. **Deterministic Sovereignty**: The Replay Doctrine is the sole authority on reconstructed state; it never "guesses" or auto-repairs history.
3. **Deny-by-Default Sovereignty**: The Governance Doctrine is the final arbiter of intent; no other layer can bypass its decision.
4. **Receipt-Native Authority**: All state transitions must originate from a receipt defined by the Workspace Doctrine.
