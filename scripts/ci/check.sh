#!/usr/bin/env bash
set -euo pipefail

python -m compileall src tests rig.py scripts/rig.py
python -m pytest -q tests/test_rig_cli.py tests/test_rig_v1_shape.py tests/test_rig_events.py tests/test_rig_os_sentinel.py
