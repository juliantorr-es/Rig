from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rig_tools.gc import GarbageCollector
from rig_tools.docs_normalization import DocsNormalizationPlanner

def register(subparsers, helpers):
    """Registers the 'gc' command group."""
    parser = subparsers.add_parser("gc", help="Rig OS garbage collection and docs normalization")
    sub = parser.add_subparsers(dest="gc_command")
    
    # Status
    status_parser = sub.add_parser("status", help="Show GC subsystem status")
    status_parser.set_defaults(handler=lambda args: run_status(helpers))
    
    # Plan
    plan_parser = sub.add_parser("plan", help="Generate a GC plan")
    plan_parser.add_argument("--format", choices=["text", "json"], default="text")
    plan_parser.set_defaults(handler=lambda args: run_plan(helpers, args.format))
    
    # Run
    run_parser = sub.add_parser("run", help="Execute the latest GC plan")
    run_parser.add_argument("--apply", action="store_true", help="Actually delete files")
    run_parser.add_argument("--dry-run", action="store_true", help="Simulate deletion (default)")
    run_parser.set_defaults(handler=lambda args: run_execute(helpers, args.apply))
    
    # Docs Plan
    docs_plan_parser = sub.add_parser("docs-plan", help="Generate a Docs Normalization plan")
    docs_plan_parser.add_argument("--format", choices=["text", "json"], default="text")
    docs_plan_parser.set_defaults(handler=lambda args: run_docs_plan(helpers, args.format))
    
    # Docs Archive
    docs_archive_parser = sub.add_parser("docs-archive", help="Execute the latest Docs Normalization plan")
    docs_archive_parser.add_argument("--apply", action="store_true", help="Actually move files")
    docs_archive_parser.add_argument("--dry-run", action="store_true", help="Simulate move (default)")
    docs_archive_parser.add_argument("--allow-git-tracked-archive", action="store_true", help="Allow moving git-tracked files")
    docs_archive_parser.set_defaults(handler=lambda args: run_docs_archive(helpers, args.apply, args.allow_git_tracked_archive))
    
    # Explain
    explain_parser = sub.add_parser("explain", help="Explain classification of a path")
    explain_parser.add_argument("--path", required=True, help="Path relative to repo root")
    explain_parser.set_defaults(handler=lambda args: run_explain(helpers, args.path))

def run_docs_plan(helpers, format: str):
    planner = DocsNormalizationPlanner(helpers.repo_root)
    plan = planner.create_plan()
    
    if format == "json":
        print(json.dumps(plan, indent=2))
    else:
        print(f"Docs Normalization Plan: {plan['plan_id']}")
        print(f"Status: {plan['status']}")
        print(f"Candidates for Archive: {len(plan['candidates'])}")
        print(f"Duplicate Groups: {len(plan['duplicate_groups'])}")
        
        if plan['warnings']:
            print("\nWarnings:")
            for w in plan['warnings']:
                print(f"- {w}")
                
        if len(plan['candidates']) > 0:
            print("\nRun `rig gc docs-archive --apply` to execute.")
    return 0

def run_docs_archive(helpers, apply: bool, allow_git: bool):
    planner = DocsNormalizationPlanner(helpers.repo_root)
    latest_plan = planner.gc_dir / "latest-docs-plan.json"
    if not latest_plan.exists():
        print("No docs plan found. Run `rig gc docs-plan` first.")
        return 1
        
    try:
        plan = json.loads(latest_plan.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read latest docs plan: {e}")
        return 1
        
    manifest = planner.run_archive(plan, apply=apply, allow_git_tracked=allow_git)
    
    mode = "apply" if apply else "dry_run"
    print(f"Docs Archive Run (Mode: {mode})")
    
    moved_count = sum(1 for e in manifest['entries'] if e['applied'])
    print(f"Files Archived: {moved_count} of {len(manifest['entries'])}")
    
    if manifest['warnings']:
        print("\nWarnings:")
        for w in manifest['warnings']:
            print(f"- {w}")
            
    return 0 if mode == "dry_run" or moved_count > 0 or not manifest['entries'] else 1

def run_status(helpers):
    gc = GarbageCollector(helpers.repo_root)
    print("Rig GC Status:")
    print(f"- Policy: {json.dumps(gc.policy)}")
    
    latest_plan = gc.gc_dir / "latest-plan.json"
    if latest_plan.exists():
        try:
            plan = json.loads(latest_plan.read_text(encoding="utf-8"))
            print(f"- Latest Plan: {plan['plan_id']} ({plan['created_at']})")
            print(f"  - Delete Candidates: {plan['delete_count']}")
            print(f"  - Reclaimable Bytes: {plan['bytes_reclaimable']}")
        except Exception:
            pass
    else:
        print("- Latest Plan: None")
        
    return 0

def run_plan(helpers, format: str):
    gc = GarbageCollector(helpers.repo_root)
    plan = gc.create_plan()
    
    if format == "json":
        print(json.dumps(plan, indent=2))
    else:
        print(f"GC Plan: {plan['plan_id']}")
        print(f"Status: {plan['status']}")
        print(f"Delete Candidates: {plan['delete_count']}")
        print(f"Protected Files: {len(plan['protected'])}")
        print(f"Reclaimable Bytes: {plan['bytes_reclaimable']}")
        
        if plan['warnings']:
            print("\nWarnings:")
            for w in plan['warnings']:
                print(f"- {w}")
                
        if plan['delete_count'] > 0:
            print("\nRun `rig gc run --apply` to execute.")
    return 0

def run_execute(helpers, apply: bool):
    gc = GarbageCollector(helpers.repo_root)
    latest_plan = gc.gc_dir / "latest-plan.json"
    if not latest_plan.exists():
        print("No GC plan found. Run `rig gc plan` first.")
        return 1
        
    try:
        plan = json.loads(latest_plan.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to read latest plan: {e}")
        return 1
        
    mode = "apply" if apply else "dry_run"
    run = gc.run(plan, mode=mode)
    
    print(f"GC Run: {run['run_id']} (Mode: {run['mode']})")
    print(f"Status: {run['status']}")
    print(f"Deleted Paths: {len(run['deleted_paths'])}")
    print(f"Bytes Reclaimed: {run['bytes_reclaimed']}")
    
    if run['failed_paths']:
        print("\nFailed to delete:")
        for f in run['failed_paths']:
            print(f"- {f['path']}: {f['error']}")
            
    return 0 if run['status'] in {"passed", "dry_run"} else 1

def run_explain(helpers, path: str):
    gc = GarbageCollector(helpers.repo_root)
    res = gc.explain(path)
    print(json.dumps(res, indent=2))
    return 0
