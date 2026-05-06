from __future__ import annotations

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from rig_tools import project_adapters

SCHEMA_VERSION = "1.0.0"

def get_profile(repo_root: Path) -> Optional[Dict[str, Any]]:
    profile_path = repo_root / ".rig" / "project.json"
    if profile_path.exists():
        try:
            return json.loads(profile_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None

def create_profile_plan(repo_root: Path, adapter_ids: List[str]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    project_id = repo_root.name
    
    selected_adapters = []
    build_commands = []
    test_commands = []
    validator_rules = []
    
    for aid in adapter_ids:
        adapter = project_adapters.get_effective_adapter(aid)
        if adapter:
            selected_adapters.append(aid)
            build_commands.extend(adapter.get("build_commands", []))
            test_commands.extend(adapter.get("test_commands", []))
            validator_rules.extend(adapter.get("validator_rules", []))
            
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "repo_root": str(repo_root),
        "selected_adapters": selected_adapters,
        "enabled_validators": sorted(list(set(validator_rules))),
        "build_commands": build_commands,
        "test_commands": test_commands,
        "created_at": now,
        "updated_at": now,
        "authoritative": True
    }

def apply_profile(repo_root: Path, profile: Dict[str, Any], dry_run: bool = False) -> Path:
    target_dir = repo_root / ".rig"
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
    
    profile_path = target_dir / "project.json"
    
    # In dry-run, we write to .build
    if dry_run:
        target_dir = repo_root / ".build" / "rig" / "project"
        target_dir.mkdir(parents=True, exist_ok=True)
        profile_path = target_dir / "profile-plan.json"
        
    if not dry_run or True: # Always write for MVP proof
        profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
        
    return profile_path
