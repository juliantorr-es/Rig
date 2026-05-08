"""Canonical Receipt Envelope Domain Module.

This module provides the unified ReceiptEnvelope domain model for Receipt Formalization Phase 2.

Receipts are evidence, not decoration.
Receipts must describe what happened, who/what caused it, what authority allowed it,
what subject changed, what inputs were used, what outputs were produced, and whether
the receipt is authoritative or advisory.

Core doctrine:
- Rig remains the authority
- All models are pure deterministic dataclasses
- All models are JSON-serializable
- No filesystem access inside basic constructors
- No frontend authority logic
- No external system becomes authoritative
- Public intake/funding receipts remain advisory_only
- Receipt IDs must be deterministic where possible

file: src/rig/domain/receipt_envelope.py
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.workspace_audit import AuditActor as WorkspaceAuditActor


# ---------------------------------------------------------------------------
# Placeholder Constants
# ---------------------------------------------------------------------------

# Required placeholders for missing/explicit null states
PLACEHOLDER_UNKNOWN = "unknown"
PLACEHOLDER_UNAVAILABLE = "unavailable"
PLACEHOLDER_NOT_CREATED = "not_created"
PLACEHOLDER_NOT_RUN = "not_run"
PLACEHOLDER_NOT_PROOF = "not_proof"
PLACEHOLDER_ADVISORY_ONLY = "advisory_only"
PLACEHOLDER_NOT_AUTHORITATIVE = "not_authoritative"
PLACEHOLDER_NO_RECEIPT = "no_receipt"

# Validation-specific placeholders
PLACEHOLDER_NO_VALIDATION = "no_validation"
PLACEHOLDER_NO_GATE_DECISION = "no_gateDecision"
PLACEHOLDER_VALIDATION_FAILED = "validation_failed"
PLACEHOLDER_VALIDATION_INCOMPLETE = "validation_incomplete"

# Review-specific placeholders
PLACEHOLDER_NO_REVIEW_BUNDLE = "no_review_bundle"
PLACEHOLDER_REVIEW_INCOMPLETE = "review_incomplete"

# Apply gate placeholders
PLACEHOLDER_NO_APPLY_GATE = "no_apply_gate"
PLACEHOLDER_APPLY_BLOCKED = "apply_blocked"

# All required placeholders as a tuple for validation
REQUIRED_PLACEHOLDERS = (
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_UNAVAILABLE,
    PLACEHOLDER_NOT_CREATED,
    PLACEHOLDER_NOT_RUN,
    PLACEHOLDER_NOT_PROOF,
    PLACEHOLDER_ADVISORY_ONLY,
    PLACEHOLDER_NOT_AUTHORITATIVE,
    PLACEHOLDER_NO_RECEIPT,
    PLACEHOLDER_NO_VALIDATION,
    PLACEHOLDER_NO_GATE_DECISION,
    PLACEHOLDER_VALIDATION_FAILED,
    PLACEHOLDER_VALIDATION_INCOMPLETE,
    PLACEHOLDER_NO_REVIEW_BUNDLE,
    PLACEHOLDER_REVIEW_INCOMPLETE,
    PLACEHOLDER_NO_APPLY_GATE,
    PLACEHOLDER_APPLY_BLOCKED,
)


# ---------------------------------------------------------------------------
# Helper for enum/value serialization
# ---------------------------------------------------------------------------

def _value_to_json(obj: Any) -> Any:
    """Convert objects to JSON-serializable values."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return {k: _value_to_json(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, (list, tuple)):
        return [_value_to_json(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _value_to_json(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Canonical Receipt Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReceiptActor:
    """Represents the actor/authority that performed or initiated an action.

    Deterministic, serializable, side-effect free.
    """

    actor_id: str
    actor_kind: str  # e.g., "cli", "connector", "domain", "system"
    display_name: Optional[str] = None
    is_human: bool = False
    is_authoritative: bool = True

    @classmethod
    def system(cls) -> "ReceiptActor":
        """Create a system actor placeholder."""
        return cls(
            actor_id="system",
            actor_kind="system",
            display_name="System",
            is_human=False,
            is_authoritative=True,
        )

    @classmethod
    def cli(cls) -> "ReceiptActor":
        """Create a CLI actor placeholder."""
        return cls(
            actor_id="cli",
            actor_kind="cli",
            display_name="CLI",
            is_human=True,
            is_authoritative=True,
        )

    @classmethod
    def connector(cls, connector_name: str) -> "ReceiptActor":
        """Create a connector actor placeholder (NOT authoritative)."""
        return cls(
            actor_id=f"connector_{connector_name}",
            actor_kind="connector",
            display_name=connector_name,
            is_human=False,
            is_authoritative=False,  # Connectors are NOT authoritative
        )

    @classmethod
    def unknown(cls) -> "ReceiptActor":
        """Create an unknown actor placeholder."""
        return cls(
            actor_id=PLACEHOLDER_UNKNOWN,
            actor_kind=PLACEHOLDER_UNKNOWN,
            display_name=PLACEHOLDER_UNKNOWN,
            is_human=False,
            is_authoritative=False,
        )

    @classmethod
    def from_audit_actor(cls, actor: "WorkspaceAuditActor") -> "ReceiptActor":
        """Convert from workspace_audit.AuditActor to ReceiptActor."""
        return cls(
            actor_id=actor.actor_id,
            actor_kind=actor.actor_kind,
            display_name=actor.display_name,
            is_human=actor.is_human,
            is_authoritative=actor.is_authoritative,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReceiptSubject:
    """Represents the subject being acted upon.

    Deterministic, serializable, side-effect free.
    """

    subject_id: str
    subject_kind: str  # e.g., "workspace", "validation", "review", "apply", "sync"
    display_name: Optional[str] = None
    workspace_id: Optional[str] = None
    authoritative: bool = True
    advisory_only: bool = False

    @classmethod
    def workspace(cls, workspace_id: str) -> "ReceiptSubject":
        """Create a workspace subject."""
        return cls(
            subject_id=workspace_id,
            subject_kind="workspace",
            display_name=workspace_id,
            workspace_id=workspace_id,
            authoritative=True,
            advisory_only=False,
        )

    @classmethod
    def validation(cls, validation_id: str, workspace_id: Optional[str] = None) -> "ReceiptSubject":
        """Create a validation subject."""
        return cls(
            subject_id=validation_id,
            subject_kind="validation",
            display_name=validation_id,
            workspace_id=workspace_id,
            authoritative=True,
            advisory_only=False,
        )

    @classmethod
    def review_bundle(cls, review_id: str, workspace_id: Optional[str] = None) -> "ReceiptSubject":
        """Create a review bundle subject."""
        return cls(
            subject_id=review_id,
            subject_kind="review_bundle",
            display_name=review_id,
            workspace_id=workspace_id,
            authoritative=True,
            advisory_only=False,
        )

    @classmethod
    def apply(cls, apply_id: str, workspace_id: Optional[str] = None) -> "ReceiptSubject":
        """Create an apply subject."""
        return cls(
            subject_id=apply_id,
            subject_kind="apply",
            display_name=apply_id,
            workspace_id=workspace_id,
            authoritative=True,
            advisory_only=False,
        )

    @classmethod
    def sync(cls, sync_id: str, connector: str) -> "ReceiptSubject":
        """Create a sync subject (advisory only)."""
        return cls(
            subject_id=sync_id,
            subject_kind="sync",
            display_name=f"{connector} sync",
            workspace_id=None,
            authoritative=False,
            advisory_only=True,
        )

    @classmethod
    def unknown(cls) -> "ReceiptSubject":
        """Create an unknown subject placeholder."""
        return cls(
            subject_id=PLACEHOLDER_UNKNOWN,
            subject_kind=PLACEHOLDER_UNKNOWN,
            display_name=PLACEHOLDER_UNKNOWN,
            workspace_id=None,
            authoritative=False,
            advisory_only=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReceiptInput:
    """Represents an input to the receipted operation.

    Deterministic, serializable, side-effect free.
    """

    input_id: str
    input_kind: str  # e.g., "workspace_record", "worktree_path", "config", "command"
    reference: str  # path or URI
    hash: Optional[str] = None
    summary: str = ""

    @classmethod
    def of(
        cls,
        input_id: str,
        input_kind: str,
        reference: str,
        hash: Optional[str] = None,
        summary: str = "",
    ) -> "ReceiptInput":
        """Create a ReceiptInput."""
        return cls(
            input_id=input_id,
            input_kind=input_kind,
            reference=reference,
            hash=hash,
            summary=summary,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReceiptOutput:
    """Represents an output from the receipted operation.

    Deterministic, serializable, side-effect free.
    """

    output_id: str
    output_kind: str  # e.g., "workspace_record", "receipt", "validation_result"
    reference: str  # path or URI
    hash: Optional[str] = None
    status: str = "unknown"  # "success", "failed", "pending"

    @classmethod
    def of(
        cls,
        output_id: str,
        output_kind: str,
        reference: str,
        hash: Optional[str] = None,
        status: str = "unknown",
    ) -> "ReceiptOutput":
        """Create a ReceiptOutput."""
        return cls(
            output_id=output_id,
            output_kind=output_kind,
            reference=reference,
            hash=hash,
            status=status,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReceiptDecision:
    """Represents the decision/authority classification for the receipt.

    Deterministic, serializable, side-effect free.
    """

    decision_id: str
    decision_kind: str  # "allowed", "blocked", "pending", "not_applicable"
    reason: str
    authoritative: bool = True

    @classmethod
    def allowed(cls, decision_id: str, reason: str = "Rig authority") -> "ReceiptDecision":
        """Create an allowed decision."""
        return cls(
            decision_id=decision_id,
            decision_kind="allowed",
            reason=reason,
            authoritative=True,
        )

    @classmethod
    def blocked(cls, decision_id: str, reason: str = "Blocked by policy") -> "ReceiptDecision":
        """Create a blocked decision."""
        return cls(
            decision_id=decision_id,
            decision_kind="blocked",
            reason=reason,
            authoritative=True,
        )

    @classmethod
    def advisory_only(cls, decision_id: str, reason: str = PLACEHOLDER_ADVISORY_ONLY) -> "ReceiptDecision":
        """Create an advisory-only decision."""
        return cls(
            decision_id=decision_id,
            decision_kind="advisory_only",
            reason=reason,
            authoritative=False,
        )

    @classmethod
    def not_applicable(cls, decision_id: str, reason: str = "Not applicable") -> "ReceiptDecision":
        """Create a not-applicable decision."""
        return cls(
            decision_id=decision_id,
            decision_kind="not_applicable",
            reason=reason,
            authoritative=False,
        )

    @classmethod
    def unknown(cls, decision_id: str = PLACEHOLDER_UNKNOWN) -> "ReceiptDecision":
        """Create an unknown decision placeholder."""
        return cls(
            decision_id=decision_id,
            decision_kind=PLACEHOLDER_UNKNOWN,
            reason=PLACEHOLDER_UNKNOWN,
            authoritative=False,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReceiptEvidence:
    """Represents evidence/artifacts associated with the receipt.

    Deterministic, serializable, side-effect free.
    """

    evidence_id: str
    evidence_kind: str  # e.g., "file", "log", "diff", "snapshot", "screenshot"
    reference: str  # path or URI
    hash: Optional[str] = None
    mime_type: Optional[str] = None

    @classmethod
    def of(
        cls,
        evidence_id: str,
        evidence_kind: str,
        reference: str,
        hash: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> "ReceiptEvidence":
        """Create ReceiptEvidence."""
        return cls(
            evidence_id=evidence_id,
            evidence_kind=evidence_kind,
            reference=reference,
            hash=hash,
            mime_type=mime_type,
        )

    @classmethod
    def file(
        cls,
        evidence_id: str,
        reference: str,
        hash: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> "ReceiptEvidence":
        """Create file evidence."""
        return cls(
            evidence_id=evidence_id,
            evidence_kind="file",
            reference=reference,
            hash=hash,
            mime_type=mime_type,
        )

    @classmethod
    def log(
        cls,
        evidence_id: str,
        reference: str,
        hash: Optional[str] = None,
    ) -> "ReceiptEvidence":
        """Create log evidence."""
        return cls(
            evidence_id=evidence_id,
            evidence_kind="log",
            reference=reference,
            hash=hash,
            mime_type="text/plain",
        )

    @classmethod
    def diff(
        cls,
        evidence_id: str,
        reference: str,
        hash: Optional[str] = None,
    ) -> "ReceiptEvidence":
        """Create diff evidence."""
        return cls(
            evidence_id=evidence_id,
            evidence_kind="diff",
            reference=reference,
            hash=hash,
            mime_type="text/x-patch",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ==--------------------------------------------------------------------------
# ReceiptEnvelope - The Canonical Receipt Container
# ==--------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReceiptEnvelope:
    """Canonical Receipt Envelope - unified container for all receipts.

    Receipts are evidence, not decoration.
    Receipts must describe what happened, who/what caused it, what authority allowed it,
    what subject changed, what inputs were used, what outputs were produced, and whether
    the receipt is authoritative or advisory.

    Deterministic, serializable, side-effect free.
    Pure data model - no file writes, no database, no frontend state.
    
    Attributes:
        schema_version: The receipt envelope schema version (e.g., "rig.receipt_envelope.v1")
        receipt_id: Unique deterministic identifier for this receipt
        receipt_type: The type of receipt (e.g., "workspace_create", "workspace_transition", "apply", "validation")
        authority_level: "authoritative" or "advisory_only"
        advisory_only: True if this receipt is advisory only
        created_at: ISO 8601 timestamp when the receipt was created
        actor: Who/what caused the receipted operation
        subject: What was acted upon
        decision: The authority decision classification
        inputs: Inputs used in the receipted operation
        outputs: Outputs produced by the receipted operation
        evidence: Evidence/artifacts associated with the receipt
        related_receipt_ids: IDs of receipts this receipt is related to
        related_audit_event_ids: IDs of audit events this receipt is linked from/to
        summary: Human-readable summary
    """

    schema_version: str
    receipt_id: str
    receipt_type: str
    authority_level: str
    advisory_only: bool
    created_at: str
    actor: ReceiptActor
    subject: ReceiptSubject
    decision: ReceiptDecision
    inputs: Tuple[ReceiptInput, ...]
    outputs: Tuple[ReceiptOutput, ...]
    evidence: Tuple[ReceiptEvidence, ...]
    related_receipt_ids: Tuple[str, ...]
    related_audit_event_ids: Tuple[str, ...]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary.
        
        Produces stable key ordering for deterministic serialization.
        """
        result = {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "receipt_type": self.receipt_type,
            "authority_level": self.authority_level,
            "advisory_only": self.advisory_only,
            "created_at": self.created_at,
            "actor": self.actor.to_dict(),
            "subject": self.subject.to_dict(),
            "decision": self.decision.to_dict(),
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "evidence": [e.to_dict() for e in self.evidence],
            "related_receipt_ids": list(self.related_receipt_ids),
            "related_audit_event_ids": list(self.related_audit_event_ids),
            "summary": self.summary,
        }
        return result

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Convert to JSON string with sorted keys for deterministic output."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReceiptEnvelope":
        """Reconstruct ReceiptEnvelope from dictionary."""
        return cls(
            schema_version=data.get("schema_version", "rig.receipt_envelope.v1"),
            receipt_id=data["receipt_id"],
            receipt_type=data["receipt_type"],
            authority_level=data["authority_level"],
            advisory_only=data.get("advisory_only", False),
            created_at=data["created_at"],
            actor=ReceiptActor(**data["actor"]),
            subject=ReceiptSubject(**data["subject"]),
            decision=ReceiptDecision(**data["decision"]),
            inputs=tuple(ReceiptInput(**i) for i in data.get("inputs", [])),
            outputs=tuple(ReceiptOutput(**o) for o in data.get("outputs", [])),
            evidence=tuple(ReceiptEvidence(**e) for e in data.get("evidence", [])),
            related_receipt_ids=tuple(data.get("related_receipt_ids", [])),
            related_audit_event_ids=tuple(data.get("related_audit_event_ids", [])),
            summary=data.get("summary", ""),
        )


@dataclass(frozen=True, slots=True)
class ReceiptIndexEntry:
    """Index entry for receipt catalog.

    Deterministic, serializable, side-effect free.
    """

    entry_id: str
    receipt_id: str
    receipt_type: str
    workspace_id: Optional[str]
    receipt_path: str  # string path for JSON serialization
    created_at: str
    authority_level: str
    advisory_only: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReceiptWriteResult:
    """Result of writing a receipt to storage.

    Deterministic, serializable, side-effect free.
    """

    receipt_id: str
    receipt_path: str  # string path for JSON serialization
    status: str  # "success", "failed"
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Convert Path to string if needed
        if isinstance(d.get("receipt_path"), Path):
            d["receipt_path"] = str(d["receipt_path"])
        return d


# ==--------------------------------------------------------------------------
# Helper Functions
# ==--------------------------------------------------------------------------


def utc_now() -> str:
    """Get current UTC timestamp in ISO 8601 format without microseconds."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    """Compute SHA256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_receipt_id(
    receipt_type: str,
    workspace_id: Optional[str] = None,
    additional_parts: Optional[List[str]] = None,
) -> str:
    """Build a deterministic receipt ID.
    
    Examples:
        workspace_create: ws_create_{workspace_id}
        workspace_transition: ws_trans_{workspace_id}_{old}_to_{new}
        apply: ws_apply_{workspace_id}
        validation: ws_val_{workspace_id}
        sync: sync_{connector}_{hash}
    
    Args:
        receipt_type: The type prefix (e.g., "ws_create", "ws_trans", "ws_apply")
        workspace_id: The workspace ID if applicable
        additional_parts: Additional parts to include in the ID
        
    Returns:
        A deterministic receipt ID string
    """
    parts = [receipt_type]
    if workspace_id:
        parts.append(workspace_id)
    if additional_parts:
        parts.extend(additional_parts)
    return "_".join(parts)


def build_receipt_envelope(
    receipt_type: str,
    receipt_id: str,
    workspace_id: Optional[str] = None,
    actor: Optional[ReceiptActor] = None,
    subject: Optional[ReceiptSubject] = None,
    decision: Optional[ReceiptDecision] = None,
    inputs: Optional[List[ReceiptInput]] = None,
    outputs: Optional[List[ReceiptOutput]] = None,
    evidence: Optional[List[ReceiptEvidence]] = None,
    related_receipt_ids: Optional[List[str]] = None,
    related_audit_event_ids: Optional[List[str]] = None,
    summary: str = "",
    authoritative: bool = True,
    created_at: Optional[str] = None,
) -> ReceiptEnvelope:
    """Factory function to build a ReceiptEnvelope.
    
    This is a helper to create ReceiptEnvelopes with sensible defaults.
    
    Args:
        receipt_type: The type of receipt
        receipt_id: The unique receipt ID
        workspace_id: The workspace ID if applicable
        actor: The actor performing the action
        subject: The subject being acted upon
        decision: The decision/authority classification
        inputs: Inputs to the operation
        outputs: Outputs from the operation
        evidence: Evidence/artifacts
        related_receipt_ids: Related receipt IDs
        related_audit_event_ids: Related audit event IDs
        summary: Human-readable summary
        authoritative: Whether this receipt is authoritative
        created_at: Timestamp (defaults to now if not provided)
        
    Returns:
        A fully constructed ReceiptEnvelope
    """
    authority_level = "authoritative" if authoritative else "advisory_only"
    advisory_only = not authoritative
    
    if created_at is None:
        created_at = utc_now()
    
    if actor is None:
        actor = ReceiptActor.unknown()
    
    if subject is None and workspace_id:
        subject = ReceiptSubject.workspace(workspace_id)
    elif subject is None:
        subject = ReceiptSubject.unknown()
    
    if decision is None:
        decision = ReceiptDecision.unknown()
    
    return ReceiptEnvelope(
        schema_version="rig.receipt_envelope.v1",
        receipt_id=receipt_id,
        receipt_type=receipt_type,
        authority_level=authority_level,
        advisory_only=advisory_only,
        created_at=created_at,
        actor=actor,
        subject=subject,
        decision=decision,
        inputs=tuple(inputs or []),
        outputs=tuple(outputs or []),
        evidence=tuple(evidence or []),
        related_receipt_ids=tuple(related_receipt_ids or []),
        related_audit_event_ids=tuple(related_audit_event_ids or []),
        summary=summary,
    )


def receipt_to_dict(envelope: ReceiptEnvelope) -> dict[str, Any]:
    """Convert a ReceiptEnvelope to a JSON-serializable dict."""
    return envelope.to_dict()


def receipt_from_dict(data: dict[str, Any]) -> ReceiptEnvelope:
    """Reconstruct a ReceiptEnvelope from a dict."""
    return ReceiptEnvelope.from_dict(data)


def write_receipt(
    repo_root: Path,
    envelope: ReceiptEnvelope,
    receipt_dir: Optional[Path] = None,
) -> ReceiptWriteResult:
    """Write a receipt envelope to the filesystem.
    
    Args:
        repo_root: The repository root path
        envelope: The ReceiptEnvelope to write
        receipt_dir: Optional custom receipt directory (defaults to .build/rig/receipts)
        
    Returns:
        ReceiptWriteResult with the receipt path and status
    """
    if receipt_dir is None:
        receipt_dir = repo_root / ".build" / "rig" / "receipts"
    
    receipt_path = receipt_dir / f"{envelope.receipt_id}.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        receipt_path.write_text(envelope.to_json(), encoding="utf-8")
        return ReceiptWriteResult(
            receipt_id=envelope.receipt_id,
            receipt_path=str(receipt_path),
            status="success",
            error=None,
        )
    except Exception as e:
        return ReceiptWriteResult(
            receipt_id=envelope.receipt_id,
            receipt_path=str(receipt_path),
            status="failed",
            error=str(e),
        )


def read_receipt(receipt_path: Path) -> Optional[ReceiptEnvelope]:
    """Read a receipt envelope from a JSON file.
    
    Args:
        receipt_path: Path to the receipt JSON file
        
    Returns:
        ReceiptEnvelope if successful, None otherwise
    """
    if not receipt_path.exists():
        return None
    
    try:
        data = json.loads(receipt_path.read_text(encoding="utf-8"))
        return receipt_from_dict(data)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def index_receipts(
    repo_root: Path,
    receipt_dir: Optional[Path] = None,
) -> Tuple[ReceiptIndexEntry, ...]:
    """Build an index of all receipts in the receipt directory.
    
    Args:
        repo_root: The repository root path
        receipt_dir: Optional custom receipt directory
        
    Returns:
        Tuple of ReceiptIndexEntry objects for all found receipts
    """
    if receipt_dir is None:
        receipt_dir = repo_root / ".build" / "rig" / "receipts"
    
    if not receipt_dir.exists():
        return ()
    
    entries: List[ReceiptIndexEntry] = []
    
    for receipt_file in receipt_dir.glob("*.json"):
        try:
            envelope = read_receipt(receipt_file)
            if envelope:
                entry = ReceiptIndexEntry(
                    entry_id=f"index_{envelope.receipt_id}",
                    receipt_id=envelope.receipt_id,
                    receipt_type=envelope.receipt_type,
                    workspace_id=envelope.subject.workspace_id if hasattr(envelope.subject, 'workspace_id') else None,
                    receipt_path=str(receipt_file),
                    created_at=envelope.created_at,
                    authority_level=envelope.authority_level,
                    advisory_only=envelope.advisory_only,
                )
                entries.append(entry)
        except Exception:
            continue
    
    # Also check subdirectories (for sharded storage)
    for subdir in receipt_dir.iterdir():
        if subdir.is_dir():
            for receipt_file in subdir.glob("*.json"):
                try:
                    envelope = read_receipt(receipt_file)
                    if envelope:
                        entry = ReceiptIndexEntry(
                            entry_id=f"index_{envelope.receipt_id}",
                            receipt_id=envelope.receipt_id,
                            receipt_type=envelope.receipt_type,
                            workspace_id=envelope.subject.workspace_id if hasattr(envelope.subject, 'workspace_id') else None,
                            receipt_path=str(receipt_file),
                            created_at=envelope.created_at,
                            authority_level=envelope.authority_level,
                            advisory_only=envelope.advisory_only,
                        )
                        entries.append(entry)
                except Exception:
                    continue
    
    # Sort by receipt_id for deterministic ordering
    entries.sort(key=lambda e: e.receipt_id)
    return tuple(entries)


def resolve_receipt_authority(
    receipt_type: str,
    actor_kind: str,
    subject_kind: str,
) -> dict[str, Any]:
    """Resolve the authority classification for a receipt.
    
    Args:
        receipt_type: The receipt type
        actor_kind: The actor kind
        subject_kind: The subject kind
        
    Returns:
        Dict with authoritative, advisory_only, and reason
    """
    # Public intake/funding are ALWAYS advisory only
    if receipt_type in ("public_sync", "public_intake_packet", "funding_pledge"):
        return {
            "authoritative": False,
            "advisory_only": True,
            "reason": "Public intake and funding data is advisory_only by doctrine",
        }
    
    # Connector actions are NOT authoritative
    if actor_kind == "connector":
        return {
            "authoritative": False,
            "advisory_only": True,
            "reason": "Connector actions are not authoritative - Rig remains the authority",
        }
    
    # Workspace and validation receipts from Rig domain are authoritative
    if actor_kind in ("cli", "domain", "system") and receipt_type in (
        "workspace_create", "workspace_transition", "workspace_apply",
        "validation", "validator_run", "review_bundle", "execution",
    ):
        return {
            "authoritative": True,
            "advisory_only": False,
            "reason": "Workspace and validation mutations by Rig are authoritative",
        }
    
    # Default: assume authoritative unless proven otherwise
    return {
        "authoritative": True,
        "advisory_only": False,
        "reason": PLACEHOLDER_UNKNOWN,
    }


def resolve_receipt_completeness(
    envelope: ReceiptEnvelope,
) -> dict[str, Any]:
    """Resolve the completeness of a receipt envelope.
    
    Checks for required fields and placeholder values.
    
    Args:
        envelope: The ReceiptEnvelope to check
        
    Returns:
        Dict with complete, missing_fields, placeholder_fields, completeness_score
    """
    required_fields = {
        "receipt_id": True,
        "receipt_type": True,
        "authority_level": True,
        "created_at": True,
        "actor": True,
        "subject": True,
        "decision": True,
    }
    
    missing = []
    for field_name, is_required in required_fields.items():
        value = getattr(envelope, field_name, None)
        if is_required and (value is None or value == ""):
            missing.append(field_name)
    
    # Check for placeholder values
    placeholder_fields = {
        "authority_level": PLACEHOLDER_UNKNOWN,
        "created_at": PLACEHOLDER_NOT_CREATED,
        "summary": PLACEHOLDER_UNKNOWN,
    }
    
    placeholders_used = []
    for field_name, placeholder in placeholder_fields.items():
        value = getattr(envelope, field_name, None)
        if value == placeholder:
            placeholders_used.append(field_name)
    
    # Check actor/decision/subject for placeholders
    if envelope.actor.actor_id == PLACEHOLDER_UNKNOWN:
        placeholders_used.append("actor")
    if envelope.subject.subject_id == PLACEHOLDER_UNKNOWN:
        placeholders_used.append("subject")
    if envelope.decision.decision_id == PLACEHOLDER_UNKNOWN:
        placeholders_used.append("decision")
    
    is_complete = len(missing) == 0 and len(placeholders_used) == 0
    
    return {
        "complete": is_complete,
        "missing_fields": tuple(missing),
        "placeholder_fields": tuple(placeholders_used),
        "completeness_score": 1.0 if is_complete else 0.5 if len(missing) == 0 else 0.0,
    }


def resolve_receipt_projection_summary(
    envelopes: List[ReceiptEnvelope],
) -> dict[str, Any]:
    """Resolve projection summary from a list of receipt envelopes.
    
    Args:
        envelopes: List of ReceiptEnvelope objects
        
    Returns:
        Dict with receipt counts, status summary, and next action
    """
    total = len(envelopes)
    authoritative = [e for e in envelopes if not e.advisory_only]
    advisory = [e for e in envelopes if e.advisory_only]
    
    # Count by type
    type_counts: Dict[str, Dict[str, int]] = {}
    for env in envelopes:
        kind = env.receipt_type
        if kind not in type_counts:
            type_counts[kind] = {"authoritative": 0, "advisory": 0}
        if env.advisory_only:
            type_counts[kind]["advisory"] += 1
        else:
            type_counts[kind]["authoritative"] += 1
    
    # Find last authoritative receipt
    last_auth_id = None
    last_auth_summary = PLACEHOLDER_UNKNOWN
    for env in sorted(envelopes, key=lambda e: e.created_at, reverse=True):
        if not env.advisory_only:
            last_auth_id = env.receipt_id
            last_auth_summary = env.summary
            break
    
    # Check for validation receipts
    validation_envelopes = [e for e in envelopes if e.receipt_type in ("validation", "validator_run")]
    validation_status = resolve_validation_receipt_status(validation_envelopes)
    
    # Check for review receipts
    review_envelopes = [e for e in envelopes if e.receipt_type in ("review_bundle", "review")]
    review_status = resolve_review_receipt_status(review_envelopes)
    
    # Check for apply gate receipts
    apply_envelopes = [e for e in envelopes if e.receipt_type in ("apply", "workspace_apply", "gate_decision")]
    apply_gate_status = resolve_apply_gate_receipt_status(apply_envelopes)
    
    # Check for gate decision receipts
    gate_decision_envelopes = [e for e in envelopes if e.receipt_type == "gate_decision"]
    gate_decision_status = "passed" if gate_decision_envelopes else PLACEHOLDER_NOT_RUN
    for env in sorted(gate_decision_envelopes, key=lambda e: e.created_at, reverse=True):
        for output in env.outputs:
            if output.status == "allowed":
                gate_decision_status = "allowed"
                break
            elif output.status == "blocked":
                gate_decision_status = "blocked"
                break
    
    # Compute missing receipt count based on expected receipt types
    expected_types = {"workspace_create", "workspace_transition", "validation", "review_bundle", "workspace_apply"}
    present_types = {env.receipt_type for env in envelopes}
    missing_types = expected_types - present_types
    missing_receipt_count = len(missing_types)
    
    # Determine next missing receipt action
    if missing_receipt_count > 0:
        missing_list = sorted(missing_types)
        next_missing_receipt_action = f"Create missing receipts for: {', '.join(missing_list)}"
    else:
        next_missing_receipt_action = PLACEHOLDER_NO_RECEIPT
    
    # Determine auditability status
    has_authoritative = len(authoritative) > 0
    has_validation = len(validation_envelopes) > 0
    has_review = len(review_envelopes) > 0
    has_apply = len(apply_envelopes) > 0
    
    if has_authoritative and has_validation and has_review:
        auditability_status = "fully_auditable"
    elif has_authoritative and has_validation:
        auditability_status = "partially_auditable"
    elif has_authoritative:
        auditability_status = "minimally_auditable"
    else:
        auditability_status = "not_auditable"
    
    authoritative_evidence_available = has_authoritative and has_validation
    
    return {
        # Count fields
        "receipt_count": total,
        "authoritative_receipt_count": len(authoritative),
        "advisory_receipt_count": len(advisory),
        "missing_receipt_count": missing_receipt_count,
        # Summary fields
        "last_receipt_id": last_auth_id or PLACEHOLDER_NO_RECEIPT,
        "last_receipt_summary": last_auth_summary,
        # Type distribution
        "type_counts": type_counts,
        # Validation status
        "validation_receipt_status": validation_status,
        "review_receipt_status": review_status,
        "apply_gate_receipt_status": apply_gate_status,
        # Gate decision status
        "gate_decision_status": gate_decision_status,
        # Next action
        "next_missing_receipt_action": next_missing_receipt_action,
        # Auditability
        "auditability_status": auditability_status,
        "authoritative_evidence_available": authoritative_evidence_available,
    }


def resolve_validation_receipt_status(
    envelopes: List[ReceiptEnvelope],
) -> str:
    """Resolve validation status from validation receipts."""
    if not envelopes:
        return PLACEHOLDER_NOT_RUN
    
    # Check the most recent validation
    for env in sorted(envelopes, key=lambda e: e.created_at, reverse=True):
        # Check outputs for status
        for output in env.outputs:
            if output.status in ("success", "passed"):
                return "passed"
            if output.status in ("failed", "error"):
                return "failed"
    
    return "unknown"


def resolve_review_receipt_status(
    envelopes: List[ReceiptEnvelope],
) -> str:
    """Resolve review status from review receipts."""
    if not envelopes:
        return PLACEHOLDER_NOT_RUN
    
    # Check the most recent review
    for env in sorted(envelopes, key=lambda e: e.created_at, reverse=True):
        for output in env.outputs:
            if output.status == "success":
                return "review_ready"
            if output.status in ("failed", "error", "blocked"):
                return "blocked"
    
    return "pending"


def resolve_apply_gate_receipt_status(
    envelopes: List[ReceiptEnvelope],
) -> str:
    """Resolve apply gate status from apply receipts."""
    if not envelopes:
        return PLACEHOLDER_NOT_RUN
    
    # Check the most recent apply
    for env in sorted(envelopes, key=lambda e: e.created_at, reverse=True):
        for output in env.outputs:
            if output.status == "success":
                return "applied"
            if output.status in ("failed", "error", "blocked"):
                return "blocked"
    
    return "pending"


def convert_legacy_to_envelope(
    legacy_data: dict[str, Any],
    receipt_type: str,
    workspace_id: Optional[str] = None,
) -> ReceiptEnvelope:
    """Convert a legacy receipt dict to a canonical ReceiptEnvelope.
    
    This provides backward compatibility for existing receipt files.
    
    Args:
        legacy_data: The legacy receipt dictionary
        receipt_type: The canonical receipt type
        workspace_id: The workspace ID if not in legacy data
        
    Returns:
        A ReceiptEnvelope with data from the legacy receipt
    """
    receipt_id = legacy_data.get("receipt_id", legacy_data.get("id", ""))
    
    # Build actor from legacy data
    if "actor_id" in legacy_data:
        actor = ReceiptActor(
            actor_id=legacy_data["actor_id"],
            actor_kind="domain",
            display_name=legacy_data.get("actor_id"),
            is_human=False,
            is_authoritative=legacy_data.get("authoritative", True),
        )
    else:
        actor = ReceiptActor.system()
    
    # Build subject
    subject_workspace_id = legacy_data.get("workspace_id") or workspace_id
    if subject_workspace_id:
        subject = ReceiptSubject.workspace(subject_workspace_id)
    else:
        subject = ReceiptSubject.unknown()
    
    # Build decision
    if legacy_data.get("status") == "success":
        decision = ReceiptDecision.allowed(f"{receipt_id}_allowed", "Success")
    elif legacy_data.get("status") == "failed":
        decision = ReceiptDecision.blocked(f"{receipt_id}_blocked", "Failed")
    else:
        decision = ReceiptDecision.unknown()
    
    # Determine if authoritative
    authoritative = legacy_data.get("authoritative", True)
    
    return build_receipt_envelope(
        receipt_type=receipt_type,
        receipt_id=receipt_id,
        workspace_id=subject_workspace_id,
        actor=actor,
        subject=subject,
        decision=decision,
        summary=legacy_data.get("summary", ""),
        authoritative=authoritative,
        created_at=legacy_data.get("timestamp") or legacy_data.get("created_at") or utc_now(),
    )


# =============================================================================
# Phase 4: Validation Receipt Integration
# =============================================================================

def build_validation_receipt(
    workspace_id: str,
    validation_result: dict[str, Any],
    started_at: str,
    finished_at: str,
    authoritative: bool = True,
) -> ReceiptEnvelope:
    """Build a canonical ReceiptEnvelope for validation results.
    
    This creates a formal receipt for validation runs, capturing:
    - The validation result data (validators, exit codes, output)
    - Timing information
    - Authority classification
    
    Args:
        workspace_id: The workspace ID being validated
        validation_result: The validation result dict from generate_validation_result()
        started_at: When validation started (ISO format)
        finished_at: When validation finished (ISO format)
        authoritative: Whether this receipt is authoritative (default True)
    
    Returns:
        A ReceiptEnvelope representing the validation receipt
    """
    receipt_id = build_receipt_id(
        receipt_type="validation",
        workspace_id=workspace_id,
    )
    
    # Build actor - validation is performed by Rig domain
    actor = ReceiptActor(
        actor_id="rig_validator",
        actor_kind="domain",
        display_name="Rig Validation System",
        is_human=False,
        is_authoritative=True,
    )
    
    # Build subject - the validation itself
    subject = ReceiptSubject.validation(receipt_id, workspace_id)
    
    # Build decision based on validation status
    validation_status = validation_result.get("status", PLACEHOLDER_UNKNOWN)
    if validation_status == "passed":
        decision = ReceiptDecision.allowed(
            decision_id=f"val_decision_{receipt_id}",
            reason="All required validators passed",
        )
    elif validation_status == "failed":
        decision = ReceiptDecision.blocked(
            decision_id=f"val_decision_{receipt_id}",
            reason="One or more required validators failed",
        )
    else:
        decision = ReceiptDecision.unknown()
    
    # Build inputs - from validation result
    validators = validation_result.get("validators", [])
    inputs = [
        ReceiptInput.of(
            input_id=f"workspace_{workspace_id}",
            input_kind="workspace",
            reference=workspace_id,
            summary=f"Validation for workspace {workspace_id}",
        ),
    ]
    
    for idx, validator in enumerate(validators):
        validator_id = validator.get("validator_id", f"validator_{idx}")
        command = validator.get("command", [])
        inputs.append(
            ReceiptInput.of(
                input_id=f"validator_{validator_id}",
                input_kind="validator",
                reference=" ".join(command) if isinstance(command, list) else str(command),
                summary=f"Validator: {validator_id}",
            )
        )
    
    # Build outputs - validator results
    outputs = []
    for idx, validator in enumerate(validators):
        validator_id = validator.get("validator_id", f"validator_{idx}")
        exit_code = validator.get("exit_code", -1)
        is_required = validator.get("required", False)
        
        if exit_code == 0:
            status = "passed"
        elif exit_code != 0:
            status = "failed"
        else:
            status = "unknown"
        
        outputs.append(
            ReceiptOutput.of(
                output_id=f"validator_result_{validator_id}",
                output_kind="validator_result",
                reference=validator_id,
                status=status,
            )
        )
    
    # Add overall validation status output
    outputs.append(
        ReceiptOutput.of(
            output_id=f"validation_overall_{receipt_id}",
            output_kind="validation_overall",
            reference=receipt_id,
            status=validation_status,
        )
    )
    
    # Build evidence from validator output
    evidence = []
    for validator in validators:
        stdout_tail = validator.get("stdout_tail", "")
        stderr_tail = validator.get("stderr_tail", "")
        if stdout_tail:
            evidence.append(
                ReceiptEvidence.of(
                    evidence_id=f"validator_stdout_{validator.get('validator_id', 'unknown')}",
                    evidence_kind="validator_stdout",
                    reference=f"validator_{validator.get('validator_id', 'unknown')}",
                )
            )
        if stderr_tail:
            evidence.append(
                ReceiptEvidence.of(
                    evidence_id=f"validator_stderr_{validator.get('validator_id', 'unknown')}",
                    evidence_kind="validator_stderr",
                    reference=f"validator_{validator.get('validator_id', 'unknown')}",
                )
            )
    
    # Build summary
    validator_count = len(validators)
    passed_count = sum(1 for v in validators if v.get("exit_code") == 0)
    failed_count = sum(1 for v in validators if v.get("exit_code", -1) != 0 and v.get("required", False))
    
    summary = (
        f"Validation for workspace {workspace_id}: "
        f"{passed_count}/{validator_count} validators passed, "
        f"{failed_count} required failures"
    )
    
    return build_receipt_envelope(
        receipt_type="validation",
        receipt_id=receipt_id,
        workspace_id=workspace_id,
        actor=actor,
        subject=subject,
        decision=decision,
        inputs=inputs,
        outputs=outputs,
        evidence=evidence,
        related_receipt_ids=[],
        related_audit_event_ids=[],
        summary=summary,
        authoritative=authoritative,
        created_at=started_at,
    )


def build_gate_decision_receipt(
    workspace_id: str,
    gate_name: str,
    decision: str,  # "allowed", "blocked"
    reason: str,
    related_receipt_ids: List[str],
    authoritative: bool = True,
) -> ReceiptEnvelope:
    """Build a canonical ReceiptEnvelope for gate decisions.
    
    This creates a formal receipt for gate decisions (e.g., validation gate,
    apply gate), capturing:
    - The gate name
    - The decision (allowed/blocked)
    - The reason for the decision
    - Related receipt IDs that informed the decision
    
    Args:
        workspace_id: The workspace ID
        gate_name: The name of the gate (e.g., "validation_gate", "apply_gate")
        decision: The decision - "allowed" or "blocked"
        reason: Human-readable reason for the decision
        related_receipt_ids: List of receipt IDs that informed this decision
        authoritative: Whether this receipt is authoritative (default True)
    
    Returns:
        A ReceiptEnvelope representing the gate decision receipt
    """
    receipt_id = build_receipt_id(
        receipt_type="gate_decision",
        workspace_id=workspace_id,
        additional_parts=[gate_name],
    )
    
    # Build actor - gate decisions are made by Rig domain
    actor = ReceiptActor(
        actor_id="rig_gate",
        actor_kind="domain",
        display_name="Rig Gate System",
        is_human=False,
        is_authoritative=True,
    )
    
    # Build subject - the gate decision
    subject = ReceiptSubject.apply(gate_name, workspace_id)
    
    # Build decision
    if decision == "allowed":
        decision_obj = ReceiptDecision.allowed(
            decision_id=f"gate_decision_{gate_name}_{receipt_id}",
            reason=reason,
        )
    elif decision == "blocked":
        decision_obj = ReceiptDecision.blocked(
            decision_id=f"gate_decision_{gate_name}_{receipt_id}",
            reason=reason,
        )
    else:
        decision_obj = ReceiptDecision.unknown()
    
    # Build inputs - the related receipts that informed this decision
    inputs = [
        ReceiptInput.of(
            input_id=f"workspace_{workspace_id}",
            input_kind="workspace",
            reference=workspace_id,
            summary=f"Gate decision for workspace {workspace_id}",
        ),
        ReceiptInput.of(
            input_id=f"gate_{gate_name}",
            input_kind="gate",
            reference=gate_name,
            summary=f"Gate: {gate_name}",
        ),
    ]
    
    for related_id in related_receipt_ids:
        inputs.append(
            ReceiptInput.of(
                input_id=f"related_receipt_{related_id}",
                input_kind="related_receipt",
                reference=related_id,
                summary=f"Related receipt: {related_id}",
            )
        )
    
    # Build outputs - the gate decision
    outputs = [
        ReceiptOutput.of(
            output_id=f"gate_decision_{gate_name}_{receipt_id}",
            output_kind="gate_decision",
            reference=gate_name,
            status=decision,
        ),
    ]
    
    return build_receipt_envelope(
        receipt_type="gate_decision",
        receipt_id=receipt_id,
        workspace_id=workspace_id,
        actor=actor,
        subject=subject,
        decision=decision_obj,
        inputs=inputs,
        outputs=outputs,
        evidence=[],
        related_receipt_ids=related_receipt_ids,
        related_audit_event_ids=[],
        summary=f"Gate decision for {gate_name}: {decision} - {reason}",
        authoritative=authoritative,
        created_at=utc_now(),
    )


def build_review_bundle_receipt(
    workspace_id: str,
    review_bundle: dict[str, Any],
    started_at: str,
    finished_at: str,
    authoritative: bool = True,
) -> ReceiptEnvelope:
    """Build a canonical ReceiptEnvelope for review bundles.
    
    This creates a formal receipt for review bundle creation, capturing:
    - The review bundle data
    - Changed files, diff hash
    - Validation status at time of bundle creation
    - Apply eligibility
    
    Args:
        workspace_id: The workspace ID
        review_bundle: The review bundle dict from build_review_bundle()
        started_at: When bundle creation started (ISO format)
        finished_at: When bundle creation finished (ISO format)
        authoritative: Whether this receipt is authoritative (default True)
    
    Returns:
        A ReceiptEnvelope representing the review bundle receipt
    """
    receipt_id = build_receipt_id(
        receipt_type="review_bundle",
        workspace_id=workspace_id,
    )
    
    # Build actor - review bundles are created by Rig domain
    actor = ReceiptActor(
        actor_id="rig_review",
        actor_kind="domain",
        display_name="Rig Review System",
        is_human=False,
        is_authoritative=True,
    )
    
    # Build subject - the review bundle
    subject = ReceiptSubject.review_bundle(receipt_id, workspace_id)
    
    # Build decision based on apply eligibility
    apply_eligible = review_bundle.get("apply_eligibility", False)
    validation_status = review_bundle.get("validation_status", PLACEHOLDER_UNKNOWN)
    
    if apply_eligible and validation_status == "passed":
        decision = ReceiptDecision.allowed(
            decision_id=f"review_decision_{receipt_id}",
            reason="Review bundle ready for apply - all gates passed",
        )
    else:
        decision = ReceiptDecision.blocked(
            decision_id=f"review_decision_{receipt_id}",
            reason=f"Review bundle not ready: {validation_status}",
        )
    
    # Build inputs
    inputs = [
        ReceiptInput.of(
            input_id=f"workspace_{workspace_id}",
            input_kind="workspace",
            reference=workspace_id,
            summary=f"Review bundle for workspace {workspace_id}",
        ),
        ReceiptInput.of(
            input_id=f"workspace_status_{review_bundle.get('workspace_status', 'unknown')}",
            input_kind="workspace_status",
            reference=review_bundle.get("workspace_status", "unknown"),
            summary=f"Workspace status: {review_bundle.get('workspace_status', 'unknown')}",
        ),
        ReceiptInput.of(
            input_id=f"validation_status_{validation_status}",
            input_kind="validation_status",
            reference=validation_status,
            summary=f"Validation status: {validation_status}",
        ),
    ]
    
    # Add execution receipt info if present
    exec_receipt_id = review_bundle.get("execution_receipt_id")
    if exec_receipt_id:
        inputs.append(
            ReceiptInput.of(
                input_id=f"execution_receipt_{exec_receipt_id}",
                input_kind="execution_receipt",
                reference=exec_receipt_id,
                summary=f"Execution receipt: {exec_receipt_id}",
            )
        )
    
    # Build outputs
    changed_files = review_bundle.get("changed_files", [])
    diff_hash = review_bundle.get("diff_hash", "")
    
    outputs = [
        ReceiptOutput.of(
            output_id=f"review_bundle_{receipt_id}",
            output_kind="review_bundle",
            reference=str(Path(review_bundle.get("worktree_path", "")) / "review" / "review.json"),
            status="success",
        ),
        ReceiptOutput.of(
            output_id=f"diff_hash_{diff_hash[:8] if diff_hash else 'none'}",
            output_kind="diff_hash",
            reference=diff_hash,
            status="success" if diff_hash else "skipped",
        ),
        ReceiptOutput.of(
            output_id=f"apply_eligibility_{receipt_id}",
            output_kind="apply_eligibility",
            reference="apply_eligible" if apply_eligible else "not_eligible",
            status="passed" if apply_eligible else "failed",
        ),
    ]
    
    # Add evidence for changed files
    evidence = []
    for file_path in changed_files[:10]:  # Limit to first 10 files for evidence
        evidence.append(
            ReceiptEvidence.of(
                evidence_id=f"changed_file_{hashlib.sha256(file_path.encode()).hexdigest()[:8]}",
                evidence_kind="changed_file",
                reference=file_path,
            )
        )
    
    # Add blocker info if present
    known_blockers = review_bundle.get("known_blockers", [])
    if known_blockers:
        for blocker in known_blockers:
            evidence.append(
                ReceiptEvidence.of(
                    evidence_id=f"blocker_{hashlib.sha256(blocker.encode()).hexdigest()[:8]}",
                    evidence_kind="blocker",
                    reference="blocker",
                )
            )
    
    # Build summary
    summary = (
        f"Review bundle for workspace {workspace_id}: "
        f"{len(changed_files)} files changed, "
        f"validation: {validation_status}, "
        f"apply eligible: {apply_eligible}"
    )
    
    return build_receipt_envelope(
        receipt_type="review_bundle",
        receipt_id=receipt_id,
        workspace_id=workspace_id,
        actor=actor,
        subject=subject,
        decision=decision,
        inputs=inputs,
        outputs=outputs,
        evidence=evidence,
        related_receipt_ids=[],
        related_audit_event_ids=[],
        summary=summary,
        authoritative=authoritative,
        created_at=started_at,
    )


def build_apply_receipt(
    workspace_id: str,
    apply_result: dict[str, Any],
    started_at: str,
    finished_at: str,
    related_receipt_ids: List[str],
    authoritative: bool = True,
) -> ReceiptEnvelope:
    """Build a canonical ReceiptEnvelope for apply operations.
    
    This creates a formal receipt for workspace apply, capturing:
    - The apply result
    - Merge information
    - Related receipts (validation, review bundle)
    
    Args:
        workspace_id: The workspace ID
        apply_result: The apply result dict
        started_at: When apply started (ISO format)
        finished_at: When apply finished (ISO format)
        related_receipt_ids: List of related receipt IDs
        authoritative: Whether this receipt is authoritative (default True)
    
    Returns:
        A ReceiptEnvelope representing the apply receipt
    """
    receipt_id = build_receipt_id(
        receipt_type="workspace_apply",
        workspace_id=workspace_id,
    )
    
    # Build actor - apply is performed by Rig domain
    actor = ReceiptActor(
        actor_id="rig_apply",
        actor_kind="domain",
        display_name="Rig Apply System",
        is_human=False,
        is_authoritative=True,
    )
    
    # Build subject - the workspace being applied
    subject = ReceiptSubject.workspace(workspace_id)
    
    # Build decision - apply is typically allowed if we got here
    decision = ReceiptDecision.allowed(
        decision_id=f"apply_decision_{receipt_id}",
        reason="Apply completed successfully",
    )
    
    # Build inputs
    inputs = [
        ReceiptInput.of(
            input_id=f"workspace_{workspace_id}",
            input_kind="workspace",
            reference=workspace_id,
            summary=f"Apply for workspace {workspace_id}",
        ),
    ]
    
    for related_id in related_receipt_ids:
        inputs.append(
            ReceiptInput.of(
                input_id=f"related_receipt_{related_id}",
                input_kind="related_receipt",
                reference=related_id,
                summary=f"Related: {related_id}",
            )
        )
    
    # Build outputs
    base_commit = apply_result.get("base_commit", "")
    workspace_branch = apply_result.get("workspace_branch", "")
    main_before = apply_result.get("main_before", "")
    main_after = apply_result.get("main_after", "")
    
    outputs = [
        ReceiptOutput.of(
            output_id=f"merge_result_{receipt_id}",
            output_kind="merge_result",
            reference=f"{main_before}..{main_after}",
            status="success",
        ),
        ReceiptOutput.of(
            output_id=f"workspace_apply_{receipt_id}",
            output_kind="workspace_apply",
            reference=workspace_id,
            status="success",
        ),
    ]
    
    return build_receipt_envelope(
        receipt_type="workspace_apply",
        receipt_id=receipt_id,
        workspace_id=workspace_id,
        actor=actor,
        subject=subject,
        decision=decision,
        inputs=inputs,
        outputs=outputs,
        evidence=[],
        related_receipt_ids=related_receipt_ids,
        related_audit_event_ids=[],
        summary=f"Workspace {workspace_id} applied successfully",
        authoritative=authoritative,
        created_at=started_at,
    )


# ==--------------------------------------------------------------------------
# Exports
# ==--------------------------------------------------------------------------

__all__ = [
    # Placeholder constants
    "PLACEHOLDER_UNKNOWN",
    "PLACEHOLDER_UNAVAILABLE",
    "PLACEHOLDER_NOT_CREATED",
    "PLACEHOLDER_NOT_RUN",
    "PLACEHOLDER_NOT_PROOF",
    "PLACEHOLDER_ADVISORY_ONLY",
    "PLACEHOLDER_NOT_AUTHORITATIVE",
    "PLACEHOLDER_NO_RECEIPT",
    "PLACEHOLDER_NO_VALIDATION",
    "PLACEHOLDER_NO_GATE_DECISION",
    "PLACEHOLDER_VALIDATION_FAILED",
    "PLACEHOLDER_VALIDATION_INCOMPLETE",
    "PLACEHOLDER_NO_REVIEW_BUNDLE",
    "PLACEHOLDER_REVIEW_INCOMPLETE",
    "PLACEHOLDER_NO_APPLY_GATE",
    "PLACEHOLDER_APPLY_BLOCKED",
    "REQUIRED_PLACEHOLDERS",
    # Canonical types
    "ReceiptEnvelope",
    "ReceiptActor",
    "ReceiptSubject",
    "ReceiptInput",
    "ReceiptOutput",
    "ReceiptDecision",
    "ReceiptEvidence",
    "ReceiptIndexEntry",
    "ReceiptWriteResult",
    # Helper functions
    "utc_now",
    "sha256_text",
    "build_receipt_id",
    "build_receipt_envelope",
    "receipt_to_dict",
    "receipt_from_dict",
    "write_receipt",
    "read_receipt",
    "index_receipts",
    "resolve_receipt_authority",
    "resolve_receipt_completeness",
    "resolve_receipt_projection_summary",
    "resolve_validation_receipt_status",
    "resolve_review_receipt_status",
    "resolve_apply_gate_receipt_status",
    "convert_legacy_to_envelope",
    # Phase 4: Validation receipt integration
    "build_validation_receipt",
    "build_gate_decision_receipt",
    # Phase 5: Review bundle formalization
    "build_review_bundle_receipt",
    # Apply receipt helper
    "build_apply_receipt",
]
