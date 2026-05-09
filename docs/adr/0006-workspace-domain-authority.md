# Workspace Domain Authority

The **Workspace** concept (CONTEXT.md: "A governed environment for work items") is defined in CONTEXT.md as the central domain authority, but the implementation is shallow. `WorkspaceDomain` in `workspace.py` mixes git operations, path management, and validation coordination. Separate files (`workspace_status.py`, `workspace_audit.py`, `workspace_hygiene.py`, `workspace_runtime.py`) each define their own workspace-related logic. Delete `workspace.py` and complexity scatters across domain modules. We should deepen into a single **WorkspaceDomain** that owns all workspace concerns.

**Status**: proposed

## Context

- `src/rig/domain/workspace.py` — 850+ lines: `WorkspaceDomain` with git ops, worktree management, validation coordination
- `src/rig/domain/workspace_status.py` — 200+ lines: `WorkspaceStatusSummary`, status building
- `src/rig/domain/workspace_audit.py` — 800+ lines: audit trail, state building
- `src/rig/domain/workspace_hygiene.py` — 700+ lines: hygiene checks, cleanup actions
- `src/rig/domain/workspace_runtime.py` — 20+ lines: runtime integration
- `src/rig/commands_workspace.py` — CLI adapter calling into all of the above
- No single module owns the complete workspace state

## Decision

Depen **WorkspaceDomain** into a single authoritative module that:
- Owns all workspace types and state
- Exposes composite interface: `WorkspaceDomain.get_state(repo_root: Path) -> WorkspaceState`
- `WorkspaceState` is a frozen dataclass containing:
  - Git state (branch, status, changes)
  - Workspace records and lane status
  - Audit state and receipt backing
  - Hygiene status and violations
  - Runtime state
- Internal modules become private implementation details
- CLI commands and domain code access workspace only through this interface

## Consequences

**Leverage**: One place for all workspace state. UI needs workspace info? One call. CLI needs workspace summary? One call. Domain needs to know workspace status? One call.

**Locality**: All workspace-related change in one module. Git operation changes? One place. Audit logic changes? One place. Introduce new workspace concept? One place.

**Testability**: Test workspace through `get_state()` interface. Create test scenario, call `get_state()`, assert on composite state. No need to coordinate multiple domain modules.

**Seam**: `WorkspaceDomain` interface is the seam. Two adapters: production (real git, real filesystem) and test (in-memory mock).

## Files Involved

- `src/rig/domain/workspace_domain.py` — new deep module (public interface)
- `src/rig/domain/workspace_domain/_git.py` — internal git operations
- `src/rig/domain/workspace_domain/_status.py` — internal status building (formerly `workspace_status.py`)
- `src/rig/domain/workspace_domain/_audit.py` — internal audit (formerly `workspace_audit.py`)
- `src/rig/domain/workspace_domain/_hygiene.py` — internal hygiene (formerly `workspace_hygiene.py`)
- `src/rig/domain/workspace_domain/_runtime.py` — internal runtime integration
- `src/rig/domain/workspace.py` — deprecated, functionality moves to new module
- Other `workspace_*.py` files — deprecated
- `src/rig/commands_workspace.py` — simplified to call new interface

## Migration Path

1. Create new `workspace_domain` package with `WorkspaceState` composite type
2. Move git operations into `_git.py`
3. Move status building into `_status.py`
4. Move audit into `_audit.py`
5. Move hygiene into `_hygiene.py`
6. Create composite `get_state()` that assembles all sub-states
7. Expose public interface
8. Update all consumers to use new interface
9. Deprecate old modules
10. Delete old modules once migrated
