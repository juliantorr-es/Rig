from __future__ import annotations

import json
from pathlib import Path

def register(subparsers, helpers):
    parser = subparsers.add_parser("bootstrap", help="Project bootstrap walkthrough", description="Guided project initialization for empty folders.")
    boot = parser.add_subparsers(dest="bootstrap_cmd", required=True)

    # 1. Status
    status = boot.add_parser("status", help="Show bootstrap status")
    status.set_defaults(handler=lambda args: _run_status(helpers, args))

    # 2. Walkthrough (Dry-run by default)
    walkthrough = boot.add_parser("walkthrough", help="Start guided walkthrough")
    walkthrough.add_argument("--dry-run", action="store_true", default=True)
    walkthrough.set_defaults(handler=lambda args: _run_walkthrough(helpers, args))

    # 3. Blueprint
    blueprint = boot.add_parser("blueprint", help="Generate a project blueprint")
    blueprint.add_argument("--goal", required=True, help="Your project goal")
    blueprint.add_argument("--name", help="Project name")
    blueprint.add_argument("--write", action="store_true", help="Write blueprint to disk")
    blueprint.set_defaults(handler=lambda args: _run_blueprint(helpers, args))

    # 4. Apply
    apply = boot.add_parser("apply", help="Apply a project blueprint")
    apply.add_argument("--blueprint", type=Path, required=True, help="Path to blueprint JSON")
    apply.add_argument("--execute", action="store_true", help="Execute the blueprint (writes files)")
    apply.add_argument("--force", action="store_true", help="Overwrite existing files")
    apply.set_defaults(handler=lambda args: _run_apply(helpers, args))

def _run_status(helpers, args) -> int:
    from rig_tools import bootstrap_walkthrough
    state = bootstrap_walkthrough.detect_folder_state(helpers.repo_root)
    status = {
        "repo_root": str(helpers.repo_root),
        "detected_state": state,
        "rig_initialized": (helpers.repo_root / ".rig").is_dir(),
        "latest_blueprint": str((helpers.repo_root / ".build" / "rig" / "bootstrap" / "latest-blueprint.json").relative_to(helpers.repo_root)) if (helpers.repo_root / ".build" / "rig" / "bootstrap" / "latest-blueprint.json").exists() else None
    }
    print(json.dumps(status, indent=2))
    return 0

def _run_walkthrough(helpers, args) -> int:
    # In CLI, we simulate the walkthrough for MVP
    print("Bootstrap Walkthrough MVP")
    print("1. What are you trying to make? (e.g. 'I want to build a python cli tool')")
    print("2. Who is it for?")
    print("3. How should someone use it?")
    print("\nUse 'rig bootstrap blueprint --goal \"...\"' to generate a plan.")
    return 0

def _run_blueprint(helpers, args) -> int:
    from rig_tools import bootstrap_walkthrough
    answers = {"goal": args.goal, "project_name": args.name}
    blueprint = bootstrap_walkthrough.generate_blueprint(helpers.repo_root, answers)
    
    if args.write:
        path = bootstrap_walkthrough.write_blueprint_report(helpers.repo_root, blueprint)
        if helpers.output_mode == "human":
            print(f"Blueprint written to {path}")
            
    print(json.dumps(blueprint, indent=2))
    return 0

def _run_apply(helpers, args) -> int:
    from rig_tools import bootstrap_walkthrough
    try:
        blueprint = json.loads(args.blueprint.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Error loading blueprint: {e}")
        return 1
        
    result = bootstrap_walkthrough.apply_blueprint(helpers.repo_root, blueprint, dry_run=not args.execute, force=args.force)
    print(json.dumps(result, indent=2))
    return 0
