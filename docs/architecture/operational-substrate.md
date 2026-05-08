# Rig as Operational Substrate

Rig is a governed operational substrate layered above Git and GitHub. Git remains the persistence and history layer. Rig provides the runtime semantics, coordination, replay, observability, and isolation that sit above that substrate.

## Architectural Layers

| Layer | Responsibility |
|---|---|
| Git | Persistence, history, branching, diffing, and distributed synchronization |
| GitHub | Governance, collaboration, review, and merge authority |
| Rig runtime | Orchestration, execution governance, routing, and receipts |
| Replay | Operational memory and deterministic reconstruction |
| Topology | Operational cognition and relationship visibility |
| Event substrate | Live coordination and structured runtime transport |
| Workspace substrate | Operational isolation and execution lanes |
| Frontend | Operational observability and projection rendering |
| SwiftUI shell | Native operational supervision on macOS |

## Convergence Claims

- Git is no longer the primary operational UX.
- Rig-native operations should become the default entry point for agents and humans.
- Replay, topology, telemetry, and governance are unified as runtime concerns rather than separate ad hoc systems.
- Workspaces are governed execution environments, not just checked-out repositories.

## Non-Goals

- Replace Git.
- Replace GitHub governance.
- Introduce a monolithic new runtime.
- Add speculative distributed-systems machinery.

## Operational Relationship

```
agent -> Rig runtime -> governed operations -> Git persistence
```

## Key Outcomes

| Outcome | Meaning |
|---|---|
| Operational abstraction | Users interact with Rig concepts instead of raw Git mechanics |
| Deterministic memory | Replay is the canonical reconstruction path |
| Truthful observability | UI renders backend-authored state only |
| Governed execution | Every lane, route, and promotion is policy-bound |

