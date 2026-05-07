"""
Workspace Governance for Rig

Manages workspace lifecycle, validation, and transitions between states.

Uses rig_tools.core.process for subprocess execution.
Uses rig_tools.core.io for JSON I/O.
Uses rig_tools.core.filesystem for directory operations.
"""

from __future__ import annotations

import hashlib
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except Exception:  # pragma: no cover
    import tomli as tomllib  # type: ignore

# Use core utilities
from rig_tools.core import run_capture
from rig_tools.core.io import read_json, write_json
from rig_tools.core.filesystem import ensure_dir


WORKSPACE_STATUSES = ["planned", "active", "blocked", "executed", "validated", "review_ready", "applied"]
ALLOWED_TRANSITIONS = {
    "planned": {"active"},
    "active": {"executed", "blocked"},
    "executed": {"validated", "blocked"},
    "validated": {"review_ready", "blocked"},
    "review_ready": {"applied", "blocked"},
    "blocked": set(),
    "applied": set(),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command."""
    return run_capture(["git"] + list(args), cwd=repo_root, timeout=30)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class WorkspaceRecord:
    payload: dict[str, Any]
    path: Path


class WorkspaceGovernance:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.build_root = repo_root / ".build" / "rig"
        self.workspace_dir = self.build_root / "workspaces"
        self.review_dir = self.build_root / "reviews"
        self.receipt_dir = self.build_root / "receipts"
        self.validation_dir = self.build_root / "validation"
        self.worktree_root = self.build_root / "worktrees"
        for path in (self.workspace_dir, self.review_dir, self.receipt_dir, self.validation_dir, self.worktree_root):
            ensure_dir(path)
    
    def workspace_path(self, workspace_id: str) -> Path:
        return self.workspace_dir / f"{workspace_id}.json"
    
    def review_path(self, workspace_id: str) -> Path:
        return self.review_dir / workspace_id
    
    def apply_receipt_path(self, workspace_id: str) -> Path:
        return self.receipt_dir / f"{workspace_id}_apply.json"
    
    def validation_result_path(self, workspace_id: str) -> Path:
        return self.validation_dir / workspace_id / "validation.json"
    
    def load_workspace(self, workspace_id: str) -> Optional[WorkspaceRecord]:
        path = self.workspace_path(workspace_id)
        if not path.exists():
            return None
        return WorkspaceRecord(read_json(path), path)
    
    def save_workspace(self, payload: dict[str, Any]) -> Path:
        path = self.workspace_path(payload["workspace_id"])
        ensure_dir(path.parent)
        write_json(path, payload)
        return path
    
    def _workspace_worktree_dir(self, workspace_id: str) -> Path:
        return self.worktree_root / workspace_id
    
    def _workspace_branch(self, workspace_id: str) -> str:
        return f"rig/workspaces/{workspace_id}"
