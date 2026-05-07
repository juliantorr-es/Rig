"""
Workspace Domain Module

This is a **deep module** that provides the core workspace domain logic.
It hides git operations, path management, validation coordination,
and worktree lifecycle behind a narrow, well-defined interface.

The interface is the test surface.

Architecture:
- WorkspaceRecord: Compatibility type for payload+path return
- WorkspaceDomain: Core workspace operations (renamed from WorkspaceGovernance)
- Uses rig_tools.core for process, I/O, and filesystem operations

Note: All file I/O, git commands, and subprocess calls are internal implementation details.
"""

from __future__ import annotations

import hashlib
import json
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
    """Compatibility type for code migrating from WorkspaceGovernance."""
    payload: dict[str, Any]
    path: Path


class WorkspaceDomain:
    """
    **Deep module** for workspace governance.
    
    This class provides a narrow interface for workspace operations,
    hiding the complexity of git worktree management, validation, 
    receipt management, and review bundle generation.
    
    The interface is the test surface - all callers should only use
    the public methods, not the internal git operations or path management.
    """
    
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
    
    def create_workspace(self, task: str) -> WorkspaceRecord:
        workspace_id = uuid.uuid4().hex[:8]
        branch = self._workspace_branch(workspace_id)
        worktree_path = self._workspace_worktree_dir(workspace_id)
        parent_branch = git(self.repo_root, "branch", "--show-current").stdout.strip() or "HEAD"
        base_commit = git(self.repo_root, "rev-parse", "HEAD").stdout.strip()
        res = git(self.repo_root, "worktree", "add", "-b", branch, str(worktree_path), parent_branch)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or "failed to create worktree")
        payload = {
            "workspace_id": workspace_id,
            "repo_root": str(self.repo_root),
            "task": task,
            "branch": branch,
            "base_commit": base_commit,
            "worktree_path": str(worktree_path),
            "worktree_hash": self.compute_worktree_hash(worktree_path),
            "status": "planned",
            "status_history": [{"status": "planned", "at": utc_now()}],
            "receipt_paths": [],
            "authoritative": True,
        }
        self.save_workspace(payload)
        return WorkspaceRecord(payload, self.workspace_path(workspace_id))
    
    def list_workspaces(self) -> list[dict[str, Any]]:
        return [read_json(path) for path in sorted(self.workspace_dir.glob("*.json"))]
    
    def transition_workspace(self, workspace_id: str, new_status: str) -> dict[str, Any]:
        record = self.load_workspace(workspace_id)
        if not record:
            raise FileNotFoundError(workspace_id)
        old = record.payload.get("status", "planned")
        if new_status not in ALLOWED_TRANSITIONS.get(old, set()):
            raise ValueError(f"invalid transition: {old} -> {new_status}")
        record.payload["status"] = new_status
        history = list(record.payload.get("status_history") or [])
        history.append({"status": new_status, "at": utc_now()})
        record.payload["status_history"] = history
        self.save_workspace(record.payload)
        return record.payload
    
    def compute_worktree_hash(self, worktree_path: Path) -> str:
        entries: list[str] = []
        proc = git(worktree_path, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        for item in proc.stdout.split("\0"):
            if not item:
                continue
            entries.append(item)
        proc = git(worktree_path, "ls-files", "-z", "--others", "--exclude-standard")
        entries.extend([f"?? {p}" for p in proc.stdout.split("\0") if p])
        digest = sha256_text("\n".join(sorted(entries)))
        head = git(worktree_path, "rev-parse", "HEAD").stdout.strip()
        return sha256_text(f"{head}:{digest}")
    
    def read_validator_config(self) -> list[dict[str, Any]]:
        pyproject = self.repo_root / "pyproject.toml"
        if not pyproject.exists():
            return []
        payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        validators = (((payload.get("tool") or {}).get("rig") or {}).get("validators")) or []
        if not isinstance(validators, list):
            return []
        out: list[dict[str, Any]] = []
        for item in validators:
            if isinstance(item, dict) and isinstance(item.get("argv"), list):
                out.append(item)
        return out
    
    def generate_validation_result(self, workspace_id: str) -> dict[str, Any]:
        record = self.load_workspace(workspace_id)
        if not record:
            raise FileNotFoundError(workspace_id)
        worktree = Path(record.payload["worktree_path"])
        validators = self.read_validator_config()
        started = utc_now()
        results: list[dict[str, Any]] = []
        status = "passed"
        for validator in validators:
            argv = [str(part) for part in validator["argv"]]
            started_at = utc_now()
            proc = subprocess.run(argv, cwd=worktree, text=True, capture_output=True, check=False)
            tail_stdout = (proc.stdout or "")[-4000:]
            tail_stderr = (proc.stderr or "")[-4000:]
            result = {
                "validator_id": validator.get("id") or argv[0],
                "command": argv,
                "required": bool(validator.get("required", False)),
                "exit_code": proc.returncode,
                "stdout_tail": tail_stdout,
                "stderr_tail": tail_stderr,
                "started_at": started_at,
                "finished_at": utc_now(),
                "duration_seconds": 0,
                "authoritative": True,
            }
            results.append(result)
            if proc.returncode != 0 and validator.get("required", False):
                status = "failed"
        payload = {
            "schema_version": "rig.validation_result.v1",
            "workspace_id": workspace_id,
            "workspace_branch": record.payload.get("branch"),
            "worktree_path": str(worktree),
            "started_at": started,
            "finished_at": utc_now(),
            "status": status,
            "validators": results,
            "authoritative": True,
        }
        path = self.validation_result_path(workspace_id)
        write_json(path, payload)
        record.payload["validation_result_path"] = str(path)
        record.payload["validation_status"] = status
        if status == "failed":
            record.payload["status"] = "blocked"
        else:
            record.payload["status"] = "validated"
        self.save_workspace(record.payload)
        return payload
    
    def build_review_bundle(self, workspace_id: str) -> dict[str, Any]:
        record = self.load_workspace(workspace_id)
        if not record:
            raise FileNotFoundError(workspace_id)
        worktree = Path(record.payload["worktree_path"])
        diff = git(self.repo_root, "diff", "--binary", f"{record.payload['base_commit']}..HEAD")
        patch = git(worktree, "diff", "--binary", record.payload["base_commit"], "HEAD", "--")
        bundle_dir = self.review_path(workspace_id)
        bundle_dir.mkdir(parents=True, exist_ok=True)
        validation_path = self.validation_result_path(workspace_id)
        validation = read_json(validation_path) if validation_path.exists() else self.generate_validation_result(workspace_id)
        changed = git(worktree, "status", "--porcelain=v1").stdout.splitlines()
        review = {
            "schema_version": "rig.review_bundle.v1",
            "workspace_id": workspace_id,
            "task": record.payload.get("task"),
            "workspace_status": record.payload.get("status"),
            "base_commit": record.payload.get("base_commit"),
            "workspace_branch": record.payload.get("branch"),
            "worktree_path": str(worktree),
            "execution_receipt_id": (self.load_execution_receipt(workspace_id) or {}).get("receipt_id"),
            "execution_receipt_hash": self.execution_receipt_hash(workspace_id),
            "changed_files": changed,
            "diff_hash": sha256_bytes(diff.stdout.encode("utf-8")),
            "validation_status": validation.get("status"),
            "apply_eligibility": self.apply_eligibility(workspace_id),
            "known_blockers": [] if self.apply_eligibility(workspace_id) else ["validation or receipt gate failed"],
            "authoritative": True,
        }
        write_json(bundle_dir / "review.json", review)
        (bundle_dir / "summary.md").write_text(
            f"# Review Bundle\n\n- Workspace: `{workspace_id}`\n- Status: `{review['workspace_status']}`\n- Branch: `{review['workspace_branch']}`\n- Apply eligible: `{review['apply_eligibility']}`\n",
            encoding="utf-8",
        )
        (bundle_dir / "diff.patch").write_text(patch.stdout, encoding="utf-8")
        write_json(bundle_dir / "validation.json", validation)
        return review
    
    def load_execution_receipt(self, workspace_id: str) -> dict[str, Any] | None:
        path = self.receipt_dir / f"{workspace_id}_run.json"
        if not path.exists():
            return None
        try:
            return read_json(path)
        except Exception:
            return None
    
    def execution_receipt_hash(self, workspace_id: str) -> str | None:
        receipt = self.load_execution_receipt(workspace_id)
        if not receipt:
            return None
        return sha256_text(json.dumps(receipt, sort_keys=True))
    
    def apply_eligibility(self, workspace_id: str) -> bool:
        record = self.load_workspace(workspace_id)
        if not record:
            return False
        receipt = self.load_execution_receipt(workspace_id)
        if not receipt or receipt.get("status") != "success":
            return False
        worktree = Path(record.payload["worktree_path"])
        return self.compute_worktree_hash(worktree) == receipt.get("worktree_hash_after")
    
    def apply_workspace(self, workspace_id: str) -> dict[str, Any]:
        record = self.load_workspace(workspace_id)
        if not record:
            raise FileNotFoundError(workspace_id)
        if git(self.repo_root, "status", "--porcelain=v1").stdout.strip():
            raise RuntimeError("main worktree dirty")
        if not self.apply_eligibility(workspace_id):
            raise RuntimeError("apply gates failed")
        self.build_review_bundle(workspace_id)
        validation = read_json(self.validation_result_path(workspace_id))
        if validation.get("status") != "passed":
            raise RuntimeError("validators failed")
        main_before = git(self.repo_root, "rev-parse", "HEAD").stdout.strip()
        branch = record.payload["branch"]
        merge = git(self.repo_root, "merge", "--no-ff", branch)
        if merge.returncode != 0:
            git(self.repo_root, "merge", "--abort")
            record.payload["status"] = "blocked"
            self.save_workspace(record.payload)
            raise RuntimeError(merge.stderr.strip() or "merge failed")
        main_after = git(self.repo_root, "rev-parse", "HEAD").stdout.strip()
        apply_payload = {
            "schema_version": "rig.apply_receipt.v1",
            "receipt_id": uuid.uuid4().hex[:12],
            "workspace_id": workspace_id,
            "base_commit": record.payload.get("base_commit"),
            "workspace_branch": branch,
            "workspace_commit": git(self.repo_root, "rev-parse", branch).stdout.strip(),
            "main_before": main_before,
            "main_after": main_after,
            "execution_receipt_id": (self.load_execution_receipt(workspace_id) or {}).get("receipt_id"),
            "validation_receipt_ids": [workspace_id],
            "review_bundle_hash": sha256_text((self.review_path(workspace_id) / "review.json").read_text(encoding="utf-8")),
            "apply_method": "git merge --no-ff",
            "status": "success",
            "authoritative": True,
        }
        write_json(self.apply_receipt_path(workspace_id), apply_payload)
        record.payload["status"] = "applied"
        self.save_workspace(record.payload)
        return apply_payload
