from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rig_tools.projections import ProjectionsBuilder

def register(subparsers, helpers):
    """Registers the 'projections' command group."""
    parser = subparsers.add_parser("projections", help="Rig OS derived read model commands")
    sub = parser.add_subparsers(dest="projections_command")
    
    status_parser = sub.add_parser("status", help="Show projections manifest status")
    status_parser.set_defaults(handler=lambda args: show_status(helpers))
    
    rebuild_parser = sub.add_parser("rebuild", help="Rebuild all projections")
    rebuild_parser.add_argument("--dry-run", action="store_true", help="Show planned rebuild actions")
    rebuild_parser.set_defaults(handler=lambda args: run_rebuild(helpers, dry_run=args.dry_run))
    
    show_parser = sub.add_parser("show", help="Show a specific projection")
    show_parser.add_argument("--kind", choices=["kanban", "task_graph", "monitor", "tui_snapshot"], required=True)
    show_parser.set_defaults(handler=lambda args: run_show(helpers, kind=args.kind))

def show_status(helpers):
    """Shows the status of the projections manifest."""
    builder = ProjectionsBuilder(helpers.repo_root)
    path = builder.projections_dir / "latest.json"
    
    if not path.exists():
        print("Projections manifest missing. Run 'rig projections rebuild'.")
        return 1
    
    manifest = json.loads(path.read_text())
    if helpers.output_mode == "human":
        print(f"Rig Projections: {manifest['status'].upper()}")
        print(f"Created: {manifest['created_at']}")
        print("\nProjections:")
        for p in manifest["projections"]:
            marker = "✓" if p["status"] == "pass" else "▲"
            print(f"- {marker} {p['kind']:15} {p['status']:10} ({p['record_count']} records)")
    else:
        print(json.dumps(manifest, indent=2))
    return 0

def run_rebuild(helpers, dry_run: bool = False):
    """Rebuilds all projections."""
    builder = ProjectionsBuilder(helpers.repo_root)
    manifest = builder.rebuild(dry_run=dry_run)
    
    if dry_run:
        print("Dry run: planned projections")
        for p in manifest["projections"]:
            print(f"- Would rebuild {p['kind']} at {p['path']}")
    else:
        if helpers.output_mode == "human":
            print(f"Rebuilt {len(manifest['projections'])} projections.")
            print(f"Status: {manifest['status'].upper()}")
        else:
            print(json.dumps(manifest, indent=2))
    return 0

def run_show(helpers, kind: str):
    """Shows a specific projection's content."""
    builder = ProjectionsBuilder(helpers.repo_root)
    filename = f"{kind.replace('_', '-')}.json"
    path = builder.projections_dir / filename
    
    if not path.exists():
        print(f"Projection {kind} not found at {path}. Run 'rig projections rebuild'.")
        return 1
        
    content = json.loads(path.read_text())
    print(json.dumps(content, indent=2))
    return 0
