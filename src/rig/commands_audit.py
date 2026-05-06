from __future__ import annotations

from rig_tools.contract_audit import run_contract_audit


def register(subparsers, helpers):
    parser = subparsers.add_parser("audit", help="Rig contract and assumptions audits", description="Validate Rig command/action contracts and assumptions.")
    audit_sub = parser.add_subparsers(dest="audit_cmd", required=True)

    contracts = audit_sub.add_parser("contracts", help="Audit Rig command/action contracts")
    contracts.add_argument("--format", choices=["text", "json"], default="text")
    contracts.add_argument("--surface", choices=["tui_actions", "scheduler", "loop_engine", "gc", "vault"], default=None)
    contracts.set_defaults(handler=lambda args: run_contract_audit(helpers.repo_root, format_type=args.format, surface=args.surface))
