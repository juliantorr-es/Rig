#!/usr/bin/env bash
set -euo pipefail

find src scripts -name "*.py" -print0 | xargs -0 python -m py_compile
python -m pytest -q tests/test_rig_cli.py tests/test_rig_v1_shape.py tests/test_rig_events.py tests/test_rig_os_sentinel.py
