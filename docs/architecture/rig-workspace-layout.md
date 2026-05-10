# Rig Workspace Layout

Rig treats the repository workspace as governed operational infrastructure.

## Canonical Layout

```text
.rig/
├── worktrees/
│   ├── preproduction/
│   ├── research/
│   ├── agent-ui/
│   ├── agent-runtime/
│   └── agent-governance/
├── artifacts/
├── replay/
├── topology/
├── receipts/
├── runtime/
└── cache/
```

## Doctrine

- `.rig/` is workspace-owned operational substrate.
- `.git/` remains Git-owned and must not be relocated or replicated under `.rig/`.
- Worktrees are isolated execution environments.
- Artifacts, replay bundles, topology snapshots, receipts, and runtime support files live under `.rig/`.
- `.rig/worktrees/` is operational state and should not be committed.

## Bootstrap Expectations

- `rig init` creates the governed `.rig/` directory skeleton.
- `rig workspace create --task <task-id>` ensures the layout exists before creating a workspace worktree.
- Future lane/bootstrap helpers should reuse the same layout contract.

## Non-Goals

- No Git internals under `.rig/`.
- No hidden automation that mutates `.git/`.
- No repository-content tracking for operational worktree directories.
