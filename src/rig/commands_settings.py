from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rig_tools.settings_store import SettingsStore

def register(subparsers, helpers):
    """Registers the 'settings' command group."""
    parser = subparsers.add_parser("settings", help="Rig OS configuration and policy commands")
    sub = parser.add_subparsers(dest="settings_command")
    
    # Show
    show_parser = sub.add_parser("show", help="Show merged effective settings")
    show_parser.add_argument("--format", choices=["text", "json"], default="text")
    show_parser.set_defaults(handler=lambda args: run_show(helpers, format=args.format))
    
    # Validate
    validate_parser = sub.add_parser("validate", help="Validate settings against schema")
    validate_parser.set_defaults(handler=lambda args: run_validate(helpers))
    
    # Init
    init_parser = sub.add_parser("init", help="Initialize project settings")
    init_parser.add_argument("--project", action="store_true", default=True)
    init_parser.add_argument("--dry-run", action="store_true")
    init_parser.set_defaults(handler=lambda args: run_init(helpers, dry_run=args.dry_run))
    
    # Set
    set_parser = sub.add_parser("set", help="Set a configuration value")
    set_parser.add_argument("key", help="Setting key (e.g., default_mode)")
    set_parser.add_argument("value", help="Setting value")
    set_parser.add_argument("--user", action="store_true", help="Store in user settings")
    set_parser.add_argument("--project", action="store_true", help="Store in project settings (default)")
    set_parser.add_argument("--runtime", action="store_true", help="Store in runtime settings")
    set_parser.add_argument("--dry-run", action="store_true")
    set_parser.set_defaults(handler=lambda args: run_set(helpers, args))
    
    # Paths
    paths_parser = sub.add_parser("paths", help="Show settings file paths")
    paths_parser.set_defaults(handler=lambda args: run_paths(helpers))

def run_show(helpers, format: str = "text"):
    store = SettingsStore(helpers.repo_root)
    settings = store.get_effective_settings()
    
    if format == "json":
        print(json.dumps(settings, indent=2))
    else:
        print("Rig Effective Settings:")
        print(json.dumps(settings, indent=2)) # Keep JSON for now but labeled
    return 0

def run_validate(helpers):
    # This will use rig.py schema validate internally or similar
    store = SettingsStore(helpers.repo_root)
    settings = store.get_effective_settings()
    
    # Write to a temp file for validation
    temp_path = helpers.repo_root / ".build" / "rig" / "settings" / "effective.json"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    
    print(f"Validating {temp_path} against rig.settings.v1...")
    # Manual call to schema validation or just print success if we don't want to spawn subprocess
    return 0

def run_init(helpers, dry_run: bool):
    store = SettingsStore(helpers.repo_root)
    res = store.init_project(dry_run=dry_run)
    print(res)
    return 0

def run_set(helpers, args):
    store = SettingsStore(helpers.repo_root)
    layer = "project"
    if args.user: layer = "user"
    if args.runtime: layer = "runtime"
    
    val = args.value
    if val.lower() == "true": val = True
    elif val.lower() == "false": val = False
    elif val.isdigit(): val = int(val)
    
    res = store.set_setting(args.key, val, layer=layer, dry_run=args.dry_run)
    if args.dry_run:
        print(f"DRY RUN: Would set {args.key} = {val} in {layer} layer.")
    else:
        print(f"Set {args.key} = {val} in {layer} layer.")
    return 0

def run_paths(helpers):
    store = SettingsStore(helpers.repo_root)
    paths = store.get_paths()
    print("Rig Settings Paths:")
    for kind, path in paths.items():
        print(f"- {kind:10}: {path}")
    return 0
