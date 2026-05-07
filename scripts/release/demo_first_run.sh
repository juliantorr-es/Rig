#!/usr/bin/env bash
set -euo pipefail

python3.14 -m rig init --yes
python3.14 -m rig doctor
python3.14 -m rig run --task "inspect this repo" --provider custom-command --dry-run
python3.14 -m rig debug bundle --dry-run
