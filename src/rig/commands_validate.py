from __future__ import annotations

from rig.domain.workspace import WorkspaceDomain


def register(subparsers, helpers):
    parser = subparsers.add_parser("validate", help="Validation commands")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    workspace = sub.add_parser("workspace", help="Validate a workspace")
    workspace.add_argument("workspace_id")
    workspace.set_defaults(handler=lambda args: validate_workspace(helpers, args.workspace_id))


def validate_workspace(helpers, workspace_id: str) -> int:
    domain = WorkspaceDomain(helpers.repo_root)
    payload = domain.generate_validation_result(workspace_id)
    print(payload["workspace_id"], payload["status"])
    return 0

