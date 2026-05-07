from __future__ import annotations

import json
from pathlib import Path

from rig_tools.runtime_registry import runtime_manifests, inspect_manifest


def register(subparsers, helpers):
    parser = subparsers.add_parser("runtime", help="Runtime capability registry")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("list", help="List runtime providers").set_defaults(handler=lambda args: _list(helpers))
    insp = sub.add_parser("inspect", help="Inspect provider")
    insp.add_argument("provider_id")
    insp.set_defaults(handler=lambda args: _inspect(helpers, args.provider_id))


def _list(helpers):
    print(json.dumps(runtime_manifests(helpers.repo_root), indent=2))
    return 0


def _inspect(helpers, provider_id: str):
    print(json.dumps(inspect_manifest(helpers.repo_root, provider_id), indent=2))
    return 0

