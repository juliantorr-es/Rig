from __future__ import annotations

import json
import uuid
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"

PROFILES = {
    "python_cli": {
        "display_name": "Python CLI Tool",
        "adapters": ["python-cli", "generic"],
        "files": ["README.md", "pyproject.toml", "src/{project_name}/__init__.py", "src/{project_name}/cli.py", "tests/test_smoke.py"]
    },
    "web_app": {
        "display_name": "Web Application",
        "adapters": ["web", "generic"],
        "files": ["README.md", "package.json", "src/index.js", "public/index.html"]
    },
    "docs_vault": {
        "display_name": "Documentation Vault",
        "adapters": ["docs", "generic"],
        "files": ["README.md", "Docs/tutorials/README.md", "Docs/how-to/README.md", "Docs/reference/README.md", "Docs/explanation/README.md"]
    },
    "swift_app": {
        "display_name": "Swift/macOS App",
        "adapters": ["swift", "generic"],
        "files": ["README.md", "Docs/design.md"]
    },
    "research_repo": {
        "display_name": "Research Repository",
        "adapters": ["generic", "docs"],
        "files": ["README.md", "experiments/README.md", "data/README.md", "results/README.md", "Docs/theory.md"]
    },
    "automation_script": {
        "display_name": "Automation Scripts",
        "adapters": ["python-cli", "generic"],
        "files": ["README.md", "scripts/main.py", "tests/test_scripts.py"]
    },
    "library_package": {
        "display_name": "Library Package",
        "adapters": ["generic"],
        "files": ["README.md", "src/README.md", "tests/README.md"]
    },
    "unsure": {
        "display_name": "Generic/Unsure",
        "adapters": ["generic"],
        "files": ["README.md", "Docs/idea.md"]
    }
}

def detect_folder_state(repo_root: Path) -> str:
    """Detects if folder is empty, unknown, or an existing project."""
    if not any(repo_root.iterdir()):
        return "empty"
    
    # Check for common project markers
    markers = [".git", "Package.swift", "pyproject.toml", "package.json", "Cargo.toml", "README.md", ".rig"]
    if any((repo_root / m).exists() for m in markers):
        return "existing_project"
        
    return "unknown"

def map_goal_to_profile(goal: str) -> str:
    """Maps a user's natural language goal to a profile ID."""
    goal_lower = goal.lower()
    if any(k in goal_lower for k in ["python", "cli", "command line", "tool", "terminal"]):
        return "python_cli"
    if any(k in goal_lower for k in ["web", "site", "website", "frontend", "react", "html"]):
        return "web_app"
    if any(k in goal_lower for k in ["docs", "documentation", "vault", "notes", "knowledge"]):
        return "docs_vault"
    if any(k in goal_lower for k in ["swift", "mac", "ios", "app", "application"]):
        return "swift_app"
    if any(k in goal_lower for k in ["research", "data", "experiment", "notebook", "science"]):
        return "research_repo"
    if any(k in goal_lower for k in ["automation", "script", "cron", "workflow"]):
        return "automation_script"
    if any(k in goal_lower for k in ["library", "package", "module", "sdk"]):
        return "library_package"
    return "unsure"

def generate_blueprint(repo_root: Path, answers: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a project blueprint based on answers."""
    blueprint_id = f"blu-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    
    goal = answers.get("goal", "Generic project")
    profile_id = map_goal_to_profile(goal)
    if answers.get("project_type"):
        # Map explicit selection
        type_map = {
            "website": "web_app",
            "command-line tool": "python_cli",
            "app": "swift_app",
            "documentation project": "docs_vault",
            "research repo": "research_repo",
            "automation script": "automation_script"
        }
        profile_id = type_map.get(answers["project_type"], profile_id)
        
    profile = PROFILES.get(profile_id, PROFILES["unsure"])
    project_name = answers.get("project_name") or repo_root.name
    project_name = project_name.lower().replace(" ", "_").replace("-", "_")
    
    would_create = []
    generated_files = {}
    
    # 1. Base files
    for template_path in profile["files"]:
        f_path = template_path.format(project_name=project_name)
        would_create.append(f_path)
        
        # Simple content generation
        content = f"# {project_name.replace('_', ' ').title()}\n\n{goal}\n"
        if f_path.endswith("pyproject.toml"):
            content = f'[project]\nname = "{project_name}"\nversion = "0.1.0"\ndescription = "{goal}"\n'
        elif f_path.endswith("package.json"):
            content = json.dumps({"name": project_name, "version": "0.1.0", "description": goal}, indent=2)
            
        generated_files[f_path] = content

    # 2. Rig config
    would_create.extend([".rig/settings.toml", ".rig/project.json"])
    generated_files[".rig/project.json"] = json.dumps({
        "schema_version": "1.0.0",
        "project_id": project_name,
        "repo_root": str(repo_root),
        "selected_adapters": profile["adapters"],
        "authoritative": True
    }, indent=2)
    generated_files[".rig/settings.toml"] = 'default_mode = "safe"\n'

    return {
        "schema_version": SCHEMA_VERSION,
        "blueprint_id": blueprint_id,
        "created_at": created_at,
        "repo_root": str(repo_root),
        "project_name": project_name,
        "project_kind": profile_id,
        "confidence": "high" if profile_id != "unsure" else "medium",
        "user_goal": goal,
        "recommended_profile": profile_id,
        "selected_adapters": profile["adapters"],
        "would_create": would_create,
        "would_modify": [],
        "would_skip": [],
        "generated_files": generated_files,
        "recommended_validators": [],
        "recommended_first_tasks": ["refine-readme", "setup-ci"],
        "warnings": [],
        "authoritative": True
    }

def apply_blueprint(repo_root: Path, blueprint: Dict[str, Any], dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
    """Applies the blueprint to the filesystem."""
    status = "applied" if not dry_run else "dry_run"
    applied_files = []
    skipped_files = []
    
    for rel_path, content in blueprint.get("generated_files", {}).items():
        f_path = repo_root / rel_path
        if f_path.exists() and not force:
            skipped_files.append(rel_path)
            continue
            
        if not dry_run:
            f_path.parent.mkdir(parents=True, exist_ok=True)
            f_path.write_text(content, encoding="utf-8")
            
        applied_files.append(rel_path)
        
    return {
        "status": status,
        "applied": applied_files,
        "skipped": skipped_files
    }

def write_blueprint_report(repo_root: Path, blueprint: Dict[str, Any]) -> Path:
    target_dir = repo_root / ".build" / "rig" / "bootstrap"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = target_dir / "latest-blueprint.json"
    json_path.write_text(json.dumps(blueprint, indent=2), encoding="utf-8")
    
    md_path = target_dir / "latest-blueprint.md"
    md_content = [
        f"# Project Blueprint: {blueprint['project_name']}",
        f"Goal: {blueprint['user_goal']}",
        f"Kind: {blueprint['project_kind']}",
        "",
        "## Planned Files",
    ]
    for f in blueprint["would_create"]:
        md_content.append(f"- [ ] {f}")
        
    md_path.write_text("\n".join(md_content), encoding="utf-8")
    return json_path
