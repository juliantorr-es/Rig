from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

ALLOWED_PROGRESS_PHASES = {
    "operation.started",
    "operation.log",
    "operation.progress",
    "operation.warning",
    "operation.error",
    "operation.completed",
    "workspace.projection.refreshed",
    "workspace.status.refreshed",
    "validator.started",
    "validator.output",
    "validator.completed",
}

ALLOWED_PROGRESS_LEVELS = {"debug", "info", "warning", "error"}
ALLOWED_PROGRESS_STATUSES = {"running", "completed", "failed", "blocked", "unknown"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_sequence(value: Any) -> int:
    try:
        sequence = int(value)
    except (TypeError, ValueError):
        raise ValueError("sequence must be an integer") from None
    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    return sequence


def _coerce_str(value: Any, field_name: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


@dataclass(slots=True)
class ProgressEvent:
    event_id: str
    operation_id: str
    command: str
    phase: str
    message: str
    level: str
    status: str
    sequence: int
    timestamp: str
    parent_operation_id: Optional[str] = None
    intent: Optional[str] = None
    workspace_id: Optional[str] = None
    workspace_path: Optional[str] = None
    receipt_candidate: bool = False
    receipt_kind: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.event_id = _coerce_str(self.event_id, "event_id")
        self.operation_id = _coerce_str(self.operation_id, "operation_id")
        self.command = _coerce_str(self.command, "command")
        self.phase = _coerce_str(self.phase, "phase")
        if self.phase not in ALLOWED_PROGRESS_PHASES:
            raise ValueError(f"Unsupported progress phase: {self.phase}")
        self.message = str(self.message or "")
        self.level = _coerce_str(self.level, "level")
        if self.level not in ALLOWED_PROGRESS_LEVELS:
            raise ValueError(f"Unsupported progress level: {self.level}")
        self.status = _coerce_str(self.status, "status")
        if self.status not in ALLOWED_PROGRESS_STATUSES:
            raise ValueError(f"Unsupported progress status: {self.status}")
        self.sequence = _coerce_sequence(self.sequence)
        self.timestamp = _coerce_str(self.timestamp, "timestamp")
        if self.parent_operation_id is not None:
            self.parent_operation_id = _coerce_str(self.parent_operation_id, "parent_operation_id")
        if self.intent is not None:
            self.intent = _coerce_str(self.intent, "intent")
        if self.workspace_id is not None:
            self.workspace_id = str(self.workspace_id)
        if self.workspace_path is not None:
            self.workspace_path = str(self.workspace_path)
        self.receipt_candidate = bool(self.receipt_candidate)
        if self.receipt_kind is not None:
            self.receipt_kind = _coerce_str(self.receipt_kind, "receipt_kind")
        if not isinstance(self.evidence_refs, list):
            raise ValueError("evidence_refs must be a list")
        self.evidence_refs = [str(ref) for ref in self.evidence_refs]
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")
        self.metadata = dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_envelope(self) -> dict[str, Any]:
        return {"kind": "progress_event", "event": self.to_dict()}


def build_progress_event(
    *,
    operation_id: str,
    command: str,
    phase: str,
    message: str,
    status: str,
    level: str = "info",
    sequence: int = 1,
    parent_operation_id: Optional[str] = None,
    intent: Optional[str] = None,
    workspace_id: Optional[str] = None,
    workspace_path: Optional[str] = None,
    receipt_candidate: bool = False,
    receipt_kind: Optional[str] = None,
    evidence_refs: Optional[list[str]] = None,
    metadata: Optional[dict[str, Any]] = None,
    event_id: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> ProgressEvent:
    return ProgressEvent(
        event_id=event_id or f"evt-{uuid4().hex}",
        operation_id=operation_id,
        command=command,
        phase=phase,
        message=message,
        level=level,
        status=status,
        sequence=sequence,
        timestamp=timestamp or utc_now(),
        parent_operation_id=parent_operation_id,
        intent=intent,
        workspace_id=workspace_id,
        workspace_path=workspace_path,
        receipt_candidate=receipt_candidate,
        receipt_kind=receipt_kind,
        evidence_refs=evidence_refs or [],
        metadata=metadata or {},
    )
