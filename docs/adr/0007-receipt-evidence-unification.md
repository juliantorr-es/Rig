# Receipt/Evidence Unification

The **Evidence** concept (CONTEXT.md: "Durable proof of an event (Receipts)") is defined as the authoritative record, but the implementation is shallow across multiple modules. `receipt_envelope.py` (60K+ lines) contains receipt building, validation, and derivation logic. `receipts.py` defines a separate `ReceiptStore`. No single module owns the **Evidence** concept end-to-end. We should create a **EvidenceDomain** that unifies all receipt/evidence concerns.

**Status**: proposed

## Context

- `src/rig/domain/receipt_envelope.py` — 60K+ lines: `ReceiptEnvelope`, actor/subject models, receipt types, building helpers, validation
- `src/rig/domain/receipts.py` — `ReceiptStore`, `ReceiptQuery`, store operations
- `src/rig/domain/progress_receipt_derivation.py` — deriving receipts from progress events
- `src/rig/commands_public_intake.py` — creates intake receipts directly
- Various domain modules create receipts directly using `build_receipt_envelope()`
- No single seam for evidence/receipt operations

## Decision

Create a **EvidenceDomain** deep module that:
- Owns all evidence types (`ReceiptEnvelope`, `Receipt`, etc.)
- Owns the receipt store and query interface
- Owns receipt derivation from events/progress
- Owns receipt validation and verification
- Exposes interfaces:
  - `EvidenceDomain.create(receipt_input: ReceiptInput) -> ReceiptEnvelope`
  - `EvidenceDomain.append(envelope: ReceiptEnvelope) -> str` (returns receipt_id)
  - `EvidenceDomain.query(filter: ReceiptFilter) -> List[ReceiptEnvelope]`
  - `EvidenceDomain.derive_from_progress(event: ProgressEvent) -> Optional[ReceiptEnvelope]`
  - `EvidenceDomain.validate(envelope: ReceiptEnvelope) -> ValidationResult`
- All receipt creation goes through this module

## Consequences

**Leverage**: One place for all evidence/receipt operations. New receipt type? One place. New derivation rule? One place. Change receipt schema? One place.

**Locality**: All receipt-related knowledge concentrated. Schema changes, validation logic, store operations — all in one module.

**Testability**: Test evidence through domain interface. Create receipt, append to store, query, validate. Tests don't need to know about envelope internals or store implementation.

**Seam**: `EvidenceDomain` interface is the seam. Two adapters: production (real filesystem store) and test (in-memory store).

## Files Involved

- `src/rig/domain/evidence_domain.py` — new deep module (public interface)
- `src/rig/domain/evidence_domain/_types.py` — internal: all receipt types
- `src/rig/domain/evidence_domain/_store.py` — internal: store and query
- `src/rig/domain/evidence_domain/_derivation.py` — internal: derivation logic
- `src/rig/domain/evidence_domain/_validation.py` — internal: validation
- `src/rig/domain/receipt_envelope.py` — deprecated, types/logic move to new module
- `src/rig/domain/receipts.py` — deprecated
- `src/rig/domain/progress_receipt_derivation.py` — deprecated
- All consumers — update to use `EvidenceDomain` instead of direct receipt creation

## Migration Path

1. Create new `evidence_domain` package with composite types
2. Move all types from `receipt_envelope.py` into `_types.py`
3. Move store from `receipts.py` into `_store.py`
4. Move derivation from `progress_receipt_derivation.py` into `_derivation.py`
5. Create unified validation in `_validation.py`
6. Expose public interface methods
7. Update all receipt creation sites to use `EvidenceDomain.create()`
8. Update all store access to use `EvidenceDomain.query()`
9. Deprecate old modules
10. Delete old modules once migrated
