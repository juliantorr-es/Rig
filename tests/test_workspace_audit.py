"""Tests for workspace authority and auditability primitives.

These tests verify:
- Audit primitives are deterministic dataclasses
- All models are JSON-serializable
- No side effects
- Placeholders are used for missing data
- Public intake remains advisory_only
- Funding remains advisory_only
- Unknown values use explicit placeholders
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from rig.domain.workspace_audit import (
    # Placeholders
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_UNAVAILABLE,
    PLACEHOLDER_NOT_CREATED,
    PLACEHOLDER_NOT_RUN,
    PLACEHOLDER_NOT_PROOF,
    PLACEHOLDER_ADVISORY_ONLY,
    PLACEHOLDER_NOT_AUTHORITATIVE,
    PLACEHOLDER_NO_RECEIPT,
    REQUIRED_PLACEHOLDERS,
    # Enums
    AuditAction,
    AuditSubjectKind,
    AuditDecision,
    AuditReceiptStatus,
    # Models
    AuditActor,
    AuditSubject,
    AuditEvent,
    AuditReceiptLink,
    WorkspaceAuditTrail,
    # Helpers
    resolve_mutation_authority,
    resolve_receipt_status,
    resolve_audit_completeness,
    build_workspace_audit_trail,
    build_auditability_state,
)


# =============================================================================
# Placeholder Tests
# =============================================================================

class TestPlaceholders:
    """Test that all required placeholders are defined."""
    
    def test_all_required_placeholders_defined(self):
        """All required placeholders must be defined."""
        for placeholder in REQUIRED_PLACEHOLDERS:
            assert isinstance(placeholder, str)
            assert len(placeholder) > 0
    
    def test_placeholder_values(self):
        """Placeholder constants have expected values."""
        assert PLACEHOLDER_UNKNOWN == "unknown"
        assert PLACEHOLDER_UNAVAILABLE == "unavailable"
        assert PLACEHOLDER_NOT_CREATED == "not_created"
        assert PLACEHOLDER_NOT_RUN == "not_run"
        assert PLACEHOLDER_NOT_PROOF == "not_proof"
        assert PLACEHOLDER_ADVISORY_ONLY == "advisory_only"
        assert PLACEHOLDER_NOT_AUTHORITATIVE == "not_authoritative"
        assert PLACEHOLDER_NO_RECEIPT == "no_receipt"


# =============================================================================
# Enum Tests
# =============================================================================

class TestAuditEnums:
    """Test audit enum values."""
    
    def test_audit_action_enum(self):
        """AuditAction enum has expected values."""
        assert AuditAction.CREATE.value == "create"
        assert AuditAction.READ.value == "read"
        assert AuditAction.UPDATE.value == "update"
        assert AuditAction.DELETE.value == "delete"
        assert AuditAction.TRANSITION.value == "transition"
        assert AuditAction.APPLY.value == "apply"
        assert AuditAction.REVIEW.value == "review"
        assert AuditAction.VALIDATE.value == "validate"
        assert AuditAction.IMPORT.value == "import"
        assert AuditAction.SYNC.value == "sync"
        assert AuditAction.UNKNOWN.value == PLACEHOLDER_UNKNOWN
    
    def test_audit_subject_kind_enum(self):
        """AuditSubjectKind enum has expected values."""
        assert AuditSubjectKind.WORKSPACE.value == "workspace"
        assert AuditSubjectKind.PUBLIC_INTAKE_PACKET.value == "public_intake_packet"
        assert AuditSubjectKind.PUBLIC_SYNC_RECEIPT.value == "public_sync_receipt"
        assert AuditSubjectKind.UNKNOWN.value == PLACEHOLDER_UNKNOWN
    
    def test_audit_decision_enum(self):
        """AuditDecision enum has expected values."""
        assert AuditDecision.ALLOWED.value == "allowed"
        assert AuditDecision.BLOCKED.value == "blocked"
        assert AuditDecision.PENDING.value == "pending"
        assert AuditDecision.ADVISORY_ONLY.value == PLACEHOLDER_ADVISORY_ONLY
    
    def test_audit_receipt_status_enum(self):
        """AuditReceiptStatus enum has expected values."""
        assert AuditReceiptStatus.EXISTS.value == "exists"
        assert AuditReceiptStatus.LINKED.value == "linked"
        assert AuditReceiptStatus.MISSING.value == "missing"
        assert AuditReceiptStatus.NOT_REQUIRED.value == "not_required"
        assert AuditReceiptStatus.ADVISORY_ONLY.value == PLACEHOLDER_ADVISORY_ONLY
        assert AuditReceiptStatus.NOT_AUTHORITATIVE.value == PLACEHOLDER_NOT_AUTHORITATIVE
        assert AuditReceiptStatus.NO_RECEIPT.value == PLACEHOLDER_NO_RECEIPT


# =============================================================================
# AuditActor Tests
# =============================================================================

class TestAuditActor:
    """Test AuditActor model."""
    
    def test_system_actor(self):
        """System actor has correct defaults."""
        actor = AuditActor.system()
        assert actor.actor_id == "system"
        assert actor.actor_kind == "system"
        assert actor.display_name == "System"
        assert actor.is_human is False
        assert actor.is_authoritative is True
    
    def test_cli_actor(self):
        """CLI actor has correct defaults."""
        actor = AuditActor.cli()
        assert actor.actor_id == "cli"
        assert actor.actor_kind == "cli"
        assert actor.display_name == "CLI"
        assert actor.is_human is True
        assert actor.is_authoritative is True
    
    def test_connector_actor(self):
        """Connector actor is NOT authoritative."""
        actor = AuditActor.connector("google_forms")
        assert actor.actor_id == "connector_google_forms"
        assert actor.actor_kind == "connector"
        assert actor.display_name == "google_forms"
        assert actor.is_human is False
        assert actor.is_authoritative is False  # Connectors are NOT authoritative
    
    def test_unknown_actor(self):
        """Unknown actor has placeholder values."""
        actor = AuditActor.unknown()
        assert actor.actor_id == PLACEHOLDER_UNKNOWN
        assert actor.actor_kind == PLACEHOLDER_UNKNOWN
        assert actor.display_name == PLACEHOLDER_UNKNOWN
        assert actor.is_human is False
        assert actor.is_authoritative is False
    
    def test_to_dict(self):
        """AuditActor is JSON-serializable via to_dict."""
        actor = AuditActor.cli()
        d = actor.to_dict()
        assert isinstance(d, dict)
        assert d["actor_id"] == "cli"
        assert d["actor_kind"] == "cli"
    
    def test_deterministic(self):
        """AuditActor instances with same values are equal."""
        actor1 = AuditActor.cli()
        actor2 = AuditActor.cli()
        assert actor1 == actor2


# =============================================================================
# AuditSubject Tests
# =============================================================================

class TestAuditSubject:
    """Test AuditSubject model."""
    
    def test_workspace_subject(self):
        """Workspace subject has correct defaults."""
        subject = AuditSubject.workspace("ws_123")
        assert subject.subject_id == "ws_123"
        assert subject.subject_kind == AuditSubjectKind.WORKSPACE
        assert subject.workspace_id == "ws_123"
        assert subject.authoritative is True
        assert subject.advisory_only is False
    
    def test_proposal_subject(self):
        """Proposal subject has correct defaults."""
        subject = AuditSubject.proposal("prop_456", workspace_id="ws_123")
        assert subject.subject_id == "prop_456"
        assert subject.subject_kind == AuditSubjectKind.PROPOSAL
        assert subject.workspace_id == "ws_123"
        assert subject.authoritative is True
        assert subject.advisory_only is False
    
    def test_public_intake_packet_subject(self):
        """Public intake packet subject is advisory only."""
        subject = AuditSubject.public_intake_packet("packet_789")
        assert subject.subject_id == "packet_789"
        assert subject.subject_kind == AuditSubjectKind.PUBLIC_INTAKE_PACKET
        assert subject.authoritative is False  # Public intake is NEVER authoritative
        assert subject.advisory_only is True
    
    def test_unknown_subject(self):
        """Unknown subject has placeholder values."""
        subject = AuditSubject.unknown()
        assert subject.subject_id == PLACEHOLDER_UNKNOWN
        assert subject.subject_kind == AuditSubjectKind.UNKNOWN
        assert subject.authoritative is False
        assert subject.advisory_only is True
    
    def test_to_dict(self):
        """AuditSubject is JSON-serializable via to_dict."""
        subject = AuditSubject.workspace("ws_123")
        d = subject.to_dict()
        assert isinstance(d, dict)
        assert d["subject_id"] == "ws_123"
    
    def test_deterministic(self):
        """AuditSubject instances with same values are equal."""
        subject1 = AuditSubject.workspace("ws_123")
        subject2 = AuditSubject.workspace("ws_123")
        assert subject1 == subject2


# =============================================================================
# AuditEvent Tests
# =============================================================================

class TestAuditEvent:
    """Test AuditEvent model."""
    
    def test_workspace_creation_event(self):
        """Workspace creation event has correct properties."""
        event = AuditEvent.for_workspace_creation(
            workspace_id="ws_123",
            receipt_id="receipt_456",
        )
        assert event.event_id == "ws_create_ws_123"
        assert event.action == AuditAction.CREATE
        assert event.subject.subject_id == "ws_123"
        assert event.decision == AuditDecision.ALLOWED
        assert event.status == "success"
        assert event.receipt_id == "receipt_456"
        assert event.receipt_kind == "workspace_create_receipt"
        assert event.receipt_status == AuditReceiptStatus.EXISTS
        assert event.authoritative is True
        assert event.advisory_only is False
    
    def test_workspace_creation_event_no_receipt(self):
        """Workspace creation event without receipt has MISSING status."""
        event = AuditEvent.for_workspace_creation(
            workspace_id="ws_123",
            receipt_id=None,
        )
        assert event.receipt_status == AuditReceiptStatus.MISSING
    
    def test_workspace_transition_event(self):
        """Workspace transition event has correct properties."""
        event = AuditEvent.for_workspace_transition(
            workspace_id="ws_123",
            old_status="planned",
            new_status="active",
            receipt_id="receipt_789",
        )
        assert event.event_id == "ws_trans_ws_123_planned_to_active"
        assert event.action == AuditAction.TRANSITION
        assert event.details["old_status"] == "planned"
        assert event.details["new_status"] == "active"
        assert event.receipt_id == "receipt_789"
    
    def test_workspace_apply_event(self):
        """Workspace apply event has correct properties."""
        event = AuditEvent.for_workspace_apply(
            workspace_id="ws_123",
            main_before="abc123",
            main_after="def456",
            receipt_id="apply_receipt",
        )
        assert event.event_id == "ws_apply_ws_123"
        assert event.action == AuditAction.APPLY
        assert event.details["main_before"] == "abc123"
        assert event.details["main_after"] == "def456"
        assert event.receipt_id == "apply_receipt"
    
    def test_public_intake_import_event(self):
        """Public intake import event is advisory only."""
        event = AuditEvent.for_public_intake_import(
            connector="google_forms",
            packet_count=5,
            sync_receipt_id="sync_123",
        )
        assert event.action == AuditAction.IMPORT
        assert event.authoritative is False
        assert event.advisory_only is True
        assert event.details["connector"] == "google_forms"
        assert event.details["packet_count"] == 5
    
    def test_to_dict(self):
        """AuditEvent is JSON-serializable via to_dict."""
        event = AuditEvent.for_workspace_creation("ws_123")
        d = event.to_dict()
        assert isinstance(d, dict)
        assert "actor" in d
        assert "subject" in d
        assert d["event_id"] == "ws_create_ws_123"
    
    def test_full_json_serialization(self):
        """AuditEvent can be fully serialized to JSON and back."""
        event = AuditEvent.for_workspace_creation(
            workspace_id="ws_123",
            actor=AuditActor.cli(),
            receipt_id="receipt_456",
        )
        d = event.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        
        # Verify it can be parsed back
        parsed = json.loads(json_str)
        assert parsed["event_id"] == "ws_create_ws_123"
        assert parsed["action"] == "create"
    
    def test_deterministic(self):
        """AuditEvent instances with same explicit values are equal."""
        # Use same timestamp for both to ensure equality
        ts = "2024-01-01T00:00:00Z"
        event1 = AuditEvent(
            event_id="ws_create_ws_123",
            action=AuditAction.CREATE,
            actor=AuditActor.cli(),
            subject=AuditSubject.workspace("ws_123"),
            decision=AuditDecision.ALLOWED,
            timestamp=ts,
            status="success",
            summary="Workspace ws_123 created",
            receipt_id="r1",
            receipt_kind="workspace_create_receipt",
            receipt_status=AuditReceiptStatus.EXISTS,
            workspace_id="ws_123",
            authoritative=True,
            advisory_only=False,
        )
        event2 = AuditEvent(
            event_id="ws_create_ws_123",
            action=AuditAction.CREATE,
            actor=AuditActor.cli(),
            subject=AuditSubject.workspace("ws_123"),
            decision=AuditDecision.ALLOWED,
            timestamp=ts,
            status="success",
            summary="Workspace ws_123 created",
            receipt_id="r1",
            receipt_kind="workspace_create_receipt",
            receipt_status=AuditReceiptStatus.EXISTS,
            workspace_id="ws_123",
            authoritative=True,
            advisory_only=False,
        )
        assert event1 == event2


# =============================================================================
# AuditReceiptLink Tests
# =============================================================================

class TestAuditReceiptLink:
    """Test AuditReceiptLink model."""
    
    def test_of_link(self):
        """Receipt link via of() has correct properties."""
        link = AuditReceiptLink.of(
            event_id="event_123",
            receipt_id="receipt_456",
            receipt_kind="workspace_create",
            workspace_id="ws_789",
        )
        assert link.link_id == "link_event_123_receipt_456"
        assert link.event_id == "event_123"
        assert link.receipt_id == "receipt_456"
        assert link.receipt_kind == "workspace_create"
        assert link.workspace_id == "ws_789"
        assert link.status == AuditReceiptStatus.EXISTS
    
    def test_missing_link(self):
        """Missing receipt link has correct properties."""
        link = AuditReceiptLink.missing(
            event_id="event_123",
            receipt_kind="workspace_create",
            reason=PLACEHOLDER_NO_RECEIPT,
        )
        assert link.link_id == "link_event_123_missing_workspace_create"
        assert link.receipt_id == PLACEHOLDER_NO_RECEIPT
        assert link.status == AuditReceiptStatus.MISSING
        assert link.authoritative is False
        assert link.advisory_only is True
    
    def test_to_dict(self):
        """AuditReceiptLink is JSON-serializable via to_dict."""
        link = AuditReceiptLink.of("event_123", "receipt_456", "create")
        d = link.to_dict()
        assert isinstance(d, dict)
        assert d["event_id"] == "event_123"
    
    def test_deterministic(self):
        """AuditReceiptLink instances with same values are equal."""
        link1 = AuditReceiptLink.of("e1", "r1", "create")
        link2 = AuditReceiptLink.of("e1", "r1", "create")
        assert link1 == link2


# =============================================================================
# WorkspaceAuditTrail Tests
# =============================================================================

class TestWorkspaceAuditTrail:
    """Test WorkspaceAuditTrail model."""
    
    def test_empty_trail(self):
        """Empty trail has correct defaults."""
        trail = WorkspaceAuditTrail.empty("ws_123")
        assert trail.workspace_id == "ws_123"
        assert trail.events == ()
        assert trail.receipt_links == ()
        assert trail.audit_completeness == PLACEHOLDER_UNKNOWN
    
    def test_with_event(self):
        """Trail with event adds event correctly."""
        trail = WorkspaceAuditTrail.empty("ws_123")
        event = AuditEvent.for_workspace_creation("ws_123")
        trail2 = trail.with_event(event)
        assert len(trail2.events) == 1
        assert trail2.events[0] == event
    
    def test_with_receipt_link(self):
        """Trail with receipt link adds link correctly."""
        trail = WorkspaceAuditTrail.empty("ws_123")
        link = AuditReceiptLink.of("event_123", "receipt_456", "create")
        trail2 = trail.with_receipt_link(link)
        assert len(trail2.receipt_links) == 1
        assert trail2.receipt_links[0] == link
    
    def test_to_dict(self):
        """WorkspaceAuditTrail is JSON-serializable via to_dict."""
        trail = WorkspaceAuditTrail.empty("ws_123")
        d = trail.to_dict()
        assert isinstance(d, dict)
        assert d["workspace_id"] == "ws_123"
        assert d["events"] == []
    
    def test_deterministic(self):
        """WorkspaceAuditTrail instances with same values are equal."""
        trail1 = WorkspaceAuditTrail(
            workspace_id="ws_123",
            events=(),
            receipt_links=(),
        )
        trail2 = WorkspaceAuditTrail(
            workspace_id="ws_123",
            events=(),
            receipt_links=(),
        )
        assert trail1 == trail2


# =============================================================================
# Resolution Helper Tests
# =============================================================================

class TestResolveMutationAuthority:
    """Test resolve_mutation_authority helper."""
    
    def test_public_intake_is_advisory_only(self):
        """Public intake mutations are always advisory only."""
        result = resolve_mutation_authority(
            action=AuditAction.IMPORT,
            subject_kind=AuditSubjectKind.PUBLIC_INTAKE_PACKET,
            actor_kind="connector",
        )
        assert result["authoritative"] is False
        assert result["advisory_only"] is True
        assert "advisory_only" in result["reason"]
    
    def test_connector_is_not_authoritative(self):
        """Connector actions are NOT authoritative."""
        result = resolve_mutation_authority(
            action=AuditAction.CREATE,
            subject_kind=AuditSubjectKind.WORKSPACE,
            actor_kind="connector",
        )
        assert result["authoritative"] is False
        assert result["advisory_only"] is True
    
    def test_workspace_mutation_is_authoritative(self):
        """Workspace mutations by Rig are authoritative."""
        result = resolve_mutation_authority(
            action=AuditAction.CREATE,
            subject_kind=AuditSubjectKind.WORKSPACE,
            actor_kind="cli",
        )
        assert result["authoritative"] is True
        assert result["advisory_only"] is False
    
    def test_apply_to_main_is_authoritative(self):
        """Apply to main branch is authoritative."""
        result = resolve_mutation_authority(
            action=AuditAction.APPLY,
            subject_kind=AuditSubjectKind.GIT_MAIN,
            actor_kind="cli",
        )
        assert result["authoritative"] is True
        assert result["advisory_only"] is False


class TestResolveReceiptStatus:
    """Test resolve_receipt_status helper."""
    
    def test_receipt_exists(self):
        """Existing receipt returns EXISTS status."""
        event = AuditEvent.for_workspace_creation("ws_123", receipt_id="r123")
        status = resolve_receipt_status(event, receipt_exists=True)
        assert status == AuditReceiptStatus.EXISTS
    
    def test_receipt_missing(self):
        """Missing receipt returns MISSING status."""
        event = AuditEvent.for_workspace_creation("ws_123", receipt_id="r123")
        status = resolve_receipt_status(event, receipt_exists=False)
        assert status == AuditReceiptStatus.MISSING
    
    def test_no_receipt_id(self):
        """No receipt_id returns NO_RECEIPT status."""
        event = AuditEvent(
            event_id="test",
            action=AuditAction.CREATE,
            receipt_id=None,
        )
        status = resolve_receipt_status(event, receipt_exists=False)
        assert status == AuditReceiptStatus.NO_RECEIPT
    
    def test_advisory_only_no_receipt_required(self):
        """Advisory only events don't require receipts."""
        event = AuditEvent.for_public_intake_import("google_forms", 5, sync_receipt_id=None)
        status = resolve_receipt_status(event, receipt_exists=False)
        assert status == AuditReceiptStatus.ADVISORY_ONLY


class TestResolveAuditCompleteness:
    """Test resolve_audit_completeness helper."""
    
    def test_empty_trail(self):
        """Empty trail has NOT_CREATED completeness."""
        trail = WorkspaceAuditTrail.empty("ws_123")
        result = resolve_audit_completeness(trail)
        assert result["completeness"] == PLACEHOLDER_NOT_CREATED
        assert result["score"] == 0.0
    
    def test_workspace_create_without_receipt(self):
        """Workspace creation without receipt is incomplete."""
        trail = WorkspaceAuditTrail(
            workspace_id="ws_123",
            events=(
                AuditEvent.for_workspace_creation("ws_123", receipt_id=None),
            ),
        )
        result = resolve_audit_completeness(trail)
        assert result["completeness"] == PLACEHOLDER_NOT_PROOF
        assert "workspace_create" in result["missing"]
    
    def test_workspace_create_with_receipt(self):
        """Workspace creation with receipt is more complete."""
        trail = WorkspaceAuditTrail(
            workspace_id="ws_123",
            events=(
                AuditEvent.for_workspace_creation("ws_123", receipt_id="r123"),
            ),
        )
        result = resolve_audit_completeness(trail)
        # Creation has receipt, so missing_receipts should not include workspace_create
        # But the receipt_exists check in resolve_audit_completeness doesn't verify
        # if the receipt actually exists - it just checks receipt_id is present
        assert "workspace_create" not in result["missing"]


class TestBuildWorkspaceAuditTrail:
    """Test build_workspace_audit_trail helper."""
    
    def test_basic_trail(self):
        """Basic trail building works."""
        events = [
            AuditEvent.for_workspace_creation("ws_123", receipt_id="r1"),
        ]
        trail = build_workspace_audit_trail("ws_123", events)
        assert trail.workspace_id == "ws_123"
        assert len(trail.events) == 1
        # Completeness should be calculated
        assert trail.audit_completeness in ("complete", PLACEHOLDER_NOT_PROOF, PLACEHOLDER_NOT_RUN, PLACEHOLDER_UNKNOWN)


class TestBuildAuditabilityState:
    """Test build_auditability_state helper."""
    
    def test_with_audit_trail(self):
        """Auditability state from trail."""
        trail = WorkspaceAuditTrail(
            workspace_id="ws_123",
            events=(
                AuditEvent.for_workspace_creation("ws_123", receipt_id="r1"),
            ),
            audit_completeness="complete",
            last_authoritative_event_id="ws_create_ws_123",
        )
        state = build_auditability_state(audit_trail=trail)
        assert state["audit_completeness"] == "complete"
        assert state["last_authoritative_event_id"] == "ws_create_ws_123"
        assert state["next_missing_audit_action"] == PLACEHOLDER_NO_RECEIPT
    
    def test_without_audit_trail(self):
        """Auditability state without trail uses placeholders."""
        state = build_auditability_state()
        assert state["audit_completeness"] == PLACEHOLDER_NOT_CREATED
        assert state["last_authoritative_event_id"] == PLACEHOLDER_UNKNOWN


# =============================================================================
# Side Effect Tests
# =============================================================================

class TestNoSideEffects:
    """Verify no side effects from audit primitives."""
    
    def test_audit_actor_no_side_effects(self):
        """AuditActor creation has no side effects."""
        before = AuditActor.system()
        after = AuditActor.system()
        assert before == after
    
    def test_audit_event_no_side_effects(self):
        """AuditEvent creation has no side effects (with same timestamp)."""
        ts = "2024-01-01T00:00:00Z"
        before = AuditEvent(
            event_id="ws_create_ws_123",
            action=AuditAction.CREATE,
            actor=AuditActor.cli(),
            subject=AuditSubject.workspace("ws_123"),
            decision=AuditDecision.ALLOWED,
            timestamp=ts,
            receipt_id="r1",
        )
        after = AuditEvent(
            event_id="ws_create_ws_123",
            action=AuditAction.CREATE,
            actor=AuditActor.cli(),
            subject=AuditSubject.workspace("ws_123"),
            decision=AuditDecision.ALLOWED,
            timestamp=ts,
            receipt_id="r1",
        )
        assert before == after
    
    def test_audit_trail_no_side_effects(self):
        """WorkspaceAuditTrail creation has no side effects."""
        ts = "2024-01-01T00:00:00Z"
        events = [AuditEvent(
            event_id="ws_create_ws_123",
            action=AuditAction.CREATE,
            actor=AuditActor.cli(),
            subject=AuditSubject.workspace("ws_123"),
            decision=AuditDecision.ALLOWED,
            timestamp=ts,
            receipt_id="r1",
        )]
        before = build_workspace_audit_trail("ws_123", events)
        after = build_workspace_audit_trail("ws_123", events)
        assert before == after


# =============================================================================
# Integration Tests
# =============================================================================

class TestAuditIntegration:
    """Integration tests for audit primitives."""
    
    def test_full_audit_flow(self):
        """Test complete audit flow from creation to trail."""
        # Create audit actors
        cli_actor = AuditActor.cli()
        
        # Create workspace
        create_event = AuditEvent.for_workspace_creation(
            workspace_id="ws_123",
            actor=cli_actor,
            receipt_id="create_receipt",
        )
        
        # Transition workspace
        transition_event = AuditEvent.for_workspace_transition(
            workspace_id="ws_123",
            old_status="planned",
            new_status="active",
            actor=cli_actor,
            receipt_id="transition_receipt",
        )
        
        # Create receipt links
        create_link = AuditReceiptLink.of(
            event_id=create_event.event_id,
            receipt_id="create_receipt",
            receipt_kind="workspace_create",
            workspace_id="ws_123",
        )
        transition_link = AuditReceiptLink.of(
            event_id=transition_event.event_id,
            receipt_id="transition_receipt",
            receipt_kind="workspace_transition",
            workspace_id="ws_123",
        )
        
        # Build trail
        trail = build_workspace_audit_trail(
            workspace_id="ws_123",
            events=[create_event, transition_event],
            receipt_links=[create_link, transition_link],
        )
        
        # Build auditability state
        audit_state = build_auditability_state(audit_trail=trail)
        
        # Verify
        assert audit_state["authoritative_events"] == 2
        assert audit_state["advisory_only_events"] == 0
    
    def test_advisory_only_flow(self):
        """Test advisory only flow for public intake."""
        # Create connector actor (not authoritative)
        connector_actor = AuditActor.connector("google_forms")
        
        # Create import event (advisory only)
        import_event = AuditEvent.for_public_intake_import(
            connector="google_forms",
            packet_count=5,
            sync_receipt_id="sync_receipt",
            actor=connector_actor,
        )
        
        # Verify it's advisory only
        assert import_event.authoritative is False
        assert import_event.advisory_only is True
        
        # Build trail (public intake events don't have a workspace_id)
        trail = build_workspace_audit_trail(
            workspace_id="advisory_only",  # Use placeholder workspace_id for advisory events
            events=[import_event],
        )
        
        # Build auditability state
        audit_state = build_auditability_state(audit_trail=trail)
        
        # Verify
        assert audit_state["authoritative_events"] == 0
        assert audit_state["advisory_only_events"] == 1
        assert "advisory_only" in audit_state["advisory_only_warning"].lower()
