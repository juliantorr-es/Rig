# Context Pack: Governance Engine Architecture

## Core Concepts

- **Governance Engine**: The central domain service that evaluates action legality.
- **GateDecision**: A rich, data-driven result object (`allowed`, `blocked`, `requires_review`, `not_applicable`) containing `DecisionReason`s and `BlockedIntent`s.
- **Intent-based Security**: Every UI action must map to an "Intent" which is validated by the engine before execution.

## Architectural Patterns

- **Separation of Concerns**: Pure evaluation of governance rules (Decider) vs. execution of commands (Executor).
- **Deny-by-default**: All intents are blocked unless explicitly allowed by the Governance Engine.
- **Backend-Authoritative**: The UI provides the *request*, but the backend makes the final *decision*. The UI must never infer legality based on client-side state.
- **Auditability**: All decisions must return structured `DecisionReason`s for UI explanation and backend logging.

## Governance Design Checklist

- [ ] Is the evaluation pure? (Does it avoid side effects like file mutation or external network calls?)
- [ ] Are all gate decisions returned as `GateDecision` objects?
- [ ] Does the evaluation account for the current `Proposal` and `Evidence` (Receipts)?
- [ ] Are intents explicitly blocked or allowed based on the governance state?
- [ ] Does the UI receive structured reasons for "blocked" states?

## Recommended Implementation (MVP)

The Governance Engine should follow a hierarchical evaluation flow:
1. **Workspace Check**: Is a workspace active?
2. **Proposal Check**: Is a proposal present?
3. **Evidence/Gate Check**: Have the required gates (e.g., validators) been passed?
4. **Policy Check**: Does the current user/config policy permit the intent?

## Threat Model Reminders
- **Untrusted Output**: Model-generated proposals must be treated as untrusted until validated.
- **Governance Evasion**: Frontend logic can be easily bypassed. The backend MUST re-validate all intents using the `GovernanceEngine` before dispatching.
