from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rig_tools.state_store import StateStore

def register(subparsers, helpers):
    """Registers the 'state' command group."""
    parser = subparsers.add_parser("state", help="Rig OS operational state commands")
    state_sub = parser.add_subparsers(dest="state_command")
    
    status_parser = state_sub.add_parser("status", help="Show state store status")
    status_parser.set_defaults(handler=lambda args: show_status(helpers))
    
    migrate_parser = state_sub.add_parser("migrate", help="Apply state store migrations")
    migrate_parser.add_argument("--dry-run", action="store_true", help="Show planned migrations without applying")
    migrate_parser.set_defaults(handler=lambda args: run_migrate(helpers, dry_run=args.dry_run))
    
    rebuild_parser = state_sub.add_parser("rebuild-index", help="Rebuild state from artifacts")
    rebuild_parser.add_argument("--dry-run", action="store_true", help="Show planned index rebuild actions")
    rebuild_parser.set_defaults(handler=lambda args: run_rebuild_index(helpers, dry_run=args.dry_run))

def show_status(helpers):
    """Shows the status of the state store."""
    store = StateStore(helpers.repo_root)
    status = store.get_status()
    
    if helpers.output_mode == "human":
        print(f"Rig State Store: {status['status'].upper()}")
        print(f"DB Path: {status['db_path']}")
        print("\nTables:")
        for name, info in status["tables"].items():
            exists = "✓" if info["exists"] else "✗"
            print(f"- {exists} {name:20} ({info['count']} rows)")
        
        if status["migrations"]:
            print("\nMigrations:")
            for m in status["migrations"]:
                print(f"- {m['version']} applied at {m['applied_at']}")
    else:
        print(json.dumps(status, indent=2))
    
    return 0

def run_migrate(helpers, dry_run: bool = False):
    """Runs database migrations."""
    store = StateStore(helpers.repo_root)
    if dry_run:
        plan = store.get_migration_plan()
        print(f"Planned migrations (DRY RUN):")
        for sql in plan:
            print(f"\n{sql.strip()}")
        return 0
    
    applied = store.migrate()
    if helpers.output_mode == "human":
        print(f"Applied {len(applied)} migration steps.")
        for step in applied:
            print(f"- {step.splitlines()[1].strip() if len(step.splitlines()) > 1 else step.strip()}")
    else:
        print(json.dumps({"applied": applied}, indent=2))
    return 0

def run_rebuild_index(helpers, dry_run: bool = False):
    """Rebuilds the state index from artifacts."""
    store = StateStore(helpers.repo_root)
    results = store.rebuild_index(dry_run=dry_run)
    for res in results:
        print(res)
    return 0
