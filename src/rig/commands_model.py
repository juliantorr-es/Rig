from __future__ import annotations

import json
from pathlib import Path

from rig_tools.model_registry import list_models, inspect_model, register_model, verify_model


def register(subparsers, helpers):
    parser = subparsers.add_parser("model", help="Model inventory")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("list", help="List models").set_defaults(handler=lambda args: _emit(list_models(helpers.repo_root)))
    insp = sub.add_parser("inspect", help="Inspect model"); insp.add_argument("model_id"); insp.set_defaults(handler=lambda args: _emit(inspect_model(helpers.repo_root, args.model_id)))
    reg = sub.add_parser("register", help="Register model"); reg.add_argument("path_or_name"); reg.set_defaults(handler=lambda args: _emit(register_model(helpers.repo_root, args.path_or_name)))
    ver = sub.add_parser("verify", help="Verify model"); ver.add_argument("model_id"); ver.set_defaults(handler=lambda args: _emit(verify_model(helpers.repo_root, args.model_id)))


def _emit(payload):
    print(json.dumps(payload, indent=2))
    return 0

