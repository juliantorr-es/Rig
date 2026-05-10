# Operational Event Substrate

Rig is becoming stream-oriented. Structured operational events are the canonical transport for runtime state, topology updates, replay reconstruction, and governance signals.

## Event Families

| Event family | Purpose |
|---|---|
| `runtime.lifecycle` | Execution state and lifecycle transitions |
| `runtime.telemetry` | Throughput, load, latency, and memory pressure |
| `replay.event` | Deterministic reconstruction inputs |
| `topology.delta` | Graph updates and relationship changes |
| `governance.state` | Merge, protection, and policy state |
| `execution.routing` | Backend selection and execution dispatch |
| `workspace.lifecycle` | Workspace state and lane transitions |
| `integration.status` | CI and integration progress |

## Contract Principles

- Events are typed and explicit.
- Event routing is deterministic.
- Replay and live transport converge on the same semantics.
- Projections must derive from canonical events rather than inventing state.
- WebSockets are transport, not authority.

## Substrate Behaviors

| Behavior | Requirement |
|---|---|
| Live coordination | Events flow through structured channels |
| Replay | Historical state can be reconstructed from event records |
| Observability | UI consumes projections built from event streams |
| Governance | Policy decisions are emitted as canonical events |

## Non-Goals

- Replace receipts with events.
- Allow untyped event blobs to become canonical.
- Make transport semantics depend on UI state.

