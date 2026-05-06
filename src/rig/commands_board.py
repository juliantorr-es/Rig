from __future__ import annotations

import json
from pathlib import Path
from rig_tools import kanban_board

def register(subparsers, helpers):
    parser = subparsers.add_parser("board", help="Manage Rig Kanban board")
    sub = parser.add_subparsers(dest="board_cmd", required=True)

    sub.add_parser("build", help="Build latest Kanban board artifact")
    sub.add_parser("status", help="Show compact Kanban board status")

    parser.set_defaults(handler=lambda args: _run(helpers, args))

def _run(helpers, args) -> int:
    cmd = args.board_cmd
    if cmd == "build":
        board = kanban_board.build_kanban_board(helpers.repo_root)
        print(json.dumps({"status": "passed", "path": ".build/rig/kanban/latest.json"}))
    elif cmd == "status":
        board = kanban_board.build_kanban_board(helpers.repo_root)
        for col in kanban_board.COLUMNS:
            count = len([c for c in board["cards"] if c["column_id"] == col])
            print(f"{col:15} | {count}")
    return 0
