from __future__ import annotations

from rig.domain.execution_telemetry import normalize_telemetry


def test_execution_telemetry_normalization() -> None:
    sample = normalize_telemetry(
        {
            "backend": "oMLX",
            "telemetry_type": "queue depth",
            "value": 12,
            "unit": "items",
            "metadata": {"lane": "a"},
        }
    )
    assert sample.backend == "oMLX"
    assert sample.telemetry_type == "queue depth"
    assert sample.to_dict()["metadata"] == {"lane": "a"}

