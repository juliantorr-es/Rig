# Workspace Progress Stream

## Purpose

Rig uses live progress telemetry for workspace and lane operations. Streams are telemetry, not authority. The backend may refresh projections and emit receipts when an operation completes.

The first implemented slice uses the existing WebSocket path and emits `progress_event` messages for read-only refresh operations.

## Event Model

### ProgressEvent

Progress events are normalized before they leave the backend.

Fields:

- `event_id`
- `operation_id`
- `parent_operation_id`
- `command`
- `intent`
- `phase`
- `message`
- `level`
- `status`
- `sequence`
- `timestamp`
- `workspace_id`
- `workspace_path`
- `receipt_candidate`
- `receipt_kind`
- `evidence_refs`
- `metadata`

Notes:

- `receipt_candidate` is a marker only; it is not evidence.
- `receipt_kind` is reserved for future receipt-backed progress.
- `evidence_refs` are inert until receipt-backed progress exists.
- `metadata` is for non-authoritative details only.

Malformed payloads should be rejected at construction time.

### WebSocket Shape

Progress events are sent inside the existing UI message envelope:

```json
{
  "schema_version": "rig.ui.message.v1",
  "kind": "progress_event",
  "event": { "...": "ProgressEvent" }
}
```

## Event Phases

- `operation.started`
- `operation.log`
- `operation.progress`
- `operation.warning`
- `operation.error`
- `operation.completed`
- `workspace.projection.refreshed`
- `workspace.status.refreshed`
- `validator.started`
- `validator.output`
- `validator.completed`

Implemented initial read-only operation:

- `rig.intent.refresh_projection`
- `rig.intent.workspace_status`

This operation emits progress telemetry for:

- `operation.started`
- `operation.progress`
- `operation.completed`
- `workspace.projection.refreshed`
- `workspace.status.refreshed`

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
- the frontend keeps a bounded in-memory event buffer
- the frontend groups events by `operation_id`
- the frontend orders events by `sequence` and `timestamp`
- history is bounded per operation and across operations
- `CommandProgressCard` is a dumb renderer for backend-authored progress payloads
- the workspace projection declares a `workspace.command_progress` region for transient command telemetry
