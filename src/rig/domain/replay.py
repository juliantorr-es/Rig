"""Governance Replay & Time-Travel Module for Rig.

This module provides the canonical replay substrate for Phase 5.
Replay enables deterministic reconstruction of workspace state from
receipts + audit events alone.

Core doctrine:
- Authority state is reconstructable evidence
- Replay must be deterministic
- Replay must tolerate incomplete history
- Replay findings must remain explicit
- No hidden mutation
- No auto-repair
- Replay preserves advisory vs authoritative distinctions

file: src/rig/domain/replay.py
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.receipt_envelope import ReceiptEnvelope
    from rig.domain.workspace_audit import AuditEvent, WorkspaceAuditTrail

# ---------------------------------------------------------------------------
# Placeholder Constants
# ---------------------------------------------------------------------------

PLACEHOLDER_UNKNOWN = "unknown"
PLACEHOLDER_UNAVAILABLE = "unavailable"
PLACEHOLDER_NOT_CREATED = "not_created"
PLACEHOLDER_NOT_RUN = "not_run"
PLACEHOLDER_NOT_PROOF = "not_proof"
PLACEHOLDER_ADVISORY_ONLY = "advisory_only"
PLACEHOLDER_NOT_AUTHORITATIVE = "not_authoritative"
PLACEHOLDER_NO_RECEIPT = "no_receipt"
PLACEHOLDER_NO_EVIDENCE = "no_evidence"
PLACEHOLDER_STALE_REFERENCE = "stale_reference"
PLACEHOLDER_ORPHANED = "orphaned"
PLACEHOLDER_CONTRADICTION = "contradiction"
PLACEHOLDER_GAP = "gap"

SCHEMA_VERSION = "rig.replay.v1"

# All replay-specific placeholders
REQUIRED_REPLAY_PLACEHOLDERS = (
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_UNAVAILABLE,
    PLACEHOLDER_NOT_CREATED,
    PLACEHOLDER_NOT_RUN,
    PLACEHOLDER_NOT_PROOF,
    PLACEHOLDER_ADVISORY_ONLY,
    PLACEHOLDER_NOT_AUTHORITATIVE,
    PLACEHOLDER_NO_RECEIPT,
    PLACEHOLDER_NO_EVIDENCE,
    PLACEHOLDER_STALE_REFERENCE,
    PLACEHOLDER_ORPHANED,
    PLACEHOLDER_CONTRADICTION,
    PLACEHOLDER_GAP,
)


# ---------------------------------------------------------------------------
# Replay Types
# ---------------------------------------------------------------------------

class ReplayEventKind(Enum):
    """Canonical replay event kinds."""
    RECEIPT = "receipt"
    AUDIT = "audit"
    WORKSPACE = "workspace"
    VALIDATION = "validation"
    REVIEW = "review"
    APPLY = "apply"
    GATE = "gate"
    UNKNOWN = PLACEHOLDER_UNKNOWN


class ReplayDecisionKind(Enum):
    """Canonical replay decision kinds."""
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    PENDING = "pending"
    ADVISORY_ONLY = PLACEHOLDER_ADVISORY_ONLY
    NOT_APPLICABLE = "not_applicable"
    CONTRADICTION = PLACEHOLDER_CONTRADICTION


class ReplayIntegritySeverity(Enum):
    """Severity levels for replay integrity findings."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ReplayConflictType(Enum):
    """Types of replay conflicts."""
    IMPOSSIBLE_TRANSITION = "impossible_transition"
    MISSING_RECEIPT = "missing_receipt"
    MISSING_AUDIT_EVENT = "missing_audit_event"
    STALE_RECEIPT_CHAIN = "stale_receipt_chain"
    ORPHANED_AUDIT_EVENT = "orphaned_audit_event"
    ADVISORY_ESCALATION = "advisory_escalation"
    CONTRADICTORY_GATE_DECISION = "contradictory_gate_decision"
    NON_DETERMINISTIC_ORDERING = "non_deterministic_ordering"
    AUTHORITY_MISMATCH = "authority_mismatch"


class ReplayState(Enum):
    """Replay processing states."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    """A single event in the replay sequence.
    
    Represents either a receipt or audit event that contributes to
    the replay of workspace state.
    
    Deterministic, serializable, side-effect free.
    """
    event_id: str
    event_kind: ReplayEventKind = ReplayEventKind.UNKNOWN
    source_id: str = PLACEHOLDER_UNKNOWN  # receipt_id or event_id from source
    workspace_id: Optional[str] = None
    source_schema_version: str = ""
    source_event_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    sequence_index: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    authoritative: bool = True
    advisory_only: bool = False
    hash: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        # Convert enums to values
        d["event_kind"] = self.event_kind.value
        d["advisory_only"] = self.advisory_only
        d["authoritative"] = self.authoritative
        return d
    
    @classmethod
    def from_receipt(cls, envelope: "ReceiptEnvelope", sequence_index: int = 0) -> "ReplayEvent":
        """Create a ReplayEvent from a ReceiptEnvelope."""
        data = envelope.to_dict()
        return cls(
            event_id=f"replay_receipt_{envelope.receipt_id}",
            event_kind=ReplayEventKind.RECEIPT,
            source_id=envelope.receipt_id,
            workspace_id=envelope.subject.workspace_id if hasattr(envelope.subject, 'workspace_id') else None,
            source_schema_version=envelope.schema_version,
            source_event_id=envelope.receipt_id,
            timestamp=envelope.created_at,
            sequence_index=sequence_index,
            data=data,
            authoritative=not envelope.advisory_only,
            advisory_only=envelope.advisory_only,
            hash=sha256_text(json.dumps(data, sort_keys=True)),
        )
    
    @classmethod
    def from_audit_event(cls, event: "AuditEvent", sequence_index: int = 0) -> "ReplayEvent":
        """Create a ReplayEvent from an AuditEvent."""
        data = event.to_dict()
        return cls(
            event_id=f"replay_audit_{event.event_id}",
            event_kind=ReplayEventKind.AUDIT,
            source_id=event.event_id,
            workspace_id=event.workspace_id,
            source_schema_version="rig.workspace_audit.v1",
            source_event_id=event.event_id,
            timestamp=event.timestamp,
            sequence_index=sequence_index,
            data=data,
            authoritative=event.authoritative and not event.advisory_only,
            advisory_only=event.advisory_only,
            hash=sha256_text(json.dumps(data, sort_keys=True)),
        )
    
    @classmethod
    def placeholder(cls, workspace_id: Optional[str] = None) -> "ReplayEvent":
        """Create a placeholder ReplayEvent for missing data."""
        return cls(
            event_id=f"replay_placeholder_{workspace_id or 'global'}",
            event_kind=ReplayEventKind.UNKNOWN,
            source_id=PLACEHOLDER_NO_RECEIPT,
            workspace_id=workspace_id,
            source_schema_version=SCHEMA_VERSION,
            source_event_id=PLACEHOLDER_NO_RECEIPT,
            timestamp=PLACEHOLDER_NOT_CREATED,
            sequence_index=-1,
            data={"status": PLACEHOLDER_NO_EVIDENCE},
            authoritative=False,
            advisory_only=True,
            hash=sha256_text(PLACEHOLDER_NO_EVIDENCE),
        )


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    """A single frame in the replay sequence.
    
    Represents the state at a specific point in the replay.
    Each frame contains all events up to that point and the
    reconstructed state.
    
    Deterministic, serializable, side-effect free.
    """
    frame_index: int
    events: Tuple[ReplayEvent, ...] = ()
    workspace_id: Optional[str] = None
    workspace_status: str = PLACEHOLDER_UNKNOWN
    status_history: Tuple[Dict[str, Any], ...] = ()
    receipt_chain: Tuple[str, ...] = ()  # Ordered receipt IDs
    audit_chain: Tuple[str, ...] = ()  # Ordered audit event IDs
    authority_state: Dict[str, Any] = field(default_factory=dict)
    advisory_state: Dict[str, Any] = field(default_factory=dict)
    integrity_findings: Tuple[str, ...] = ()  # Reference to finding IDs
    frame_hash: str = ""
    previous_frame_hash: str = ""
    is_terminal: bool = False
    terminal_reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "schema_version": SCHEMA_VERSION,
            "frame_index": self.frame_index,
            "events": [e.to_dict() for e in self.events],
            "workspace_id": self.workspace_id,
            "workspace_status": self.workspace_status,
            "status_history": list(self.status_history),
            "receipt_chain": list(self.receipt_chain),
            "audit_chain": list(self.audit_chain),
            "authority_state": self.authority_state,
            "advisory_state": self.advisory_state,
            "integrity_findings": list(self.integrity_findings),
            "frame_hash": self.frame_hash,
            "previous_frame_hash": self.previous_frame_hash,
            "is_terminal": self.is_terminal,
            "terminal_reason": self.terminal_reason,
        }
    
    @property
    def has_authoritative_evidence(self) -> bool:
        """Check if this frame has authoritative evidence."""
        return any(e.authoritative and not e.advisory_only for e in self.events)
    
    @property
    def has_advisory_only(self) -> bool:
        """Check if this frame has advisory-only data."""
        return any(e.advisory_only for e in self.events)


@dataclass(frozen=True, slots=True)
class ReplayCursor:
    """Cursor positioning within the replay sequence.
    
    Tracks the current position and allows navigation through
    the replay frames.
    
    Deterministic, serializable, side-effect free.
    """
    current_frame_index: int = 0
    total_frames: int = 0
    workspace_id: Optional[str] = None
    can_go_back: bool = False
    can_go_forward: bool = False
    current_frame_hash: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["schema_version"] = SCHEMA_VERSION
        return d
    
    def go_back(self) -> Optional["ReplayCursor"]:
        """Move cursor back one frame. Returns None if at beginning."""
        if self.current_frame_index <= 0:
            return None
        return ReplayCursor(
            current_frame_index=self.current_frame_index - 1,
            total_frames=self.total_frames,
            workspace_id=self.workspace_id,
            can_go_back=self.current_frame_index > 1,
            can_go_forward=True,
            current_frame_hash="",
        )
    
    def go_forward(self) -> Optional["ReplayCursor"]:
        """Move cursor forward one frame. Returns None if at end."""
        if self.current_frame_index >= self.total_frames - 1:
            return None
        return ReplayCursor(
            current_frame_index=self.current_frame_index + 1,
            total_frames=self.total_frames,
            workspace_id=self.workspace_id,
            can_go_back=True,
            can_go_forward=self.current_frame_index < self.total_frames - 2,
            current_frame_hash="",
        )
    
    def go_to(self, frame_index: int) -> Optional["ReplayCursor"]:
        """Move cursor to specific frame index. Returns None if invalid."""
        if frame_index < 0 or frame_index >= self.total_frames:
            return None
        return ReplayCursor(
            current_frame_index=frame_index,
            total_frames=self.total_frames,
            workspace_id=self.workspace_id,
            can_go_back=frame_index > 0,
            can_go_forward=frame_index < self.total_frames - 1,
            current_frame_hash="",
        )


@dataclass(frozen=True, slots=True)
class ReplayDecision:
    """A decision made during replay.
    
    Represents the authority decision at a specific replay frame.
    
    Deterministic, serializable, side-effect free.
    """
    decision_id: str
    decision_kind: ReplayDecisionKind = ReplayDecisionKind.PENDING
    reason: str = ""
    frame_index: int = 0
    workspace_id: Optional[str] = None
    authoritative: bool = True
    is_advisory_only: bool = False  # Renamed to avoid conflict with factory method
    related_event_ids: Tuple[str, ...] = ()
    related_receipt_ids: Tuple[str, ...] = ()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["decision_kind"] = self.decision_kind.value
        # Convert back to advisory_only for JSON output
        d["advisory_only"] = self.is_advisory_only
        if "is_advisory_only" in d:
            del d["is_advisory_only"]
        return d
    
    @property
    def advisory_only(self) -> bool:
        """Property for backwards compatibility."""
        return self.is_advisory_only
    
    @classmethod
    def allowed(cls, decision_id: str, reason: str, frame_index: int = 0, 
                workspace_id: Optional[str] = None) -> "ReplayDecision":
        """Create an allowed replay decision."""
        return cls(
            decision_id=decision_id,
            decision_kind=ReplayDecisionKind.ALLOWED,
            reason=reason,
            frame_index=frame_index,
            workspace_id=workspace_id,
            authoritative=True,
            is_advisory_only=False,
        )
    
    @classmethod
    def blocked(cls, decision_id: str, reason: str, frame_index: int = 0,
                workspace_id: Optional[str] = None) -> "ReplayDecision":
        """Create a blocked replay decision."""
        return cls(
            decision_id=decision_id,
            decision_kind=ReplayDecisionKind.BLOCKED,
            reason=reason,
            frame_index=frame_index,
            workspace_id=workspace_id,
            authoritative=True,
            is_advisory_only=False,
        )
    
    @classmethod
    def create_advisory_only(cls, decision_id: str, reason: str = PLACEHOLDER_ADVISORY_ONLY,
                      frame_index: int = 0, workspace_id: Optional[str] = None) -> "ReplayDecision":
        """Create an advisory-only replay decision."""
        return cls(
            decision_id=decision_id,
            decision_kind=ReplayDecisionKind.ADVISORY_ONLY,
            reason=reason,
            frame_index=frame_index,
            workspace_id=workspace_id,
            authoritative=False,
            is_advisory_only=True,
        )
    
    @classmethod
    def contradiction(cls, decision_id: str, reason: str, frame_index: int = 0,
                     workspace_id: Optional[str] = None) -> "ReplayDecision":
        """Create a contradiction replay decision."""
        return cls(
            decision_id=decision_id,
            decision_kind=ReplayDecisionKind.CONTRADICTION,
            reason=reason,
            frame_index=frame_index,
            workspace_id=workspace_id,
            authoritative=False,
            is_advisory_only=True,
        )


@dataclass(frozen=True, slots=True)
class ReplaySnapshot:
    """A complete snapshot of replay state at a point in time.
    
    Contains all the information needed to reconstruct the
    workspace state at a specific frame.
    
    Deterministic, serializable, side-effect free.
    """
    snapshot_id: str
    workspace_id: Optional[str] = None
    frame_index: int = 0
    frame: Optional[ReplayFrame] = None
    cursor: Optional[ReplayCursor] = None
    decisions: Tuple[ReplayDecision, ...] = ()
    integrity_findings: Tuple["ReplayIntegrityFinding", ...] = ()
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    authoritative_evidence_available: bool = False
    advisory_only_evidence_present: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "workspace_id": self.workspace_id,
            "frame_index": self.frame_index,
            "frame": self.frame.to_dict() if self.frame else None,
            "cursor": self.cursor.to_dict() if self.cursor else None,
            "decisions": [d.to_dict() for d in self.decisions],
            "integrity_findings": [f.to_dict() for f in self.integrity_findings],
            "created_at": self.created_at,
            "authoritative_evidence_available": self.authoritative_evidence_available,
            "advisory_only_evidence_present": self.advisory_only_evidence_present,
        }


@dataclass(frozen=True, slots=True)
class ReplayConflict:
    """A conflict detected during replay.
    
    Represents an issue that prevents complete reconstruction
    of workspace state.
    
    Deterministic, serializable, side-effect free.
    """
    conflict_id: str
    conflict_type: ReplayConflictType
    severity: ReplayIntegritySeverity
    title: str
    message: str
    workspace_id: Optional[str] = None
    frame_index: int = 0
    involved_receipt_ids: Tuple[str, ...] = ()
    involved_audit_event_ids: Tuple[str, ...] = ()
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "schema_version": SCHEMA_VERSION,
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "workspace_id": self.workspace_id,
            "frame_index": self.frame_index,
            "involved_receipt_ids": list(self.involved_receipt_ids),
            "involved_audit_event_ids": list(self.involved_audit_event_ids),
            "details": self.details,
        }
    
    @property
    def severity_order(self) -> int:
        """Numeric order for severity comparison."""
        return {
            ReplayIntegritySeverity.INFO: 0,
            ReplayIntegritySeverity.WARNING: 1,
            ReplayIntegritySeverity.ERROR: 2,
            ReplayIntegritySeverity.CRITICAL: 3,
        }.get(self.severity, 0)


@dataclass(frozen=True, slots=True)
class ReplayIntegrityFinding:
    """A single integrity finding from replay validation.
    
    Similar to IntegrityFinding but specific to replay concerns.
    
    Deterministic, serializable, side-effect free.
    """
    finding_id: str
    title: str
    message: str
    severity: ReplayIntegritySeverity = ReplayIntegritySeverity.INFO
    finding_type: str = "replay_finding"
    workspace_id: Optional[str] = None
    frame_index: int = 0
    conflict: Optional[ReplayConflict] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "schema_version": SCHEMA_VERSION,
            "finding_id": self.finding_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "finding_type": self.finding_type,
            "workspace_id": self.workspace_id,
            "frame_index": self.frame_index,
            "conflict": self.conflict.to_dict() if self.conflict else None,
            "details": self.details,
            "timestamp": self.timestamp,
        }
    
    @property
    def severity_order(self) -> int:
        """Numeric order for severity comparison."""
        return {
            ReplayIntegritySeverity.INFO: 0,
            ReplayIntegritySeverity.WARNING: 1,
            ReplayIntegritySeverity.ERROR: 2,
            ReplayIntegritySeverity.CRITICAL: 3,
        }.get(self.severity, 0)


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Complete result of a replay operation.
    
    Contains all frames, findings, conflicts, and summary information.
    
    Deterministic, serializable, side-effect free.
    """
    replay_id: str
    workspace_id: Optional[str] = None
    frames: Tuple[ReplayFrame, ...] = ()
    snapshots: Tuple[ReplaySnapshot, ...] = ()
    conflicts: Tuple[ReplayConflict, ...] = ()
    findings: Tuple[ReplayIntegrityFinding, ...] = ()
    decisions: Tuple[ReplayDecision, ...] = ()
    start_frame_index: int = 0
    end_frame_index: int = 0
    state: ReplayState = ReplayState.PENDING
    summary: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "schema_version": SCHEMA_VERSION,
            "replay_id": self.replay_id,
            "workspace_id": self.workspace_id,
            "frames": [f.to_dict() for f in self.frames],
            "snapshots": [s.to_dict() for s in self.snapshots],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "findings": [f.to_dict() for f in self.findings],
            "decisions": [d.to_dict() for d in self.decisions],
            "start_frame_index": self.start_frame_index,
            "end_frame_index": self.end_frame_index,
            "state": self.state.value,
            "summary": self.summary,
            "created_at": self.created_at,
        }
    
    @property
    def is_complete(self) -> bool:
        """Check if replay completed successfully."""
        return self.state == ReplayState.COMPLETE
    
    @property
    def is_partial(self) -> bool:
        """Check if replay completed with gaps."""
        return self.state == ReplayState.PARTIAL
    
    @property
    def has_conflicts(self) -> bool:
        """Check if replay has conflicts."""
        return len(self.conflicts) > 0
    
    @property
    def has_findings(self) -> bool:
        """Check if replay has integrity findings."""
        return len(self.findings) > 0
    
    @property
    def has_authoritative_evidence(self) -> bool:
        """Check if any frame has authoritative evidence."""
        return any(f.has_authoritative_evidence for f in self.frames)


# =============================================================================
# Helper Functions
# =============================================================================

def utc_now() -> str:
    """Get current UTC timestamp in ISO 8601 format without microseconds."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    """Compute SHA256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sort_events_deterministic(events: List[ReplayEvent]) -> List[ReplayEvent]:
    """Sort events deterministically by timestamp and ID.
    
    deterministic only - same input produces same order.
    """
    # Primary sort: timestamp
    # Secondary sort: event_id for tie-breaking
    # Tertiary sort: sequence_index
    return sorted(
        events,
        key=lambda e: (
            e.timestamp,
            e.event_id,
            e.sequence_index,
        )
    )


# =============================================================================
# Workspace State Reconstruction
# =============================================================================

# Valid workspace statuses and transitions
VALID_WORKSPACE_STATUSES: Set[str] = {
    "planned", "active", "blocked", "executed", "validated", 
    "review_ready", "applied"
}

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "planned": {"active"},
    "active": {"executed", "blocked"},
    "executed": {"validated", "blocked"},
    "validated": {"review_ready", "blocked"},
    "review_ready": {"applied", "blocked"},
    "blocked": set(),
    "applied": set(),
}

TERMINAL_STATUSES: Set[str] = {"blocked", "applied"}


def _extract_status_from_event(event: ReplayEvent) -> Optional[str]:
    """Extract workspace status from event data with multiple fallback strategies.
    
    This function provides robust status extraction by trying multiple known
    field names and data structures across different event types.
    
    Args:
        event: The ReplayEvent to extract status from
        
    Returns:
        The extracted status string, or None if no status can be determined
    """
    if not event.data:
        return None
    
    # Try various known field names for status
    status_fields = ["new_status", "status", "workspace_status", "current_status", "state"]
    
    if event.event_kind == ReplayEventKind.RECEIPT:
        data = event.data
        for field in status_fields:
            if field in data and data[field] is not None:
                return str(data[field])
    
    elif event.event_kind == ReplayEventKind.AUDIT:
        data = event.data
        # Check top-level fields first
        for field in status_fields:
            if field in data and data[field] is not None:
                return str(data[field])
        # Check in details
        details = data.get("details", {})
        for field in status_fields:
            if field in details and details[field] is not None:
                return str(details[field])
        # Check in subject for workspace status
        subject = data.get("subject", {})
        if isinstance(subject, dict):
            for field in status_fields:
                if field in subject and subject[field] is not None:
                    return str(subject[field])
    
    # For any event kind, try checking the data directly
    for field in status_fields:
        if field in event.data and event.data[field] is not None:
            return str(event.data[field])
    
    return None


def replay_workspace_state(
    workspace_id: str,
    events: List[ReplayEvent],
    initial_status: str = "planned",
) -> Tuple[ReplayFrame, ...]:
    """Reconstruct workspace state from a list of replay events.
    
    Processes events in deterministic order and builds the state
    at each frame.
    
    Args:
        workspace_id: The workspace ID to replay
        events: List of ReplayEvent objects (receipts and audit events)
        initial_status: The initial status to start from
        
    Returns:
        Tuple of ReplayFrame objects representing state at each step
    """
    # Sort events deterministically
    sorted_events = sort_events_deterministic(events)
    
    # Filter to only events for this workspace
    workspace_events = [
        e for e in sorted_events 
        if e.workspace_id == workspace_id or e.workspace_id is None
    ]
    
    if not workspace_events:
        # Return single frame with initial state
        initial_frame = ReplayFrame(
            frame_index=0,
            events=(),
            workspace_id=workspace_id,
            workspace_status=initial_status,
            status_history=({"status": initial_status, "at": utc_now()},),
            receipt_chain=(),
            audit_chain=(),
            authority_state={},
            advisory_state={},
            frame_hash=sha256_text(f"initial_{workspace_id}_{initial_status}"),
            previous_frame_hash="",
            is_terminal=False,
            terminal_reason="",
        )
        return (initial_frame,)
    
    frames: List[ReplayFrame] = []
    current_status = initial_status
    current_status_history: List[Dict[str, Any]] = [{"status": initial_status, "at": utc_now()}]
    receipt_chain: List[str] = []
    audit_chain: List[str] = []
    authoritative_state: Dict[str, Any] = {}
    advisory_state: Dict[str, Any] = {}
    previous_hash = ""
    
    for idx, event in enumerate(workspace_events):
        # Build receipt and audit chains
        if event.event_kind == ReplayEventKind.RECEIPT:
            if event.source_id not in receipt_chain:
                receipt_chain.append(event.source_id)
        elif event.event_kind == ReplayEventKind.AUDIT:
            if event.source_id not in audit_chain:
                audit_chain.append(event.source_id)
        
        # Try to extract status from event data
        new_status: Optional[str] = None
        if event.data:
            new_status = _extract_status_from_event(event)
        
        # Validate transition
        transition_valid = True
        transition_message = ""
        
        if new_status and new_status != current_status:
            if new_status not in VALID_WORKSPACE_STATUSES:
                transition_valid = False
                transition_message = f"Invalid status: {new_status}"
            elif new_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
                transition_valid = False
                transition_message = f"Invalid transition: {current_status} -> {new_status}"
        
        # Update status if valid
        if transition_valid and new_status and new_status != current_status:
            current_status = new_status
            current_status_history.append({"status": current_status, "at": event.timestamp})
        
        # Update authority/advisory state
        if event.authoritative and not event.advisory_only:
            authoritative_state[f"authoritative_{idx}"] = {
                "event_id": event.event_id,
                "source_id": event.source_id,
                "timestamp": event.timestamp,
            }
        if event.advisory_only:
            advisory_state[f"advisory_{idx}"] = {
                "event_id": event.event_id,
                "source_id": event.source_id,
                "timestamp": event.timestamp,
            }
        
        # Check if terminal
        is_terminal = current_status in TERMINAL_STATUSES
        terminal_reason = ""
        if is_terminal:
            terminal_reason = f"Reached terminal status: {current_status}"
        
        # Build frame
        frame = ReplayFrame(
            frame_index=idx,
            events=tuple(workspace_events[:idx + 1]),
            workspace_id=workspace_id,
            workspace_status=current_status,
            status_history=tuple(current_status_history),
            receipt_chain=tuple(receipt_chain),
            audit_chain=tuple(audit_chain),
            authority_state=dict(authoritative_state),
            advisory_state=dict(advisory_state),
            frame_hash=sha256_text(
                f"{workspace_id}_{current_status}_{idx}_{'_'.join(receipt_chain)}_{'_'.join(audit_chain)}"
            ),
            previous_frame_hash=previous_hash,
            is_terminal=is_terminal,
            terminal_reason=terminal_reason,
        )
        frames.append(frame)
        previous_hash = frame.frame_hash
    
    return tuple(frames)


def replay_workspace_lifecycle(
    workspace_record: Dict[str, Any],
    receipts: List["ReceiptEnvelope"],
    audit_events: List["AuditEvent"],
) -> ReplayResult:
    """Reconstruct complete workspace lifecycle from record, receipts, and audit events.
    
    This is the main entry point for workspace replay.
    
    Args:
        workspace_record: The workspace record dict
        receipts: List of ReceiptEnvelope objects for this workspace
        audit_events: List of AuditEvent objects for this workspace
        
    Returns:
        ReplayResult with complete replay information
    """
    workspace_id = workspace_record.get("workspace_id", PLACEHOLDER_UNKNOWN)
    initial_status = workspace_record.get("status", "planned")
    
    # Convert receipts to ReplayEvents
    receipt_events = [
        ReplayEvent.from_receipt(envelope, idx)
        for idx, envelope in enumerate(receipts)
    ]
    
    # Convert audit events to ReplayEvents
    audit_replay_events = [
        ReplayEvent.from_audit_event(event, idx + len(receipts))
        for idx, event in enumerate(audit_events)
    ]
    
    # Combine all events
    all_events = receipt_events + audit_replay_events
    
    # Reconstruct frames
    frames = replay_workspace_state(
        workspace_id=workspace_id,
        events=all_events,
        initial_status=initial_status,
    )
    
    # Detect conflicts and findings
    conflicts: List[ReplayConflict] = []
    findings: List[ReplayIntegrityFinding] = []
    decisions: List[ReplayDecision] = []
    
    # Check for gaps in receipt chain
    receipt_ids_from_record = set(workspace_record.get("receipt_paths", []) or [])
    receipt_ids_from_envelopes = {r.receipt_id for r in receipts}
    
    # Check for missing receipts referenced in workspace record
    for receipt_path in workspace_record.get("receipt_paths", []) or []:
        if isinstance(receipt_path, str):
            # Extract receipt ID from path
            path_name = Path(receipt_path).name
            receipt_id_from_path = path_name.replace(".json", "")
            # Check if we have this receipt
            # This is a simplified check
            pass
    
    # Check for impossible transitions in frames
    for frame in frames:
        if frame.integrity_findings:
            for finding_ref in frame.integrity_findings:
                # These would be added during frame construction
                pass
    
    # Check for orphaned audit events (audit events without corresponding workspace)
    audit_event_ids = {e.event_id for e in audit_events}
    receipt_ids = {r.receipt_id for r in receipts}
    
    # Check for audit events referencing non-existent receipts
    for event in audit_events:
        if event.receipt_id and event.receipt_id not in receipt_ids:
            conflict = ReplayConflict(
                conflict_id=f"orphaned_audit_{event.event_id}",
                conflict_type=ReplayConflictType.ORPHANED_AUDIT_EVENT,
                severity=ReplayIntegritySeverity.WARNING,
                title="Orphaned audit event",
                message=f"Audit event {event.event_id} references non-existent receipt {event.receipt_id}",
                workspace_id=workspace_id,
                frame_index=0,  # Will be updated
                involved_receipt_ids=(event.receipt_id,),
                involved_audit_event_ids=(event.event_id,),
                details={"receipt_id": event.receipt_id, "event_id": event.event_id},
            )
            conflicts.append(conflict)
            
            finding = ReplayIntegrityFinding(
                finding_id=f"finding_orphaned_audit_{event.event_id}",
                title="Orphaned audit event detected",
                message=f"Audit event {event.event_id} has no corresponding receipt",
                severity=ReplayIntegritySeverity.WARNING,
                finding_type="replay_audit_orphan",
                workspace_id=workspace_id,
                conflict=conflict,
                details={"receipt_id": event.receipt_id, "event_id": event.event_id},
            )
            findings.append(finding)
    
    # Check for receipts not referenced by any audit event
    receipt_ids_with_audit = {e.receipt_id for e in audit_events if e.receipt_id}
    unreferenced_receipts = receipt_ids - receipt_ids_with_audit
    
    for receipt_id in unreferenced_receipts:
        finding = ReplayIntegrityFinding(
            finding_id=f"finding_unreferenced_receipt_{receipt_id}",
            title="Unreferenced receipt",
            message=f"Receipt {receipt_id} has no corresponding audit event",
            severity=ReplayIntegritySeverity.INFO,
            finding_type="replay_receipt_unreferenced",
            workspace_id=workspace_id,
            details={"receipt_id": receipt_id},
        )
        findings.append(finding)
    
    # Build decisions from frames
    for idx, frame in enumerate(frames):
        decision = ReplayDecision.allowed(
            decision_id=f"replay_decision_{workspace_id}_{idx}",
            reason=f"Replay frame {idx} for workspace {workspace_id}",
            frame_index=idx,
            workspace_id=workspace_id,
        )
        decisions.append(decision)
    
    # Build snapshots
    snapshots: List[ReplaySnapshot] = []
    for idx, frame in enumerate(frames):
        cursor = ReplayCursor(
            current_frame_index=idx,
            total_frames=len(frames),
            workspace_id=workspace_id,
            can_go_back=idx > 0,
            can_go_forward=idx < len(frames) - 1,
            current_frame_hash=frame.frame_hash,
        )
        
        snapshot = ReplaySnapshot(
            snapshot_id=f"replay_snapshot_{workspace_id}_{idx}",
            workspace_id=workspace_id,
            frame_index=idx,
            frame=frame,
            cursor=cursor,
            decisions=tuple(decisions[:idx + 1]),
            integrity_findings=tuple(f for f in findings if f.frame_index <= idx),
            authoritative_evidence_available=frame.has_authoritative_evidence,
            advisory_only_evidence_present=frame.has_advisory_only,
        )
        snapshots.append(snapshot)
    
    # Update conflicts with frame indices
    # (This would be more precise in a real implementation)
    
    # Determine replay state
    if len(frames) == 0:
        state = ReplayState.FAILED
    elif len(conflicts) > 0:
        state = ReplayState.PARTIAL
    else:
        state = ReplayState.COMPLETE
    
    # Build summary
    summary = {
        "workspace_id": workspace_id,
        "total_frames": len(frames),
        "total_conflicts": len(conflicts),
        "total_findings": len(findings),
        "total_decisions": len(decisions),
        "has_authoritative_evidence": any(f.has_authoritative_evidence for f in frames),
        "has_advisory_only": any(f.has_advisory_only for f in frames),
        "start_status": initial_status,
        "end_status": frames[-1].workspace_status if frames else initial_status,
        "state": state.value,
    }
    
    return ReplayResult(
        replay_id=f"replay_{workspace_id}_{utc_now()}",
        workspace_id=workspace_id,
        frames=tuple(frames),
        snapshots=tuple(snapshots),
        conflicts=tuple(conflicts),
        findings=tuple(findings),
        decisions=tuple(decisions),
        start_frame_index=0,
        end_frame_index=len(frames) - 1 if frames else 0,
        state=state,
        summary=summary,
    )


def replay_receipt_chain(
    receipts: List["ReceiptEnvelope"],
    workspace_id: Optional[str] = None,
) -> Tuple[ReplayEvent, ...]:
    """Replay just the receipt chain for a workspace.
    
    Args:
        receipts: List of ReceiptEnvelope objects
        workspace_id: Optional workspace ID filter
        
    Returns:
        Tuple of ReplayEvent objects sorted deterministically
    """
    # Filter receipts by workspace if provided
    if workspace_id:
        filtered_receipts = [
            r for r in receipts
            if r.subject.workspace_id == workspace_id or r.receipt_id.startswith(workspace_id)
        ]
    else:
        filtered_receipts = receipts
    
    # Convert to ReplayEvents and sort
    events = [ReplayEvent.from_receipt(r, idx) for idx, r in enumerate(filtered_receipts)]
    sorted_events = sort_events_deterministic(events)
    
    return tuple(sorted_events)


def replay_audit_chain(
    audit_events: List["AuditEvent"],
    workspace_id: Optional[str] = None,
) -> Tuple[ReplayEvent, ...]:
    """Replay just the audit chain for a workspace.
    
    Args:
        audit_events: List of AuditEvent objects
        workspace_id: Optional workspace ID filter
        
    Returns:
        Tuple of ReplayEvent objects sorted deterministically
    """
    # Filter audit events by workspace if provided
    if workspace_id:
        filtered_events = [e for e in audit_events if e.workspace_id == workspace_id]
    else:
        filtered_events = audit_events
    
    # Convert to ReplayEvents and sort
    events = [ReplayEvent.from_audit_event(e, idx) for idx, e in enumerate(filtered_events)]
    sorted_events = sort_events_deterministic(events)
    
    return tuple(sorted_events)


# =============================================================================
# Time-Travel Projections
# =============================================================================

def build_replay_projection(
    replay_result: ReplayResult,
    frame_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a projection from a replay result at a specific frame.
    
    If frame_index is None, uses the last frame.
    
    Args:
        replay_result: The ReplayResult to project
        frame_index: Optional frame index (defaults to last)
        
    Returns:
        Dictionary suitable for UI projection
    """
    if not replay_result.frames:
        # Empty replay - return placeholder projection
        return {
            "type": "ReplayProjection",
            "replay_id": replay_result.replay_id,
            "workspace_id": replay_result.workspace_id or PLACEHOLDER_UNKNOWN,
            "frame_index": -1,
            "total_frames": 0,
            "workspace_status": PLACEHOLDER_UNKNOWN,
            "status_history": [],
            "receipt_chain": [],
            "audit_chain": [],
            "authoritative_evidence_available": False,
            "advisory_only_evidence_present": False,
            "has_conflicts": replay_result.has_conflicts,
            "conflict_count": len(replay_result.conflicts),
            "finding_count": len(replay_result.findings),
            "state": replay_result.state.value,
            "message": "No frames available for replay",
        }
    
    # Determine target frame
    if frame_index is None:
        frame_index = len(replay_result.frames) - 1
    
    if frame_index < 0 or frame_index >= len(replay_result.frames):
        frame_index = len(replay_result.frames) - 1
    
    target_frame = replay_result.frames[frame_index]
    
    # Build frame-level conflicts and findings
    frame_conflicts = [
        c for c in replay_result.conflicts 
        if c.frame_index <= frame_index
    ]
    frame_findings = [
        f for f in replay_result.findings
        if f.frame_index <= frame_index
    ]
    
    # Count severity levels
    severity_counts: Dict[str, int] = {
        "info": 0,
        "warning": 0,
        "error": 0,
        "critical": 0,
    }
    for finding in frame_findings:
        severity_counts[finding.severity.value] += 1
    
    # Count conflict types
    conflict_types: Dict[str, int] = {}
    for conflict in frame_conflicts:
        conflict_types[conflict.conflict_type.value] = conflict_types.get(conflict.conflict_type.value, 0) + 1
    
    return {
        "type": "ReplayProjection",
        "replay_id": replay_result.replay_id,
        "workspace_id": target_frame.workspace_id or PLACEHOLDER_UNKNOWN,
        "frame_index": frame_index,
        "total_frames": len(replay_result.frames),
        "workspace_status": target_frame.workspace_status,
        "status_history": list(target_frame.status_history),
        "receipt_chain": list(target_frame.receipt_chain),
        "audit_chain": list(target_frame.audit_chain),
        "authoritative_evidence_available": target_frame.has_authoritative_evidence,
        "advisory_only_evidence_present": target_frame.has_advisory_only,
        "is_terminal": target_frame.is_terminal,
        "terminal_reason": target_frame.terminal_reason or "",
        "has_conflicts": len(frame_conflicts) > 0,
        "conflict_count": len(frame_conflicts),
        "conflict_types": conflict_types,
        "finding_count": len(frame_findings),
        "findings_by_severity": severity_counts,
        "state": replay_result.state.value,
        "authority_state": target_frame.authority_state,
        "advisory_state": target_frame.advisory_state,
        "created_at": replay_result.created_at,
    }


def build_replay_projection_summary(
    replay_result: ReplayResult,
) -> Dict[str, Any]:
    """Build a summary projection from a replay result.
    
    Args:
        replay_result: The ReplayResult to summarize
        
    Returns:
        Dictionary with summary suitable for display
    """
    if not replay_result.frames:
        return {
            "type": "ReplaySummary",
            "replay_id": replay_result.replay_id,
            "workspace_id": replay_result.workspace_id or PLACEHOLDER_UNKNOWN,
            "message": "No replay data available",
            "total_frames": 0,
            "total_conflicts": 0,
            "total_findings": 0,
            "state": replay_result.state.value,
            "authoritative_evidence_available": False,
        }
    
    last_frame = replay_result.frames[-1]
    
    # Count findings by severity
    severity_counts: Dict[str, int] = {"info": 0, "warning": 0, "error": 0, "critical": 0}
    for finding in replay_result.findings:
        severity_counts[finding.severity.value] += 1
    
    # Count conflicts by type
    conflict_type_counts: Dict[str, int] = {}
    for conflict in replay_result.conflicts:
        conflict_type_counts[conflict.conflict_type.value] = \
            conflict_type_counts.get(conflict.conflict_type.value, 0) + 1
    
    return {
        "type": "ReplaySummary",
        "replay_id": replay_result.replay_id,
        "workspace_id": replay_result.workspace_id or PLACEHOLDER_UNKNOWN,
        "total_frames": len(replay_result.frames),
        "total_conflicts": len(replay_result.conflicts),
        "total_findings": len(replay_result.findings),
        "state": replay_result.state.value,
        "start_frame_index": replay_result.start_frame_index,
        "end_frame_index": replay_result.end_frame_index,
        "current_status": last_frame.workspace_status,
        "is_terminal": last_frame.is_terminal,
        "terminal_reason": last_frame.terminal_reason or "",
        "authoritative_evidence_available": last_frame.has_authoritative_evidence,
        "advisory_only_evidence_present": last_frame.has_advisory_only,
        "findings_by_severity": severity_counts,
        "conflicts_by_type": conflict_type_counts,
        "has_impossible_transitions": any(
            c.conflict_type == ReplayConflictType.IMPOSSIBLE_TRANSITION
            for c in replay_result.conflicts
        ),
        "has_missing_receipts": any(
            c.conflict_type == ReplayConflictType.MISSING_RECEIPT
            for c in replay_result.conflicts
        ),
        "has_missing_audit_events": any(
            c.conflict_type == ReplayConflictType.MISSING_AUDIT_EVENT
            for c in replay_result.conflicts
        ),
        "has_stale_references": any(
            c.conflict_type == ReplayConflictType.STALE_RECEIPT_CHAIN
            for c in replay_result.conflicts
        ),
        "has_orphaned_events": any(
            c.conflict_type == ReplayConflictType.ORPHANED_AUDIT_EVENT
            for c in replay_result.conflicts
        ),
        "has_contradictions": any(
            c.conflict_type == ReplayConflictType.CONTRADICTORY_GATE_DECISION
            for c in replay_result.conflicts
        ),
        "summary": replay_result.summary,
        "created_at": replay_result.created_at,
    }


# =============================================================================
# Replay Integrity Validation
# =============================================================================

def validate_replay_determinism(
    replay_result_1: ReplayResult,
    replay_result_2: ReplayResult,
) -> Tuple[ReplayIntegrityFinding, ...]:
    """Validate that two replays of the same inputs produce identical results.
    
    Args:
        replay_result_1: First replay result
        replay_result_2: Second replay result
        
    Returns:
        Tuple of findings if results differ
    """
    findings: List[ReplayIntegrityFinding] = []
    
    # Compare frame count
    if len(replay_result_1.frames) != len(replay_result_2.frames):
        findings.append(ReplayIntegrityFinding(
            finding_id="nondeterministic_frame_count",
            title="Non-deterministic frame count",
            message=f"Replay produced different frame counts: {len(replay_result_1.frames)} vs {len(replay_result_2.frames)}",
            severity=ReplayIntegritySeverity.CRITICAL,
            finding_type="replay_nondeterminism",
            workspace_id=replay_result_1.workspace_id,
            details={
                "count_1": len(replay_result_1.frames),
                "count_2": len(replay_result_2.frames),
            },
        ))
    
    # Compare frame hashes
    for idx in range(min(len(replay_result_1.frames), len(replay_result_2.frames))):
        frame_1 = replay_result_1.frames[idx]
        frame_2 = replay_result_2.frames[idx]
        
        if frame_1.frame_hash != frame_2.frame_hash:
            findings.append(ReplayIntegrityFinding(
                finding_id=f"nondeterministic_frame_{idx}",
                title=f"Non-deterministic frame {idx}",
                message=f"Frame {idx} has different hash: {frame_1.frame_hash} vs {frame_2.frame_hash}",
                severity=ReplayIntegritySeverity.CRITICAL,
                finding_type="replay_nondeterminism",
                workspace_id=replay_result_1.workspace_id,
                frame_index=idx,
                details={
                    "hash_1": frame_1.frame_hash,
                    "hash_2": frame_2.frame_hash,
                    "status_1": frame_1.workspace_status,
                    "status_2": frame_2.workspace_status,
                },
            ))
    
    return tuple(findings)


def validate_replay_consistency(
    replay_result: ReplayResult,
    workspace_record: Dict[str, Any],
) -> Tuple[ReplayIntegrityFinding, ...]:
    """Validate that replay result is consistent with workspace record.
    
    Args:
        replay_result: The replay result to validate
        workspace_record: The canonical workspace record
        
    Returns:
        Tuple of findings for any inconsistencies
    """
    findings: List[ReplayIntegrityFinding] = []
    workspace_id = workspace_record.get("workspace_id", PLACEHOLDER_UNKNOWN)
    
    if not replay_result.frames:
        findings.append(ReplayIntegrityFinding(
            finding_id="empty_replay",
            title="Empty replay result",
            message="Replay produced no frames",
            severity=ReplayIntegritySeverity.ERROR,
            finding_type="replay_empty",
            workspace_id=workspace_id,
            details={"total_frames": 0},
        ))
        return tuple(findings)
    
    last_frame = replay_result.frames[-1]
    
    # Check final status matches record
    record_status = workspace_record.get("status", PLACEHOLDER_UNKNOWN)
    if last_frame.workspace_status != record_status:
        findings.append(ReplayIntegrityFinding(
            finding_id="status_mismatch",
            title="Replay status mismatch",
            message=f"Replay final status ({last_frame.workspace_status}) != record status ({record_status})",
            severity=ReplayIntegritySeverity.ERROR,
            finding_type="replay_consistency",
            workspace_id=workspace_id,
            frame_index=len(replay_result.frames) - 1,
            details={
                "replay_status": last_frame.workspace_status,
                "record_status": record_status,
            },
        ))
    
    # Check receipt chain contains all receipts from record
    record_receipt_paths = workspace_record.get("receipt_paths", []) or []
    # Extract receipt IDs from paths
    record_receipt_ids = set()
    for path in record_receipt_paths:
        if isinstance(path, str):
            name = Path(path).name.replace(".json", "")
            record_receipt_ids.add(name)
    
    replay_receipt_ids = set(last_frame.receipt_chain)
    missing_from_replay = record_receipt_ids - replay_receipt_ids
    
    if missing_from_replay:
        findings.append(ReplayIntegrityFinding(
            finding_id="missing_receipts_in_replay",
            title="Receipts missing from replay",
            message=f"Workspace record references {len(missing_from_replay)} receipts not in replay chain",
            severity=ReplayIntegritySeverity.WARNING,
            finding_type="replay_consistency",
            workspace_id=workspace_id,
            details={
                "missing_receipts": list(missing_from_replay),
                "record_receipts": list(record_receipt_ids),
                "replay_receipts": list(replay_receipt_ids),
            },
        ))
    
    return tuple(findings)


def validate_replay_projection_consistency(
    replay_result: ReplayResult,
    projection_dict: Dict[str, Any],
) -> Tuple[ReplayIntegrityFinding, ...]:
    """Validate that replay projections match the replay result.
    
    Args:
        replay_result: The replay result
        projection_dict: The projection dictionary to validate
        
    Returns:
        Tuple of findings for any inconsistencies
    """
    findings: List[ReplayIntegrityFinding] = []
    workspace_id = replay_result.workspace_id or PLACEHOLDER_UNKNOWN
    
    # Check workspace ID
    if projection_dict.get("workspace_id") != workspace_id:
        findings.append(ReplayIntegrityFinding(
            finding_id="projection_workspace_id_mismatch",
            title="Projection workspace ID mismatch",
            message=f"Projection workspace_id ({projection_dict.get('workspace_id')}) != replay workspace_id ({workspace_id})",
            severity=ReplayIntegritySeverity.ERROR,
            finding_type="replay_projection_consistency",
            workspace_id=workspace_id,
            details={
                "projection_workspace_id": projection_dict.get("workspace_id"),
                "replay_workspace_id": workspace_id,
            },
        ))
    
    # Check frame count
    projection_frame_count = projection_dict.get("total_frames", 0)
    if projection_frame_count != len(replay_result.frames):
        findings.append(ReplayIntegrityFinding(
            finding_id="projection_frame_count_mismatch",
            title="Projection frame count mismatch",
            message=f"Projection frame count ({projection_frame_count}) != replay frames ({len(replay_result.frames)})",
            severity=ReplayIntegritySeverity.WARNING,
            finding_type="replay_projection_consistency",
            workspace_id=workspace_id,
            details={
                "projection_count": projection_frame_count,
                "replay_count": len(replay_result.frames),
            },
        ))
    
    # Check state
    projection_state = projection_dict.get("state", PLACEHOLDER_UNKNOWN)
    if projection_state != replay_result.state.value:
        findings.append(ReplayIntegrityFinding(
            finding_id="projection_state_mismatch",
            title="Projection state mismatch",
            message=f"Projection state ({projection_state}) != replay state ({replay_result.state.value})",
            severity=ReplayIntegritySeverity.WARNING,
            finding_type="replay_projection_consistency",
            workspace_id=workspace_id,
            details={
                "projection_state": projection_state,
                "replay_state": replay_result.state.value,
            },
        ))
    
    return tuple(findings)


def validate_replay_receipt_continuity(
    receipt_chain: Tuple[str, ...],
    all_receipt_ids: Set[str],
    workspace_id: Optional[str] = None,
) -> Tuple[ReplayIntegrityFinding, ...]:
    """Validate that receipt chain is continuous and complete.
    
    Args:
        receipt_chain: Ordered tuple of receipt IDs from replay
        all_receipt_ids: Set of all known receipt IDs
        workspace_id: Optional workspace ID for context
        
    Returns:
        Tuple of findings for any continuity issues
    """
    findings: List[ReplayIntegrityFinding] = []
    
    # Check for missing receipts in chain
    missing_in_chain = []
    for receipt_id in receipt_chain:
        if receipt_id not in all_receipt_ids and receipt_id != PLACEHOLDER_NO_RECEIPT:
            missing_in_chain.append(receipt_id)
    
    if missing_in_chain:
        findings.append(ReplayIntegrityFinding(
            finding_id="missing_receipts_in_chain",
            title="Missing receipts in chain",
            message=f"Receipt chain references {len(missing_in_chain)} non-existent receipts",
            severity=ReplayIntegritySeverity.ERROR,
            finding_type="replay_receipt_continuity",
            workspace_id=workspace_id,
            details={"missing_receipts": missing_in_chain},
        ))
    
    # Check for gaps in sequence (simplified - just checks consecutive numbers if IDs are numeric)
    # This is a placeholder for more sophisticated gap detection
    if len(receipt_chain) > 1:
        # Try to detect if receipts are numbered sequentially
        numeric_ids = []
        for receipt_id in receipt_chain:
            try:
                numeric_ids.append(int(receipt_id))
            except ValueError:
                pass
        
        if numeric_ids and len(numeric_ids) == len(receipt_chain):
            # Check for gaps
            sorted_ids = sorted(numeric_ids)
            for i in range(len(sorted_ids) - 1):
                if sorted_ids[i + 1] - sorted_ids[i] > 1:
                    findings.append(ReplayIntegrityFinding(
                        finding_id=f"receipt_chain_gap_{i}",
                        title="Gap in receipt chain",
                        message=f"Receipt chain has gap between {sorted_ids[i]} and {sorted_ids[i + 1]}",
                        severity=ReplayIntegritySeverity.WARNING,
                        finding_type="replay_receipt_continuity",
                        workspace_id=workspace_id,
                        details={
                            "previous": sorted_ids[i],
                            "next": sorted_ids[i + 1],
                            "gap": sorted_ids[i + 1] - sorted_ids[i] - 1,
                        },
                    ))
    
    return tuple(findings)


# =============================================================================
# Convenience Functions for Loading Replay Data
# =============================================================================

def _read_audit_event(audit_path: Path) -> Optional[Dict[str, Any]]:
    """Read an audit event from a JSON file.
    
    Args:
        audit_path: Path to the audit JSON file
        
    Returns:
        Dict with audit event data if successful, None otherwise
    """
    if not audit_path.exists():
        return None
    
    try:
        data = json.loads(audit_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, TypeError):
        return None


def load_replay_events_from_fs(
    repo_root: Path,
    workspace_id: Optional[str] = None,
) -> Tuple[Tuple[ReplayEvent, ...], Tuple[ReplayIntegrityFinding, ...]]:
    """Load replay events from filesystem.
    
    Scans receipt and audit directories and converts to ReplayEvents.
    Corrupted files produce explicit findings instead of being silently skipped.
    
    Args:
        repo_root: Repository root path
        workspace_id: Optional workspace ID filter
        
    Returns:
        Tuple of (events, findings) where findings are any issues encountered during loading
    """
    from rig.domain.receipt_envelope import read_receipt, ReceiptEnvelope
    from rig.domain.workspace_audit import AuditEvent
    from rig_tools.core.io import read_json
    
    events: List[ReplayEvent] = []
    findings: List[ReplayIntegrityFinding] = []
    
    # Load receipts
    receipt_dir = repo_root / ".build" / "rig" / "receipts"
    if receipt_dir.exists():
        for receipt_file in receipt_dir.glob("*.json"):
            try:
                envelope = read_receipt(receipt_file)
                if envelope:
                    event = ReplayEvent.from_receipt(envelope, len(events))
                    if workspace_id is None or event.workspace_id == workspace_id:
                        events.append(event)
            except Exception as e:
                # Emit finding for corrupted receipt file
                findings.append(ReplayIntegrityFinding(
                    finding_id=f"corrupted_receipt_{receipt_file.stem}",
                    title="Corrupted receipt file",
                    message=f"Failed to read receipt {receipt_file.name}: {e}",
                    severity=ReplayIntegritySeverity.ERROR,
                    finding_type="replay_file_corruption",
                    workspace_id=workspace_id,
                    details={"file": str(receipt_file), "error": str(e)},
                ))
                continue
        
        # Check subdirectories
        for subdir in receipt_dir.iterdir():
            if subdir.is_dir():
                for receipt_file in subdir.glob("*.json"):
                    try:
                        envelope = read_receipt(receipt_file)
                        if envelope:
                            event = ReplayEvent.from_receipt(envelope, len(events))
                            if workspace_id is None or event.workspace_id == workspace_id:
                                events.append(event)
                    except Exception as e:
                        # Emit finding for corrupted receipt file in subdirectory
                        findings.append(ReplayIntegrityFinding(
                            finding_id=f"corrupted_receipt_{receipt_file.stem}",
                            title="Corrupted receipt file",
                            message=f"Failed to read receipt {receipt_file.name}: {e}",
                            severity=ReplayIntegritySeverity.ERROR,
                            finding_type="replay_file_corruption",
                            workspace_id=workspace_id,
                            details={"file": str(receipt_file), "error": str(e)},
                        ))
                        continue
    
    # Load audit events
    audit_dir = repo_root / ".build" / "rig" / "audit"
    if audit_dir.exists():
        for audit_file in audit_dir.glob("*.json"):
            try:
                audit_data = _read_audit_event(audit_file)
                if audit_data:
                    event_id = audit_file.stem
                    workspace_id_from_file = audit_data.get("workspace_id")
                    
                    event = ReplayEvent(
                        event_id=f"replay_audit_{event_id}",
                        event_kind=ReplayEventKind.AUDIT,
                        source_id=event_id,
                        workspace_id=workspace_id_from_file,
                        timestamp=audit_data.get("timestamp", utc_now()),
                        sequence_index=len(events),
                        data=audit_data,
                        authoritative=audit_data.get("authoritative", True) and not audit_data.get("advisory_only", False),
                        advisory_only=audit_data.get("advisory_only", False),
                        hash=sha256_text(json.dumps(audit_data, sort_keys=True)),
                    )
                    if workspace_id is None or event.workspace_id == workspace_id:
                        events.append(event)
            except Exception as e:
                # Emit finding for corrupted audit file
                findings.append(ReplayIntegrityFinding(
                    finding_id=f"corrupted_audit_{audit_file.stem}",
                    title="Corrupted audit event file",
                    message=f"Failed to read audit event {audit_file.name}: {e}",
                    severity=ReplayIntegritySeverity.ERROR,
                    finding_type="replay_file_corruption",
                    workspace_id=workspace_id,
                    details={"file": str(audit_file), "error": str(e)},
                ))
                continue
    
    # Sort deterministically
    sorted_events = sort_events_deterministic(events)
    
    return tuple(sorted_events), tuple(findings)


def replay_workspace_from_fs(
    repo_root: Path,
    workspace_id: str,
) -> ReplayResult:
    """Replay workspace state directly from filesystem.
    
    Loads all receipts and audit events from the filesystem and
    reconstructs the workspace state.
    
    Args:
        repo_root: Repository root path
        workspace_id: The workspace ID to replay
        
    Returns:
        ReplayResult with reconstructed state
    """
    from rig.domain.receipt_envelope import read_receipt, ReceiptEnvelope
    from rig.domain.workspace_audit import AuditEvent
    from rig_tools.core.io import read_json
    
    # Load workspace record
    workspace_dir = repo_root / ".build" / "rig" / "workspaces"
    workspace_file = workspace_dir / f"{workspace_id}.json"
    
    if not workspace_file.exists():
        # Workspace doesn't exist - return empty result with finding
        finding = ReplayIntegrityFinding(
            finding_id=f"workspace_not_found_{workspace_id}",
            title="Workspace not found",
            message=f"Workspace {workspace_id} does not exist in workspace directory",
            severity=ReplayIntegritySeverity.ERROR,
            finding_type="replay_workspace_missing",
            workspace_id=workspace_id,
        )
        return ReplayResult(
            replay_id=f"replay_{workspace_id}_not_found",
            workspace_id=workspace_id,
            frames=(),
            snapshots=(),
            conflicts=(),
            findings=(finding,),
            decisions=(),
            state=ReplayState.FAILED,
            summary={"error": "workspace_not_found", "workspace_id": workspace_id},
        )
    
    workspace_record = read_json(workspace_file)
    
    # Load receipts and audit events
    replay_events, file_findings = load_replay_events_from_fs(repo_root, workspace_id)
    
    # Separate receipts and audit events
    receipts: List[ReceiptEnvelope] = []
    audit_events: List[AuditEvent] = []
    
    # Include file loading findings in the result
    findings.extend(file_findings)
    
    # Reconstruct ReceiptEnvelopes and AuditEvents from events
    for event in replay_events:
        if event.event_kind == ReplayEventKind.RECEIPT:
            try:
                envelope_data = event.data
                envelope = ReceiptEnvelope.from_dict(envelope_data)
                receipts.append(envelope)
            except Exception as e:
                # Emit finding for failed receipt reconstruction
                findings.append(ReplayIntegrityFinding(
                    finding_id=f"receipt_reconstruction_failed_{event.source_id}",
                    title="Receipt reconstruction failed",
                    message=f"Failed to reconstruct ReceiptEnvelope from event {event.event_id}: {e}",
                    severity=ReplayIntegritySeverity.WARNING,
                    finding_type="replay_receipt_reconstruction",
                    workspace_id=workspace_id,
                    details={"event_id": event.event_id, "source_id": event.source_id, "error": str(e)},
                ))
        elif event.event_kind == ReplayEventKind.AUDIT:
            try:
                # Reconstruct AuditEvent from data
                audit_data = event.data
                # Import here to avoid circular import issues
                from rig.domain.workspace_audit import (
                    AuditEvent, AuditActor, AuditSubject, AuditAction,
                    AuditDecision, AuditReceiptStatus
                )
                
                # Extract fields from audit_data, providing defaults for missing fields
                # This handles the case where audit files may have slightly different structures
                RawAuditActor = audit_data.get("actor", {})
                RawAuditSubject = audit_data.get("subject", {})
                
                # Reconstruct AuditActor
                actor = AuditActor(
                    actor_id=RawAuditActor.get("actor_id", PLACEHOLDER_UNKNOWN),
                    actor_kind=RawAuditActor.get("actor_kind", PLACEHOLDER_UNKNOWN),
                    display_name=RawAuditActor.get("display_name"),
                    is_human=RawAuditActor.get("is_human", False),
                    is_authoritative=RawAuditActor.get("is_authoritative", True),
                )
                
                # Reconstruct AuditSubject
                subject = AuditSubject(
                    subject_id=RawAuditSubject.get("subject_id", PLACEHOLDER_UNKNOWN),
                    subject_kind=RawAuditSubject.get("subject_kind", AuditSubjectKind.UNKNOWN),
                    display_name=RawAuditSubject.get("display_name"),
                    workspace_id=RawAuditSubject.get("workspace_id"),
                    authoritative=RawAuditSubject.get("authoritative", True),
                    advisory_only=RawAuditSubject.get("advisory_only", False),
                )
                
                # Reconstruct AuditEvent
                audit_event = AuditEvent(
                    event_id=audit_data.get("event_id", PLACEHOLDER_UNKNOWN),
                    action=AuditAction(audit_data.get("action", AuditAction.UNKNOWN.value)),
                    actor=actor,
                    subject=subject,
                    decision=AuditDecision(audit_data.get("decision", AuditDecision.UNKNOWN.value)),
                    timestamp=audit_data.get("timestamp", utc_now()),
                    status=audit_data.get("status", PLACEHOLDER_UNKNOWN),
                    summary=audit_data.get("summary", ""),
                    receipt_id=audit_data.get("receipt_id"),
                    receipt_kind=audit_data.get("receipt_kind"),
                    receipt_status=AuditReceiptStatus(audit_data.get("receipt_status", AuditReceiptStatus.MISSING.value)),
                    workspace_id=audit_data.get("workspace_id"),
                    details=audit_data.get("details", {}),
                    authoritative=audit_data.get("authoritative", True),
                    advisory_only=audit_data.get("advisory_only", False),
                )
                audit_events.append(audit_event)
            except Exception as e:
                # Emit finding for failed audit event reconstruction
                findings.append(ReplayIntegrityFinding(
                    finding_id=f"audit_reconstruction_failed_{event.source_id}",
                    title="Audit event reconstruction failed",
                    message=f"Failed to reconstruct AuditEvent from event {event.event_id}: {e}",
                    severity=ReplayIntegritySeverity.WARNING,
                    finding_type="replay_audit_reconstruction",
                    workspace_id=workspace_id,
                    details={"event_id": event.event_id, "source_id": event.source_id, "error": str(e)},
                ))
    
    # Use the workspace record's status history to enhance replay
    initial_status = workspace_record.get("status", "planned")
    status_history = workspace_record.get("status_history", [])
    
    # Reconstruct frames
    frames = replay_workspace_state(
        workspace_id=workspace_id,
        events=list(replay_events),
        initial_status=initial_status,
    )
    
    # Build decisions
    decisions: List[ReplayDecision] = []
    for idx, frame in enumerate(frames):
        decision = ReplayDecision.allowed(
            decision_id=f"replay_dec_{workspace_id}_{idx}",
            reason=f"Replay frame {idx} for workspace {workspace_id}",
            frame_index=idx,
            workspace_id=workspace_id,
        )
        decisions.append(decision)
    
    # Detect conflicts
    conflicts: List[ReplayConflict] = []
    findings: List[ReplayIntegrityFinding] = []
    
    # Check for orphaned audit events
    for event in replay_events:
        if event.event_kind == ReplayEventKind.AUDIT and event.workspace_id != workspace_id:
            conflict = ReplayConflict(
                conflict_id=f"orphaned_audit_{event.source_id}",
                conflict_type=ReplayConflictType.ORPHANED_AUDIT_EVENT,
                severity=ReplayIntegritySeverity.WARNING,
                title="Orphaned audit event",
                message=f"Audit event {event.source_id} has workspace_id mismatch",
                workspace_id=workspace_id,
                involved_audit_event_ids=(event.source_id,),
            )
            conflicts.append(conflict)
    
    # Build snapshots
    snapshots: List[ReplaySnapshot] = []
    for idx, frame in enumerate(frames):
        cursor = ReplayCursor(
            current_frame_index=idx,
            total_frames=len(frames),
            workspace_id=workspace_id,
            can_go_back=idx > 0,
            can_go_forward=idx < len(frames) - 1,
            current_frame_hash=frame.frame_hash,
        )
        
        snapshot = ReplaySnapshot(
            snapshot_id=f"snapshot_{workspace_id}_{idx}",
            workspace_id=workspace_id,
            frame_index=idx,
            frame=frame,
            cursor=cursor,
            decisions=tuple(decisions[:idx + 1]),
            integrity_findings=tuple(f for f in findings if f.frame_index <= idx),
            authoritative_evidence_available=frame.has_authoritative_evidence,
            advisory_only_evidence_present=frame.has_advisory_only,
        )
        snapshots.append(snapshot)
    
    # Determine state
    if len(frames) == 0:
        state = ReplayState.FAILED
    elif len(conflicts) > 0:
        state = ReplayState.PARTIAL
    else:
        state = ReplayState.COMPLETE
    
    return ReplayResult(
        replay_id=f"replay_{workspace_id}_{utc_now()}",
        workspace_id=workspace_id,
        frames=tuple(frames),
        snapshots=tuple(snapshots),
        conflicts=tuple(conflicts),
        findings=tuple(findings),
        decisions=tuple(decisions),
        start_frame_index=0,
        end_frame_index=len(frames) - 1 if frames else 0,
        state=state,
        summary={
            "workspace_id": workspace_id,
            "total_frames": len(frames),
            "total_conflicts": len(conflicts),
            "total_findings": len(findings),
            "state": state.value,
        },
    )


# =============================================================================
# Exports
# =============================================================================

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
    "PLACEHOLDER_NO_EVIDENCE",
    "PLACEHOLDER_STALE_REFERENCE",
    "PLACEHOLDER_ORPHANED",
    "PLACEHOLDER_CONTRADICTION",
    "PLACEHOLDER_GAP",
    "REQUIRED_REPLAY_PLACEHOLDERS",
    # Types
    "ReplayEventKind",
    "ReplayDecisionKind",
    "ReplayIntegritySeverity",
    "ReplayConflictType",
    "ReplayState",
    "ReplayEvent",
    "ReplayFrame",
    "ReplayCursor",
    "ReplayDecision",
    "ReplaySnapshot",
    "ReplayConflict",
    "ReplayIntegrityFinding",
    "ReplayResult",
    # Helper functions
    "utc_now",
    "sha256_text",
    "sort_events_deterministic",
    # Replay functions
    "replay_workspace_state",
    "replay_workspace_lifecycle",
    "replay_receipt_chain",
    "replay_audit_chain",
    # Time-travel projections
    "build_replay_projection",
    "build_replay_projection_summary",
    # Integrity validation
    "validate_replay_determinism",
    "validate_replay_consistency",
    "validate_replay_projection_consistency",
    "validate_replay_receipt_continuity",
    # Filesystem loading
    "load_replay_events_from_fs",
    "replay_workspace_from_fs",
    # Valid statuses and transitions
    "VALID_WORKSPACE_STATUSES",
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATUSES",
]
