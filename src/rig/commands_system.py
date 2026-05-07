from __future__ import annotations

import json
from rig_tools.system_probe import inspect_system


def register(subparsers, helpers):
    parser = subparsers.add_parser("system", help="System capability inspection")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("inspect", help="Inspect system capabilities").set_defaults(handler=lambda args: _emit(inspect_system()))


def _emit(payload):
    print(json.dumps(payload, indent=2))
    return 0

