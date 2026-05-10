from __future__ import annotations

from rig.domain.runtime_events import RuntimeLifecycleEvent, RuntimeTelemetryEvent, event_from_dict


def test_runtime_event_serialization_is_deterministic() -> None:
    event = RuntimeLifecycleEvent(
        event_type="started",
        sequence=1,
        timestamp="2024-01-01T00:00:00+00:00",
        payload={"b": 2, "a": 1},
        workspace_id="ws_1",
    )
    assert event.to_dict()["timestamp"] == "2024-01-01T00:00:00Z"
    assert list(event.to_dict()["payload"].keys()) == ["a", "b"]
    assert event.event_id.startswith("evt_")


def test_event_from_dict_round_trips_family() -> None:
    event = RuntimeTelemetryEvent(sequence=3, payload={"load": 4}, workspace_id="ws_2")
    rebuilt = event_from_dict(event.to_dict())
    assert rebuilt.event_family == "runtime.telemetry"
    assert rebuilt.sequence == 3
    assert rebuilt.payload == {"load": 4}

