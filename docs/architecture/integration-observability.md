# Integration Observability

## Purpose

Rig integration must be observable end to end.

The preproduction lane is not just a merge queue. It is a governed system with visible validation stages, explicit failure surfaces, and artifact-backed debugging.

## What Must Be Visible

### Merge Pipeline Visibility

- Which branch is proposing change
- Which branch is receiving change
- Whether the change is agent-generated or human-directed
- Whether the merge target is `preproduction` or `main`
- Whether the change is blocked by review, validation, or soak requirements

### Validation Visibility

- Syntax validation status
- Type validation status
- Replay validation status
- Projection contract status
- Frontend contract status
- SVG/runtime instrumentation status
- Doctor command status
- Browser boot smoke status

### Failure Surfaces

#### Replay failure surfaces

- Deterministic reconstruction mismatch
- Frame ordering drift
- Receipt or audit continuity failures
- Replay-safe visualization mismatches

#### Frontend contract failure surfaces

- Missing widget exports
- Registry drift
- Renderer signature drift
- Reduced-motion or disclosure participation drift
- Invalid bootstrap or ESM import surface

#### Topology convergence failure surfaces

- Unexpected branch role changes
- Workspace routing drift
- Agent lane confusion
- Protected branch bypass attempts

## Artifact Surfaces

Artifacts should make failures reviewable without re-running the entire system.

Expected artifacts:

- Replay bundles
- Projection traces
- Topology snapshots
- Frontend diagnostics
- Validation summaries

## Soak Expectations

`preproduction` should show the current validation state of integrated work in a way that is:

- deterministic
- reviewable
- artifact-backed
- human-legible

Soak is not a hidden queue. It is a visible integration state.

## Operational Principle

If integration cannot be observed, it cannot be governed.
