# Agent Operational Model

Agents should operate through Rig-native primitives first, with Git used as the persistence substrate underneath. This shifts the agent loop from shell-centric mutation to governed operations.

## Old and New Models

| Model | Flow |
|---|---|
| Old | agent -> shell -> git |
| New | agent -> Rig runtime -> governed operations -> Git persistence |

## Primitive Mapping

| Future Rig Primitive | Replaces or abstracts |
|---|---|
| Workspace lane | Branch creation and task isolation |
| Operational isolation | Worktree management |
| Integration submission | PR creation and promotion |
| Operational memory | Replay inspection |
| Operational cognition | Topology visualization |
| Runtime validation | Governance checks |
| Execution observability | Runtime telemetry |

## Behavioral Expectations

- Agents should prefer Rig-native operations when available.
- Git remains authoritative for persistence, but not for live coordination.
- GitHub remains authoritative for collaboration, review, and merge control.
- Operational outcomes should be expressed through receipts, events, and projections.

## Agent Safety

| Concern | Required boundary |
|---|---|
| Concurrent execution | Separate workspaces or lanes |
| Runtime collision | Isolated ports, caches, and stream namespaces |
| Unreviewed promotion | Governance validation before integration |
| Unreconstructable state | Replay evidence required |

