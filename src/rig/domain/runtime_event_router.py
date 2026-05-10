from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Iterable, Mapping

from rig.domain.runtime_events import RuntimeEvent

EventHandler = Callable[[RuntimeEvent], Any]


@dataclass
class RuntimeEventRouter:
    max_buffer_size: int = 256
    _handlers: dict[str, list[EventHandler]] = field(default_factory=dict)
    _buffer: Deque[RuntimeEvent] = field(default_factory=deque)
    _sequence: int = 0

    def register(self, event_family: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_family, []).append(handler)

    def route(self, event: RuntimeEvent) -> RuntimeEvent:
        if event.sequence < 0:
            event = type(event)(**{**event.to_dict(), "sequence": self._sequence})
        self._sequence = max(self._sequence, event.sequence + 1)
        self._buffer.append(event)
        while len(self._buffer) > self.max_buffer_size:
            self._buffer.popleft()
        for handler in self._handlers.get(event.event_family, []):
            handler(event)
        return event

    def filter(self, *, event_family: str | None = None, workspace_id: str | None = None) -> list[RuntimeEvent]:
        events = list(self._buffer)
        if event_family is not None:
            events = [event for event in events if event.event_family == event_family]
        if workspace_id is not None:
            events = [event for event in events if event.workspace_id == workspace_id]
        return events

    def subscribe(self, event_family: str, handler: EventHandler) -> None:
        self.register(event_family, handler)

    def replay(self, events: Iterable[RuntimeEvent]) -> list[RuntimeEvent]:
        ordered = sorted(events, key=lambda event: (event.sequence, event.timestamp, event.event_id))
        return [self.route(event) for event in ordered]

    def snapshot(self) -> list[Mapping[str, Any]]:
        return [event.to_dict() for event in sorted(self._buffer, key=lambda event: (event.sequence, event.timestamp, event.event_id))]

