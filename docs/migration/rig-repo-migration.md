# Rig Repository Migration

## Source paths inspected

- `/Users/user/Developer/GitHub/Anigma_clean/scripts/rig.py`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/rig_cli/`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/rig_tools/`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/rig_os_sentinel.py`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/test_rig_cli.py`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/test_rig_v1_shape.py`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/test_rig_events.py`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/test_rig_os_sentinel.py`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/test_rig_duckdb.py`
- `/Users/user/Developer/GitHub/Anigma_clean/scripts/fixtures/`
- `/Users/user/Developer/GitHub/Anigma_clean/Docs/schemas/`
- `/Users/user/Developer/GitHub/Anigma_clean/README.md`
- `/Users/user/Developer/GitHub/Anigma_clean/pyproject.toml`

## Destination path

- `/Users/user/Developer/GitHub/Rig`

## Copied files summary

- `scripts/rig.py` -> `Rig/scripts/rig.py`
- `scripts/rig_cli/` -> `Rig/src/rig/`
- `scripts/rig_tools/` -> `Rig/src/rig_tools/`
- `scripts/anigma_common/` -> `Rig/src/anigma_common/`
- `scripts/rig_os_sentinel.py` -> `Rig/rig_os_sentinel.py`
- `scripts/rig_os_sentinel.py` -> `Rig/Scripts/rig_os_sentinel.py`
- `scripts/test_rig_cli.py` -> `Rig/tests/test_rig_cli.py`
- `scripts/test_rig_v1_shape.py` -> `Rig/tests/test_rig_v1_shape.py`
- `scripts/test_rig_events.py` -> `Rig/tests/test_rig_events.py`
- `scripts/test_rig_os_sentinel.py` -> `Rig/tests/test_rig_os_sentinel.py`
- `scripts/test_rig_duckdb.py` -> `Rig/tests/test_rig_duckdb.py`
- `scripts/fixtures/` -> `Rig/tests/fixtures/`
- `Docs/schemas/` -> `Rig/Docs/schemas/`

## Files created

- `README.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `.gitignore`
- `.editorconfig`
- `pyproject.toml`
- `scripts/ci/check.sh`
- `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`
- `.github/workflows/ci.yml`
- `Scripts/rig_os_sentinel.py`

## Files modified

- `rig.py`
- `src/rig/main.py`
- `src/rig_tools/monitor.py`
- `src/rig_tools/model_manager.py`
- `src/rig_tools/release_readiness.py`
- `src/rig_tools/affected.py`
- `src/rig_tools/context_compression.py`
- `src/rig_tools/doctor.py`
- `src/rig_tools/diff_review.py`
- `src/rig_tools/loop_actions.py`
- `src/rig_tools/local_patch.py`
- `src/rig_tools/proposal_swarm.py`
- `src/rig_tools/supervisor_loop.py`
- `src/rig_tools/work_queue.py`
- `src/rig_tools/anigma_loop.py`
- `src/rig_tools/contract_audit.py`
- `tests/test_rig_v1_shape.py`
- `tests/test_rig_cli.py`
- `tests/test_rig_events.py`
- `tests/test_rig_os_sentinel.py`
- `tests/fixtures/affected/docs_scripts_change.txt`
- `README.md`
- `pyproject.toml`
- `scripts/rig.py`
- `Scripts/rig_os_sentinel.py`

## Files excluded

- Caches: `.pytest_cache/`, `__pycache__/`, `.build/`
- Env/state: `.env`, `.venv-rig/`, other virtualenvs
- Logs and build outputs
- Zip archives and archive bundles
- Source-tree noise not needed for the standalone repo shape
- Destination pre-existing `.git/` metadata and `LICENSE`

## Path and import fixes

- Replaced `rig_cli` package references with `rig`.
- Added `src/anigma_common/` because migrated helpers depended on it.
- Added `scripts/rig.py` and `rig.py` wrappers that force `src/` onto `sys.path`.
- Added `Scripts/rig_os_sentinel.py` compatibility wrapper for mixed-case path references.
- Fixed `src/rig_tools/monitor.py` to call `model_manager.load_catalog(repo_root)`.
- Added `src/rig_tools/model_manager.list_local_models()` as a compatibility alias.

## Unresolved risks

- Some helpers still assume Anigma workspace paths such as `Docs/dev/rig`, `anigma/`, or legacy `scripts/` call sites.
- This repo now validates the current migrated surface, but broader Anigma-specific commands may still require future path repair.
- Runtime behavior depends on optional workspace data that is not present in the standalone repo.

## Validation commands and results

- `python -m compileall src tests rig.py scripts/rig.py` -> PASS
- `PATH=/tmp/rig-venv2/bin:$PATH bash scripts/ci/check.sh` -> PASS
- `PATH=/tmp/rig-venv2/bin:$PATH python -m pytest -q tests/test_rig_cli.py tests/test_rig_v1_shape.py tests/test_rig_events.py tests/test_rig_os_sentinel.py` -> PASS
- `PATH=/tmp/rig-venv2/bin:$PATH python scripts/rig.py --help` -> PASS
- `PATH=/tmp/rig-venv2/bin:$PATH python scripts/rig.py doctor --help` -> PASS
