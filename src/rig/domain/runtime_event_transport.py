from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from rig.domain.runtime_events import RuntimeEvent, event_from_dict


@dataclass(frozen=True, slots=True)
class RuntimeEventEnvelope:
    schema_version: str
    event_family: str
    event_type: str
    event_id: str
    sequence: int
    timestamp: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_family": self.event_family,
            "event_type": self.event_type,
            "event_id": self.event_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


def envelope_from_event(event: RuntimeEvent) -> RuntimeEventEnvelope:
    return RuntimeEventEnvelope(
        schema_version=event.schema_version,
        event_family=event.event_family,
        event_type=event.event_type,
        event_id=event.event_id,
        sequence=event.sequence,
        timestamp=event.timestamp,
        payload=dict(event.payload),
    )


def event_from_envelope(data: Mapping[str, Any]) -> RuntimeEvent:
    return event_from_dict(data)

