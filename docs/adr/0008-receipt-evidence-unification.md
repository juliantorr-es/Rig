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

Create a **EvidenceDomain** deep module that unifies all receipt/evidence concerns. Currently 3 files with 2,307 lines and scattered creation sites; after: 1 public interface with internal seams.

### New Interface
- `EvidenceDomain.create(receipt_input: ReceiptInput) -> ReceiptEnvelope` — unified receipt creation
- `EvidenceDomain.append(envelope: ReceiptEnvelope) -> str` — returns receipt_id, persists to filesystem
- `EvidenceDomain.query(filter: ReceiptFilter) -> List[ReceiptEnvelope]` — search/retrieve receipts
- `EvidenceDomain.derive_from_progress(event: ProgressEvent) -> Optional[ReceiptEnvelope]` — auto-derivation
- `EvidenceDomain.validate(envelope: ReceiptEnvelope) -> ValidationResult` — integrity checks
- `EvidenceDomain.get_store(repo_root: Path) -> ReceiptStore` — store accessor
- `EvidenceDomain` also owns intake packets, sync receipts, replay receipts, and forensic reconstruction inputs as evidence lineage, not just generic receipts

### Architecture
- `evidence_domain.py` — public interface with 6 methods
- `_types.py` — all receipt types from `receipt_envelope.py`
- `_store.py` — receipt store and I/O from `receipts.py`
- `_derivation.py` — derivation logic from `progress_receipt_derivation.py`
- `_validation.py` — validation helpers extracted from `receipt_envelope.py`

### Key change: Single creation path
All direct calls to `build_receipt_envelope()` and direct `ReceiptEnvelope` instantiation must route through `EvidenceDomain.create()`. This enables:
- Centralized validation
- Consistent schema versioning
- Automatic provenance tracking
- Unified integrity hashing

## Consequences

**Leverage**: One place for all evidence operations. Currently: receipt creation in `workspace.py`, `workspace_audit.py`, `intents/dispatcher.py`, `commands_public_intake.py`. After: all through `EvidenceDomain.create()`. New receipt type? Extend `_types.py`. New derivation rule? Extend `_derivation.py`.

**Locality**: All 2,307 lines of receipt knowledge in one deep module. Currently: types + building in `receipt_envelope.py`, storage in `receipts.py`, derivation in `progress_receipt_derivation.py`. After: clean internal seams.

**Testability**: Test evidence through domain interface. Currently: need to mock `build_receipt_envelope()`, store separately. After: mock `EvidenceDomain` once with in-memory store. Test cases: create → append → query → validate → derive.

**Seam**: `EvidenceDomain` interface is the real seam. Two adapters:
- Production: filesystem store, real derivation, real validation
- Test: in-memory store, mock derivation, passthrough validation

**Cross-package impact**: Currently `receipt_envelope.py` imports `write_json` from `rig_tools.core.io`. After deepening, this dependency moves to `_store.py` internal, not exposed at the seam.

**Topology contract**: Evidence continuity includes intake packets, sync receipts, replay reads, and reconstruction traces. Filesystem layout is part of the evidence model, but the domain still owns derivation, validation, and append/query semantics.

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
s wired to internal modules

### Phase 3: Migrate direct creation sites (week 2)
10. Update `workspace.py` to use `EvidenceDomain.create()`
11. Update `workspace_audit.py` to use `EvidenceDomain.create()`
12. Update `intents/dispatcher.py` to use `EvidenceDomain.create()` + `.append()`
13. Update `commands_public_intake.py` to use `EvidenceDomain.create()`

### Phase 4: Migrate type consumers (week 2)
14. Update `domain/__init__.py` exports
15. Update `integrity.py` imports
16. Update all tests

### Phase 5: Add deprecation shims (week 2)
17. Add `__getattr__` shims to old files pointing to new package
18. Verify all consumers work

### Phase 6: Cleanup (week 3)
19. Delete old `receipt*.py` files
20. Delete deprecation shims

**Risk**: Medium-High. Affects core receipt functionality. `receipt_envelope.py` is imported by 6+ modules. Schedule 2-3 weeks with thorough testing.
