# Workspace UI Projection Contract

## Purpose

This contract defines the workspace-level widgets that the backend may project to the UI. The frontend is a renderer, not a governor.

## Widget Types

### WorkspaceHeader

Purpose:
- show repository identity and workspace authority boundary

Fields:
- `repo_root`
- `workspace_id`
- `workspace_status`
- `branch`
- `head`
- `authority_label`

Allowed intentions:
- refresh projection

Forbidden frontend inference:
- workspace lifecycle decisions
- lane creation or promotion decisions

Sample:

```json
{
  "repo_root": "/Users/user/Developer/GitHub/Rig",
  "workspace_id": "legacy-or-none",
  "workspace_status": "planned",
  "branch": "main",
  "head": "1ecab3f",
  "authority_label": "Workspace control plane (future lane registry)"
}
```

### WorkspaceGitState

Purpose:
- surface repo cleanliness and safe-to-commit context

Fields:
- `branch`
- `head`
- `dirty`
- `dirty_files_count`
- `safe_to_commit`
- `reason`

Allowed intentions:
- refresh projection

Forbidden frontend inference:
- commit permission
- lane promotion readiness

Sample:

```json
{
  "branch": "main",
  "head": "1ecab3f",
  "dirty": false,
  "dirty_files_count": 0,
  "safe_to_commit": false,
  "reason": "Current branch is main"
}
```

### WorkspaceLaneSummary

Purpose:
- show whether governed lane data is connected

Fields:
- `status`
- `lane_count`
- `active_lanes`
- `clean_lanes`
- `review_ready_lanes`
- `workspace_records`
- `connected`
- `message`
- `next_action`

Allowed intentions:
- refresh projection

Forbidden frontend inference:
- whether lanes exist unless the backend says so
- whether promotion is allowed

Sample:

```json
{
  "status": "not_connected",
  "lane_count": 0,
  "active_lanes": 0,
  "clean_lanes": 0,
  "review_ready_lanes": 0,
  "workspace_records": 0,
  "connected": false,
  "message": "Agent lane data is not connected to the workspace projection yet.",
  "next_action": "Use scripts/rig_agent_worktree.py review/recommend from CLI until workspace integration lands."
}
```

### AgentLaneCard

Purpose:
- show one governed agent lane

Fields:
- `lane_id`
- `agent`
- `task`
- `path`
- `branch`
- `expected_branch`
- `branch_matches_convention`
- `head`
- `dirty`
- `ahead`
- `behind`
- `status`
- `blockers`
- `warnings`
- `next_actions`

Forbidden frontend inference:
- staging decisions
- promotion decisions

### LaneReviewCard

Purpose:
- summarize review readiness

Fields:
- `ready_for_review`
- `changed_files`
- `commits`
- `blockers`
- `warnings`

Forbidden frontend inference:
- whether the lane should be promoted automatically

### PromotionPlanCard

Purpose:
- show a read-only promotion plan

Fields:
- `strategy`
- `base`
- `target`
- `ready_to_promote`
- `blockers`
- `warnings`
- `planned_operations`
- `future_commands`
- `dry_run`
- `would_mutate`

Forbidden frontend inference:
- actual promotion execution

### LaneRecommendationCard

Purpose:
- show the safest next path chosen by policy

Fields:
- `preferred_path`
- `recommended_path`
- `ready`
- `rationale`
- `future_commands`
- `validations_to_run`
- `next_safe_action`

Forbidden frontend inference:
- changing the recommendation

### CommandProgressCard

Purpose:
- show live telemetry for a workspace or lane operation

Fields:
- `operation_id`
- `kind`
- `status`
- `message`
- `percent`
- `started_at`
- `completed_at`

Forbidden frontend inference:
- operation authority

### ReceiptTimeline

Purpose:
- show durable evidence of operations and validations

Fields:
- `receipt ids`
- `operation kind`
- `result`
- `timestamp`
- `summary`

Forbidden frontend inference:
- receipt creation
- receipt verification policy

## Contract Rules

- Backend authors the state.
- Frontend renders the state.
- Frontend emits intentions only.
- Frontend must not infer checkpointability, lane readiness, or promotion decisions.
- Missing data should degrade to explicit placeholder text, not fabricated state.
