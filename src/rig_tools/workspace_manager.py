from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"

class WorkspaceManager:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.workspaces_dir = self.repo_root / ".build" / "rig" / "workspaces"

    def list_workspaces(self) -> List[Dict[str, Any]]:
        if not self.workspaces_dir.exists():
            return []
            
        workspaces = []
        for d in self.workspaces_dir.iterdir():
            if d.is_dir() and (d / "workspace.json").exists():
                try:
                    workspaces.append(json.loads((d / "workspace.json").read_text(encoding="utf-8")))
                except: pass
        return sorted(workspaces, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_workspace(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        path = self.workspaces_dir / workspace_id / "workspace.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except: pass
        return None

    def create_workspace(self, task: Optional[str], mode: str = "safe", dry_run: bool = False) -> Dict[str, Any]:
        workspace_id = f"ws-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        
        # Load project adapters
        digest_path = self.repo_root / ".build" / "rig" / "project" / "latest.json"
        if digest_path.exists():
            try:
                digest = json.loads(digest_path.read_text(encoding="utf-8"))
                adapters = digest.get("selected_adapters", ["generic"])
            except:
                adapters = ["generic"]
        else:
            adapters = ["generic"]
        
        workspace = {
            "schema_version": SCHEMA_VERSION,
            "workspace_id": workspace_id,
            "created_at": created_at,
            "updated_at": created_at,
            "repo_root": str(self.repo_root),
            "task": task,
            "title": f"Workspace for {task}" if task else "Generic Workspace",
            "mode": mode,
            "status": "active",
            "selected_adapters": adapters,
            "selected_bias_profiles": [],
            "worktree": {
                "enabled": False,
                "path": None,
                "branch": None,
                "status": None
            },
            "loop_run_id": None,
            "swarm_run_id": None,
            "diff_review_id": None,
            "receipt_paths": [],
            "warnings": [],
            "authoritative": True
        }
        
        if not dry_run:
            ws_dir = self.workspaces_dir / workspace_id
            ws_dir.mkdir(parents=True, exist_ok=True)
            (ws_dir / "workspace.json").write_text(json.dumps(workspace, indent=2), encoding="utf-8")
            
            # Write markdown representation
            md_path = ws_dir / "workspace.md"
            md_content = [
                f"# Workspace: {workspace_id}",
                f"- Task: {task}",
                f"- Mode: {mode}",
                f"- Created: {created_at}",
                "",
                "## Adapters",
            ]
            for a in adapters:
                md_content.append(f"- {a}")
            md_path.write_text("\n".join(md_content), encoding="utf-8")
            
            # Update latest symlink-like marker
            (self.workspaces_dir / "latest.json").write_text(json.dumps(workspace, indent=2), encoding="utf-8")
            
        return workspace

    def archive_workspace(self, workspace_id: str, dry_run: bool = False) -> Dict[str, Any]:
        ws = self.get_workspace(workspace_id)
        if not ws:
            raise ValueError(f"Workspace {workspace_id} not found")
            
        ws["status"] = "archived"
        ws["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        if not dry_run:
            path = self.workspaces_dir / workspace_id / "workspace.json"
            path.write_text(json.dumps(ws, indent=2), encoding="utf-8")
            
        return ws
