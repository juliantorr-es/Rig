# Governance Engine Architecture

## Overview

The **Governance Engine** is a core domain service in Rig that serves as the central authority for action legality. It answers a fundamental question for any actor (CLI, TUI, or Web UI): **"What is allowed now, what is blocked, and why?"**

By centralizing governance logic into a pure domain module, we ensure that security gates and workspace invariants are enforced consistently across all interfaces, rather than being scattered across shallow command handlers or UI state logic.

## Core Concepts

### 1. Decision-Oriented Evaluation
The engine does not perform actions (like running validators or mutating files). It evaluates the **loaded state** of the workspace, proposals, and evidence against configured policies.

### 2. GateDecision
The primary output of the engine is a `GateDecision` object. This is a rich data structure that includes:
- **Decision Status:** `allowed`, `blocked`, `requires_review`, or `not_applicable`.
- **Reasons:** A list of `DecisionReason` objects explaining the severity and context of the decision.
- **Allowed/Blocked Intents:** Explicit lists of which Rig intents (e.g., `intent.apply_patch`) are permitted in the current state.

## Domain Model

Located in `src/rig/domain/governance/`:

- **`decisions.py`**: Defines the data structures for evaluation results (`GateDecision`, `DecisionReason`, `BlockedIntent`).
- **`engine.py`**: Contains the `GovernanceEngine` class, which implements the evaluation logic.

## Evaluation Flow

The engine evaluates state in a hierarchical manner:

1.  **Workspace Level:** Is there an active workspace? If not, most destructive or state-changing actions are blocked.
2.  **Proposal Level:** Is there a proposal being evaluated?
3.  **Evidence Level:** Have the necessary governance gates (e.g., validators) been satisfied? Is there evidence (receipts) of passing results?
4.  **Policy Level:** Does the current user or environment allow for the requested action (e.g., `allow_auto_apply`)?

## UI Integration (Projection/Intention Loop)

The Governance Engine is the authority behind the UI's projection and intention loop:

1.  **Projection:** The backend builds a UI projection. It calls `GovernanceEngine.evaluate_action_legality()` and uses the resulting `GateDecision` to set the `enabled` and `disabled_reason` properties of UI intents.
2.  **Intention:** When a user submits an intent, the backend re-evaluates the governance state. If the intent is blocked by the engine, the request is rejected with a clear explanation, regardless of whether the UI had the action "enabled."

## Benefits

- **Locality:** All security and governance logic lives in one place, making it easier to audit and update.
- **Leverage:** Callers (CLI commands, UI servers) get high leverage by asking a single question to receive a comprehensive legality decision.
- **Consistency:** The same rules apply whether you are using the terminal or the dashboard.
- **Testability:** The engine is pure and can be exhaustively tested against various state combinations without requiring complex environment mocks or filesystem operations.
