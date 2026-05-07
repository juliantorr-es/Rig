# Rig Productization Phase 3 Proof

Files created or modified:

- `src/rig_tools/workspace_governance.py`
- `src/rig/commands_workspace.py`
- `src/rig/commands_validate.py`
- `src/rig/main.py`
- `src/rig_tools/schema_validation.py`
- `src/rig_tools/tui_views.py`
- `pyproject.toml`
- `docs/schemas/rig.validation_result.v1.schema.json`
- `docs/schemas/rig.apply_receipt.v1.schema.json`
- `docs/schemas/rig.review_bundle.v1.schema.json`
- `docs/dev/rig/GOVERNED_APPLY.md`
- `docs/dev/rig/REVIEW_BUNDLES.md`
- `tests/test_workspace_governance.py`

Runtime behavior changed:

- Added governed workspace review, validation, and apply commands.
- Added workspace lifecycle transitions and status tracking.
- Added explicit git-merge-based apply path with abort on merge failure.
- Added review bundle generation and apply receipt output.
- Added validator execution from `[tool.rig.validators]` in `pyproject.toml`.
- Added workspace indicators to TUI snapshot data.

Commands added or changed:

- `rig workspace review <workspace_id>`
- `rig workspace apply <workspace_id>`
- `rig workspace transition <workspace_id> <status>`
- `rig validate workspace <workspace_id>`

Schemas added:

- `Docs/schemas/rig.validation_result.v1.schema.json`
- `Docs/schemas/rig.apply_receipt.v1.schema.json`
- `Docs/schemas/rig.review_bundle.v1.schema.json`

Tests added:

- dirty main worktree blocks apply
- missing execution receipt blocks apply
- review bundle writes required files
- validator failure blocks apply path
- invalid workspace status transition is rejected

Validation commands and results:

- `.build/venv/bin/python -m pytest -q tests/test_workspace_governance.py` -> passed
- `.build/venv/bin/python -m pytest -q tests/test_rig_v1_shape.py` -> passed
- `.build/venv/bin/python -m pytest -q` -> passed
- `python scripts/rig.py --help` -> passed
- `python scripts/check_rig_local.py` -> file missing in repo

Remaining risks:

- `validation_receipt_ids` still needs a richer per-validator identity model if downstream consumers require one.
- `main worktree clean` currently relies on repo `.gitignore` hygiene for `.build`.
- `scripts/check_rig_local.py` is referenced by the prompt but not present in this repository.
- TUI apply/review actions are still read-only indicators, not full interactive buttons.

Phase 4 work:

- Not started.

