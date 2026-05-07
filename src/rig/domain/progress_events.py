from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

ALLOWED_PROGRESS_EVENT_KINDS = {
    "operation.started",
    "operation.log",
    "operation.progress",
    "operation.warning",
    "operation.error",
    "operation.completed",
    "workspace.projection.refreshed",
    "validator.started",
    "validator.output",
    "validator.completed",
}


@dataclass(slots=True)
class OperationProgressEvent:
    event_id: str
    operation_id: str
    kind: str
    status: str
    message: str
    timestamp: str
    workspace_id: Optional[str] = None
    lane_id: Optional[str] = None
    payload: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_progress_event(
    *,
    operation_id: str,
    kind: str,
    status: str,
    message: str,
    workspace_id: Optional[str] = None,
    lane_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    event_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> OperationProgressEvent:
    if kind not in ALLOWED_PROGRESS_EVENT_KINDS:
        raise ValueError(f"Unsupported progress event kind: {kind}")
    if not operation_id:
        raise ValueError("operation_id is required")
    return OperationProgressEvent(
        event_id=event_id or f"evt-{uuid4().hex}",
        operation_id=operation_id,
        workspace_id=workspace_id,
        lane_id=lane_id,
        kind=kind,
        status=status,
        message=message,
        timestamp=timestamp or utc_now(),
        payload=payload,
    )

