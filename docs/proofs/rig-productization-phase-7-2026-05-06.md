# Rig Productization Phase 7 Proof

## Canonical decisions

- Canonical job store: `.build/rig/jobs/<job_id>.json`
- Legacy queue: `.build/rig/queue/queue.json` is deprecated
- Atomic write model: same-directory temp file + `os.replace`
- Locking model: exclusive advisory lock on `.build/rig/jobs/.lock`

## Behavior proven

- Job creation writes durable canonical job files.
- Concurrent job creation stays unique and does not corrupt job files.
- Normal loading ignores `.tmp` files.
- Malformed job files do not crash `rig job list`, `rig doctor queue`, or the TUI snapshot path.
- `rig doctor repair --queue` quarantines malformed files to `.bad`.
- `rig doctor repair --migrate-legacy-queue` migrates legacy queue entries and preserves the original queue file.
- `rig init --dry-run` warns when legacy queue state is detected.
- Product commands write canonical job files and do not write `queue.json`.

## Validation

- `find src tests -name "*.py" -print0 | xargs -0 python -m py_compile`
- `.build/venv/bin/python -m pytest -q tests/test_phase7_job_store.py tests/test_phase6b_orchestration.py` -> `19 passed`
- `.build/venv/bin/python -m pytest -q` -> `42 passed`
- `.build/venv/bin/python -m rig --help` -> passed
- `.build/venv/bin/python -m rig job create --task phase7-smoke --provider custom-command` -> passed
- `.build/venv/bin/python -m rig doctor queue` -> passed and reported `canonical_job_count`, `legacy_queue_detected`, and `lock_path`
- `.build/venv/bin/python -m rig init --dry-run` -> passed and warned about legacy queue state
- `.build/venv/bin/python -m rig doctor repair --migrate-legacy-queue` -> passed and wrote `.build/rig/receipts/20260507T010744Z_legacy_queue_migration.json`

## Remaining risks

- Legacy `work_queue.py` still exists for historical compatibility surfaces.
- The TUI projection is read-only and does not heal state.
- Phase 8 scheduling, daemon, and autonomous loop work was not started.
