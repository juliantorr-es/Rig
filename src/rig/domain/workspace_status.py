from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except Exception:  # pragma: no cover
    import tomli as tomllib  # type: ignore


@dataclass(frozen=True, slots=True)
class WorkspaceWorktreeState:
    branch: str
    head: str
    dirty: bool
    dirty_files_count: int
    safe_to_commit: bool
    reason: str


@dataclass(frozen=True, slots=True)
class WorkspaceProposalState:
    status: str
    summary: str
    next_action: str


@dataclass(frozen=True, slots=True)
class WorkspaceValidationState:
    status: str
    summary: str
    next_action: str
    proof_status: str = "not_proof"


@dataclass(frozen=True, slots=True)
class WorkspaceStatusSummary:
    workspace_id: Optional[str]
    repo_path: str
    workspace_path: Optional[str]
    branch: Optional[str]
    head: Optional[str]
    status: str
    gate: str = "A"
    selected: bool = False
    worktree_state: WorkspaceWorktreeState = field(default_factory=lambda: WorkspaceWorktreeState(
        branch="HEAD",
        head="",
        dirty=False,
        dirty_files_count=0,
        safe_to_commit=False,
        reason="No workspace selected.",
    ))
    proposal_state: WorkspaceProposalState = field(default_factory=lambda: WorkspaceProposalState(
        status="not_created",
        summary="No proposal has been projected yet.",
        next_action="Create or select a workspace proposal lane.",
    ))
    validation_state: WorkspaceValidationState = field(default_factory=lambda: WorkspaceValidationState(
        status="not_run",
        summary="No validation summary has been projected yet.",
        next_action="Run read-only validation summary before review.",
    ))
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["worktree_state"] = asdict(self.worktree_state)
        payload["proposal_state"] = asdict(self.proposal_state)
        payload["validation_state"] = asdict(self.validation_state)
        return payload


def _workspace_dir(repo_root: Path) -> Path:
    """Path to workspace records directory. Does not create it."""
    return repo_root / ".build" / "rig" / "workspaces"


def list_workspaces_read_only(repo_root: Path) -> list[dict[str, Any]]:
    """List workspace records without creating any directories.

    This is the read-only entry point for workspace enumeration.
    Returns empty list if the workspace directory does not exist.
    """
    workspace_dir = _workspace_dir(repo_root)
    if not workspace_dir.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(workspace_dir.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return records


def read_validator_config(repo_root: Path) -> list[dict[str, Any]]:
    """Read validator config from pyproject.toml without creating directories.

    This is a standalone function for read-only use.
    """
    pyproject = repo_root / "pyproject.toml"
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


def _git_capture(repo_root: Path, *args: str) -> str:
    import subprocess

    proc = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
    return (proc.stdout or "").strip()


def _git_status_entries(path: Path) -> list[str]:
    raw = _git_capture(path, "status", "--porcelain=v1", "-z")
    return [entry for entry in raw.split("\0") if entry]


def _select_workspace_record(records: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not records:
        return None

    def _sort_key(ws: dict[str, Any]) -> str:
        history = ws.get("status_history")
        if isinstance(history, list) and history:
            last = history[-1]
            if isinstance(last, dict):
                return str(last.get("at", ""))
        return ""

    for ws in sorted(records, key=_sort_key, reverse=True):
        if ws.get("status") != "applied":
            return ws
    return records[0]


def build_workspace_status_summary(
    repo_root: Path,
    *,
    workspace_record: Optional[dict[str, Any]] = None,
) -> WorkspaceStatusSummary:
    records = list_workspaces_read_only(repo_root)
    record = workspace_record or _select_workspace_record(records)
    current_branch = _git_capture(repo_root, "branch", "--show-current") or "HEAD"
    current_head = _git_capture(repo_root, "rev-parse", "--short", "HEAD") or None

    if not record:
        dirty_entries = _git_status_entries(repo_root)
        dirty = bool(dirty_entries)
        reason = "Workspace root is dirty." if dirty else "No workspace is currently selected."
        return WorkspaceStatusSummary(
            workspace_id=None,
            repo_path=str(repo_root),
            workspace_path=None,
            branch=current_branch,
            head=current_head,
            status="unselected",
            gate="A",
            selected=False,
            worktree_state=WorkspaceWorktreeState(
                branch=current_branch,
                head=current_head or "",
                dirty=dirty,
                dirty_files_count=len(dirty_entries),
                safe_to_commit=not dirty and current_branch != "main",
                reason=reason,
            ),
            warnings=("No workspace is selected.",),
            metadata={
                "workspace_records": len(records),
                "source": "workspace.records",
            },
        )

    workspace_path = record.get("worktree_path")
    worktree = Path(str(workspace_path)) if workspace_path else repo_root
    dirty_entries = _git_status_entries(worktree) if worktree.exists() else []
    dirty = bool(dirty_entries)
    branch = str(record.get("branch") or current_branch)
    head = _git_capture(worktree, "rev-parse", "--short", "HEAD") if worktree.exists() else current_head
    status = str(record.get("status") or "unknown")
    proposal_status = "review_ready" if status == "review_ready" else ("not_created" if status in {"planned", "active", "executed", "blocked"} else "unknown")
    validation_status = "passed" if status == "validated" else ("failed" if status == "blocked" else "not_run")
    return WorkspaceStatusSummary(
        workspace_id=str(record.get("workspace_id") or "") or None,
        repo_path=str(repo_root),
        workspace_path=str(workspace_path) if workspace_path else None,
        branch=branch,
        head=head,
        status=status,
        gate="A",
        selected=True,
        worktree_state=WorkspaceWorktreeState(
            branch=branch,
            head=head or "",
            dirty=dirty,
            dirty_files_count=len(dirty_entries),
            safe_to_commit=not dirty and branch != "main",
            reason=(
                "Workspace is dirty."
                if dirty
                else ("Current branch is main." if branch == "main" else "Clean workspace record.")
            ),
        ),
        proposal_state=WorkspaceProposalState(
            status=proposal_status,
            summary="No proposal has been projected yet." if proposal_status == "not_created" else "Proposal state is available from the workspace record.",
            next_action="Run review/recommend in an isolated proposal lane." if proposal_status == "not_created" else "Review proposed changes; apply remains blocked under Gate A.",
        ),
        validation_state=WorkspaceValidationState(
            status=validation_status,
            summary=(
                "No validation summary has been projected yet."
                if validation_status == "not_run"
                else "Validation summary is available from the workspace record."
            ),
            next_action=(
                "Run read-only validation summary before review."
                if validation_status == "not_run"
                else "Review proposed changes; apply remains blocked under Gate A."
            ),
            proof_status="not_proof",
        ),
        warnings=("Workspace path is not selected.",) if not workspace_path else (),
        metadata={
            "workspace_records": len(records),
            "status_history": record.get("status_history") or [],
            "source": "workspace.records",
        },
    )
