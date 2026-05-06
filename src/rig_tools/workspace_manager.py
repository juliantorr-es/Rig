import json
import uuid
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from rig.paths import resolve_repo_path

WORKSPACE_DIR = resolve_repo_path(".build", "rig", "workspaces")

class WorkspaceManager:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.workspace_dir = repo_root / ".build" / "rig" / "workspaces"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def create(self, task: str, mode: str = "safe") -> Path:
        workspace_id = uuid.uuid4().hex[:8]
        workspace_path = self.workspace_dir / f"{workspace_id}.json"
        data = {
            "workspace_id": workspace_id,
            "repo_root": str(self.repo_root),
            "task": task,
            "mode": mode,
            "status": "created",
            "worktree": None,
            "receipt_paths": [],
            "authoritative": True
        }
        workspace_path.write_text(json.dumps(data, indent=2))
        return workspace_path

    def list_workspaces(self) -> list[Dict[str, Any]]:
        workspaces = []
        for path in self.workspace_dir.glob("*.json"):
            workspaces.append(json.loads(path.read_text()))
        return workspaces

    def show(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        path = self.workspace_dir / f"{workspace_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def archive(self, workspace_id: str) -> bool:
        path = self.workspace_dir / f"{workspace_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
