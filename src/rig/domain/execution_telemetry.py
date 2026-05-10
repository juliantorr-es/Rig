from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ExecutionTelemetrySample:
    backend: str
    telemetry_type: str
    value: float | int | None = None
    unit: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "telemetry_type": self.telemetry_type,
            "value": self.value,
            "unit": self.unit,
            "metadata": dict(self.metadata),
        }


def normalize_telemetry(payload: Mapping[str, Any]) -> ExecutionTelemetrySample:
    return ExecutionTelemetrySample(
        backend=str(payload.get("backend", "generic runtime")),
        telemetry_type=str(payload.get("telemetry_type", "throughput")),
        value=payload.get("value"),
        unit=payload.get("unit"),
        metadata=dict(payload.get("metadata", {})),
    )

