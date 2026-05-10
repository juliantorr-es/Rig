# Rig Contributor Orientation

Welcome to Rig. This document explains how to approach the codebase safely and effectively, respecting the established doctrines and governance rules.

---

## 1. How to Approach the Repo

Rig is not a standard web application or a generic CLI tool. It is a **governed operational systems platform**. This means:

- **Doctrine First**: Before changing code, understand the doctrine that governs that subsystem.
- **Evidence Over Intent**: Implementation must focus on producing and validating evidence (receipts), not just "making it work."
- **Replay Safety is Mandatory**: Any change to state management must be validated against the Replay system.
- **Dumb UI**: The frontend is a derived view. Never add business logic or authority inference to the UI.

## 2. Contributor Guidelines by Type

### 🎨 Frontend / UI Contributor
- **Focus**: Consuming projections, building widgets, ensuring truthful visualization.
- **Safety**: Never mutate domain state from the UI. Use `textContent` and `createElement` to avoid injection.
- **Critical Docs**: [visual-execution-doctrine.md](visual-execution-doctrine.md), [frontend-systems-architecture.md](frontend-systems-architecture.md), [ui-projections.md](ui-projections.md).

### ⚙️ Runtime / Backend Contributor
- **Focus**: Workspace lifecycle, agent orchestration, streaming, execution.
- **Safety**: Ensure every state transition produces a receipt. Respect the Trust Level boundaries.
- **Critical Docs**: [workspace-control-plane.md](workspace-control-plane.md), [runtime-streaming.md](runtime-streaming.md), [governance-replay.md](governance-replay.md).

### 🛡️ Governance / Security Contributor
- **Focus**: `GovernanceEngine`, `IntegrityEngine`, validation gates.
- **Safety**: Maintain the "Deny by Default" posture. Ensure rules are deterministic and auditable.
- **Critical Docs**: [governance-engine.md](governance-engine.md), [integrity-validation.md](integrity-validation.md), [receipt-formalization.md](receipt-formalization.md).

### 🚀 CI / Operational Contributor
- **Focus**: Preproduction gates, integration soak, release governance.
- **Safety**: Protect the `main` branch. Ensure validation scripts are rigorous and fast.
- **Critical Docs**: [preproduction-governance.md](preproduction-governance.md), [protected-branch-governance.md](protected-branch-governance.md), [release-checklist.md](../release/release-checklist.md).

### 🧪 Research / UX Contributor
- **Focus**: Motion cadence, disclosure scaling, runtime learning.
- **Safety**: Ensure "truthful animation" is preserved. Design for cognitive load management.
- **Critical Docs**: [truthful-animation.md](truthful-animation.md), [visual-priority-hierarchy.md](visual-priority-hierarchy.md), [experiential-runtime-learning.md](experiential-runtime-learning.md).

## 3. Avoiding Doctrine Violations

1. **No Authority Leaks**: Do not let the UI decide what is "allowed."
2. **No Synthetic State**: Do not invent state in projections that doesn't exist in receipts.
3. **No Hidden Transitions**: Do not transition workspace status without an audit event.
4. **No Destructive Recovery**: Do not use `git reset --hard` or `rm -rf` as part of a tool's recovery logic.

## 4. Navigation Strategy

1. Start with the **Navigation Map** in [README.md](README.md).
2. Follow the **Canonical Reading Path** for your contributor type.
3. Consult the **Terminology** in [terminology.md](terminology.md) to avoid synonyms.
4. Verify your implementation against the **Convergence Audit** in [convergence-audit.md](convergence-audit.md).
