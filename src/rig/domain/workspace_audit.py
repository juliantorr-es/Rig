"""Workspace Authority and Auditability Primitives.

This module provides deterministic, JSON-serializable audit primitives for
workspace/proposal/public-intake mutation tracking.

Core doctrine:
- Rig remains the authority.
- All models are deterministic dataclasses.
- All models are JSON-serializable.
- No side effects.
- No frontend authority logic.
- No external systems as authority.
- Public intake remains advisory_only.
- Funding remains advisory_only.
- Unknown values use explicit placeholders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Tuple


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
)


# ---------------------------------------------------------------------------
# Helper for enum serialization
# ---------------------------------------------------------------------------

def _enum_to_value(obj: Any) -> Any:
    """Convert Enum instances to their .value for JSON serialization."""
    if isinstance(obj, Enum):
        return obj.value
    return obj


# ---------------------------------------------------------------------------
# Audit Enums
# ---------------------------------------------------------------------------

class AuditAction(Enum):
    """Canonical audit action types for workspace mutations."""
    
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    TRANSITION = "transition"
    APPLY = "apply"
    REVIEW = "review"
    VALIDATE = "validate"
    IMPORT = "import"
    SYNC = "sync"
    UNKNOWN = PLACEHOLDER_UNKNOWN


class AuditSubjectKind(Enum):
    """Canonical subject kinds for audit trails."""
    
    WORKSPACE = "workspace"
    WORKSPACE_RECORD = "workspace_record"
    WORKSPACE_STATUS = "workspace_status"
    PROPOSAL = "proposal"
    PROPOSAL_STATE = "proposal_state"
    VALIDATION = "validation"
    VALIDATION_RESULT = "validation_result"
    REVIEW_BUNDLE = "review_bundle"
    RECEIPT = "receipt"
    EXECUTION_RECEIPT = "execution_receipt"
    VALIDATOR_RECEIPT = "validator_receipt"
    APPLY_RECEIPT = "apply_receipt"
    PUBLIC_INTAKE_PACKET = "public_intake_packet"
    PUBLIC_SYNC_RECEIPT = "public_sync_receipt"
    FUNDING_PLEDGE = "funding_pledge"
    WORKTREE = "worktree"
    GIT_BRANCH = "git_branch"
    GIT_MAIN = "git_main"
    UNKNOWN = PLACEHOLDER_UNKNOWN


class AuditDecision(Enum):
    """Canonical audit decision outcomes."""
    
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    PENDING = "pending"
    UNKNOWN = PLACEHOLDER_UNKNOWN
    NOT_APPLICABLE = "not_applicable"
    ADVISORY_ONLY = PLACEHOLDER_ADVISORY_ONLY


class AuditReceiptStatus(Enum):
    """Canonical receipt status values."""
    
    EXISTS = "exists"
    LINKED = "linked"
    MISSING = "missing"
    NOT_REQUIRED = "not_required"
    ADVISORY_ONLY = PLACEHOLDER_ADVISORY_ONLY
    NOT_AUTHORITATIVE = PLACEHOLDER_NOT_AUTHORITATIVE
    NO_RECEIPT = PLACEHOLDER_NO_RECEIPT


# ---------------------------------------------------------------------------
# Audit Primitive Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class AuditActor:
    """Represents the actor/authority that performed or initiated an action.
    
    Deterministic, serializable, side-effect free.
    """
    
    actor_id: str
    actor_kind: str  # e.g., "cli", "connector", "domain", "governance_engine"
    display_name: Optional[str] = None
    is_human: bool = False
    is_authoritative: bool = True
    
    @classmethod
    def system(cls) -> "AuditActor":
        """Create a system actor placeholder."""
        return cls(
            actor_id="system",
            actor_kind="system",
            display_name="System",
            is_human=False,
            is_authoritative=True,
        )
    
    @classmethod
    def cli(cls) -> "AuditActor":
        """Create a CLI actor placeholder."""
        return cls(
            actor_id="cli",
            actor_kind="cli",
            display_name="CLI",
            is_human=True,
            is_authoritative=True,
        )
    
    @classmethod
    def connector(cls, connector_name: str) -> "AuditActor":
        """Create a connector actor placeholder."""
        return cls(
            actor_id=f"connector_{connector_name}",
            actor_kind="connector",
            display_name=connector_name,
            is_human=False,
            is_authoritative=False,  # Connectors are NOT authoritative
        )
    
    @classmethod
    def unknown(cls) -> "AuditActor":
        """Create an unknown actor placeholder."""
        return cls(
            actor_id=PLACEHOLDER_UNKNOWN,
            actor_kind=PLACEHOLDER_UNKNOWN,
            display_name=PLACEHOLDER_UNKNOWN,
            is_human=False,
            is_authoritative=False,
        )
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Ensure all values are JSON-serializable
        return {k: _enum_to_value(v) for k, v in d.items()}


@dataclass(frozen=True, slots=True)
class AuditSubject:
    """Represents the subject being acted upon.
    
    Deterministic, serializable, side-effect free.
    """
    
    subject_id: str
    subject_kind: AuditSubjectKind = AuditSubjectKind.UNKNOWN
    display_name: Optional[str] = None
    workspace_id: Optional[str] = None
    authoritative: bool = True
    advisory_only: bool = False
    
    @classmethod
    def workspace(cls, workspace_id: str) -> "AuditSubject":
        """Create a workspace subject."""
        return cls(
            subject_id=workspace_id,
            subject_kind=AuditSubjectKind.WORKSPACE,
            display_name=workspace_id,
            workspace_id=workspace_id,
            authoritative=True,
            advisory_only=False,
        )
    
    @classmethod
    def proposal(cls, proposal_id: str, workspace_id: Optional[str] = None) -> "AuditSubject":
        """Create a proposal subject."""
        return cls(
            subject_id=proposal_id,
            subject_kind=AuditSubjectKind.PROPOSAL,
            display_name=proposal_id,
            workspace_id=workspace_id,
            authoritative=True,
            advisory_only=False,
        )
    
    @classmethod
    def public_intake_packet(cls, packet_id: str, advisory: bool = True) -> "AuditSubject":
        """Create a public intake packet subject (advisory only)."""
        return cls(
            subject_id=packet_id,
            subject_kind=AuditSubjectKind.PUBLIC_INTAKE_PACKET,
            display_name=packet_id,
            workspace_id=None,
            authoritative=False,  # Public intake is NEVER authoritative
            advisory_only=True,
        )
    
    @classmethod
    def unknown(cls) -> "AuditSubject":
        """Create an unknown subject placeholder."""
        return cls(
            subject_id=PLACEHOLDER_UNKNOWN,
            subject_kind=AuditSubjectKind.UNKNOWN,
            display_name=PLACEHOLDER_UNKNOWN,
            workspace_id=None,
            authoritative=False,
            advisory_only=True,
        )
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: _enum_to_value(v) for k, v in d.items()}


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Represents a single auditable event.
    
    Deterministic, serializable, side-effect free.
    Links actors, actions, subjects, decisions, and receipts.
    """
    
    event_id: str
    action: AuditAction = AuditAction.UNKNOWN
    actor: AuditActor = field(default_factory=AuditActor.unknown)
    subject: AuditSubject = field(default_factory=AuditSubject.unknown)
    decision: AuditDecision = AuditDecision.UNKNOWN
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    status: str = PLACEHOLDER_UNKNOWN
    summary: str = ""
    
    # Receipt linkage
    receipt_id: Optional[str] = None
    receipt_kind: Optional[str] = None
    receipt_status: AuditReceiptStatus = AuditReceiptStatus.MISSING
    
    # Context
    workspace_id: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    
    # Authority classification
    authoritative: bool = True
    advisory_only: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["actor"] = self.actor.to_dict()
        d["subject"] = self.subject.to_dict()
        # Convert any remaining enums
        return {k: _enum_to_value(v) for k, v in d.items()}
    
    @classmethod
    def for_workspace_creation(
        cls,
        workspace_id: str,
        actor: Optional[AuditActor] = None,
        receipt_id: Optional[str] = None,
    ) -> "AuditEvent":
        """Create an audit event for workspace creation."""
        return cls(
            event_id=f"ws_create_{workspace_id}",
            action=AuditAction.CREATE,
            actor=actor or AuditActor.cli(),
            subject=AuditSubject.workspace(workspace_id),
            decision=AuditDecision.ALLOWED,
            status="success",
            summary=f"Workspace {workspace_id} created",
            receipt_id=receipt_id,
            receipt_kind="workspace_create_receipt",
            receipt_status=AuditReceiptStatus.EXISTS if receipt_id else AuditReceiptStatus.MISSING,
            workspace_id=workspace_id,
            authoritative=True,
            advisory_only=False,
        )
    
    @classmethod
    def for_workspace_transition(
        cls,
        workspace_id: str,
        old_status: str,
        new_status: str,
        actor: Optional[AuditActor] = None,
        receipt_id: Optional[str] = None,
    ) -> "AuditEvent":
        """Create an audit event for workspace status transition."""
        return cls(
            event_id=f"ws_trans_{workspace_id}_{old_status}_to_{new_status}",
            action=AuditAction.TRANSITION,
            actor=actor or AuditActor.cli(),
            subject=AuditSubject.workspace(workspace_id),
            decision=AuditDecision.ALLOWED,
            status="success",
            summary=f"Workspace {workspace_id} transitioned: {old_status} -> {new_status}",
            receipt_id=receipt_id,
            receipt_kind="workspace_transition_receipt",
            receipt_status=AuditReceiptStatus.EXISTS if receipt_id else AuditReceiptStatus.MISSING,
            workspace_id=workspace_id,
            details={"old_status": old_status, "new_status": new_status},
            authoritative=True,
            advisory_only=False,
        )
    
    @classmethod
    def for_workspace_apply(
        cls,
        workspace_id: str,
        main_before: str,
        main_after: str,
        actor: Optional[AuditActor] = None,
        receipt_id: Optional[str] = None,
    ) -> "AuditEvent":
        """Create an audit event for workspace apply."""
        return cls(
            event_id=f"ws_apply_{workspace_id}",
            action=AuditAction.APPLY,
            actor=actor or AuditActor.cli(),
            subject=AuditSubject.workspace(workspace_id),
            decision=AuditDecision.ALLOWED,
            status="success",
            summary=f"Workspace {workspace_id} applied to main",
            receipt_id=receipt_id,
            receipt_kind="apply_receipt",
            receipt_status=AuditReceiptStatus.EXISTS if receipt_id else AuditReceiptStatus.MISSING,
            workspace_id=workspace_id,
            details={"main_before": main_before, "main_after": main_after},
            authoritative=True,
            advisory_only=False,
        )
    
    @classmethod
    def for_public_intake_import(
        cls,
        connector: str,
        packet_count: int,
        sync_receipt_id: Optional[str],
        actor: Optional[AuditActor] = None,
    ) -> "AuditEvent":
        """Create an audit event for public intake import (advisory only)."""
        return cls(
            event_id=f"intake_import_{connector}",
            action=AuditAction.IMPORT,
            actor=actor or AuditActor.connector(connector),
            subject=AuditSubject(
                subject_id=connector,
                subject_kind=AuditSubjectKind.PUBLIC_SYNC_RECEIPT,
                display_name=f"{connector} import",
                authoritative=False,
                advisory_only=True,
            ),
            decision=AuditDecision.ALLOWED,
            status="success",
            summary=f"Imported {packet_count} packets from {connector}",
            receipt_id=sync_receipt_id,
            receipt_kind="public_sync_receipt",
            receipt_status=AuditReceiptStatus.EXISTS if sync_receipt_id else AuditReceiptStatus.MISSING,
            workspace_id=None,
            details={"connector": connector, "packet_count": packet_count},
            authoritative=False,
            advisory_only=True,
        )


@dataclass(frozen=True, slots=True)
class AuditReceiptLink:
    """Links an audit event to a receipt.
    
    Deterministic, serializable, side-effect free.
    """
    
    link_id: str
    event_id: str
    receipt_id: str
    receipt_kind: str
    workspace_id: Optional[str] = None
    status: AuditReceiptStatus = AuditReceiptStatus.MISSING
    
    # Whether this receipt is authoritative or advisory
    authoritative: bool = True
    advisory_only: bool = False
    
    @classmethod
    def of(
        cls,
        event_id: str,
        receipt_id: str,
        receipt_kind: str,
        workspace_id: Optional[str] = None,
        authoritative: bool = True,
    ) -> "AuditReceiptLink":
        """Create a receipt link."""
        return cls(
            link_id=f"link_{event_id}_{receipt_id}",
            event_id=event_id,
            receipt_id=receipt_id,
            receipt_kind=receipt_kind,
            workspace_id=workspace_id,
            status=AuditReceiptStatus.EXISTS,
            authoritative=authoritative,
            advisory_only=not authoritative,
        )
    
    @classmethod
    def missing(
        cls,
        event_id: str,
        receipt_kind: str,
        workspace_id: Optional[str] = None,
        reason: str = PLACEHOLDER_NO_RECEIPT,
    ) -> "AuditReceiptLink":
        """Create a missing receipt link with reason."""
        return cls(
            link_id=f"link_{event_id}_missing_{receipt_kind}",
            event_id=event_id,
            receipt_id=PLACEHOLDER_NO_RECEIPT,
            receipt_kind=receipt_kind,
            workspace_id=workspace_id,
            status=AuditReceiptStatus.MISSING,
            authoritative=False,
            advisory_only=True,
        )
    
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: _enum_to_value(v) for k, v in d.items()}


@dataclass(frozen=True, slots=True)
class WorkspaceAuditTrail:
    """Complete audit trail for a workspace.
    
    Deterministic, serializable, side-effect free.
    Aggregates all audit events for a workspace.
    """
    
    workspace_id: str
    events: Tuple[AuditEvent, ...] = ()
    receipt_links: Tuple[AuditReceiptLink, ...] = ()
    
    # Completeness tracking
    audit_completeness: str = PLACEHOLDER_UNKNOWN
    last_authoritative_event_id: Optional[str] = None
    receipt_status_summary: dict[str, Any] = field(default_factory=dict)
    
    # Placeholder for missing data
    missing_receipts: Tuple[str, ...] = ()  # List of receipt kinds that are missing
    advisory_only_events: int = 0
    authoritative_events: int = 0
    
    @classmethod
    def empty(cls, workspace_id: str) -> "WorkspaceAuditTrail":
        """Create an empty audit trail for a workspace."""
        return cls(workspace_id=workspace_id)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "events": [e.to_dict() for e in self.events],
            "receipt_links": [rl.to_dict() for rl in self.receipt_links],
            "audit_completeness": self.audit_completeness,
            "last_authoritative_event_id": self.last_authoritative_event_id,
            "receipt_status_summary": self.receipt_status_summary,
            "missing_receipts": list(self.missing_receipts),
            "advisory_only_events": self.advisory_only_events,
            "authoritative_events": self.authoritative_events,
        }
    
    def with_event(self, event: AuditEvent) -> "WorkspaceAuditTrail":
        """Return a new trail with an additional event."""
        events = (*self.events, event)
        return WorkspaceAuditTrail(
            workspace_id=self.workspace_id,
            events=events,
            receipt_links=self.receipt_links,
        )
    
    def with_receipt_link(self, link: AuditReceiptLink) -> "WorkspaceAuditTrail":
        """Return a new trail with an additional receipt link."""
        links = (*self.receipt_links, link)
        return WorkspaceAuditTrail(
            workspace_id=self.workspace_id,
            events=self.events,
            receipt_links=links,
        )


# ---------------------------------------------------------------------------
# Resolution Helpers
# ---------------------------------------------------------------------------

def resolve_mutation_authority(
    action: AuditAction,
    subject_kind: AuditSubjectKind,
    actor_kind: str,
) -> dict[str, Any]:
    """Resolve the authority classification for a mutation.
    
    Returns a dict with:
    - authoritative: bool
    - advisory_only: bool
    - reason: str
    
    Deterministic, side-effect free.
    """
    # Public intake is ALWAYS advisory only
    if subject_kind in (
        AuditSubjectKind.PUBLIC_INTAKE_PACKET,
        AuditSubjectKind.PUBLIC_SYNC_RECEIPT,
        AuditSubjectKind.FUNDING_PLEDGE,
    ):
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
    
    # Git main mutations via apply are authoritative
    if action == AuditAction.APPLY and subject_kind == AuditSubjectKind.GIT_MAIN:
        return {
            "authoritative": True,
            "advisory_only": False,
            "reason": "Apply merges to main branch - Rig authority",
        }
    
    # Workspace mutations by Rig domain are authoritative
    if actor_kind in ("cli", "domain", "system") and subject_kind in (
        AuditSubjectKind.WORKSPACE,
        AuditSubjectKind.WORKSPACE_RECORD,
        AuditSubjectKind.WORKSPACE_STATUS,
        AuditSubjectKind.PROPOSAL,
        AuditSubjectKind.PROPOSAL_STATE,
    ):
        return {
            "authoritative": True,
            "advisory_only": False,
            "reason": "Workspace and proposal mutations by Rig are authoritative",
        }
    
    # Default: assume authoritative unless proven otherwise
    return {
        "authoritative": True,
        "advisory_only": False,
        "reason": PLACEHOLDER_UNKNOWN,
    }


def resolve_receipt_status(
    event: AuditEvent,
    receipt_exists: bool,
) -> AuditReceiptStatus:
    """Resolve the receipt status for an audit event.
    
    Deterministic, side-effect free.
    """
    # If we have a receipt_id and it exists
    if event.receipt_id and receipt_exists:
        return AuditReceiptStatus.EXISTS
    
    # If we have a receipt_id but it doesn't exist
    if event.receipt_id and not receipt_exists:
        return AuditReceiptStatus.MISSING
    
    # If advisory only, receipt not required
    if event.advisory_only:
        return AuditReceiptStatus.ADVISORY_ONLY
    
    # No receipt_id
    if not event.receipt_id:
        return AuditReceiptStatus.NO_RECEIPT
    
    return AuditReceiptStatus.MISSING


def resolve_audit_completeness(
    trail: WorkspaceAuditTrail,
) -> dict[str, Any]:
    """Resolve the audit completeness for a workspace audit trail.
    
    Returns a dict with:
    - completeness: str (one of the placeholder constants or "complete")
    - score: float (0.0 to 1.0)
    - missing: list of missing receipt kinds
    - advisory_only_count: int
    
    Deterministic, side-effect free.
    """
    if not trail.events:
        return {
            "completeness": PLACEHOLDER_NOT_CREATED,
            "score": 0.0,
            "missing": [],
            "advisory_only_count": 0,
        }
    
    # Count events by type
    event_actions = {e.action.value for e in trail.events}
    advisory_count = sum(1 for e in trail.events if e.advisory_only)
    
    # Check for critical mutations that need receipts
    needed_receipts = []
    missing_receipts = []
    
    for event in trail.events:
        # Workspace creation needs a receipt
        if event.action == AuditAction.CREATE and event.subject.subject_kind == AuditSubjectKind.WORKSPACE:
            needed_receipts.append("workspace_create")
            if not event.receipt_id:
                missing_receipts.append("workspace_create")
        
        # Workspace transitions need receipts
        if event.action == AuditAction.TRANSITION and event.subject.subject_kind == AuditSubjectKind.WORKSPACE:
            needed_receipts.append("workspace_transition")
            if not event.receipt_id:
                missing_receipts.append("workspace_transition")
        
        # Apply needs receipts (already has them, but verify)
        if event.action == AuditAction.APPLY:
            needed_receipts.append("apply")
            if not event.receipt_id:
                missing_receipts.append("apply")
    
    # Calculate score
    # Score is based on: all needed receipts present, all authoritative events have receipts
    authoritative_without_receipts = sum(
        1 for e in trail.events 
        if not e.advisory_only and not e.receipt_id
    )
    authoritative_total = sum(1 for e in trail.events if not e.advisory_only)
    
    if authoritative_total == 0:
        score = 1.0 if not missing_receipts else 0.5
    else:
        score = max(0.0, 1.0 - (authoritative_without_receipts / authoritative_total))
    
    # Determine completeness label
    if not missing_receipts and authoritative_without_receipts == 0:
        completeness = "complete"
    elif missing_receipts:
        completeness = PLACEHOLDER_NOT_PROOF
    elif authoritative_without_receipts > 0:
        completeness = PLACEHOLDER_NOT_RUN
    else:
        completeness = PLACEHOLDER_UNKNOWN
    
    return {
        "completeness": completeness,
        "score": round(score, 2),
        "missing": list(set(missing_receipts)),
        "needed": list(set(needed_receipts)),
        "advisory_only_count": advisory_count,
    }


def build_workspace_audit_trail(
    workspace_id: str,
    events: list[AuditEvent],
    receipt_links: Optional[list[AuditReceiptLink]] = None,
) -> WorkspaceAuditTrail:
    """Build a complete workspace audit trail from events and receipt links.
    
    Deterministic, side-effect free.
    """
    event_objs = tuple(events)
    link_objs = tuple(receipt_links or [])
    
    # Calculate completeness
    completeness = resolve_audit_completeness(
        WorkspaceAuditTrail(
            workspace_id=workspace_id,
            events=event_objs,
            receipt_links=link_objs,
        )
    )
    
    # Find last authoritative event
    last_auth_event = None
    for event in reversed(event_objs):
        if not event.advisory_only:
            last_auth_event = event.event_id
            break
    
    # Build receipt status summary
    receipt_status = {}
    for link in link_objs:
        kind = link.receipt_kind
        if kind not in receipt_status:
            receipt_status[kind] = {"exists": 0, "missing": 0}
        if link.status == AuditReceiptStatus.EXISTS:
            receipt_status[kind]["exists"] += 1
        else:
            receipt_status[kind]["missing"] += 1
    
    # Count missing receipts by kind
    missing = []
    for kind, counts in receipt_status.items():
        if counts["missing"] > 0:
            missing.append(kind)
    
    advisory_count = sum(1 for e in event_objs if e.advisory_only)
    auth_count = sum(1 for e in event_objs if not e.advisory_only)
    
    return WorkspaceAuditTrail(
        workspace_id=workspace_id,
        events=event_objs,
        receipt_links=link_objs,
        audit_completeness=completeness["completeness"],
        last_authoritative_event_id=last_auth_event,
        receipt_status_summary=receipt_status,
        missing_receipts=tuple(missing),
        advisory_only_events=advisory_count,
        authoritative_events=auth_count,
    )


def build_auditability_state(
    workspace_summary: Optional[Any] = None,
    audit_trail: Optional[WorkspaceAuditTrail] = None,
) -> dict[str, Any]:
    """Build auditability state for projection.
    
    Returns a dict suitable for projection consumption.
    Pure function: no file writes, no database.
    """
    # Default auditability state with placeholders
    state = {
        "audit_completeness": PLACEHOLDER_NOT_CREATED,
        "last_authoritative_event_id": PLACEHOLDER_UNKNOWN,
        "receipt_status_summary": {},
        "missing_receipts": [],
        "advisory_only_events": 0,
        "authoritative_events": 0,
    }
    
    # If we have an audit trail, use it
    if audit_trail is not None:
        state = {
            "audit_completeness": audit_trail.audit_completeness,
            "last_authoritative_event_id": audit_trail.last_authoritative_event_id or PLACEHOLDER_UNKNOWN,
            "receipt_status_summary": audit_trail.receipt_status_summary,
            "missing_receipts": list(audit_trail.missing_receipts),
            "advisory_only_events": audit_trail.advisory_only_events,
            "authoritative_events": audit_trail.authoritative_events,
        }
    
    # Add note about advisory-only public intake data if present
    if workspace_summary:
        # Check if workspace has public intake/funding data (advisory only)
        # This would be tracked in workspace metadata or separate store
        # For now, add a placeholder warning
        state["advisory_only_warning"] = (
            "Public intake and funding data is advisory_only. "
            "External systems are NOT authoritative."
        )
    else:
        state["advisory_only_warning"] = (
            "Public intake and funding data is advisory_only. "
            "External systems are NOT authoritative."
        )
    
    # Add next missing audit action if there are missing receipts
    if state["missing_receipts"]:
        state["next_missing_audit_action"] = (
            f"Create receipts for: {', '.join(state['missing_receipts'])}"
        )
    else:
        state["next_missing_audit_action"] = PLACEHOLDER_NO_RECEIPT
    
    return state
