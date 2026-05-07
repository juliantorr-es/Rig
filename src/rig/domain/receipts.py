"""Domain models for Receipts and ReceiptStore.

Receipts are authoritative records of executions, validations, and other
governed operations. They provide evidence for what happened, when, and with
what result.

Structure:
- Receipt: Base abstract receipt
- ExecutionReceipt: Receipt for command/process execution
- ValidatorReceipt: Receipt for validator runs
- ReceiptStore: Protocol and implementation for storing/retrieving receipts
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


# =============================================================================
# Receipt Models
# =============================================================================

@dataclass
class Receipt:
    """Base receipt model.
    
    All receipts record:
    - What happened (kind)
    - When it happened (timestamp)
    - Who/what initiated it (actor_id)
    - The result state
    - A reference to raw evidence
    """
    receipt_id: str
    kind: str  # e.g., "execution", "validation", "checkpoint"
    workspace_id: Optional[str] = None
    actor_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "unknown"  # "started", "success", "failed", "cancelled"
    summary: str = ""
    raw_ref: Optional[str] = None
    verified: bool = False  # True if cryptographically verified (future), False if local/unknown
    
    @property
    def label(self) -> str:
        """Human-readable label for the receipt kind."""
        kind_labels = {
            "execution": "Execution",
            "validation": "Validation", 
            "validator_run": "Validator Run",
            "checkpoint": "Checkpoint",
            "snapshot": "Snapshot",
        }
        return kind_labels.get(self.kind, self.kind)
    
    def to_projection(self) -> "ReceiptProjection":
        """Convert to projection format for UI display."""
        from rig.domain.projections import ReceiptProjection
        return ReceiptProjection(
            id=self.receipt_id,
            kind=self.kind,
            label=self.label,
            timestamp=self.timestamp,
            verified=self.verified,
            summary=self.summary,
            raw_reference=self.raw_ref
        )


@dataclass
class ExecutionReceipt(Receipt):
    """Receipt for process/command execution.
    
    Records:
    - Command executed (argv)
    - Working directory
    - Exit code
    - Timing information
    - Output references
    """
    kind: str = "execution"
    
    # Execution details
    argv: List[str] = field(default_factory=list)
    cwd: Optional[str] = None
    env_overlay: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: Optional[float] = None
    
    # Result
    exit_code: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Output references
    stdout_ref: Optional[str] = None
    stderr_ref: Optional[str] = None
    stdout_summary: str = ""
    stderr_summary: str = ""
    
    # Optional context
    purpose: str = ""
    stream_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.receipt_id:
            self.receipt_id = f"exec_{uuid.uuid4().hex[:12]}"
    
    @classmethod
    def from_subprocess_result(
        cls,
        argv: List[str],
        cwd: Optional[str],
        exit_code: int,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None,
        workspace_id: Optional[str] = None,
        purpose: str = "",
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        **kwargs: Any
    ) -> "ExecutionReceipt":
        """Create an ExecutionReceipt from a completed subprocess result."""
        stdout_ref = None
        stderr_ref = None
        stdout_summary = ""
        stderr_summary = ""
        
        if stdout:
            # Truncate for summary, keep full in ref
            stdout_summary = stdout[:500]
            if len(stdout) > 500:
                stdout_summary += "..."
        if stderr:
            stderr_summary = stderr[:500]
            if len(stderr) > 500:
                stderr_summary += "..."
        
        return cls(
            receipt_id=f"exec_{uuid.uuid4().hex[:12]}",
            kind="execution",
            argv=argv,
            cwd=cwd,
            exit_code=exit_code,
            started_at=started_at,
            completed_at=completed_at,
            stdout_ref=stdout_ref,
            stderr_ref=stderr_ref,
            stdout_summary=stdout_summary,
            stderr_summary=stderr_summary,
            workspace_id=workspace_id,
            purpose=purpose,
            status="success" if exit_code == 0 else "failed",
            summary=f"Command exited with code {exit_code}",
            **kwargs
        )


@dataclass  
class ValidatorReceipt(Receipt):
    """Receipt for validator execution."""
    kind: str = "validation"
    
    validator_id: str = ""
    validator_version: Optional[str] = None
    validated_path: Optional[str] = None
    exit_code: Optional[int] = None
    
    def __post_init__(self):
        if not self.receipt_id:
            self.receipt_id = f"val_{uuid.uuid4().hex[:12]}"


# =============================================================================
# ReceiptStore Protocol and Implementation
# =============================================================================

@runtime_checkable
class ReceiptStore(Protocol):
    """Protocol for receipt storage backs."""
    
    def append(self, receipt: Receipt) -> str:
        """Append a receipt to the store. Returns receipt_id."""
        ...
    
    def get(self, receipt_id: str) -> Optional[Receipt]:
        """Retrieve a receipt by ID."""
        ...
    
    def list(
        self,
        workspace_id: Optional[str] = None,
        kind: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Receipt]:
        """List receipts with optional filters."""
        ...
    
    def raw_ref(self, receipt_id: str) -> Optional[str]:
        """Get the raw reference (file path) for a receipt's evidence."""
        ...
    
    def verify(self, receipt_id: str) -> bool:
        """Verify a receipt. Returns True if verified, False if not (or unknown)."""
        ...


class InMemoryReceiptStore:
    """Process-local in-memory receipt store.
    
    Suitable for single-process execution. For multi-process scenarios,
    use FilesystemReceiptStore.
    """
    
    def __init__(self):
        self._receipts: Dict[str, Receipt] = {}
        self._index: Dict[str, List[str]] = {}  # workspace_id -> [receipt_ids]
        self._kind_index: Dict[str, List[str]] = {}  # kind -> [receipt_ids]
    
    def append(self, receipt: Receipt) -> str:
        """Append a receipt to the store."""
        receipt_id = receipt.receipt_id
        self._receipts[receipt_id] = receipt
        
        # Update workspace index
        if receipt.workspace_id:
            if receipt.workspace_id not in self._index:
                self._index[receipt.workspace_id] = []
            self._index[receipt.workspace_id].append(receipt_id)
        
        # Update kind index
        if receipt.kind not in self._kind_index:
            self._kind_index[receipt.kind] = []
        self._kind_index[receipt.kind].append(receipt_id)
        
        return receipt_id
    
    def get(self, receipt_id: str) -> Optional[Receipt]:
        """Retrieve a receipt by ID."""
        return self._receipts.get(receipt_id)
    
    def list(
        self,
        workspace_id: Optional[str] = None,
        kind: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Receipt]:
        """List receipts with optional filters."""
        receipt_ids = set()
        
        if workspace_id:
            receipt_ids.update(self._index.get(workspace_id, []))
        
        if kind:
            kind_ids = self._kind_index.get(kind, [])
            if receipt_ids:
                receipt_ids.intersection_update(kind_ids)
            else:
                receipt_ids.update(kind_ids)
        
        if not receipt_ids:
            receipt_ids = set(self._receipts.keys())
        
        # Sort by timestamp descending (most recent first)
        receipts = [self._receipts[rid] for rid in receipt_ids if rid in self._receipts]
        receipts.sort(key=lambda r: r.timestamp, reverse=True)
        
        if limit:
            receipts = receipts[:limit]
        
        return receipts[offset:]
    
    def raw_ref(self, receipt_id: str) -> Optional[str]:
        """Get the raw reference for a receipt's evidence."""
        receipt = self._receipts.get(receipt_id)
        if receipt:
            return receipt.raw_ref
        return None
    
    def verify(self, receipt_id: str) -> bool:
        """Verify a receipt. Currently always returns False (unknown)."""
        # Real verification would involve cryptographic signatures
        # For now, we return False to indicate verification is not implemented
        return False


class FilesystemReceiptStore:
    """Filesystem-backed receipt store.
    
    Stores receipts as JSON files in the Rig state directory structure.
    Each receipt gets its own file, with evidence stored alongside.
    """
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._receipt_dir = repo_root / ".build" / "rig" / "receipts"
        self._receipt_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def receipt_dir(self) -> Path:
        return self._receipt_dir
    
    def _receipt_path(self, receipt_id: str) -> Path:
        """Get the file path for a receipt."""
        # Use first 2 chars as subdirectory to avoid too many files in one dir
        subdir = receipt_id[:2]
        return self._receipt_dir / subdir / f"{receipt_id}.json"
    
    def _evidence_dir(self, receipt_id: str) -> Path:
        """Get the evidence directory for a receipt."""
        subdir = receipt_id[:2]
        return self._receipt_dir / subdir / receipt_id
    
    def append(self, receipt: Receipt) -> str:
        """Append a receipt to the store."""
        receipt_id = receipt.receipt_id
        if not receipt_id:
            receipt_id = f"receipt_{uuid.uuid4().hex[:12]}"
            receipt.receipt_id = receipt_id
        
        # Write receipt JSON
        receipt_path = self._receipt_path(receipt_id)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        
        receipt_dict = {
            "receipt_id": receipt.receipt_id,
            "kind": receipt.kind,
            "workspace_id": receipt.workspace_id,
            "actor_id": receipt.actor_id,
            "timestamp": receipt.timestamp,
            "status": receipt.status,
            "summary": receipt.summary,
            "raw_ref": receipt.raw_ref,
            "verified": receipt.verified,
        }
        
        # Add execution-specific fields
        if isinstance(receipt, ExecutionReceipt):
            receipt_dict.update({
                "argv": receipt.argv,
                "cwd": receipt.cwd,
                "env_overlay": receipt.env_overlay,
                "timeout_seconds": receipt.timeout_seconds,
                "exit_code": receipt.exit_code,
                "started_at": receipt.started_at,
                "completed_at": receipt.completed_at,
                "stdout_ref": receipt.stdout_ref,
                "stderr_ref": receipt.stderr_ref,
                "stdout_summary": receipt.stdout_summary,
                "stderr_summary": receipt.stderr_summary,
                "purpose": receipt.purpose,
                "stream_id": receipt.stream_id,
            })
        elif isinstance(receipt, ValidatorReceipt):
            receipt_dict.update({
                "validator_id": receipt.validator_id,
                "validator_version": receipt.validator_version,
                "validated_path": receipt.validated_path,
                "exit_code": receipt.exit_code,
            })
        
        receipt_path.write_text(json.dumps(receipt_dict, indent=2, default=str))
        
        # Store evidence if provided
        if receipt.raw_ref:
            evidence_dir = self._evidence_dir(receipt_id)
            evidence_dir.mkdir(parents=True, exist_ok=True)
            # raw_ref is typically a relative path or identifier
            # For filesystem store, we interpret it as a filename
        
        return receipt_id
    
    def get(self, receipt_id: str) -> Optional[Receipt]:
        """Retrieve a receipt by ID."""
        receipt_path = self._receipt_path(receipt_id)
        if not receipt_path.exists():
            return None
        
        data = json.loads(receipt_path.read_text())
        kind = data.get("kind", "")
        
        if kind == "execution":
            return ExecutionReceipt(**data)
        elif kind == "validation":
            return ValidatorReceipt(**data)
        else:
            return Receipt(**data)
    
    def list(
        self,
        workspace_id: Optional[str] = None,
        kind: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Receipt]:
        """List receipts with optional filters."""
        # Walk the receipt directory structure
        receipts = []
        
        for subdir in self._receipt_dir.iterdir():
            if subdir.is_dir():
                for receipt_file in subdir.glob("*.json"):
                    try:
                        data = json.loads(receipt_file.read_text())
                        receipt = self._data_to_receipt(data)
                        
                        # Apply filters
                        if workspace_id and receipt.workspace_id != workspace_id:
                            continue
                        if kind and receipt.kind != kind:
                            continue
                        
                        receipts.append(receipt)
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        # Sort by timestamp descending
        receipts.sort(key=lambda r: r.timestamp, reverse=True)
        
        if limit:
            receipts = receipts[:limit]
        
        return receipts[offset:]
    
    def _data_to_receipt(self, data: Dict[str, Any]) -> Receipt:
        """Convert dictionary data to appropriate Receipt subclass."""
        kind = data.get("kind", "")
        if kind == "execution":
            return ExecutionReceipt(**data)
        elif kind in ("validation", "validator_run"):
            return ValidatorReceipt(**data)
        return Receipt(**data)
    
    def raw_ref(self, receipt_id: str) -> Optional[str]:
        """Get the raw reference for a receipt's evidence."""
        receipt = self.get(receipt_id)
        if receipt:
            return receipt.raw_ref
        return None
    
    def verify(self, receipt_id: str) -> bool:
        """Verify a receipt. Currently always returns False (unknown)."""
        # For filesystem store, we can't do cryptographic verification
        # without additional infrastructure
        return False


# =============================================================================
# Factory and global access
# =============================================================================

_default_store: Optional[FilesystemReceiptStore] = None


def get_receipt_store(repo_root: Path) -> ReceiptStore:
    """Get or create the default receipt store for a repository."""
    global _default_store
    if _default_store is None or _default_store.repo_root != repo_root:
        _default_store = FilesystemReceiptStore(repo_root)
    return _default_store


def create_in_memory_store() -> InMemoryReceiptStore:
    """Create an in-memory receipt store for testing."""
    return InMemoryReceiptStore()
