# Workspace Domain Authority

**ADR 0007 — Canonical**

The **Workspace** concept (CONTEXT.md: "A governed environment for work items") is defined in CONTEXT.md as the central domain authority, but the implementation is shallow. `WorkspaceDomain` in `workspace.py` mixes git operations, path management, and validation coordination. Separate files (`workspace_status.py`, `workspace_audit.py`, `workspace_hygiene.py`, `workspace_runtime.py`) each define their own workspace-related logic. Delete `workspace.py` and complexity scatters across domain modules. We should deepen into a single **WorkspaceDomain** that owns all workspace concerns.

**Status**: proposed

**Related ADRs**:
- [0006 Ingress Interpretation](0006-ingress-interpretation.md) — ingress packets feed workspace evidence and replay
- [0008 Receipt/Evidence Unification](0008-receipt-evidence-unification.md) — workspace audit should consume the unified evidence seam

## Context

- `src/rig/domain/workspace.py` — 850+ lines: `WorkspaceDomain` with git ops, worktree management, validation coordination
- `src/rig/domain/workspace_status.py` — 200+ lines: `WorkspaceStatusSummary`, status building
- `src/rig/domain/workspace_audit.py` — 800+ lines: audit trail, state building
- `src/rig/domain/workspace_hygiene.py` — 700+ lines: hygiene checks, cleanup actions
- `src/rig/domain/workspace_runtime.py` — 20+ lines: runtime integration
- `src/rig/commands_workspace.py` — CLI adapter calling into all of the above
- No single module owns the complete workspace state

## Decision

Create a **WorkspaceDomain** deep module that serves as the **single source of truth** for all workspace concerns. Currently 5 files with 2,834 lines; after: 1 public interface with internal seams.

### New Interface
- `WorkspaceDomain.get_state(repo_root: Path, workspace_id: Optional[str] = None) -> WorkspaceState` — composite state
- `WorkspaceDomain.create_workspace(repo_root: Path, task: str) -> WorkspaceRecord` — workspace creation
- `WorkspaceDomain.list_workspaces(repo_root: Path) -> List[WorkspaceRecord]` — workspace enumeration
- `WorkspaceDomain.get_audit_trail(repo_root: Path, workspace_id: str) -> WorkspaceAuditTrail` — audit access
- `WorkspaceDomain.check_hygiene(repo_root: Path) -> WorkspaceHygieneStatus` — hygiene checks

### Composite State
`WorkspaceState` frozen dataclass containing:
- `git: GitState` — branch, status, changes (from git helper)
- `records: List[WorkspaceRecord]` — workspace lane records
- `audit: WorkspaceAuditTrail` — audit state and receipt backing info
- `hygiene: WorkspaceHygieneStatus` — hygiene violations and warnings
- `runtime: WorkspaceRuntime` — runtime state for active workspace

### Architecture
- `workspace_domain.py` — public interface with 5 methods
- `_git.py` — internal git operations (currently mixed in `workspace.py`)
- `_records.py` — internal workspace record management (from `workspace.py`)
- `_status.py` — internal status building (from `workspace_status.py`)
- `_audit.py` — internal audit (from `workspace_audit.py`)
- `_hygiene.py` — internal hygiene (from `workspace_hygiene.py`)
- `_runtime.py` — internal runtime integration (from `workspace_runtime.py`)

## Consequences

**Leverage**: One place for all workspace state. Currently: UI server calls `workspace.py` for records, `workspace_status.py` for status, `workspace_audit.py` for audit. After: one call to `get_state()`. New workspace feature? Add to one module.

**Locality**: All 2,834 lines of workspace knowledge in one deep module. Currently: git ops in `workspace.py` (via `rig_tools.core`), status building in `workspace_status.py`, audit in `workspace_audit.py`, hygiene in `workspace_hygiene.py`. After: clean separation with internal seams.

**Testability**: Test workspace through `get_state()` interface. Currently: need to coordinate mocking `WorkspaceDomain`, `build_workspace_status_summary`, `WorkspaceAuditTrail`. After: mock `WorkspaceDomain.get_state()` once.

**Seam**: `WorkspaceDomain.get_state()` is the real seam. Two adapters:
- Production: real git, real filesystem, real receipt store
- Test: in-memory mock with fake git state, fake records, fake audit

**Cross-package impact**: Reduces `rig.domain` imports from `rig_tools` (currently `workspace.py` imports `run_capture` from `rig_tools.core`).

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
