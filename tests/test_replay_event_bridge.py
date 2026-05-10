from __future__ import annotations

from rig.domain.replay_event_bridge import build_replay_timeline
from rig.domain.runtime_events import RuntimeLifecycleEvent, RuntimeTelemetryEvent


def test_replay_event_bridge_orders_events() -> None:
    result = build_replay_timeline(
        [
            RuntimeTelemetryEvent(sequence=5, event_type="telemetry"),
            RuntimeLifecycleEvent(sequence=1, event_type="start"),
        ]
    )
    assert result.integrity_ok is True
    assert [entry.sequence for entry in result.entries] == [1, 5]

