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

# Audit trail integration
from rig.domain.workspace_audit import (
    AuditAction,
    AuditActor,
    AuditEvent,
    AuditSubject,
    AuditSubjectKind,
    AuditDecision,
    AuditReceiptLink,
    AuditReceiptStatus,
    WorkspaceAuditTrail,
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_ADVISORY_ONLY,
    PLACEHOLDER_NOT_AUTHORITATIVE,
    PLACEHOLDER_NO_RECEIPT,
)

# Canonical receipt envelope support (Phase 2)
from rig.domain.receipt_envelope import (
    ReceiptEnvelope as CanonicalReceiptEnvelope,
    ReceiptActor as CanonicalReceiptActor,
    ReceiptSubject as CanonicalReceiptSubject,
    ReceiptInput,
    ReceiptOutput,
    ReceiptDecision,
    ReceiptEvidence,
    build_receipt_envelope,
    write_receipt,
    # Phase 4: Validation receipt integration
    build_validation_receipt,
    build_gate_decision_receipt,
    # Phase 5: Review bundle formalization
    build_review_bundle_receipt,
    # Apply receipt helper
    build_apply_receipt,
)


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


def ensure_governed_rig_layout(repo_root: Path) -> None:
    for rel_path in [
        ".rig",
        ".rig/worktrees",
        ".rig/artifacts",
        ".rig/replay",
        ".rig/topology",
        ".rig/receipts",
        ".rig/runtime",
        ".rig/cache",
    ]:
        ensure_dir(repo_root / rel_path)


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
        self.audit_dir = self.build_root / "audit"
        ensure_governed_rig_layout(repo_root)
        for path in (self.workspace_dir, self.review_dir, self.receipt_dir, self.validation_dir, self.worktree_root, self.audit_dir):
            ensure_dir(path)
    
    def workspace_path(self, workspace_id: str) -> Path:
        return self.workspace_dir / f"{workspace_id}.json"
    
    def review_path(self, workspace_id: str) -> Path:
        return self.review_dir / workspace_id
    
    def apply_receipt_path(self, workspace_id: str) -> Path:
        return self.receipt_dir / f"{workspace_id}_apply.json"
    
    def validation_result_path(self, workspace_id: str) -> Path:
        return self.validation_dir / workspace_id / "validation.json"
    
    def audit_trail_path(self, workspace_id: str) -> Path:
        """Path to workspace audit trail file."""
        return self.audit_dir / f"{workspace_id}_audit.json"
    
    def audit_event_path(self, event_id: str) -> Path:
        """Path to individual audit event file."""
        return self.audit_dir / f"{event_id}.json"
    
    def _save_audit_event(self, event: AuditEvent) -> Path:
        """Save an audit event to the filesystem. Returns the path."""
        path = self.audit_event_path(event.event_id)
        ensure_dir(path.parent)
        write_json(path, event.to_dict())
        return path
    
    def _save_audit_receipt(self, receipt: dict[str, Any], receipt_id: str) -> Path:
        """Save an audit receipt. Returns the path."""
        path = self.receipt_dir / f"{receipt_id}.json"
        ensure_dir(path.parent)
        write_json(path, receipt)
        return path
    
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
        ensure_governed_rig_layout(self.repo_root)
        parent_branch = git(self.repo_root, "branch", "--show-current").stdout.strip() or "HEAD"
        base_commit = git(self.repo_root, "rev-parse", "HEAD").stdout.strip()
        res = git(self.repo_root, "worktree", "add", "-b", branch, str(worktree_path), parent_branch)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip() or "failed to create worktree")
        
        # --- Audit Trail: Create workspace creation receipt and event ---
        receipt_id = f"ws_create_{workspace_id}"
        create_receipt = {
            "schema_version": "rig.workspace_create_receipt.v1",
            "receipt_id": receipt_id,
            "workspace_id": workspace_id,
            "task": task,
            "branch": branch,
            "base_commit": base_commit,
            "worktree_path": str(worktree_path),
            "parent_branch": parent_branch,
            "timestamp": utc_now(),
            "status": "success",
            "authoritative": True,
        }
        receipt_path = self._save_audit_receipt(create_receipt, receipt_id)
        
        # --- Canonical Receipt: Create formal ReceiptEnvelope ---
        canonical_actor = CanonicalReceiptActor(
            actor_id="cli",
            actor_kind="cli",
            display_name="CLI",
            is_human=True,
            is_authoritative=True,
        )
        canonical_subject = CanonicalReceiptSubject.workspace(workspace_id)
        canonical_decision = ReceiptDecision.allowed(
            f"ws_create_{workspace_id}_decision",
            "Workspace creation allowed by Rig authority",
        )
        
        # Build inputs
        canonical_inputs = [
            ReceiptInput.of(
                input_id=f"task_{workspace_id}",
                input_kind="task",
                reference="",
                summary=task,
            ),
            ReceiptInput.of(
                input_id=f"base_commit_{workspace_id}",
                input_kind="base_commit",
                reference=base_commit,
                hash=base_commit,
            ),
            ReceiptInput.of(
                input_id=f"parent_branch_{workspace_id}",
                input_kind="parent_branch",
                reference=parent_branch,
                summary=parent_branch,
            ),
        ]
        
        # Build outputs
        canonical_outputs = [
            ReceiptOutput.of(
                output_id=workspace_id,
                output_kind="workspace",
                reference=str(self.workspace_path(workspace_id)),
                status="success",
            ),
            ReceiptOutput.of(
                output_id=branch,
                output_kind="branch",
                reference=branch,
                status="success",
            ),
            ReceiptOutput.of(
                output_id=str(worktree_path),
                output_kind="worktree",
                reference=str(worktree_path),
                status="success",
            ),
        ]
        
        # Build the canonical envelope
        canonical_envelope = build_receipt_envelope(
            receipt_type="workspace_create",
            receipt_id=receipt_id,
            workspace_id=workspace_id,
            actor=canonical_actor,
            subject=canonical_subject,
            decision=canonical_decision,
            inputs=canonical_inputs,
            outputs=canonical_outputs,
            related_receipt_ids=[],
            related_audit_event_ids=[],
            summary=f"Workspace {workspace_id} created with task: {task}",
            authoritative=True,
            created_at=utc_now(),
        )
        
        # Write canonical receipt (alongside legacy receipt for backward compat)
        canonical_receipt_path = self.receipt_dir / f"{receipt_id}_canonical.json"
        canonical_write_result = write_receipt(
            self.repo_root,
            canonical_envelope,
            receipt_dir=self.receipt_dir,
        )
        
        # Create and save audit event
        audit_event = AuditEvent.for_workspace_creation(
            workspace_id=workspace_id,
            actor=AuditActor.cli(),
            receipt_id=receipt_id,
        )
        self._save_audit_event(audit_event)
        
        # Create receipt link
        receipt_link = AuditReceiptLink.of(
            event_id=audit_event.event_id,
            receipt_id=receipt_id,
            receipt_kind="workspace_create_receipt",
            workspace_id=workspace_id,
            authoritative=True,
        )
        
        # Update payload with audit info (including canonical receipt)
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
            "receipt_paths": [str(receipt_path)],
            "canonical_receipt_paths": [canonical_write_result.receipt_path] if canonical_write_result.status == "success" else [],
            "audit_event_ids": [audit_event.event_id],
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
        
        # --- Audit Trail: Create transition receipt and event ---
        receipt_id = f"ws_trans_{workspace_id}_{old}_to_{new_status}"
        transition_receipt = {
            "schema_version": "rig.workspace_transition_receipt.v1",
            "receipt_id": receipt_id,
            "workspace_id": workspace_id,
            "old_status": old,
            "new_status": new_status,
            "timestamp": utc_now(),
            "status": "success",
            "authoritative": True,
        }
        receipt_path = self._save_audit_receipt(transition_receipt, receipt_id)
        
        # --- Canonical Receipt: Create formal ReceiptEnvelope ---
        canonical_actor = CanonicalReceiptActor.cli()
        canonical_subject = CanonicalReceiptSubject.workspace(workspace_id)
        canonical_decision = ReceiptDecision.allowed(
            f"ws_trans_{workspace_id}_{old}_to_{new_status}_decision",
            f"Workspace transition from {old} to {new_status} allowed by Rig authority",
        )
        
        # Build inputs
        canonical_inputs = [
            ReceiptInput.of(
                input_id=f"workspace_{workspace_id}",
                input_kind="workspace",
                reference=str(self.workspace_path(workspace_id)),
                summary=workspace_id,
            ),
            ReceiptInput.of(
                input_id=f"old_status_{old}",
                input_kind="old_status",
                reference=old,
                summary=f"Previous status: {old}",
            ),
        ]
        
        # Build outputs
        canonical_outputs = [
            ReceiptOutput.of(
                output_id=f"new_status_{new_status}",
                output_kind="new_status",
                reference=new_status,
                status="success",
            ),
        ]
        
        # Build the canonical envelope
        canonical_envelope = build_receipt_envelope(
            receipt_type="workspace_transition",
            receipt_id=receipt_id,
            workspace_id=workspace_id,
            actor=canonical_actor,
            subject=canonical_subject,
            decision=canonical_decision,
            inputs=canonical_inputs,
            outputs=canonical_outputs,
            related_receipt_ids=[],
            related_audit_event_ids=[],
            summary=f"Workspace {workspace_id} transitioned: {old} -> {new_status}",
            authoritative=True,
            created_at=utc_now(),
        )
        
        # Write canonical receipt
        canonical_write_result = write_receipt(
            self.repo_root,
            canonical_envelope,
            receipt_dir=self.receipt_dir,
        )
        
        # Create and save audit event
        audit_event = AuditEvent.for_workspace_transition(
            workspace_id=workspace_id,
            old_status=old,
            new_status=new_status,
            actor=AuditActor.cli(),
            receipt_id=receipt_id,
        )
        self._save_audit_event(audit_event)
        
        # Update payload with audit info
        record.payload["status"] = new_status
        history = list(record.payload.get("status_history") or [])
        history.append({"status": new_status, "at": utc_now()})
        record.payload["status_history"] = history
        
        # Add audit info to workspace record
        existing_receipts = list(record.payload.get("receipt_paths") or [])
        existing_events = list(record.payload.get("audit_event_ids") or [])
        existing_receipts.append(str(receipt_path))
        existing_events.append(audit_event.event_id)
        
        # Add canonical receipt path
        existing_canonical_receipts = list(record.payload.get("canonical_receipt_paths") or [])
        if canonical_write_result.status == "success":
            existing_canonical_receipts.append(canonical_write_result.receipt_path)
        record.payload["canonical_receipt_paths"] = existing_canonical_receipts
        
        record.payload["receipt_paths"] = existing_receipts
        record.payload["audit_event_ids"] = existing_events
        
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
        
        # Build payload for legacy validation.json
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
        
        # --- Phase 4: Create canonical validation receipt ---
        # Build the validation result dict for the receipt builder
        full_validation_result = {
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
        
        # Build canonical validation receipt
        canonical_validation_envelope = build_validation_receipt(
            workspace_id=workspace_id,
            validation_result=full_validation_result,
            started_at=started,
            finished_at=utc_now(),
            authoritative=True,
        )
        
        # Write canonical receipt
        canonical_validation_write_result = write_receipt(
            self.repo_root,
            canonical_validation_envelope,
            receipt_dir=self.receipt_dir,
        )
        
        # --- Create gate decision receipt for validation gate ---
        if status == "passed":
            gate_decision_envelope = build_gate_decision_receipt(
                workspace_id=workspace_id,
                gate_name="validation_gate",
                decision="allowed",
                reason="All required validators passed",
                related_receipt_ids=[canonical_validation_envelope.receipt_id],
                authoritative=True,
            )
        else:
            gate_decision_envelope = build_gate_decision_receipt(
                workspace_id=workspace_id,
                gate_name="validation_gate",
                decision="blocked",
                reason="One or more required validators failed",
                related_receipt_ids=[canonical_validation_envelope.receipt_id],
                authoritative=True,
            )
        
        # Write gate decision receipt
        canonical_gate_write_result = write_receipt(
            self.repo_root,
            gate_decision_envelope,
            receipt_dir=self.receipt_dir,
        )
        
        # Update record with canonical receipt info
        canonical_receipt_paths = record.payload.get("canonical_receipt_paths", [])
        if canonical_validation_write_result.status == "success":
            canonical_receipt_paths.append(canonical_validation_write_result.receipt_path)
        if canonical_gate_write_result.status == "success":
            canonical_receipt_paths.append(canonical_gate_write_result.receipt_path)
        
        record.payload["canonical_receipt_paths"] = canonical_receipt_paths
        record.payload["validation_result_path"] = str(path)
        record.payload["validation_status"] = status
        record.payload["validation_receipt_id"] = canonical_validation_envelope.receipt_id
        record.payload["validation_gate_decision_id"] = gate_decision_envelope.receipt_id
        
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
        
        started = utc_now()
        
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
        
        # --- Phase 5: Create canonical review bundle receipt ---
        canonical_review_envelope = build_review_bundle_receipt(
            workspace_id=workspace_id,
            review_bundle=review,
            started_at=started,
            finished_at=utc_now(),
            authoritative=True,
        )
        
        # Write canonical receipt
        canonical_review_write_result = write_receipt(
            self.repo_root,
            canonical_review_envelope,
            receipt_dir=self.receipt_dir,
        )
        
        # --- Create gate decision receipt for apply gate ---
        apply_eligible = self.apply_eligibility(workspace_id)
        validation_status = validation.get("status", "unknown")
        
        if apply_eligible and validation_status == "passed":
            apply_gate_decision_envelope = build_gate_decision_receipt(
                workspace_id=workspace_id,
                gate_name="apply_gate",
                decision="allowed",
                reason="All gates passed - ready for apply",
                related_receipt_ids=[canonical_review_envelope.receipt_id],
                authoritative=True,
            )
        else:
            blockers = review.get("known_blockers", ["validation or receipt gate failed"])
            blocker_reason = "; ".join(blockers) if blockers else "unknown blocker"
            apply_gate_decision_envelope = build_gate_decision_receipt(
                workspace_id=workspace_id,
                gate_name="apply_gate",
                decision="blocked",
                reason=f"Apply blocked: {blocker_reason}",
                related_receipt_ids=[canonical_review_envelope.receipt_id],
                authoritative=True,
            )
        
        # Write apply gate decision receipt
        canonical_apply_gate_write_result = write_receipt(
            self.repo_root,
            apply_gate_decision_envelope,
            receipt_dir=self.receipt_dir,
        )
        
        # Update record with canonical receipt info
        canonical_receipt_paths = record.payload.get("canonical_receipt_paths", [])
        if canonical_review_write_result.status == "success":
            canonical_receipt_paths.append(canonical_review_write_result.receipt_path)
        if canonical_apply_gate_write_result.status == "success":
            canonical_receipt_paths.append(canonical_apply_gate_write_result.receipt_path)
        
        record.payload["canonical_receipt_paths"] = canonical_receipt_paths
        record.payload["review_bundle_receipt_id"] = canonical_review_envelope.receipt_id
        record.payload["apply_gate_decision_id"] = apply_gate_decision_envelope.receipt_id
        self.save_workspace(record.payload)
        
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
        
        receipt_id = uuid.uuid4().hex[:12]
        apply_payload = {
            "schema_version": "rig.apply_receipt.v1",
            "receipt_id": receipt_id,
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
        
        # --- Canonical Receipt: Create formal ReceiptEnvelope ---
        canonical_actor = CanonicalReceiptActor.cli()
        canonical_subject = CanonicalReceiptSubject.workspace(workspace_id)
        canonical_decision = ReceiptDecision.allowed(
            f"ws_apply_{workspace_id}_decision",
            "Workspace apply allowed by Rig authority",
        )
        
        # Build inputs
        canonical_inputs = [
            ReceiptInput.of(
                input_id=f"workspace_{workspace_id}",
                input_kind="workspace",
                reference=str(self.workspace_path(workspace_id)),
                summary=workspace_id,
            ),
            ReceiptInput.of(
                input_id=f"main_before_{main_before}",
                input_kind="main_before",
                reference=main_before,
                hash=main_before,
            ),
            ReceiptInput.of(
                input_id=f"workspace_branch_{branch}",
                input_kind="workspace_branch",
                reference=branch,
                summary=branch,
            ),
        ]
        
        # Build outputs
        canonical_outputs = [
            ReceiptOutput.of(
                output_id=f"main_after_{main_after}",
                output_kind="main_after",
                reference=main_after,
                hash=main_after,
                status="success",
            ),
            ReceiptOutput.of(
                output_id=receipt_id,
                output_kind="apply_receipt",
                reference=str(self.apply_receipt_path(workspace_id)),
                status="success",
            ),
        ]
        
        # Build evidence
        review_bundle_path = self.review_path(workspace_id) / "review.json"
        canonical_evidence = [
            ReceiptEvidence.file(
                evidence_id=f"review_bundle_{workspace_id}",
                reference=str(review_bundle_path),
                hash=apply_payload["review_bundle_hash"],
                mime_type="application/json",
            ),
        ]
        
        # Build the canonical envelope
        canonical_envelope = build_receipt_envelope(
            receipt_type="workspace_apply",
            receipt_id=receipt_id,
            workspace_id=workspace_id,
            actor=canonical_actor,
            subject=canonical_subject,
            decision=canonical_decision,
            inputs=canonical_inputs,
            outputs=canonical_outputs,
            evidence=canonical_evidence,
            related_receipt_ids=apply_payload.get("validation_receipt_ids", []),
            related_audit_event_ids=[],
            summary=f"Workspace {workspace_id} applied to main branch",
            authoritative=True,
            created_at=utc_now(),
        )
        
        # Write canonical receipt
        canonical_write_result = write_receipt(
            self.repo_root,
            canonical_envelope,
            receipt_dir=self.receipt_dir,
        )
        
        # --- Audit Trail: Create apply audit event ---
        audit_event = AuditEvent.for_workspace_apply(
            workspace_id=workspace_id,
            main_before=main_before,
            main_after=main_after,
            actor=AuditActor.cli(),
            receipt_id=receipt_id,
        )
        self._save_audit_event(audit_event)
        
        # Add audit info to workspace record
        existing_events = list(record.payload.get("audit_event_ids") or [])
        existing_events.append(audit_event.event_id)
        record.payload["audit_event_ids"] = existing_events
        
        # Add canonical receipt path
        existing_canonical_receipts = list(record.payload.get("canonical_receipt_paths") or [])
        if canonical_write_result.status == "success":
            existing_canonical_receipts.append(canonical_write_result.receipt_path)
        record.payload["canonical_receipt_paths"] = existing_canonical_receipts
        
        record.payload["status"] = "applied"
        self.save_workspace(record.payload)
        
        # Add canonical envelope to return value for testability
        apply_payload["canonical_receipt_envelope"] = canonical_envelope.to_dict()
        
        return apply_payload
