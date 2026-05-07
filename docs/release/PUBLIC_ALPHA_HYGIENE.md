# Public Alpha Hygiene

This pass cleaned public-release surface junk and normalized a few release-facing docs without changing product behavior.

## What Was Removed

- Local cache and build artifacts:
  - `.DS_Store`
  - `.ruff_cache/`
  - `.pytest_cache/`
  - `__pycache__/`
  - `.venv/`
  - `.build/`
  - `src/rig.egg-info/`
- Root scratch files:
  - `simple_app.py`
  - `standalone_test.py`
  - `test_debug.py`
  - `test_module_direct.py`
  - `test_server.py`
  - `test_server_files.py`
  - `test_simple.py`

## What Was Moved Or Deferred

- No files were moved.
- Ambiguous legacy/runtime docs were left in place and normalized only where they touched public release claims.

## Public Docs Link Fixes

- Replaced the README absolute docs link with a relative link.
- Replaced absolute local paths in:
  - `docs/migration/rig-repo-migration.md`
  - `docs/proofs/rig-environment-stabilization-2026-05-06.md`

## Release Surface Alignment

- Public release checks now focus on:
  - `python -m rig doctor`
  - `python -m rig ui --help`
  - `python -m rig window open --dry-run`
  - `python -m rig tui` returning deprecation JSON
  - scoped Pyright
  - targeted tests and release checks
- The public command contract was updated to reflect `rig ui` and `rig window open` as the current preview surface.
- Release checklist text was updated to stop treating retired Textual behavior as the primary gate.

## Packaging Data

- Static UI assets are now included in wheel/sdist packaging via setuptools package-data.
- Verified packaged files:
  - `src/rig_tools/static/index.html`
  - `src/rig_tools/static/rig-ui.css`
  - `src/rig_tools/static/rig-ui.js`

## Python / CI Alignment

- `pyproject.toml` still requires Python 3.14+.
- CI now matches that target in the main workflow.
- Local validation here ran under Python 3.13, so runtime smoke commands correctly refused to start. That is an environment mismatch, not a behavior change in Rig.

## Remaining Public Alpha Blockers

- Local validation environment is Python 3.13, while the public target is Python 3.14+.
- The broad historical test suite still contains retired TUI-shaped tests that fail collection outside the active gate.
- Legacy Textual-era docs and proofs still exist for historical context and should remain deferred or archived, not revived.
