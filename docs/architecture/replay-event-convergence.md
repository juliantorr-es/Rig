# Replay Event Convergence

Replay convergence is implemented as a deterministic ordering bridge from canonical runtime events into replay timeline entries.

## Implementation Notes

| Concern | Implementation |
|---|---|
| Timeline bridge | `src/rig/domain/replay_event_bridge.py` |
| Ordering | Sequence, timestamp, then event ID |
| Integrity | Replay timeline reports whether sequence ordering remains monotonic |
| Scope | Reconstruction hooks only; no runtime mutation or persistence coupling |

