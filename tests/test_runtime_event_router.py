from __future__ import annotations

from rig.domain.runtime_event_router import RuntimeEventRouter
from rig.domain.runtime_events import RuntimeLifecycleEvent, RuntimeTelemetryEvent


def test_router_routes_and_bounded_buffer() -> None:
    router = RuntimeEventRouter(max_buffer_size=2)
    seen: list[str] = []
    router.register("runtime.lifecycle", lambda event: seen.append(event.event_id))

    router.route(RuntimeLifecycleEvent(sequence=2, event_type="ready"))
    router.route(RuntimeTelemetryEvent(sequence=3, event_type="load"))
    router.route(RuntimeLifecycleEvent(sequence=4, event_type="done"))

    assert seen
    assert len(router.snapshot()) == 2
    assert router.filter(event_family="runtime.lifecycle")


def test_router_replay_orders_deterministically() -> None:
    router = RuntimeEventRouter()
    late = RuntimeLifecycleEvent(sequence=2, event_type="late", timestamp="2024-01-01T00:00:02Z")
    early = RuntimeLifecycleEvent(sequence=1, event_type="early", timestamp="2024-01-01T00:00:01Z")
    ordered = router.replay([late, early])
    assert [event.sequence for event in ordered] == [1, 2]

