# Runtime Event Implementation

The canonical runtime event layer is implemented as frozen dataclass contracts, deterministic serialization helpers, and family-specific event subclasses.

## Implementation Notes

| Concern | Implementation |
|---|---|
| Canonical schema | `src/rig/domain/runtime_events.py` |
| Deterministic IDs | Derived from family, type, sequence, workspace, and bounded payload |
| Timestamp normalization | UTC ISO-8601 normalization with trailing `Z` |
| Bounded payloads | Payload keys are normalized into deterministic order |
| Event families | Lifecycle, telemetry, replay, topology, governance, routing, workspace, integration |

