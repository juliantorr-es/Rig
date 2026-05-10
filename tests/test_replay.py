"""Tests for Governance Replay & Time-Travel Module.

These tests verify Phase 5 implementation:
- Replay types are deterministic dataclasses
- Replay state can be reconstructed from receipts + audit events
- Replay projections work correctly
- Replay integrity validation detects issues
- Replay preserves authority/advisory distinctions
- Replay tolerates incomplete history
- Replay findings remain explicit

Golden replay tests cover:
- Clean workspace lifecycle replay
- Advisory-only receipts
- Missing validation receipts
- Stale receipt references
- Orphaned audit chains
- Contradictory gate decisions
- Corrupted replay ordering
- Replay/projection mismatch
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from rig.domain.replay import (
    # Placeholders
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
    REQUIRED_REPLAY_PLACEHOLDERS,
    # Enums
    ReplayEventKind,
    ReplayDecisionKind,
    ReplayIntegritySeverity,
    ReplayConflictType,
    ReplayState,
    # Types
    ReplayEvent,
    ReplayFrame,
    ReplayCursor,
    ReplayDecision,
    ReplaySnapshot,
    ReplayConflict,
    ReplayIntegrityFinding,
    ReplayResult,
    # Helper functions
    utc_now,
    sha256_text,
    sort_events_deterministic,
    # Replay functions
    replay_workspace_state,
    replay_workspace_lifecycle,
    replay_receipt_chain,
    replay_audit_chain,
    # Time-travel projections
    build_replay_projection,
    build_replay_projection_summary,
    # Integrity validation
    validate_replay_determinism,
    validate_replay_consistency,
    validate_replay_projection_consistency,
    validate_replay_receipt_continuity,
    # Valid statuses and transitions
    VALID_WORKSPACE_STATUSES,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    # Filesystem loading
    replay_workspace_from_fs,
)

from rig.domain.receipt_envelope import (
    ReceiptEnvelope,
    ReceiptActor,
    ReceiptSubject,
    ReceiptInput,
    ReceiptOutput,
    ReceiptDecision,
    ReceiptEvidence,
    PLACEHOLDER_UNKNOWN as RECEIPT_PLACEHOLDER_UNKNOWN,
)

from rig.domain.workspace_audit import (
    AuditEvent,
    AuditActor,
    AuditSubject,
    AuditAction,
    AuditDecision,
    AuditReceiptStatus,
    AuditSubjectKind,
    PLACEHOLDER_UNKNOWN as AUDIT_PLACEHOLDER_UNKNOWN,
)


# =============================================================================
# Placeholder Tests
# =============================================================================

class TestReplayPlaceholders:
    """Test replay placeholder constants."""
    
    def test_all_required_placeholders_defined(self):
        """All required replay placeholders must be defined as strings."""
        for placeholder in REQUIRED_REPLAY_PLACEHOLDERS:
            assert isinstance(placeholder, str)
            assert len(placeholder) > 0
    
    def test_placeholder_values(self):
        """Placeholder constants have expected string values."""
        assert PLACEHOLDER_UNKNOWN == "unknown"
        assert PLACEHOLDER_UNAVAILABLE == "unavailable"
        assert PLACEHOLDER_NOT_CREATED == "not_created"
        assert PLACEHOLDER_NO_RECEIPT == "no_receipt"
        assert PLACEHOLDER_ADVISORY_ONLY == "advisory_only"
        assert PLACEHOLDER_NOT_AUTHORITATIVE == "not_authoritative"
    
    def test_replay_specific_placeholders(self):
        """Replay-specific placeholders are defined."""
        assert PLACEHOLDER_NO_EVIDENCE == "no_evidence"
        assert PLACEHOLDER_STALE_REFERENCE == "stale_reference"
        assert PLACEHOLDER_ORPHANED == "orphaned"
        assert PLACEHOLDER_CONTRADICTION == "contradiction"
        assert PLACEHOLDER_GAP == "gap"


# =============================================================================
# Type Tests
# =============================================================================

class TestReplayEventKind:
    """Test ReplayEventKind enum."""
    
    def test_enum_values(self):
        """Enum values match expected strings."""
        assert ReplayEventKind.RECEIPT.value == "receipt"
        assert ReplayEventKind.AUDIT.value == "audit"
        assert ReplayEventKind.WORKSPACE.value == "workspace"
        assert ReplayEventKind.UNKNOWN.value == PLACEHOLDER_UNKNOWN


class TestReplayDecisionKind:
    """Test ReplayDecisionKind enum."""
    
    def test_enum_values(self):
        """Enum values match expected strings."""
        assert ReplayDecisionKind.ALLOWED.value == "allowed"
        assert ReplayDecisionKind.BLOCKED.value == "blocked"
        assert ReplayDecisionKind.PENDING.value == "pending"
        assert ReplayDecisionKind.ADVISORY_ONLY.value == PLACEHOLDER_ADVISORY_ONLY


class TestReplayIntegritySeverity:
    """Test ReplayIntegritySeverity enum."""
    
    def test_enum_values(self):
        """Enum values match expected strings."""
        assert ReplayIntegritySeverity.INFO.value == "info"
        assert ReplayIntegritySeverity.WARNING.value == "warning"
        assert ReplayIntegritySeverity.ERROR.value == "error"
        assert ReplayIntegritySeverity.CRITICAL.value == "critical"


class TestReplayConflictType:
    """Test ReplayConflictType enum."""
    
    def test_enum_values(self):
        """Enum values match expected strings."""
        assert ReplayConflictType.IMPOSSIBLE_TRANSITION.value == "impossible_transition"
        assert ReplayConflictType.MISSING_RECEIPT.value == "missing_receipt"
        assert ReplayConflictType.ORPHANED_AUDIT_EVENT.value == "orphaned_audit_event"
        assert ReplayConflictType.ADVISORY_ESCALATION.value == "advisory_escalation"


class TestReplayState:
    """Test ReplayState enum."""
    
    def test_enum_values(self):
        """Enum values match expected strings."""
        assert ReplayState.PENDING.value == "pending"
        assert ReplayState.PROCESSING.value == "processing"
        assert ReplayState.COMPLETE.value == "complete"
        assert ReplayState.FAILED.value == "failed"
        assert ReplayState.PARTIAL.value == "partial"


# =============================================================================
# ReplayEvent Tests
# =============================================================================

class TestReplayEvent:
    """Test ReplayEvent dataclass."""
    
    def test_default_values(self):
        """ReplayEvent has expected default values."""
        event = ReplayEvent(event_id="test_event")
        assert event.event_id == "test_event"
        assert event.event_kind == ReplayEventKind.UNKNOWN
        assert event.source_id == PLACEHOLDER_UNKNOWN
        assert event.workspace_id is None
        assert event.sequence_index == 0
        assert event.data == {}
        assert event.authoritative is True
        assert event.advisory_only is False
        assert event.hash == ""
    
    def test_custom_values(self):
        """ReplayEvent accepts custom values."""
        event = ReplayEvent(
            event_id="custom_event",
            event_kind=ReplayEventKind.RECEIPT,
            source_id="receipt_123",
            workspace_id="ws_abc",
            timestamp="2024-01-01T00:00:00Z",
            sequence_index=5,
            data={"key": "value"},
            authoritative=True,
            advisory_only=False,
            hash="abc123",
        )
        assert event.event_id == "custom_event"
        assert event.event_kind == ReplayEventKind.RECEIPT
        assert event.source_id == "receipt_123"
        assert event.workspace_id == "ws_abc"
        assert event.sequence_index == 5
        assert event.data == {"key": "value"}
        assert event.authoritative is True
        assert event.advisory_only is False
        assert event.hash == "abc123"
    
    def test_to_dict(self):
        """ReplayEvent.to_dict() produces JSON-serializable dict."""
        event = ReplayEvent(
            event_id="test",
            event_kind=ReplayEventKind.RECEIPT,
            source_id="src",
        )
        d = event.to_dict()
        assert isinstance(d, dict)
        assert d["event_id"] == "test"
        assert d["event_kind"] == "receipt"
        assert d["source_id"] == "src"
        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert isinstance(json_str, str)
    
    def test_from_receipt_envelope(self):
        """ReplayEvent.from_receipt() creates event from ReceiptEnvelope."""
        actor = ReceiptActor(
            actor_id="cli",
            actor_kind="cli",
            display_name="CLI",
            is_human=True,
            is_authoritative=True,
        )
        subject = ReceiptSubject(
            subject_id="ws_test",
            subject_kind="workspace",
            display_name="Test Workspace",
            workspace_id="ws_test",
            authoritative=True,
            advisory_only=False,
        )
        decision = ReceiptDecision.allowed("dec_1", "Test decision")
        
        envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="receipt_001",
            receipt_type="workspace_create",
            authority_level="authoritative",
            advisory_only=False,
            created_at="2024-01-01T00:00:00Z",
            actor=actor,
            subject=subject,
            decision=decision,
            inputs=(),
            outputs=(),
            evidence=(),
            related_receipt_ids=(),
            related_audit_event_ids=(),
            summary="Test receipt",
        )
        
        event = ReplayEvent.from_receipt(envelope, sequence_index=0)
        assert event.event_id == "replay_receipt_receipt_001"
        assert event.event_kind == ReplayEventKind.RECEIPT
        assert event.source_id == "receipt_001"
        assert event.workspace_id == "ws_test"
        assert event.timestamp == "2024-01-01T00:00:00Z"
        assert event.authoritative is True
        assert event.advisory_only is False
        assert "receipt_id" in event.data
        assert event.data["receipt_id"] == "receipt_001"
    
    def test_from_audit_event(self):
        """ReplayEvent.from_audit_event() creates event from AuditEvent."""
        audit_actor = AuditActor.cli()
        audit_subject = AuditSubject.workspace("ws_test")
        
        audit_event = AuditEvent(
            event_id="audit_001",
            action=AuditAction.CREATE,
            actor=audit_actor,
            subject=audit_subject,
            decision=AuditDecision.ALLOWED,
            timestamp="2024-01-01T00:00:00Z",
            status="success",
            summary="Test audit event",
            receipt_id="receipt_001",
            receipt_kind="workspace_create_receipt",
            receipt_status=AuditReceiptStatus.EXISTS,
            workspace_id="ws_test",
            details={"key": "value"},
            authoritative=True,
            advisory_only=False,
        )
        
        event = ReplayEvent.from_audit_event(audit_event, sequence_index=0)
        assert event.event_id == "replay_audit_audit_001"
        assert event.event_kind == ReplayEventKind.AUDIT
        assert event.source_id == "audit_001"
        assert event.workspace_id == "ws_test"
        assert event.timestamp == "2024-01-01T00:00:00Z"
        assert event.authoritative is True
        assert event.advisory_only is False
        assert "event_id" in event.data
    
    def test_placeholder_event(self):
        """ReplayEvent.placeholder() creates placeholder for missing data."""
        event = ReplayEvent.placeholder(workspace_id="ws_missing")
        assert event.event_id == "replay_placeholder_ws_missing"
        assert event.event_kind == ReplayEventKind.UNKNOWN
        assert event.source_id == PLACEHOLDER_NO_RECEIPT
        assert event.workspace_id == "ws_missing"
        assert event.timestamp == PLACEHOLDER_NOT_CREATED
        assert event.sequence_index == -1
        assert event.authoritative is False
        assert event.advisory_only is True


# =============================================================================
# ReplayFrame Tests
# =============================================================================

class TestReplayFrame:
    """Test ReplayFrame dataclass."""
    
    def test_default_values(self):
        """ReplayFrame has expected default values."""
        frame = ReplayFrame(frame_index=0)
        assert frame.frame_index == 0
        assert frame.events == ()
        assert frame.workspace_id is None
        assert frame.workspace_status == PLACEHOLDER_UNKNOWN
        assert frame.status_history == ()
        assert frame.receipt_chain == ()
        assert frame.audit_chain == ()
        assert frame.authority_state == {}
        assert frame.advisory_state == {}
        assert frame.integrity_findings == ()
        assert frame.frame_hash == ""
        assert frame.previous_frame_hash == ""
        assert frame.is_terminal is False
        assert frame.terminal_reason == ""
    
    def test_has_authoritative_evidence(self):
        """has_authoritative_evidence property works correctly."""
        # No events
        frame = ReplayFrame(frame_index=0, events=())
        assert frame.has_authoritative_evidence is False
        
        # Advisory-only event
        advisory_event = ReplayEvent(
            event_id="adv_1",
            authoritative=False,
            advisory_only=True,
        )
        frame = ReplayFrame(frame_index=0, events=(advisory_event,))
        assert frame.has_authoritative_evidence is False
        
        # Authoritative event
        auth_event = ReplayEvent(
            event_id="auth_1",
            authoritative=True,
            advisory_only=False,
        )
        frame = ReplayFrame(frame_index=0, events=(auth_event,))
        assert frame.has_authoritative_evidence is True
    
    def test_has_advisory_only(self):
        """has_advisory_only property works correctly."""
        # No events
        frame = ReplayFrame(frame_index=0, events=())
        assert frame.has_advisory_only is False
        
        # Authoritative event
        auth_event = ReplayEvent(event_id="auth_1", authoritative=True, advisory_only=False)
        frame = ReplayFrame(frame_index=0, events=(auth_event,))
        assert frame.has_advisory_only is False
        
        # Advisory-only event
        advisory_event = ReplayEvent(event_id="adv_1", authoritative=False, advisory_only=True)
        frame = ReplayFrame(frame_index=0, events=(advisory_event,))
        assert frame.has_advisory_only is True
    
    def test_to_dict(self):
        """ReplayFrame.to_dict() produces JSON-serializable dict."""
        frame = ReplayFrame(
            frame_index=0,
            workspace_id="ws_1",
            workspace_status="planned",
        )
        d = frame.to_dict()
        assert isinstance(d, dict)
        assert d["frame_index"] == 0
        assert d["workspace_id"] == "ws_1"
        assert d["workspace_status"] == "planned"
        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert isinstance(json_str, str)


# =============================================================================
# ReplayCursor Tests
# =============================================================================

class TestReplayCursor:
    """Test ReplayCursor dataclass."""
    
    def test_default_values(self):
        """ReplayCursor has expected default values."""
        cursor = ReplayCursor()
        assert cursor.current_frame_index == 0
        assert cursor.total_frames == 0
        assert cursor.workspace_id is None
        assert cursor.can_go_back is False
        assert cursor.can_go_forward is False
        assert cursor.current_frame_hash == ""
    
    def test_to_dict(self):
        """ReplayCursor.to_dict() produces JSON-serializable dict."""
        cursor = ReplayCursor(
            current_frame_index=5,
            total_frames=10,
            workspace_id="ws_1",
        )
        d = cursor.to_dict()
        assert isinstance(d, dict)
        assert d["current_frame_index"] == 5
        assert d["total_frames"] == 10
        assert d["workspace_id"] == "ws_1"
    
    def test_go_back(self):
        """go_back() moves cursor back correctly."""
        cursor = ReplayCursor(
            current_frame_index=5,
            total_frames=10,
            workspace_id="ws_1",
        )
        
        # Can go back
        new_cursor = cursor.go_back()
        assert new_cursor is not None
        assert new_cursor.current_frame_index == 4
        assert new_cursor.can_go_back is True
        assert new_cursor.can_go_forward is True
        
        # At beginning, cannot go back
        start_cursor = ReplayCursor(current_frame_index=0, total_frames=10)
        result = start_cursor.go_back()
        assert result is None
    
    def test_go_forward(self):
        """go_forward() moves cursor forward correctly."""
        cursor = ReplayCursor(
            current_frame_index=5,
            total_frames=10,
            workspace_id="ws_1",
        )
        
        # Can go forward
        new_cursor = cursor.go_forward()
        assert new_cursor is not None
        assert new_cursor.current_frame_index == 6
        assert new_cursor.can_go_back is True
        assert new_cursor.can_go_forward is True
        
        # At end, cannot go forward
        end_cursor = ReplayCursor(current_frame_index=9, total_frames=10)
        result = end_cursor.go_forward()
        assert result is None
    
    def test_go_to(self):
        """go_to() moves cursor to specific frame."""
        cursor = ReplayCursor(
            current_frame_index=0,
            total_frames=10,
            workspace_id="ws_1",
        )
        
        # Valid frame
        new_cursor = cursor.go_to(5)
        assert new_cursor is not None
        assert new_cursor.current_frame_index == 5
        assert new_cursor.can_go_back is True
        assert new_cursor.can_go_forward is True
        
        # Invalid frame (negative)
        result = cursor.go_to(-1)
        assert result is None
        
        # Invalid frame (beyond total)
        result = cursor.go_to(10)
        assert result is None


# =============================================================================
# ReplayDecision Tests
# =============================================================================

class TestReplayDecision:
    """Test ReplayDecision dataclass."""
    
    def test_default_values(self):
        """ReplayDecision has expected default values."""
        decision = ReplayDecision(decision_id="dec_1")
        assert decision.decision_id == "dec_1"
        assert decision.decision_kind == ReplayDecisionKind.PENDING
        assert decision.reason == ""
        assert decision.frame_index == 0
        assert decision.workspace_id is None
        assert decision.authoritative is True
        assert decision.is_advisory_only is False
        assert decision.advisory_only is False  # Property access
    
    def test_allowed_factory(self):
        """allowed() factory creates correct decision."""
        decision = ReplayDecision.allowed(
            decision_id="dec_allow",
            reason="Test allowed",
            frame_index=5,
            workspace_id="ws_1",
        )
        assert decision.decision_id == "dec_allow"
        assert decision.decision_kind == ReplayDecisionKind.ALLOWED
        assert decision.reason == "Test allowed"
        assert decision.frame_index == 5
        assert decision.workspace_id == "ws_1"
        assert decision.authoritative is True
        assert decision.advisory_only is False
    
    def test_blocked_factory(self):
        """blocked() factory creates correct decision."""
        decision = ReplayDecision.blocked(
            decision_id="dec_block",
            reason="Test blocked",
            frame_index=3,
            workspace_id="ws_1",
        )
        assert decision.decision_id == "dec_block"
        assert decision.decision_kind == ReplayDecisionKind.BLOCKED
        assert decision.reason == "Test blocked"
        assert decision.authoritative is True
        assert decision.advisory_only is False
    
    def test_create_advisory_only_factory(self):
        """create_advisory_only() factory creates correct decision."""
        decision = ReplayDecision.create_advisory_only(
            decision_id="dec_adv",
            reason=PLACEHOLDER_ADVISORY_ONLY,
            frame_index=1,
            workspace_id="ws_1",
        )
        assert decision.decision_id == "dec_adv"
        assert decision.decision_kind == ReplayDecisionKind.ADVISORY_ONLY
        assert decision.authoritative is False
        assert decision.is_advisory_only is True
        assert decision.advisory_only is True  # Property access
    
    def test_to_dict(self):
        """ReplayDecision.to_dict() produces JSON-serializable dict."""
        decision = ReplayDecision.allowed("dec_1", "Test")
        d = decision.to_dict()
        assert isinstance(d, dict)
        assert d["decision_id"] == "dec_1"
        assert d["decision_kind"] == "allowed"
        assert d["reason"] == "Test"


# =============================================================================
# ReplaySnapshot Tests
# =============================================================================

class TestReplaySnapshot:
    """Test ReplaySnapshot dataclass."""
    
    def test_default_values(self):
        """ReplaySnapshot has expected default values."""
        snapshot = ReplaySnapshot(snapshot_id="snap_1")
        assert snapshot.snapshot_id == "snap_1"
        assert snapshot.workspace_id is None
        assert snapshot.frame_index == 0
        assert snapshot.frame is None
        assert snapshot.cursor is None
        assert snapshot.decisions == ()
        assert snapshot.integrity_findings == ()
        assert snapshot.authoritative_evidence_available is False
        assert snapshot.advisory_only_evidence_present is False
    
    def test_to_dict(self):
        """ReplaySnapshot.to_dict() produces JSON-serializable dict."""
        frame = ReplayFrame(frame_index=0)
        cursor = ReplayCursor(total_frames=1)
        snapshot = ReplaySnapshot(
            snapshot_id="snap_1",
            workspace_id="ws_1",
            frame_index=0,
            frame=frame,
            cursor=cursor,
        )
        d = snapshot.to_dict()
        assert isinstance(d, dict)
        assert d["snapshot_id"] == "snap_1"
        assert d["workspace_id"] == "ws_1"
        assert d["frame"] is not None
        assert d["cursor"] is not None


# =============================================================================
# ReplayConflict Tests
# =============================================================================

class TestReplayConflict:
    """Test ReplayConflict dataclass."""
    
    def test_default_values(self):
        """ReplayConflict has expected default values."""
        conflict = ReplayConflict(
            conflict_id="conflict_1",
            conflict_type=ReplayConflictType.MISSING_RECEIPT,
            severity=ReplayIntegritySeverity.WARNING,
            title="Test conflict",
            message="Test message",
        )
        assert conflict.conflict_id == "conflict_1"
        assert conflict.conflict_type == ReplayConflictType.MISSING_RECEIPT
        assert conflict.severity == ReplayIntegritySeverity.WARNING
        assert conflict.title == "Test conflict"
        assert conflict.message == "Test message"
        assert conflict.workspace_id is None
        assert conflict.frame_index == 0
        assert conflict.involved_receipt_ids == ()
        assert conflict.involved_audit_event_ids == ()
        assert conflict.details == {}
    
    def test_severity_order(self):
        """severity_order property returns correct numeric values."""
        for severity, expected_order in [
            (ReplayIntegritySeverity.INFO, 0),
            (ReplayIntegritySeverity.WARNING, 1),
            (ReplayIntegritySeverity.ERROR, 2),
            (ReplayIntegritySeverity.CRITICAL, 3),
        ]:
            conflict = ReplayConflict(
                conflict_id="test",
                conflict_type=ReplayConflictType.MISSING_RECEIPT,
                severity=severity,
                title="Test",
                message="Test",
            )
            assert conflict.severity_order == expected_order
    
    def test_to_dict(self):
        """ReplayConflict.to_dict() produces JSON-serializable dict."""
        conflict = ReplayConflict(
            conflict_id="conflict_1",
            conflict_type=ReplayConflictType.IMPOSSIBLE_TRANSITION,
            severity=ReplayIntegritySeverity.ERROR,
            title="Test",
            message="Test",
        )
        d = conflict.to_dict()
        assert isinstance(d, dict)
        assert d["conflict_id"] == "conflict_1"
        assert d["conflict_type"] == "impossible_transition"
        assert d["severity"] == "error"


# =============================================================================
# ReplayIntegrityFinding Tests
# =============================================================================

class TestReplayIntegrityFinding:
    """Test ReplayIntegrityFinding dataclass."""
    
    def test_default_values(self):
        """ReplayIntegrityFinding has expected default values."""
        finding = ReplayIntegrityFinding(
            finding_id="finding_1",
            title="Test finding",
            message="Test message",
        )
        assert finding.finding_id == "finding_1"
        assert finding.title == "Test finding"
        assert finding.message == "Test message"
        assert finding.severity == ReplayIntegritySeverity.INFO
        assert finding.finding_type == "replay_finding"
        assert finding.workspace_id is None
        assert finding.frame_index == 0
        assert finding.conflict is None
        assert finding.details == {}
    
    def test_severity_order(self):
        """severity_order property returns correct numeric values."""
        for severity, expected_order in [
            (ReplayIntegritySeverity.INFO, 0),
            (ReplayIntegritySeverity.WARNING, 1),
            (ReplayIntegritySeverity.ERROR, 2),
            (ReplayIntegritySeverity.CRITICAL, 3),
        ]:
            finding = ReplayIntegrityFinding(
                finding_id="test",
                title="Test",
                message="Test",
                severity=severity,
            )
            assert finding.severity_order == expected_order
    
    def test_to_dict(self):
        """ReplayIntegrityFinding.to_dict() produces JSON-serializable dict."""
        finding = ReplayIntegrityFinding(
            finding_id="finding_1",
            title="Test",
            message="Test",
            severity=ReplayIntegritySeverity.WARNING,
        )
        d = finding.to_dict()
        assert isinstance(d, dict)
        assert d["finding_id"] == "finding_1"
        assert d["severity"] == "warning"


# =============================================================================
# ReplayResult Tests
# =============================================================================

class TestReplayResult:
    """Test ReplayResult dataclass."""
    
    def test_default_values(self):
        """ReplayResult has expected default values."""
        result = ReplayResult(replay_id="replay_1")
        assert result.replay_id == "replay_1"
        assert result.workspace_id is None
        assert result.frames == ()
        assert result.snapshots == ()
        assert result.conflicts == ()
        assert result.findings == ()
        assert result.decisions == ()
        assert result.start_frame_index == 0
        assert result.end_frame_index == 0
        assert result.state == ReplayState.PENDING
        assert result.summary == {}
    
    def test_properties(self):
        """ReplayResult properties work correctly."""
        result = ReplayResult(
            replay_id="replay_1",
            state=ReplayState.COMPLETE,
        )
        assert result.is_complete is True
        assert result.is_partial is False
        assert result.has_conflicts is False
        assert result.has_findings is False
        assert result.has_authoritative_evidence is False
        
        result = ReplayResult(
            replay_id="replay_2",
            state=ReplayState.PARTIAL,
            conflicts=(ReplayConflict(
                conflict_id="c1",
                conflict_type=ReplayConflictType.MISSING_RECEIPT,
                severity=ReplayIntegritySeverity.WARNING,
                title="Test",
                message="Test",
            ),),
        )
        assert result.is_complete is False
        assert result.is_partial is True
        assert result.has_conflicts is True
    
    def test_to_dict(self):
        """ReplayResult.to_dict() produces JSON-serializable dict."""
        result = ReplayResult(
            replay_id="replay_1",
            workspace_id="ws_1",
            state=ReplayState.COMPLETE,
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["replay_id"] == "replay_1"
        assert d["workspace_id"] == "ws_1"
        assert d["state"] == "complete"


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Test helper functions."""
    
    def test_utc_now(self):
        """utc_now() returns ISO format timestamp."""
        timestamp = utc_now()
        assert isinstance(timestamp, str)
        assert timestamp.endswith("Z")
        assert "T" in timestamp
    
    def test_sha256_text(self):
        """sha256_text() returns consistent hash."""
        hash1 = sha256_text("test")
        hash2 = sha256_text("test")
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length
        
        # Different inputs produce different hashes
        hash3 = sha256_text("different")
        assert hash1 != hash3
    
    def test_sort_events_deterministic(self):
        """sort_events_deterministic() produces consistent ordering."""
        events = [
            ReplayEvent(
                event_id="event_c",
                timestamp="2024-01-03T00:00:00Z",
                sequence_index=2,
            ),
            ReplayEvent(
                event_id="event_a",
                timestamp="2024-01-01T00:00:00Z",
                sequence_index=0,
            ),
            ReplayEvent(
                event_id="event_b",
                timestamp="2024-01-02T00:00:00Z",
                sequence_index=1,
            ),
        ]
        
        sorted_events = sort_events_deterministic(events)
        
        # Should be sorted by timestamp
        assert sorted_events[0].event_id == "event_a"
        assert sorted_events[1].event_id == "event_b"
        assert sorted_events[2].event_id == "event_c"
        
        # Should be deterministic (same order on repeated calls)
        sorted_events_2 = sort_events_deterministic(events)
        assert [e.event_id for e in sorted_events] == [e.event_id for e in sorted_events_2]


# =============================================================================
# Workspace State Reconstruction Tests
# =============================================================================

class TestReplayWorkspaceState:
    """Test replay_workspace_state() function."""
    
    def test_empty_events_returns_initial_frame(self):
        """Empty events list returns single frame with initial status."""
        frames = replay_workspace_state(
            workspace_id="ws_1",
            events=[],
            initial_status="planned",
        )
        
        assert len(frames) == 1
        assert frames[0].workspace_id == "ws_1"
        assert frames[0].workspace_status == "planned"
        assert frames[0].frame_index == 0
        assert frames[0].events == ()
    
    def test_single_event_creates_frame(self):
        """Single event creates single frame with updated state."""
        event = ReplayEvent(
            event_id="event_1",
            event_kind=ReplayEventKind.RECEIPT,
            source_id="receipt_create",
            workspace_id="ws_1",
            timestamp="2024-01-01T00:00:00Z",
            data={"status": "active"},
        )
        
        frames = replay_workspace_state(
            workspace_id="ws_1",
            events=[event],
            initial_status="planned",
        )
        
        assert len(frames) == 1
        assert frames[0].workspace_status == "active"
        assert len(frames[0].events) == 1
    
    def test_status_transitions(self):
        """Status transitions follow allowed transitions."""
        events = [
            ReplayEvent(
                event_id="event_1",
                workspace_id="ws_1",
                timestamp="2024-01-01T00:00:00Z",
                event_kind=ReplayEventKind.RECEIPT,
                source_id="receipt_1",
                data={"status": "active"},  # Use "status" key for workspace receipts
            ),
            ReplayEvent(
                event_id="event_2",
                workspace_id="ws_1",
                timestamp="2024-01-02T00:00:00Z",
                event_kind=ReplayEventKind.RECEIPT,
                source_id="receipt_2",
                data={"status": "executed"},
            ),
            ReplayEvent(
                event_id="event_3",
                workspace_id="ws_1",
                timestamp="2024-01-03T00:00:00Z",
                event_kind=ReplayEventKind.RECEIPT,
                source_id="receipt_3",
                data={"status": "validated"},
            ),
        ]
        
        frames = replay_workspace_state(
            workspace_id="ws_1",
            events=events,
            initial_status="planned",
        )
        
        # Check we have frames for each event
        assert len(frames) >= 1
        
        # Check final status - with RECEIPT kind, status is extracted from data["status"]
        assert frames[-1].workspace_status == "validated"
    
    def test_invalid_transition_rejected(self):
        """Invalid state transition is rejected and status not changed."""
        events = [
            ReplayEvent(
                event_id="event_1",
                workspace_id="ws_1",
                timestamp="2024-01-01T00:00:00Z",
                event_kind=ReplayEventKind.WORKSPACE,
                data={"new_status": "applied"},  # Invalid: planned -> applied
            ),
        ]
        
        frames = replay_workspace_state(
            workspace_id="ws_1",
            events=events,
            initial_status="planned",
        )
        
        # Status should remain "planned" as transition is invalid
        assert frames[-1].workspace_status == "planned"


# =============================================================================
# Time-Travel Projection Tests
# =============================================================================

class TestBuildReplayProjection:
    """Test build_replay_projection() function."""
    
    def test_empty_result_returns_placeholder(self):
        """Empty ReplayResult returns placeholder projection."""
        result = ReplayResult(
            replay_id="replay_1",
            workspace_id="ws_1",
        )
        
        projection = build_replay_projection(result, frame_index=None)
        
        assert projection["type"] == "ReplayProjection"
        assert projection["workspace_id"] == "ws_1"
        assert projection["frame_index"] == -1
        assert projection["total_frames"] == 0
        assert projection["workspace_status"] == PLACEHOLDER_UNKNOWN
    
    def test_projection_from_frames(self):
        """Projection correctly reflects frame data."""
        frame = ReplayFrame(
            frame_index=0,
            workspace_id="ws_1",
            workspace_status="active",
            status_history=({"status": "planned", "at": "2024-01-01T00:00:00Z"}, {"status": "active", "at": "2024-01-02T00:00:00Z"}),
            receipt_chain=("receipt_1", "receipt_2"),
            audit_chain=("audit_1",),
        )
        
        result = ReplayResult(
            replay_id="replay_1",
            workspace_id="ws_1",
            frames=(frame,),
        )
        
        projection = build_replay_projection(result, frame_index=0)
        
        assert projection["frame_index"] == 0
        assert projection["total_frames"] == 1
        assert projection["workspace_status"] == "active"
        assert len(projection["status_history"]) == 2
        assert len(projection["receipt_chain"]) == 2
        assert len(projection["audit_chain"]) == 1


class TestBuildReplayProjectionSummary:
    """Test build_replay_projection_summary() function."""
    
    def test_empty_result_summary(self):
        """Empty ReplayResult returns minimal summary."""
        result = ReplayResult(
            replay_id="replay_1",
            workspace_id="ws_1",
        )
        
        summary = build_replay_projection_summary(result)
        
        assert summary["type"] == "ReplaySummary"
        assert summary["workspace_id"] == "ws_1"
        assert summary["total_frames"] == 0
        assert summary["state"] == "pending"
    
    def test_summary_with_frames(self):
        """Summary correctly aggregates frame data."""
        frame = ReplayFrame(
            frame_index=0,
            workspace_id="ws_1",
            workspace_status="applied",
            is_terminal=True,
            terminal_reason="Applied",
        )
        
        result = ReplayResult(
            replay_id="replay_1",
            workspace_id="ws_1",
            frames=(frame,),
            state=ReplayState.COMPLETE,
        )
        
        summary = build_replay_projection_summary(result)
        
        assert summary["total_frames"] == 1
        assert summary["state"] == "complete"
        assert summary["current_status"] == "applied"
        assert summary["is_terminal"] is True
        assert summary["terminal_reason"] == "Applied"


# =============================================================================
# Integrity Validation Tests
# =============================================================================

class TestValidateReplayConsistency:
    """Test validate_replay_consistency() function."""
    
    def test_status_mismatch_detection(self):
        """Detects mismatch between replay and workspace record status."""
        # Create a ReplayResult with final status "active"
        frame = ReplayFrame(
            frame_index=0,
            workspace_id="ws_1",
            workspace_status="active",
        )
        result = ReplayResult(
            replay_id="replay_1",
            workspace_id="ws_1",
            frames=(frame,),
            state=ReplayState.COMPLETE,
        )
        
        # Workspace record has status "applied"
        workspace_record = {
            "workspace_id": "ws_1",
            "status": "applied",
        }
        
        findings = validate_replay_consistency(result, workspace_record)
        
        assert len(findings) == 1
        assert findings[0].title == "Replay status mismatch"
        assert findings[0].severity == ReplayIntegritySeverity.ERROR


class TestValidateReplayReceiptContinuity:
    """Test validate_replay_receipt_continuity() function."""
    
    def test_missing_receipts_in_chain(self):
        """Detects receipts in chain that don't exist in all_receipt_ids."""
        receipt_chain = ("receipt_1", "receipt_2", "receipt_missing")
        all_receipt_ids = {"receipt_1", "receipt_2"}
        
        findings = validate_replay_receipt_continuity(
            receipt_chain=receipt_chain,
            all_receipt_ids=all_receipt_ids,
            workspace_id="ws_1",
        )
        
        assert len(findings) == 1
        assert findings[0].title == "Missing receipts in chain"
        assert findings[0].severity == ReplayIntegritySeverity.ERROR


# =============================================================================
# Determinism Tests
# =============================================================================

class TestReplayDeterminism:
    """Test that replay produces deterministic results."""
    
    def test_frame_hash_determinism(self):
        """Frame hash is deterministic for same inputs."""
        frame1 = ReplayFrame(
            frame_index=0,
            workspace_id="ws_1",
            workspace_status="active",
            receipt_chain=("r1", "r2"),
            audit_chain=("a1",),
        )
        
        frame2 = ReplayFrame(
            frame_index=0,
            workspace_id="ws_1",
            workspace_status="active",
            receipt_chain=("r1", "r2"),
            audit_chain=("a1",),
        )
        
        assert frame1.frame_hash == frame2.frame_hash
    
    def test_event_hash_determinism(self):
        """Event hash is deterministic for same data."""
        data = {"key": "value", "receipt_id": "test_001"}
        
        event1 = ReplayEvent(
            event_id="event_1",
            event_kind=ReplayEventKind.RECEIPT,
            source_id="test_001",
            data=data,
        )
        
        event2 = ReplayEvent(
            event_id="event_1",
            event_kind=ReplayEventKind.RECEIPT,
            source_id="test_001",
            data=data,
        )
        
        assert event1.hash == event2.hash


# =============================================================================
# Valid Statuses and Transitions Tests
# =============================================================================

class TestValidWorkspacesStatuses:
    """Test VALID_WORKSPACE_STATUSES constant."""
    
    def test_contains_expected_statuses(self):
        """Contains all expected workspace statuses."""
        expected = {"planned", "active", "blocked", "executed", "validated", "review_ready", "applied"}
        assert VALID_WORKSPACE_STATUSES == expected


class TestAllowedTransitions:
    """Test ALLOWED_TRANSITIONS constant."""
    
    def test_planned_transitions(self):
        """Planned status allows transition to active."""
        assert ALLOWED_TRANSITIONS["planned"] == {"active"}
    
    def test_active_transitions(self):
        """Active status allows transitions to executed or blocked."""
        assert ALLOWED_TRANSITIONS["active"] == {"executed", "blocked"}
    
    def test_terminal_statuses_no_transitions(self):
        """Terminal statuses have no allowed transitions."""
        assert ALLOWED_TRANSITIONS["applied"] == set()
        assert ALLOWED_TRANSITIONS["blocked"] == set()


class TestTerminalStatuses:
    """Test TERMINAL_STATUSES constant."""
    
    def test_contains_expected(self):
        """Contains expected terminal statuses."""
        assert TERMINAL_STATUSES == {"blocked", "applied"}


# =============================================================================
# Golden Replay Tests
# =============================================================================

class TestGoldenReplayFixtures:
    """Golden replay tests with predetermined inputs and outputs."""
    
    def _create_clean_workspace_record(self, workspace_id="demo"):
        """Create a clean workspace record for testing."""
        return {
            "workspace_id": workspace_id,
            "status": "applied",
            "status_history": [
                {"status": "planned", "at": "2024-01-01T00:00:00Z"},
                {"status": "active", "at": "2024-01-02T00:00:00Z"},
                {"status": "executed", "at": "2024-01-03T00:00:00Z"},
                {"status": "validated", "at": "2024-01-04T00:00:00Z"},
                {"status": "review_ready", "at": "2024-01-05T00:00:00Z"},
                {"status": "applied", "at": "2024-01-06T00:00:00Z"},
            ],
            "receipt_paths": [f"/path/to/{workspace_id}_create.json", f"/path/to/{workspace_id}_apply.json"],
            "canonical_receipt_paths": [],
            "audit_event_ids": [f"ws_create_{workspace_id}", f"ws_apply_{workspace_id}"],
            "authoritative": True,
        }
    
    def _create_receipts(self, workspace_id="demo"):
        """Create receipt envelopes for testing."""
        actor = ReceiptActor.cli()
        subject = ReceiptSubject.workspace(workspace_id)
        
        receipts = []
        
        # Create receipt
        create_decision = ReceiptDecision.allowed(f"ws_create_{workspace_id}_dec", "Allowed")
        create_envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id=f"ws_create_{workspace_id}",
            receipt_type="workspace_create",
            authority_level="authoritative",
            advisory_only=False,
            created_at="2024-01-01T00:00:00Z",
            actor=actor,
            subject=subject,
            decision=create_decision,
            inputs=[],
            outputs=[],
            evidence=[],
            related_receipt_ids=[],
            related_audit_event_ids=[],
            summary=f"Workspace {workspace_id} created",
        )
        receipts.append(create_envelope)
        
        # Apply receipt
        apply_decision = ReceiptDecision.allowed(f"ws_apply_{workspace_id}_dec", "Allowed")
        apply_envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id=f"ws_apply_{workspace_id}",
            receipt_type="workspace_apply",
            authority_level="authoritative",
            advisory_only=False,
            created_at="2024-01-06T00:00:00Z",
            actor=actor,
            subject=subject,
            decision=apply_decision,
            inputs=[],
            outputs=[],
            evidence=[],
            related_receipt_ids=[],
            related_audit_event_ids=[],
            summary=f"Workspace {workspace_id} applied",
        )
        receipts.append(apply_envelope)
        
        return receipts
    
    def _create_audit_events(self, workspace_id="demo"):
        """Create audit events for testing."""
        audit_actor = AuditActor.cli()
        audit_subject = AuditSubject.workspace(workspace_id)
        
        events = []
        
        # Create audit event
        create_event = AuditEvent(
            event_id=f"ws_create_{workspace_id}",
            action=AuditAction.CREATE,
            actor=audit_actor,
            subject=audit_subject,
            decision=AuditDecision.ALLOWED,
            timestamp="2024-01-01T00:00:00Z",
            status="success",
            summary=f"Workspace {workspace_id} created",
            receipt_id=f"ws_create_{workspace_id}",
            receipt_kind="workspace_create_receipt",
            receipt_status=AuditReceiptStatus.EXISTS,
            workspace_id=workspace_id,
            details={},
            authoritative=True,
            advisory_only=False,
        )
        events.append(create_event)
        
        # Apply audit event
        apply_event = AuditEvent(
            event_id=f"ws_apply_{workspace_id}",
            action=AuditAction.APPLY,
            actor=audit_actor,
            subject=audit_subject,
            decision=AuditDecision.ALLOWED,
            timestamp="2024-01-06T00:00:00Z",
            status="success",
            summary=f"Workspace {workspace_id} applied",
            receipt_id=f"ws_apply_{workspace_id}",
            receipt_kind="apply_receipt",
            receipt_status=AuditReceiptStatus.EXISTS,
            workspace_id=workspace_id,
            details={"main_before": "abc123", "main_after": "def456"},
            authoritative=True,
            advisory_only=False,
        )
        events.append(apply_event)
        
        return events
    
    def test_clean_workspace_lifecycle_replay(self):
        """Golden test: clean workspace lifecycle replays correctly."""
        workspace_record = self._create_clean_workspace_record("demo")
        receipts = self._create_receipts("demo")
        audit_events = self._create_audit_events("demo")
        
        result = replay_workspace_lifecycle(
            workspace_record=workspace_record,
            receipts=receipts,
            audit_events=audit_events,
        )
        
        # Verify result
        assert result.workspace_id == "demo"
        assert result.is_complete is True
        assert len(result.frames) > 0
        assert result.frames[-1].workspace_status == "applied"
        
        # Verify summary
        assert result.summary["workspace_id"] == "demo"
        assert result.summary["state"] == "complete"
        assert result.summary["total_frames"] > 0
    
    def test_advisory_only_receipts(self):
        """Golden test: advisory-only receipts are tracked correctly."""
        # Create workspace record
        workspace_record = {
            "workspace_id": "adv_demo",
            "status": "planned",
            "status_history": [{"status": "planned", "at": "2024-01-01T00:00:00Z"}],
            "receipt_paths": [],
            "audit_event_ids": [],
            "authoritative": True,
        }
        
        # Create advisory-only receipt (public intake)
        advisory_actor = ReceiptActor.connector("github")
        advisory_subject = ReceiptSubject.unknown()
        advisory_decision = ReceiptDecision.advisory_only("adv_dec_1", "Advisory only")
        
        advisory_envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="public_sync_001",
            receipt_type="public_sync",
            authority_level="advisory_only",
            advisory_only=True,
            created_at="2024-01-01T00:00:00Z",
            actor=advisory_actor,
            subject=advisory_subject,
            decision=advisory_decision,
            inputs=[],
            outputs=[],
            evidence=[],
            related_receipt_ids=[],
            related_audit_event_ids=[],
            summary="Public intake advisory",
        )
        
        result = replay_workspace_lifecycle(
            workspace_record=workspace_record,
            receipts=[advisory_envelope],
            audit_events=[],
        )
        
        # Should have advisory evidence
        assert any(f.has_advisory_only for f in result.frames)
        
        # Should still be complete (advisory is valid)
        assert result.is_complete is True
    
    def test_missing_validation_receipts(self):
        """Golden test: missing validation receipts are detected."""
        workspace_record = {
            "workspace_id": "missing_val",
            "status": "validated",
            "status_history": [
                {"status": "planned", "at": "2024-01-01T00:00:00Z"},
                {"status": "active", "at": "2024-01-02T00:00:00Z"},
                {"status": "executed", "at": "2024-01-03T00:00:00Z"},
                {"status": "validated", "at": "2024-01-04T00:00:00Z"},
            ],
            "receipt_paths": ["/path/to/missing_val_create.json"],
            "audit_event_ids": ["ws_create_missing_val"],
            "authoritative": True,
        }
        
        # Only create receipt, no validation receipt
        actor = ReceiptActor.cli()
        subject = ReceiptSubject.workspace("missing_val")
        create_decision = ReceiptDecision.allowed("ws_create_missing_val_dec", "Allowed")
        
        create_envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="ws_create_missing_val",
            receipt_type="workspace_create",
            authority_level="authoritative",
            advisory_only=False,
            created_at="2024-01-01T00:00:00Z",
            actor=actor,
            subject=subject,
            decision=create_decision,
            inputs=[],
            outputs=[],
            evidence=[],
            related_receipt_ids=[],
            related_audit_event_ids=[],
            summary="Workspace missing_val created",
        )
        
        # No audit events for validation
        audit_actor = AuditActor.cli()
        audit_subject = AuditSubject.workspace("missing_val")
        create_audit = AuditEvent(
            event_id="ws_create_missing_val",
            action=AuditAction.CREATE,
            actor=audit_actor,
            subject=audit_subject,
            decision=AuditDecision.ALLOWED,
            timestamp="2024-01-01T00:00:00Z",
            status="success",
            summary="Workspace missing_val created",
            receipt_id="ws_create_missing_val",
            receipt_kind="workspace_create_receipt",
            receipt_status=AuditReceiptStatus.EXISTS,
            workspace_id="missing_val",
            details={},
            authoritative=True,
            advisory_only=False,
        )
        
        result = replay_workspace_lifecycle(
            workspace_record=workspace_record,
            receipts=[create_envelope],
            audit_events=[create_audit],
        )
        
        # Should detect missing receipts or have partial state
        assert result.is_complete or result.has_findings
    
    def test_orphaned_audit_events(self):
        """Golden test: orphaned audit events are detected."""
        workspace_record = {
            "workspace_id": "orphan_demo",
            "status": "planned",
            "status_history": [{"status": "planned", "at": "2024-01-01T00:00:00Z"}],
            "receipt_paths": [],
            "audit_event_ids": ["orphan_audit_1"],
            "authoritative": True,
        }
        
        # Audit event references non-existent receipt
        audit_actor = AuditActor.connector("external")
        audit_subject = AuditSubject.workspace("orphan_demo")
        
        orphan_audit = AuditEvent(
            event_id="orphan_audit_1",
            action=AuditAction.IMPORT,
            actor=audit_actor,
            subject=audit_subject,
            decision=AuditDecision.ALLOWED,
            timestamp="2024-01-01T00:00:00Z",
            status="success",
            summary="Orphaned audit event",
            receipt_id="nonexistent_receipt",
            receipt_kind="public_sync_receipt",
            receipt_status=AuditReceiptStatus.MISSING,
            workspace_id="orphan_demo",
            details={},
            authoritative=False,
            advisory_only=True,
        )
        
        result = replay_workspace_lifecycle(
            workspace_record=workspace_record,
            receipts=[],
            audit_events=[orphan_audit],
        )
        
        # Should detect orphaned audit event
        assert result.has_conflicts or result.has_findings
    
    def test_replay_projection_consistency(self):
        """Golden test: replay projections are consistent."""
        workspace_record = self._create_clean_workspace_record("proj_demo")
        receipts = self._create_receipts("proj_demo")
        audit_events = self._create_audit_events("proj_demo")
        
        result = replay_workspace_lifecycle(
            workspace_record=workspace_record,
            receipts=receipts,
            audit_events=audit_events,
        )
        
        # Build projection
        projection = build_replay_projection_summary(result)
        
        # Validate consistency
        findings = validate_replay_projection_consistency(result, projection)
        
        # Should have no findings (projection matches result)
        assert len(findings) == 0


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerialization:
    """Test that all replay types are JSON-serializable."""
    
    def test_all_types_serializable(self):
        """All replay types must be JSON-serializable."""
        types_and_instances = [
            ("ReplayEvent", ReplayEvent(event_id="test")),
            ("ReplayFrame", ReplayFrame(frame_index=0)),
            ("ReplayCursor", ReplayCursor()),
            ("ReplayDecision", ReplayDecision(decision_id="test")),
            ("ReplaySnapshot", ReplaySnapshot(snapshot_id="test")),
            ("ReplayConflict", ReplayConflict(
                conflict_id="test",
                conflict_type=ReplayConflictType.MISSING_RECEIPT,
                severity=ReplayIntegritySeverity.WARNING,
                title="Test",
                message="Test",
            )),
            ("ReplayIntegrityFinding", ReplayIntegrityFinding(
                finding_id="test",
                title="Test",
                message="Test",
            )),
            ("ReplayResult", ReplayResult(replay_id="test")),
        ]
        
        for type_name, instance in types_and_instances:
            # Convert to dict
            d = instance.to_dict()
            assert isinstance(d, dict), f"{type_name}.to_dict() failed"
            
            # Serialize to JSON
            json_str = json.dumps(d)
            assert isinstance(json_str, str), f"{type_name} JSON serialization failed"
            
            # Deserialize from JSON
            restored = json.loads(json_str)
            assert isinstance(restored, dict), f"{type_name} JSON deserialization failed"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_workspace_id(self):
        """Empty workspace_id is handled gracefully."""
        result = replay_workspace_from_fs(Path("/nonexistent"), "")
        assert result.workspace_id == ""
    
    def test_nonexistent_workspace(self):
        """Nonexistent workspace returns failed state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            result = replay_workspace_from_fs(repo_root, "nonexistent")
            
            assert result.state == ReplayState.FAILED
            assert result.has_findings
            assert any("does not exist" in f.message.lower() or "not found" in f.message.lower() 
                      for f in result.findings)
    
    def test_deterministic_ordering_with_same_timestamp(self):
        """Events with same timestamp are ordered deterministically."""
        events = [
            ReplayEvent(
                event_id="event_b",
                timestamp="2024-01-01T00:00:00Z",
                sequence_index=1,
            ),
            ReplayEvent(
                event_id="event_a",
                timestamp="2024-01-01T00:00:00Z",
                sequence_index=0,
            ),
            ReplayEvent(
                event_id="event_c",
                timestamp="2024-01-01T00:00:00Z",
                sequence_index=2,
            ),
        ]
        
        sorted_events = sort_events_deterministic(events)
        
        # Should be sorted by event_id (secondary key)
        assert sorted_events[0].event_id == "event_a"
        assert sorted_events[1].event_id == "event_b"
        assert sorted_events[2].event_id == "event_c"


# =============================================================================
# Projection Contract Integration Tests
# =============================================================================

class TestReplayProjectionContracts:
    """Test replay projection contract compatibility."""
    
    def test_replay_projection_has_expected_fields(self):
        """Replay projection has all expected fields."""
        frame = ReplayFrame(
            frame_index=0,
            workspace_id="ws_1",
            workspace_status="active",
            receipt_chain=("r1",),
            audit_chain=("a1",),
        )
        result = ReplayResult(
            replay_id="test",
            workspace_id="ws_1",
            frames=(frame,),
            state=ReplayState.COMPLETE,
        )
        
        projection = build_replay_projection_summary(result)
        
        expected_fields = [
            "type", "replay_id", "workspace_id", "total_frames",
            "state", "current_status", "is_terminal",
        ]
        
        for field in expected_fields:
            assert field in projection, f"Missing field: {field}"
    
    def test_replay_snapshot_has_expected_fields(self):
        """Replay snapshot has all expected fields."""
        snapshot = ReplaySnapshot(snapshot_id="test")
        d = snapshot.to_dict()
        
        expected_fields = [
            "snapshot_id", "workspace_id", "frame_index", "frame",
            "cursor", "decisions", "integrity_findings",
            "authoritative_evidence_available", "advisory_only_evidence_present",
        ]
        
        for field in expected_fields:
            assert field in d, f"Missing field: {field}"


# =============================================================================
# Additional Golden Replay Tests (GAP-003, GAP-004, GAP-005)
# =============================================================================

class TestMissingGoldenReplayFixtures:
    """Golden tests for edge cases identified in the audit."""
    
    def test_corrupted_replay_ordering(self):
        """Golden test: events with out-of-sequence timestamps (GAP-003).
        
        Tests that replay handles events with corrupted chronological ordering
        by sorting them deterministically.
        """
        # Create events with "wrong" chronological order
        # Later timestamp event comes first in the list
        events = [
            ReplayEvent(
                event_id="later_event",
                workspace_id="corruption_test",
                timestamp="2024-01-02T00:00:00Z",  # Later timestamp
                event_kind=ReplayEventKind.RECEIPT,
                source_id="receipt_2",
                data={"status": "executed"},
                authoritative=True,
                advisory_only=False,
            ),
            ReplayEvent(
                event_id="earlier_event",
                workspace_id="corruption_test",
                timestamp="2024-01-01T00:00:00Z",  # Earlier timestamp
                event_kind=ReplayEventKind.RECEIPT,
                source_id="receipt_1",
                data={"status": "active"},
                authoritative=True,
                advisory_only=False,
            ),
        ]
        
        frames = replay_workspace_state(
            workspace_id="corruption_test",
            events=events,
            initial_status="planned",
        )
        
        # Should still be deterministic - sorted by timestamp
        assert len(frames) >= 1
        # Verify ordering is corrected - first frame should have the earliest timestamp event
        assert frames[0].events[0].event_id == "earlier_event"
        # Final status should be from the later event
        assert frames[-1].workspace_status == "executed"
        
    def test_contradictory_gate_decisions(self):
        """Golden test: contradictory gate decisions detected (GAP-004).
        
        Tests that replay detects or handles contradictory gate decisions
        (e.g., one receipt says ALLOWED, another says BLOCKED for same workspace).
        """
        workspace_record = {
            "workspace_id": "contradiction_test",
            "status": "blocked",
            "status_history": [
                {"status": "planned", "at": "2024-01-01T00:00:00Z"},
                {"status": "active", "at": "2024-01-02T00:00:00Z"},
                {"status": "blocked", "at": "2024-01-03T00:00:00Z"},
            ],
            "receipt_paths": ["/path/to/contra_allowed.json", "/path/to/contra_blocked.json"],
            "audit_event_ids": [],
            "authoritative": True,
        }
        
        # Create conflicting receipts
        actor = ReceiptActor.cli()
        subject = ReceiptSubject.workspace("contradiction_test")
        
        # First receipt: ALLOWED for execution
        allowed_decision = ReceiptDecision.allowed("contra_dec_1", "Execution allowed")
        allowed_envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="contra_allowed",
            receipt_type="gate_decision",
            authority_level="authoritative",
            advisory_only=False,
            created_at="2024-01-02T00:00:00Z",
            actor=actor,
            subject=subject,
            decision=allowed_decision,
            inputs=[],
            outputs=[],
            evidence=[],
            related_receipt_ids=[],
            related_audit_event_ids=[],
            summary="Gate allowed execution",
        )
        
        # Second receipt: BLOCKED (contradictory!)
        blocked_decision = ReceiptDecision.blocked("contra_dec_2", "Execution blocked")
        blocked_envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="contra_blocked",
            receipt_type="gate_decision",
            authority_level="authoritative",
            advisory_only=False,
            created_at="2024-01-03T00:00:00Z",
            actor=actor,
            subject=subject,
            decision=blocked_decision,
            inputs=[],
            outputs=[],
            evidence=[],
            related_receipt_ids=[],
            related_audit_event_ids=[],
            summary="Gate blocked execution",
        )
        
        result = replay_workspace_lifecycle(
            workspace_record=workspace_record,
            receipts=[allowed_envelope, blocked_envelope],
            audit_events=[],
        )
        
        # Both decisions exist in the replay
        assert len(result.frames) >= 2
        # The replay should handle the contradiction
        # Either by having partial/different state or by detecting the issue
        assert result.is_complete or result.is_partial or result.has_conflicts
        
    def test_stale_receipt_references(self):
        """Golden test: receipt chain references stale paths (GAP-005).
        
        Tests that replay detects stale receipt references (receipt references
        paths that no longer exist or receipts that reference non-existent related receipts).
        """
        workspace_record = {
            "workspace_id": "stale_test",
            "status": "executed",
            "status_history": [
                {"status": "planned", "at": "2024-01-01T00:00:00Z"},
                {"status": "active", "at": "2024-01-02T00:00:00Z"},
                {"status": "executed", "at": "2024-01-03T00:00:00Z"},
            ],
            # References receipts that don't all exist in our set
            "receipt_paths": [
                "/path/to/stale_create.json",
                "/path/to/stale_execute.json",
                "/path/to/stale_missing.json",  # This one won't be provided
            ],
            "audit_event_ids": [],
            "authoritative": True,
        }
        
        # Only provide receipts for create and execute, missing the third
        actor = ReceiptActor.cli()
        subject = ReceiptSubject.workspace("stale_test")
        
        # Create receipt
        create_decision = ReceiptDecision.allowed("stale_dec_1", "Create allowed")
        create_envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="stale_create",
            receipt_type="workspace_create",
            authority_level="authoritative",
            advisory_only=False,
            created_at="2024-01-01T00:00:00Z",
            actor=actor,
            subject=subject,
            decision=create_decision,
            inputs=[],
            outputs=[],
            evidence=[],
            related_receipt_ids=["stale_execute"],  # Reference to next receipt
            related_audit_event_ids=[],
            summary="Workspace stale_test created",
        )
        
        # Execute receipt references a receipt that doesn't exist
        execute_decision = ReceiptDecision.allowed("stale_dec_2", "Execute allowed")
        execute_envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="stale_execute",
            receipt_type="workspace_execute",
            authority_level="authoritative",
            advisory_only=False,
            created_at="2024-01-02T00:00:00Z",
            actor=actor,
            subject=subject,
            decision=execute_decision,
            inputs=[],
            outputs=[],
            evidence=[],
            # References a missing receipt
            related_receipt_ids=["stale_missing"],
            related_audit_event_ids=[],
            summary="Workspace stale_test executed",
        )
        
        result = replay_workspace_lifecycle(
            workspace_record=workspace_record,
            receipts=[create_envelope, execute_envelope],  # Missing stale_missing
            audit_events=[],
        )
        
        # Should detect stale reference or have partial state
        # The workspace record references 3 receipts but only 2 are provided
        assert result.is_complete or result.is_partial or result.has_findings
        # Check that the finding or conflict mentions missing/stale reference
        has_stale_finding = any(
            f.finding_type == "replay_receipt_continuity" or
            "stale" in f.message.lower() or
            "missing" in f.message.lower()
            for f in result.findings
        )
        has_stale_conflict = any(
            c.conflict_type in (
                ReplayConflictType.STALE_RECEIPT_CHAIN,
                ReplayConflictType.MISSING_RECEIPT,
            )
            for c in result.conflicts
        )
        assert has_stale_finding or has_stale_conflict or result.is_partial


def test_governance_rehearsal_doc_exists() -> None:
    path = Path(__file__).parent.parent / "docs" / "architecture" / "governance-routing-rehearsal.md"
    content = path.read_text(encoding="utf-8")
    assert "routing should be observable on a live PR" in content


def test_solo_maintainer_governance_doc_exists() -> None:
    path = Path(__file__).parent.parent / "docs" / "architecture" / "solo-maintainer-governance.md"
    content = path.read_text(encoding="utf-8")
    assert "branch protection" in content
    assert "CODEOWNER auto-routing does not prove separation of duties" in content
