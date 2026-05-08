from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Mapping

SCHEMA_VERSION = "rig.runtime_event.v1"


def _utc_iso(timestamp: str | datetime | None = None) -> str:
    if timestamp is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(timestamp, datetime):
        dt = timestamp.astimezone(timezone.utc)
    else:
        value = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value).astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _bounded_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    return {key: data[key] for key in sorted(data)}


def _stable_digest(*parts: Any) -> str:
    raw = "|".join(json.dumps(part, sort_keys=True, separators=(",", ":")) if isinstance(part, (dict, list, tuple)) else str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _event_id(event_family: str, event_type: str, sequence: int, payload: Mapping[str, Any], workspace_id: str | None) -> str:
    digest = _stable_digest(SCHEMA_VERSION, event_family, event_type, sequence, workspace_id or "", _bounded_payload(payload))
    return f"evt_{digest[:24]}"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    schema_version: str = SCHEMA_VERSION
    event_family: str = "runtime.lifecycle"
    event_type: str = "event"
    event_id: str = ""
    sequence: int = 0
    timestamp: str = field(default_factory=_utc_iso)
    payload: dict[str, Any] = field(default_factory=dict)
    workspace_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", _utc_iso(self.timestamp))
        object.__setattr__(self, "payload", _bounded_payload(self.payload))
        if not self.event_id:
            object.__setattr__(self, "event_id", _event_id(self.event_family, self.event_type, self.sequence, self.payload, self.workspace_id))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class RuntimeLifecycleEvent(RuntimeEvent):
    event_family: str = "runtime.lifecycle"


@dataclass(frozen=True, slots=True)
class RuntimeTelemetryEvent(RuntimeEvent):
    event_family: str = "runtime.telemetry"


@dataclass(frozen=True, slots=True)
class ReplayEvent(RuntimeEvent):
    event_family: str = "replay.event"


@dataclass(frozen=True, slots=True)
class TopologyDeltaEvent(RuntimeEvent):
    event_family: str = "topology.delta"


@dataclass(frozen=True, slots=True)
class GovernanceStateEvent(RuntimeEvent):
    event_family: str = "governance.state"


@dataclass(frozen=True, slots=True)
class ExecutionRoutingEvent(RuntimeEvent):
    event_family: str = "execution.routing"


@dataclass(frozen=True, slots=True)
class WorkspaceLifecycleEvent(RuntimeEvent):
    event_family: str = "workspace.lifecycle"


@dataclass(frozen=True, slots=True)
class IntegrationStatusEvent(RuntimeEvent):
    event_family: str = "integration.status"


EVENT_CLASS_BY_FAMILY = {
    "runtime.lifecycle": RuntimeLifecycleEvent,
    "runtime.telemetry": RuntimeTelemetryEvent,
    "replay.event": ReplayEvent,
    "topology.delta": TopologyDeltaEvent,
    "governance.state": GovernanceStateEvent,
    "execution.routing": ExecutionRoutingEvent,
    "workspace.lifecycle": WorkspaceLifecycleEvent,
    "integration.status": IntegrationStatusEvent,
}


def event_from_dict(data: Mapping[str, Any]) -> RuntimeEvent:
    cls = EVENT_CLASS_BY_FAMILY.get(str(data.get("event_family", "runtime.lifecycle")), RuntimeEvent)
    return cls(
        schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
        event_family=str(data.get("event_family", cls.event_family if hasattr(cls, "event_family") else "runtime.lifecycle")),
        event_type=str(data.get("event_type", "event")),
        event_id=str(data.get("event_id", "")),
        sequence=int(data.get("sequence", 0)),
        timestamp=str(data.get("timestamp", "")),
        payload=dict(data.get("payload", {})),
        workspace_id=data.get("workspace_id"),
    )

