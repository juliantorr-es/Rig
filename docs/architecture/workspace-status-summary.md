# Workspace Status Summary

## Purpose

Rig's workspace projections need a canonical read-only summary of the current workspace substrate before richer proposal and validation UI can be layered on top. This document describes the hard read-only contract and authority boundary for workspace state inspection.

## Authority Boundary

- **Current authority**: Workspace state is file-backed under `.build/rig/workspaces/*.json`.
- **Selection logic**: The current workspace is inferred from the latest non-applied workspace record (by status_history timestamp).
- **Immutability**: The summary does not mutate workspace records, does not create any directories, and does not write any files.
- **No receipts**: The summary does not create or persist receipts or progress events.

## Read-Only Contract

The `list_workspaces_read_only(repo_root)` and `build_workspace_status_summary(repo_root)` functions are the canonical read-only entry points. They:

- Do NOT create `.build/rig` directories
- Do NOT create `.build/rig/workspaces` directories
- Do NOT write workspace records
- Return safe unselected summary when no workspace state exists
- Return real workspace data when records exist

## Model

`WorkspaceStatusSummary` is the canonical read-only workspace substrate model with explicit placeholder states.

### Fields

| Field | Type | Description |
|---|---|---|
| `workspace_id` | Optional[str] | Workspace identifier, None if no workspace is selected |
| `repo_path` | str | Absolute path to the repository root |
| `workspace_path` | Optional[str] | Absolute path to the workspace worktree, None if not selected |
| `branch` | Optional[str] | Current branch for the workspace or repo root |
| `head` | Optional[str] | Current HEAD commit hash |
| `status` | str | Workspace status: "unselected", "planned", "active", "blocked", "executed", "validated", "review_ready", "applied" |
| `gate` | str | Always "A" - Dogfood Gate A is active |
| `selected` | bool | True if a workspace is currently selected |
| `worktree_state` | WorkspaceWorktreeState | Git state of the worktree (branch, head, dirty, safe_to_commit, reason) |
| `proposal_state` | WorkspaceProposalState | Placeholder: status is "not_created" or "unknown" |
| `validation_state` | WorkspaceValidationState | Placeholder: status is "not_run" or "unknown", proof_status is "not_proof" |
| `warnings` | tuple[str, ...] | Warning messages if any |
| `metadata` | dict[str, Any] | Additional metadata including workspace_records count and source |

### WorkspaceWorktreeState

- `branch`: Current git branch
- `head`: Current commit hash
- `dirty`: Boolean indicating uncommitted changes
- `dirty_files_count`: Number of dirty/staged files
- `safe_to_commit`: Boolean indicating if it's safe to commit (not dirty and not on main)
- `reason`: Human-readable reason for the current state

### WorkspaceProposalState (Placeholder)

- `status`: "not_created" or "unknown" - explicitly not enriched
- `summary`: Placeholder message
- `next_action`: Suggested next action

### WorkspaceValidationState (Placeholder)

- `status`: "not_run" or "unknown" - explicitly not enriched
- `summary`: Placeholder message
- `next_action`: Suggested next action
- `proof_status`: Always "not_proof" - no proof authority

## Guidance

- Use `WorkspaceStatusSummary` to anchor workspace identity and path information in all projections
- The `workspace.proposal_lifecycle` console should consume WorkspaceStatusSummary, not infer workspace values ad hoc
- Keep proposal/validation placeholders explicit - do not enrich with actual recommendation or validation data in the substrate layer
- Do NOT use WorkspaceDomain for read-only inspection - use `list_workspaces_read_only` and `build_workspace_status_summary` instead
- Empty projection must NOT fake an active workspace - if no workspace exists, show selected=False and status="unselected"

## CLI Behavior

- `rig workspace status`: Must include `workspace_summary` with all canonical fields
- `rig workspace projection`: Must include workspace_summary shape under a stable key
