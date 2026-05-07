# Rig Environment Stabilization

Date: 2026-05-06

## Goal

Stabilize Rig as a standalone repo baseline before Phase 2.

## Commands Run

```bash
python3.10 rig.py --help
python3.10 scripts/rig.py --help
python3.10 -c "import sys, rig, rig_tools; print(sys.executable); print(rig.__file__); print(rig_tools.__file__)"
python3.10 -m pytest -q
python3.10 -m rig --help
```

## Results

### `python3.10 rig.py --help`

Passed. CLI help rendered successfully.

### `python3.10 scripts/rig.py --help`

Passed. CLI help rendered successfully.

### `python3.10 -c "import sys, rig, rig_tools; print(sys.executable); print(rig.__file__); print(rig_tools.__file__)"`

Passed.

Resolved Python executable:

`/opt/homebrew/opt/python@3.10/bin/python3.10`

Resolved `rig.__file__`:

`/Users/user/Developer/GitHub/Rig/rig.py`

Resolved `rig_tools.__file__`:

`/Users/user/Developer/GitHub/Rig/src/rig_tools/__init__.py`

### `python3.10 -m pytest -q`

Passed.

Final result:

`10 passed in 1.24s`

### `python3.10 -m rig --help`

Passed. Supported by the current launcher surface.

## Stabilization Notes

- Rig imports cleanly without Anigma repo paths.
- Tests do not require ambient `PYTHONPATH`.
- Python version behavior is deterministic through a documented 3.10+ floor.
- No scattered `sys.path` mutations remain in runtime modules.
- Phase 2 was not started during stabilization.
