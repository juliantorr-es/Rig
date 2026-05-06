from __future__ import annotations

import json
from pathlib import Path
from rig_tools import solution_bias

def register(subparsers, helpers):
    parser = subparsers.add_parser("bias", help="Rig Solution Bias Profiles", description="Manage and validate deterministic solution-bias steering profiles.")
    sub = parser.add_subparsers(dest="bias_cmd", required=True)

    profiles_cmd = sub.add_parser("profiles", help="List all available bias profiles")
    profiles_cmd.set_defaults(handler=lambda args: _list_profiles(helpers.repo_root))

    show_cmd = sub.add_parser("show", help="Show details of a specific bias profile")
    show_cmd.add_argument("profile_id", help="Profile ID (e.g., memory_safe)")
    show_cmd.set_defaults(handler=lambda args: _show_profile(helpers.repo_root, args.profile_id))

    validate_cmd = sub.add_parser("validate", help="Validate all bias profiles against schema")
    validate_cmd.set_defaults(handler=lambda args: _validate_profiles(helpers.repo_root))

def _list_profiles(repo_root: Path) -> int:
    profiles = solution_bias.list_profiles(repo_root)
    print(json.dumps([{"id": p["profile_id"], "name": p["display_name"], "description": p["description"]} for p in profiles], indent=2))
    return 0

def _show_profile(repo_root: Path, profile_id: str) -> int:
    profile = solution_bias.get_profile(repo_root, profile_id)
    if not profile:
        print(f"Error: Profile '{profile_id}' not found.")
        return 1
    print(json.dumps(profile, indent=2))
    return 0

def _validate_profiles(repo_root: Path) -> int:
    report = solution_bias.validate_profiles(repo_root)
    print(json.dumps(report, indent=2))
    if report["status"] == "fail":
        return 1
    return 0
