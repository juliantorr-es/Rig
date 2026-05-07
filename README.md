# Rig

Rig is the cryptographically governed control plane for local AI coding.

Most AI coding tools mutate your code blindly. Rig forces AI work through isolated Git worktrees, cryptographic receipts, validation gates, and explicit review before anything touches your main branch.

Models propose. Rig disposes.

## Install

```bash
python3.14 -m pip install -e ".[dev]"
```

## First Run

```bash
rig init
rig ui
rig run --task fix-imports --provider custom-command
```

## User Interfaces

- **CLI**: Use the terminal for scriptable, deterministic workflows and repository management.
- **Windowed UI (`rig ui`)**: Use the rich, windowed control plane for interactive work, streaming logs, agent chat, and governance gates.
- **Textual TUI**: Retired. Use `rig ui` for a rich interface or CLI commands for terminal workflows.

## Core Concepts

- Workspaces
- Isolated worktrees
- Receipts
- Proposals
- Review and apply gates
- Job queue

## Safety Model

- No silent mutation of main
- No auto-apply
- No provider direct mutation
- No background daemon by default
- All orchestration leaves receipts and logs

## Command Overview

- `rig init`
- `rig config inspect`
- `rig runtime list`
- `rig model list`
- `rig provider list`
- `rig context build`
- `rig system inspect`
- `rig job create`
- `rig job run`
- `rig run --task <task-id> --provider <provider_id>`
- `rig agent propose`
- `rig workspace create`
- `rig workspace review`
- `rig workspace apply`
- `rig log list`
- `rig log show`
- `rig debug bundle`
- `rig ui`

## Maturity

Rig is usable as a standalone CLI and governance shell. Runtime/model/provider integration is advisory only and remains behind explicit policy gates.

Rig requires Python 3.14 or newer.

## Documentation

See [docs/index.md](/Users/user/Developer/GitHub/Rig/docs/index.md).

## Notes

Rig originated from a migration out of the Anigma workspace, but the product surface is now standalone. Migration history remains in `docs/migration/` for reference only.
