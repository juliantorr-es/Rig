from __future__ import annotations

import json
from pathlib import Path

def register(subparsers, helpers):
    parser = subparsers.add_parser("workspace", help="Workspace management", description="Manage units of work in Rig.")
    ws = parser.add_subparsers(dest="workspace_cmd", required=True)

    # 1. Status
    status = ws.add_parser("status", help="Show workspace status")
    status.set_defaults(handler=lambda args: _run_status(helpers, args))

    # 2. List
    list_ws = ws.add_parser("list", help="List workspaces")
    list_ws.set_defaults(handler=lambda args: _run_list(helpers, args))

    # 3. Create
    create = ws.add_parser("create", help="Create a new workspace")
    create.add_argument("--task", help="Task ID")
    create.add_argument("--mode", choices=["safe", "action", "auto_approve"], default="safe")
    create.add_argument("--dry-run", action="store_true")
    create.set_defaults(handler=lambda args: _run_create(helpers, args))

    # 4. Show
    show = ws.add_parser("show", help="Show workspace details")
    show.add_argument("--workspace", required=True, help="Workspace ID")
    show.set_defaults(handler=lambda args: _run_show(helpers, args))

    # 5. Archive
    archive = ws.add_parser("archive", help="Archive a workspace")
    archive.add_argument("--workspace", required=True, help="Workspace ID")
    archive.add_argument("--dry-run", action="store_true")
    archive.set_defaults(handler=lambda args: _run_archive(helpers, args))

def _run_status(helpers, args) -> int:
    from rig_tools.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(helpers.repo_root)
    workspaces = wm.list_workspaces()
    active = [w for w in workspaces if w["status"] == "active"]
    
    status = {
        "repo_root": str(helpers.repo_root),
        "total_workspaces": len(workspaces),
        "active_workspaces": len(active),
        "latest": workspaces[0] if workspaces else None
    }
    print(json.dumps(status, indent=2))
    return 0

def _run_list(helpers, args) -> int:
    from rig_tools.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(helpers.repo_root)
    workspaces = wm.list_workspaces()
    print(json.dumps(workspaces, indent=2))
    return 0

def _run_create(helpers, args) -> int:
    from rig_tools.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(helpers.repo_root)
    ws = wm.create_workspace(task=args.task, mode=args.mode, dry_run=args.dry_run)
    
    if args.dry_run:
        print("Dry run: would create workspace metadata.")
    print(json.dumps(ws, indent=2))
    return 0

def _run_show(helpers, args) -> int:
    from rig_tools.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(helpers.repo_root)
    ws = wm.get_workspace(args.workspace)
    if ws:
        print(json.dumps(ws, indent=2))
    else:
        print(f"Workspace {args.workspace} not found.")
        return 1
    return 0

def _run_archive(helpers, args) -> int:
    from rig_tools.workspace_manager import WorkspaceManager
    wm = WorkspaceManager(helpers.repo_root)
    try:
        ws = wm.archive_workspace(args.workspace, dry_run=args.dry_run)
        if args.dry_run:
            print(f"Dry run: would archive workspace {args.workspace}")
        print(json.dumps(ws, indent=2))
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    return 0
