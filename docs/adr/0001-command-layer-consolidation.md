# Command Layer Consolidation

The CLI command layer is currently shallow: 35+ `commands_*.py` files each directly instantiate domain objects and expose near-identical registration patterns. Delete any single command file and complexity scatters to `cli/main.py` in the form of broken imports and registration gaps — not concentration. We should deepen this into a **CommandRegistry** module that owns the CLI seam (argument parsing, output formatting, help conventions) and presents a narrow interface for command registration, with each command as a deep module behind it.

**Status**: proposed

## Context

- `src/rig/cli/main.py` imports 30+ command modules individually
- Each `commands_*.py` file is 20-500 lines of argparse setup + thin glue to domain
- No seam between CLI concerns (parsing, output modes) and domain execution
- UI commands (`commands_ui.py`, `commands_window.py`) mix dependency checking with CLI glue

## Decision

Create a **CommandRegistry** deep module at the CLI seam that:
- Owns argparse patterns, help text conventions, output mode handling (JSON vs human)
- Exposes interface: `CommandRegistry.register(name, handler_factory) -> None`
- Each command becomes a handler: `Callable[[RepoContext, Args], int]`
- Commands auto-register via entry points or explicit calls in a single `__init__`

## Consequences

**Leverage**: One place to change CLI conventions. All commands get output mode handling, error formatting, help standardization for free.

**Locality**: All CLI-specific knowledge concentrated. Domain modules no longer know about argparse or output formatting.

**Testability**: Test commands through handler interface without argparse machinery. Mock `RepoContext` once for all command tests.

## Files Involved

- `src/rig/cli/main.py` — simplified from ~200 lines to ~50: instantiate registry, call `run()`
- `src/rig/cli/registry.py` — new deep module (~200 lines): owns argparse setup, output modes, help conventions
- `src/rig/cli/context.py` — new (~50 lines): `RepoContext` dataclass, output formatting utilities
- `src/rig/commands_*.py` — 66 files simplified: each defines `setup_parser(parser)` + `handler(args, ctx) -> int`, auto-registered
- `src/rig_tools/window_launcher.py` — refactor to use `RepoContext` instead of custom arg handling
- `src/rig_tools/ui_server.py` — refactor to use `RepoContext` instead of custom CLI parsing

## Migration Path

1. Create `registry.py` with base `CommandHandler` protocol and registration
2. Move one command (e.g., `commands_validate.py`) to use registry
3. Replace individual imports in `main.py` with registry auto-discovery
4. Migrate remaining commands incrementally
5. Delete old registration code from `main.py` once all commands migrated
tally
5. Delete old registration code from `main.py` once all commands migrated
