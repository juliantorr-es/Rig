# CLI

Use `rig --help` for the product shell.

Rig requires Python 3.14 or newer.
The TUI uses the Gridline Interface layout language: CSS grid for macro geometry, typed Python containers for semantic regions, and the native Textual footer for bindings.

Common commands:

- `rig init`
- `rig config inspect`
- `rig run --task <task-id> --provider custom-command`
- `rig job create --task <task-id> --provider custom-command`
- `rig job inspect <job_id>`
- `rig doctor queue`
- `rig doctor deps`
- `rig doctor repair --migrate-legacy-queue`
- `rig workspace list`
- `rig window status`
- `rig window open --dry-run`
- `rig provider list`
- `rig context build --workspace <workspace_id> --provider <provider_id> --model <model_id>`
- `rig agent propose --workspace <workspace_id> --provider <provider_id>`
- `rig log show <run_id>`
- `rig benchmark run --dry-run`
- `rig model recommend --dry-run`
