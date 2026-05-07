# Proposal Lifecycle Module (Future Implementation)

## Overview

The **Proposal Lifecycle Module** will manage the transitions of a `Proposal` from initial decoding to final application or rejection. It separates the concerns of persistence and state transitions from governance evaluation.

## Components

### 1. ProposalStore
Responsible for:
- Loading and saving proposal records (JSON/YAML).
- Listing proposals within a workspace.
- Managing schema migrations for proposal artifacts.
- **Invariant:** Does not make governance decisions; purely a data access layer.

### 2. ProposalLifecycle
Responsible for:
- **Registration:** Assigning a unique ID and persisting a newly decoded proposal.
- **State Transitions:** Validating that state changes (e.g., `proposed` -> `accepted`) are legal.
- **Event Emission:** Emitting events or receipts when state changes occur.
- **Archive:** Safely moving inactive or superseded proposals out of the active set.

## Proposed State Machine

- `decoded`: Translated from raw model output, not yet persistent.
- `proposed`: Registered in the workspace, awaiting evaluation.
- `review_required`: Evaluated by Governance Engine, requires manual approval.
- `accepted`: Formally approved as a valid set of advisory changes.
- `rejected`: Explicitly declined.
- `applied`: Changes have been merged/executed.
- `superseded`: A newer proposal has replaced this one.

## Interaction with Governance Engine

The Lifecycle module depends on the Governance Engine to authorize transitions:

```python
proposal = proposal_store.get(proposal_id)
decision = governance.evaluate_proposal(workspace_id, proposal)

if decision.decision == "allowed":
    proposal_lifecycle.accept(proposal_id, actor="validator.auto")
else:
    # Blocked or review required
    pass
```

## Benefits

- **Consistency:** Ensures proposals cannot bypass governance gates.
- **Traceability:** Durable records of why and how a proposal transitioned between states.
- **Simplicity:** CLI and UI handlers no longer manage file paths or state logic directly.
