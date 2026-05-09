# Projection Domain Consolidation

The **Projection** concept (defined in CONTEXT.md as "A derived view of the domain state optimized for UI consumption") is currently shallow across 5+ modules. `projections.py` defines dataclasses, `projection_builder.py` builds (600+ lines), `projection_contracts.py` validates, `projection_reconciliation.py` reconciles. Delete any one and nothing concentrates — imports just break. We should deepen into a single **ProjectionDomain** module that owns all projection concerns behind a narrow interface.

**Status**: proposed

## Context

- `src/rig/domain/projections.py` — type definitions only (shallow)
- `src/rig/domain/projection_builder.py` — 600+ lines of building logic, calls into contracts and reconciliation
- `src/rig/domain/projection_contracts.py` — 87K lines of validation logic
- `src/rig/domain/projection_reconciliation.py` — reconciliation controller
- `src/rig/commands_projections.py` — CLI adapter that directly uses `ProjectionsBuilder`
- UI JavaScript widgets consume projection JSON directly

## Decision

Create a **ProjectionDomain** deep module that:
- Owns all projection types (widget, intent, layout, etc.)
- Owns building logic with internal seams for contracts and reconciliation
- Exposes single interface: `build_projection(repo_root: Path, config: Optional[ProjectionConfig] = None) -> UIProjection`
- Internal modules (`_builder.py`, `_contracts.py`, `_reconciliation.py`) become private
- CLI and UI consume only through the public interface

## Consequences

**Leverage**: UI and CLI call one function. All projection knowledge (building, validating, reconciling) behind one seam.

**Locality**: Projection-related change in one place. Bug in contracts? Fix in `_contracts.py` without touching builder or CLI.

**Testability**: Test projection through `build_projection()`. No need to construct builders, validators, reconcilers separately. Tests describe desired projection state, not internal mechanism.

**AI-navigability**: Single entry point for "how does Rig build its UI state?" question.

## Files Involved

- `src/rig/domain/projection_domain.py` — new deep module (public interface)
- `src/rig/domain/projection_domain/_builder.py` — internal
- `src/rig/domain/projection_domain/_contracts.py` — internal
- `src/rig-domain/projection_domain/_reconciliation.py` — internal
- `src/rig/domain/projections.py` — deprecated, types move to new module
- `src/rig/domain/projection_builder.py` — deprecated
- `src/rig/domain/projection_contracts.py` — deprecated
- `src/rig/domain/projection_reconciliation.py` — deprecated
- `src/rig/commands_projections.py` — simplified to call new interface

## Migration Path

1. Create new `projection_domain` package with types
2. Move `projection_builder.py` logic into `_builder.py` under new package
3. Wire contracts and reconciliation as internal dependencies
4. Expose `build_projection()` as public interface
5. Update CLI command to use new interface
6. Deprecate old modules (keep for backwards compat, mark internal)
7. Delete old modules once all consumers migrated
