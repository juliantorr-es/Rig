import os
import subprocess
import hashlib
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

class WorktreeManager:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.base_dir = Path.home() / ".local" / "state" / "rig" / "worktrees"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.repo_hash = hashlib.sha256(str(repo_root).encode()).hexdigest()[:12]

    def _get_worktree_dir(self, workspace_id: str) -> Path:
        return self.base_dir / self.repo_hash / workspace_id

    def create(self, workspace_id: str, branch_name: str) -> Path:
        worktree_dir = self._get_worktree_dir(workspace_id)
        worktree_dir.mkdir(parents=True, exist_ok=True)
        
        # Git worktree add <path> <branch>
        subprocess.run(["git", "worktree", "add", "-b", branch_name, str(worktree_dir)], 
                       cwd=self.repo_root, check=True)
        return worktree_dir

    def remove(self, workspace_id: str):
        worktree_dir = self._get_worktree_dir(workspace_id)
        if worktree_dir.exists():
            subprocess.run(["git", "worktree", "remove", str(worktree_dir)], 
                           cwd=self.repo_root, check=True)
            
    def get_head_hash(self, workspace_id: str) -> str:
        worktree_dir = self._get_worktree_dir(workspace_id)
        result = subprocess.run(["git", "rev-parse", "HEAD"], 
                                cwd=worktree_dir, capture_output=True, text=True, check=True)
        return result.stdout.strip()
