# Workspace Runtime Implementation

Workspace runtime semantics are implemented as deterministic namespace derivation over `.rig/worktrees/`-style lanes.

## Implementation Notes

| Concern | Implementation |
|---|---|
| Canonical model | `src/rig/domain/workspace_runtime.py` |
| Workspace ID | Derived from repo root and lane name |
| Replay namespace | Stable `replay/<workspace_id>` form |
| Artifact namespace | Stable `artifacts/<workspace_id>` form |
| Runtime namespace | Stable `runtime/<workspace_id>` form |

