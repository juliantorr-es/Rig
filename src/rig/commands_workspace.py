from rig_tools.workspace_manager import WorkspaceManager

def register(subparsers, helpers):
    parser = subparsers.add_parser("workspace", help="Manage Rig workspaces")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    
    sub.add_parser("status", help="Workspace status").set_defaults(handler=lambda args: status(helpers))
    
    create = sub.add_parser("create", help="Create workspace")
    create.add_argument("--task", required=True)
    create.set_defaults(handler=lambda args: create_workspace(helpers, args.task))
    
    sub.add_parser("list", help="List workspaces").set_defaults(handler=lambda args: list_workspaces(helpers))

def status(helpers):
    print("Workspace subsystem operational.")
    return 0

def create_workspace(helpers, task):
    mgr = WorkspaceManager(helpers.repo_root)
    path = mgr.create(task)
    print(f"Created workspace: {path}")
    return 0

def list_workspaces(helpers):
    mgr = WorkspaceManager(helpers.repo_root)
    for ws in mgr.list_workspaces():
        print(f"{ws['workspace_id']} - {ws['task']} ({ws['status']})")
    return 0
