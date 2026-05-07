# Workspace Progress Stream

## Purpose

Rig uses live progress telemetry for workspace and lane operations. Streams are telemetry, not authority. The backend may refresh projections and emit receipts when an operation completes.

## Event Model

### OperationProgressEvent

Fields:

- `event_id`
- `operation_id`
- `workspace_id`
- `lane_id`
- `kind`
- `status`
- `message`
- `timestamp`
- `payload`

## Event Kinds

- `operation.started`
- `operation.log`
- `operation.progress`
- `operation.warning`
- `operation.error`
- `operation.completed`
- `workspace.projection.refreshed`
- `lane.attach.started`
- `lane.attach.completed`
- `lane.review.started`
- `lane.review.completed`
- `lane.recommend.started`
- `lane.recommend.completed`
- `lane.promote_plan.started`
- `lane.promote_plan.completed`
- `lane.checkpoint.dry_run.started`
- `lane.checkpoint.dry_run.completed`
- `lane.checkpoint.commit.completed`
- `validator.started`
- `validator.output`
- `validator.completed`
- `receipt.created`

## Transport Guidance

Prefer the existing WebSocket transport for browser-to-backend intentions and backend-to-browser progress.

- Do not introduce SSE unless a concrete need appears.
- Do not introduce a second transport just for style.
- Streaming events are telemetry, not authority.
- Completion should refresh the projection and/or create receipts.

## Contract Rules

- progress events may describe a lane or workspace operation
- progress events must not mutate state by themselves
- progress events should be stable enough to support receipts and later JSON export
