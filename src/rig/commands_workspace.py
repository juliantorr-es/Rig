from rig.domain.workspace import WorkspaceDomain, WORKSPACE_STATUSES

def register(subparsers, helpers):
    parser = subparsers.add_parser("workspace", help="Manage Rig workspaces")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    
    sub.add_parser("status", help="Workspace status").set_defaults(handler=lambda args: status(helpers))
    
    create = sub.add_parser("create", help="Create workspace")
    create.add_argument("--task", required=True)
    create.set_defaults(handler=lambda args: create_workspace(helpers, args.task))
    
    sub.add_parser("list", help="List workspaces").set_defaults(handler=lambda args: list_workspaces(helpers))
    review = sub.add_parser("review", help="Generate review bundle")
    review.add_argument("workspace_id")
    review.set_defaults(handler=lambda args: review_workspace(helpers, args.workspace_id))
    apply_cmd = sub.add_parser("apply", help="Apply workspace")
    apply_cmd.add_argument("workspace_id")
    apply_cmd.set_defaults(handler=lambda args: apply_workspace(helpers, args.workspace_id))
    transition = sub.add_parser("transition", help="Transition workspace status")
    transition.add_argument("workspace_id")
    transition.add_argument("status", choices=WORKSPACE_STATUSES)
    transition.set_defaults(handler=lambda args: transition_workspace(helpers, args.workspace_id, args.status))

def status(helpers):
    print("Workspace subsystem operational.")
    return 0

def create_workspace(helpers, task):
    domain = WorkspaceDomain(helpers.repo_root)
    record = domain.create_workspace(task)
    print(f"Created workspace: {record.path}")
    return 0

def list_workspaces(helpers):
    domain = WorkspaceDomain(helpers.repo_root)
    for ws in domain.list_workspaces():
        print(f"{ws['workspace_id']} - {ws['task']} ({ws['status']}) {ws.get('branch', '')}")
    return 0

def review_workspace(helpers, workspace_id):
    domain = WorkspaceDomain(helpers.repo_root)
    bundle = domain.build_review_bundle(workspace_id)
    print(bundle["workspace_id"], bundle["apply_eligibility"])
    return 0

def apply_workspace(helpers, workspace_id):
    domain = WorkspaceDomain(helpers.repo_root)
    payload = domain.apply_workspace(workspace_id)
    print(payload["receipt_id"], payload["status"])
    return 0

def transition_workspace(helpers, workspace_id, status):
    domain = WorkspaceDomain(helpers.repo_root)
    payload = domain.transition_workspace(workspace_id, status)
    print(payload["workspace_id"], payload["status"])
    return 0
