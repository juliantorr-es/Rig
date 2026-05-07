# Context Pack: Evidence Rail & Receipt Inspection

## Goal
Make execution receipts (specifically validator results) first-class, inspectable objects in the Rig cockpit, ensuring all execution outcomes are auditable and traceable.

## Architectural Rule
**Evidence is Authoritative.** The UI must reconcile its status widgets (e.g., `ValidatorStack`) directly against the `ReceiptStore` database, never against ephemeral stream chunks or frontend state.

## Implementation Plan

### 1. Projection Structure
- **`ReceiptDetail` Widget**: A new projection type for rendering a specific receipt's content.
- **Selection State**: The `ProjectionBuilder` must receive `selected_receipt_id` from the intent store to populate the `ReceiptDetail` region.

### 2. Frontend Evidence Rail
- **Selectability**: `ReceiptList` rows must be interactive (dispatch `intent.select_receipt`).
- **Safe Disclosure**: The `ReceiptDetail` renderer MUST use `createElement` + `textContent` for raw JSON disclosure. Dynamic `innerHTML` is forbidden to prevent injection from potentially malicious receipt fields.
- **Persistence**: Selection should persist if the widget ID remains stable across updates.

### 3. Validator Reconciliation
- **Source of Truth**: The `ValidatorStack` widget data must be derived by querying `ReceiptStore` for the *latest* receipt matching a specific `validator_id`.
- **Linking**: `ValidatorStack` items should link to their corresponding `receipt_id`, allowing the Evidence Rail to auto-select the result on click.

### 4. Deterministic Chat Answers
- The backend chat handler must check the `ReceiptStore` for the latest receipt when a user asks "what happened?" or "why did it fail?".
- The chat projection should then present the receipt summary as a structured snippet, not a natural language hallucination.

## Agent Checklist
- [ ] Does `ProjectionBuilder` query the latest receipt for `ValidatorStack` status?
- [ ] Is raw JSON rendered safely (`textContent`)?
- [ ] Does selecting a receipt update the `ReceiptDetail` region?
- [ ] Can users inspect raw receipt JSON without XSS risk?
- [ ] Do deterministic chat answers reference receipt content accurately?
