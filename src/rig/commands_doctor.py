from __future__ import annotations

from rig_tools.doctor import run_doctor


def register(subparsers, helpers):
    parser = subparsers.add_parser("doctor", help="Integrated Rig OS health checks", description="Integrated runtime and subsystem health checks.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.set_defaults(handler=lambda args: run_doctor(helpers.repo_root, format_type=args.format))
