# Rig

Rig is a repo-local developer control plane for the Rig source tree that was migrated out of the parent Anigma workspace.

It solves a practical problem: there were many small automation entrypoints, validators, and review helpers living inside a larger monorepo-like workspace. Rig packages the reusable Python control surface into a standalone repository so it can be installed, tested, and evolved on its own.

## Maturity

Early but serious. The core CLI and helper modules are migrated, the repo has local validation, and compatibility wrappers preserve the old `scripts/rig.py` path. Some commands still assume Anigma-specific workspace content and may need path repair when run outside the original source tree.

## Install

```bash
cd /Users/user/Developer/GitHub/Rig
python -m pip install -e ".[dev]"
```

## Run

```bash
rig --help
rig doctor
rig os sentinel --format json
python scripts/rig.py --help
```

## Main commands

- `rig doctor`
- `rig os sentinel`
- `rig affected`
- `rig atlas`
- `rig audit`
- `rig brief`
- `rig bundle`
- `rig context`
- `rig docs`
- `rig git`
- `rig loop`
- `rig monitor`
- `rig pipeline`
- `rig queue`
- `rig schema`
- `rig settings`
- `rig swarm`
- `rig text`
- `rig tui`

## Repository layout

```text
src/
  rig/         CLI and command modules
  rig_tools/   reusable validators, adapters, and helpers
scripts/
  rig.py       legacy compatibility entrypoint
  ci/          local validation gate
tests/         smoke tests and behavior checks
docs/          migration notes and repo scaffolding
```

## Development workflow

1. Edit the package under `src/`.
2. Keep the compatibility wrapper working if the legacy `scripts/rig.py` path is still referenced.
3. Run the local check script.
4. Run focused tests for the command or helper you changed.

## Validation

```bash
scripts/ci/check.sh
python -m pytest -q
python -m compileall src tests rig.py scripts/rig.py
```

## Known limitations

- A number of commands are still Anigma-aware and expect workspace files that do not exist in this standalone repo.
- The migration preserved behavior first; path cleanup is incomplete.
- Some helper modules refer to legacy `scripts/` paths that are now served through compatibility wrappers.
