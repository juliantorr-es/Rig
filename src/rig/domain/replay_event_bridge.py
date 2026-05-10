from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from rig.domain.runtime_events import RuntimeEvent


@dataclass(frozen=True, slots=True)
class ReplayTimelineEntry:
    sequence: int
    event_id: str
    event_family: str
    event_type: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class ReplayEventBridgeResult:
    entries: tuple[ReplayTimelineEntry, ...]
    integrity_ok: bool


def build_replay_timeline(events: Iterable[RuntimeEvent]) -> ReplayEventBridgeResult:
    ordered = sorted(events, key=lambda event: (event.sequence, event.timestamp, event.event_id))
    entries = tuple(
        ReplayTimelineEntry(
            sequence=event.sequence,
            event_id=event.event_id,
            event_family=event.event_family,
            event_type=event.event_type,
            timestamp=event.timestamp,
        )
        for event in ordered
    )
    integrity_ok = all(left.sequence <= right.sequence for left, right in zip(ordered, ordered[1:]))
    return ReplayEventBridgeResult(entries=entries, integrity_ok=integrity_ok)

