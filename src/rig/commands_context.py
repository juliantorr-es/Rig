from __future__ import annotations

import json
from pathlib import Path

from rig_tools import context_budget


def register(subparsers, helpers):
    parser = subparsers.add_parser("context", help="Governed context packets")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    build = sub.add_parser("build", help="Build a context packet")
    build.add_argument("--workspace", required=True)
    build.add_argument("--provider", required=True)
    build.add_argument("--model", required=True)
    build.set_defaults(handler=lambda args: _emit(context_budget.build_context_packet(helpers.repo_root, workspace_id=args.workspace, provider_id=args.provider, model_id=args.model)))
    inspect = sub.add_parser("inspect", help="Inspect a packet")
    inspect.add_argument("packet_id")
    inspect.set_defaults(handler=lambda args: _emit(context_budget.inspect_context_packet(helpers.repo_root, args.packet_id)))
    explain = sub.add_parser("explain", help="Explain a packet")
    explain.add_argument("packet_id")
    explain.set_defaults(handler=lambda args: _emit(context_budget.explain_context_packet(helpers.repo_root, args.packet_id)))


def _emit(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
