from __future__ import annotations

import json
from pathlib import Path
from rig_tools import kanban_board, task_graph

def register(subparsers, helpers):
    parser = subparsers.add_parser("graph", help="Manage Rig Task Graph")
    sub = parser.add_subparsers(dest="graph_cmd", required=True)

    sub.add_parser("build", help="Build latest task graph artifact")
    sub.add_parser("status", help="Show task graph summary")
    
    runnable = sub.add_parser("runnable", help="Show runnable tasks")
    
    blockers = sub.add_parser("blockers", help="Show blockers for a task")
    blockers.add_argument("--task", required=True)

    parser.set_defaults(handler=lambda args: _run(helpers, args))

def _run(helpers, args) -> int:
    cmd = args.graph_cmd
    board = kanban_board.build_kanban_board(helpers.repo_root)
    graph = task_graph.build_task_graph(helpers.repo_root, board.get("cards", []))
    
    if cmd == "build":
        print(json.dumps({"status": "passed", "path": ".build/rig/task-graph/latest.json"}))
    elif cmd == "status":
        print(f"Nodes: {len(graph['nodes'])} | Edges: {len(graph['edges'])}")
        print(f"Runnable: {len(graph['runnable_tasks'])} | Blocked: {len(graph['blocked_tasks'])}")
    elif cmd == "runnable":
        for t in graph["runnable_tasks"]:
            print(t)
    elif cmd == "blockers":
        tid = args.task
        blockers = [e["from_task"] for e in graph.get("edges", []) if e["to_task"] == tid]
        if blockers:
            print(f"Task {tid} is blocked by: {', '.join(blockers)}")
        else:
            print(f"Task {tid} has no detected blockers.")
            
    return 0
