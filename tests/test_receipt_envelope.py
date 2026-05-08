"""Tests for canonical ReceiptEnvelope domain module.

These tests verify:
- ReceiptEnvelope is a deterministic dataclass
- All models are JSON-serializable
- No side effects
- Placeholders are used for missing data
- Public intake remains advisory_only
- Receipt IDs are deterministic for stable inputs
- Authority classification works correctly
- Receipt completeness can be resolved
- Projection summaries can be built
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from rig.domain.receipt_envelope import (
    # Placeholders
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
    REQUIRED_PLACEHOLDERS,
    # Canonical types
    ReceiptEnvelope,
    ReceiptActor,
    ReceiptSubject,
    ReceiptInput,
    ReceiptOutput,
    ReceiptDecision,
    ReceiptEvidence,
    ReceiptIndexEntry,
    ReceiptWriteResult,
    # Helper functions
    utc_now,
    sha256_text,
    build_receipt_id,
    build_receipt_envelope,
    receipt_to_dict,
    receipt_from_dict,
    write_receipt,
    read_receipt,
    index_receipts,
    resolve_receipt_authority,
    resolve_receipt_completeness,
    resolve_receipt_projection_summary,
    resolve_validation_receipt_status,
    resolve_review_receipt_status,
    resolve_apply_gate_receipt_status,
    convert_legacy_to_envelope,
    # Phase 4: Validation receipt integration
    build_validation_receipt,
    build_gate_decision_receipt,
    # Phase 5: Review bundle formalization
    build_review_bundle_receipt,
    # Apply receipt helper
    build_apply_receipt,
    resolve_apply_gate_receipt_status,
    convert_legacy_to_envelope,
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
        # Phase 4 placeholders
        assert PLACEHOLDER_NO_VALIDATION == "no_validation"
        assert PLACEHOLDER_NO_GATE_DECISION == "no_gateDecision"
        assert PLACEHOLDER_VALIDATION_FAILED == "validation_failed"
        assert PLACEHOLDER_VALIDATION_INCOMPLETE == "validation_incomplete"
        # Phase 5 placeholders
        assert PLACEHOLDER_NO_REVIEW_BUNDLE == "no_review_bundle"
        assert PLACEHOLDER_REVIEW_INCOMPLETE == "review_incomplete"
        # Apply gate placeholders
        assert PLACEHOLDER_NO_APPLY_GATE == "no_apply_gate"
        assert PLACEHOLDER_APPLY_BLOCKED == "apply_blocked"


# =============================================================================
# ReceiptActor Tests
# =============================================================================

class TestReceiptActor:
    """Test ReceiptActor model."""
    
    def test_system_actor(self):
        """System actor has correct defaults."""
        actor = ReceiptActor.system()
        assert actor.actor_id == "system"
        assert actor.actor_kind == "system"
        assert actor.display_name == "System"
        assert actor.is_human is False
        assert actor.is_authoritative is True
    
    def test_cli_actor(self):
        """CLI actor has correct defaults."""
        actor = ReceiptActor.cli()
        assert actor.actor_id == "cli"
        assert actor.actor_kind == "cli"
        assert actor.display_name == "CLI"
        assert actor.is_human is True
        assert actor.is_authoritative is True
    
    def test_connector_actor(self):
        """Connector actor is NOT authoritative."""
        actor = ReceiptActor.connector("google_forms")
        assert actor.actor_id == "connector_google_forms"
        assert actor.actor_kind == "connector"
        assert actor.display_name == "google_forms"
        assert actor.is_human is False
        assert actor.is_authoritative is False  # Connectors are NOT authoritative
    
    def test_unknown_actor(self):
        """Unknown actor has placeholder values."""
        actor = ReceiptActor.unknown()
        assert actor.actor_id == PLACEHOLDER_UNKNOWN
        assert actor.actor_kind == PLACEHOLDER_UNKNOWN
        assert actor.display_name == PLACEHOLDER_UNKNOWN
        assert actor.is_human is False
        assert actor.is_authoritative is False
    
    def test_to_dict(self):
        """ReceiptActor is JSON-serializable via to_dict."""
        actor = ReceiptActor.cli()
        d = actor.to_dict()
        assert isinstance(d, dict)
        assert d["actor_id"] == "cli"
        assert d["actor_kind"] == "cli"
    
    def test_deterministic(self):
        """ReceiptActor instances with same values are equal."""
        actor1 = ReceiptActor.cli()
        actor2 = ReceiptActor.cli()
        assert actor1 == actor2


# =============================================================================
# ReceiptSubject Tests
# =============================================================================

class TestReceiptSubject:
    """Test ReceiptSubject model."""
    
    def test_workspace_subject(self):
        """Workspace subject has correct defaults."""
        subject = ReceiptSubject.workspace("ws_123")
        assert subject.subject_id == "ws_123"
        assert subject.subject_kind == "workspace"
        assert subject.workspace_id == "ws_123"
        assert subject.authoritative is True
        assert subject.advisory_only is False
    
    def test_validation_subject(self):
        """Validation subject has correct defaults."""
        subject = ReceiptSubject.validation("val_456", workspace_id="ws_123")
        assert subject.subject_id == "val_456"
        assert subject.subject_kind == "validation"
        assert subject.workspace_id == "ws_123"
        assert subject.authoritative is True
    
    def test_sync_subject(self):
        """Sync subject is advisory only."""
        subject = ReceiptSubject.sync("sync_789", connector="google_forms")
        assert subject.subject_id == "sync_789"
        assert subject.subject_kind == "sync"
        assert subject.authoritative is False
        assert subject.advisory_only is True
    
    def test_unknown_subject(self):
        """Unknown subject has placeholder values."""
        subject = ReceiptSubject.unknown()
        assert subject.subject_id == PLACEHOLDER_UNKNOWN
        assert subject.subject_kind == PLACEHOLDER_UNKNOWN
        assert subject.authoritative is False
        assert subject.advisory_only is True
    
    def test_to_dict(self):
        """ReceiptSubject is JSON-serializable via to_dict."""
        subject = ReceiptSubject.workspace("ws_123")
        d = subject.to_dict()
        assert isinstance(d, dict)
        assert d["subject_id"] == "ws_123"
        assert d["subject_kind"] == "workspace"
    
    def test_deterministic(self):
        """ReceiptSubject instances with same values are equal."""
        subject1 = ReceiptSubject.workspace("ws_123")
        subject2 = ReceiptSubject.workspace("ws_123")
        assert subject1 == subject2


# =============================================================================
# ReceiptDecision Tests
# =============================================================================

class TestReceiptDecision:
    """Test ReceiptDecision model."""
    
    def test_allowed_decision(self):
        """Allowed decision has correct defaults."""
        decision = ReceiptDecision.allowed("dec_1", "Test allowed")
        assert decision.decision_id == "dec_1"
        assert decision.decision_kind == "allowed"
        assert decision.reason == "Test allowed"
        assert decision.authoritative is True
    
    def test_blocked_decision(self):
        """Blocked decision has correct defaults."""
        decision = ReceiptDecision.blocked("dec_2", "Test blocked")
        assert decision.decision_id == "dec_2"
        assert decision.decision_kind == "blocked"
        assert decision.reason == "Test blocked"
        assert decision.authoritative is True
    
    def test_advisory_only_decision(self):
        """Advisory only decision is not authoritative."""
        decision = ReceiptDecision.advisory_only("dec_3")
        assert decision.decision_id == "dec_3"
        assert decision.decision_kind == "advisory_only"
        assert decision.authoritative is False
    
    def test_unknown_decision(self):
        """Unknown decision has placeholder values."""
        decision = ReceiptDecision.unknown()
        assert decision.decision_id == PLACEHOLDER_UNKNOWN
        assert decision.decision_kind == PLACEHOLDER_UNKNOWN
        assert decision.authoritative is False
    
    def test_to_dict(self):
        """ReceiptDecision is JSON-serializable via to_dict."""
        decision = ReceiptDecision.allowed("dec_1", "Allowed")
        d = decision.to_dict()
        assert isinstance(d, dict)
        assert d["decision_id"] == "dec_1"
        assert d["decision_kind"] == "allowed"
    
    def test_deterministic(self):
        """ReceiptDecision instances with same values are equal."""
        decision1 = ReceiptDecision.allowed("dec_1", "Allowed")
        decision2 = ReceiptDecision.allowed("dec_1", "Allowed")
        assert decision1 == decision2


# =============================================================================
# ReceiptInput/Output/Evidence Tests
# =============================================================================

class TestReceiptInputOutput:
    """Test ReceiptInput, ReceiptOutput, ReceiptEvidence models."""
    
    def test_input_of(self):
        """ReceiptInput.of creates correct input."""
        input_obj = ReceiptInput.of(
            input_id="in_1",
            input_kind="task",
            reference="ref/path",
            hash="abc123",
            summary="Test input",
        )
        assert input_obj.input_id == "in_1"
        assert input_obj.input_kind == "task"
        assert input_obj.reference == "ref/path"
        assert input_obj.hash == "abc123"
        assert input_obj.summary == "Test input"
    
    def test_output_of(self):
        """ReceiptOutput.of creates correct output."""
        output = ReceiptOutput.of(
            output_id="out_1",
            output_kind="receipt",
            reference="receipt/path.json",
            hash="def456",
            status="success",
        )
        assert output.output_id == "out_1"
        assert output.output_kind == "receipt"
        assert output.status == "success"
    
    def test_evidence_of(self):
        """ReceiptEvidence.of creates correct evidence."""
        evidence = ReceiptEvidence.of(
            evidence_id="ev_1",
            evidence_kind="file",
            reference="file/path.txt",
            hash="ghi789",
            mime_type="text/plain",
        )
        assert evidence.evidence_id == "ev_1"
        assert evidence.evidence_kind == "file"
    
    def test_evidence_file_constructor(self):
        """ReceiptEvidence.file creates file evidence."""
        evidence = ReceiptEvidence.file(
            evidence_id="ev_file",
            reference="file.txt",
            mime_type="text/plain",
        )
        assert evidence.evidence_kind == "file"
    
    def test_evidence_diff_constructor(self):
        """ReceiptEvidence.diff creates diff evidence."""
        evidence = ReceiptEvidence.diff(
            evidence_id="ev_diff",
            reference="changes.patch",
        )
        assert evidence.evidence_kind == "diff"
        assert evidence.mime_type == "text/x-patch"
    
    def test_to_dict(self):
        """Input/Output/Evidence are JSON-serializable."""
        input_obj = ReceiptInput.of("i1", "task", "ref")
        output = ReceiptOutput.of("o1", "receipt", "ref")
        evidence = ReceiptEvidence.of("e1", "file", "ref")
        
        assert isinstance(input_obj.to_dict(), dict)
        assert isinstance(output.to_dict(), dict)
        assert isinstance(evidence.to_dict(), dict)


# =============================================================================
# ReceiptEnvelope Tests
# =============================================================================

class TestReceiptEnvelope:
    """Test ReceiptEnvelope model."""
    
    def test_basic_envelope(self):
        """Basic ReceiptEnvelope creation."""
        actor = ReceiptActor.cli()
        subject = ReceiptSubject.workspace("ws_123")
        decision = ReceiptDecision.allowed("dec_1")
        
        envelope = build_receipt_envelope(
            receipt_type="workspace_create",
            receipt_id="ws_create_ws_123",
            workspace_id="ws_123",
            actor=actor,
            subject=subject,
            decision=decision,
            summary="Test workspace created",
        )
        
        assert envelope.receipt_id == "ws_create_ws_123"
        assert envelope.receipt_type == "workspace_create"
        assert envelope.schema_version == "rig.receipt_envelope.v1"
        assert envelope.authority_level == "authoritative"
        assert envelope.advisory_only is False
        assert envelope.actor == actor
        assert envelope.subject == subject
        assert envelope.decision == decision
        assert envelope.summary == "Test workspace created"
    
    def test_envelope_with_inputs_outputs_evidence(self):
        """ReceiptEnvelope with inputs, outputs, evidence."""
        envelope = build_receipt_envelope(
            receipt_type="workspace_apply",
            receipt_id="ws_apply_123",
            workspace_id="ws_123",
            inputs=[
                ReceiptInput.of("in_1", "workspace", "ws.json"),
                ReceiptInput.of("in_2", "task", "task.txt"),
            ],
            outputs=[
                ReceiptOutput.of("out_1", "receipt", "receipt.json", status="success"),
            ],
            evidence=[
                ReceiptEvidence.file("ev_1", "review.json", mime_type="application/json"),
            ],
        )
        
        assert len(envelope.inputs) == 2
        assert len(envelope.outputs) == 1
        assert len(envelope.evidence) == 1
    
    def test_advisory_only_envelope(self):
        """Advisory only envelope has correct flags."""
        envelope = build_receipt_envelope(
            receipt_type="public_sync",
            receipt_id="sync_123",
            authoritative=False,
        )
        
        assert envelope.authority_level == "advisory_only"
        assert envelope.advisory_only is True
    
    def test_to_dict(self):
        """ReceiptEnvelope is JSON-serializable via to_dict."""
        envelope = build_receipt_envelope(
            receipt_type="workspace_create",
            receipt_id="ws_123",
            workspace_id="ws_123",
        )
        d = envelope.to_dict()
        
        assert isinstance(d, dict)
        assert d["receipt_id"] == "ws_123"
        assert d["receipt_type"] == "workspace_create"
        assert "actor" in d
        assert "subject" in d
        assert "decision" in d
    
    def test_to_json(self):
        """ReceiptEnvelope can be serialized to JSON."""
        envelope = build_receipt_envelope(
            receipt_type="workspace_create",
            receipt_id="ws_123",
        )
        json_str = envelope.to_json()
        
        assert isinstance(json_str, str)
        # Should be parseable
        parsed = json.loads(json_str)
        assert parsed["receipt_id"] == "ws_123"
    
    def test_from_dict_roundtrip(self):
        """ReceiptEnvelope from_dict roundtrip works."""
        envelope = build_receipt_envelope(
            receipt_type="workspace_create",
            receipt_id="ws_123",
            workspace_id="ws_123",
            inputs=[ReceiptInput.of("in_1", "task", "ref")],
            outputs=[ReceiptOutput.of("out_1", "receipt", "ref", status="success")],
            summary="Test",
        )
        
        d = envelope.to_dict()
        restored = receipt_from_dict(d)
        
        assert restored.receipt_id == envelope.receipt_id
        assert restored.receipt_type == envelope.receipt_type
        assert len(restored.inputs) == len(envelope.inputs)
        assert len(restored.outputs) == len(envelope.outputs)
    
    def test_deterministic(self):
        """ReceiptEnvelope instances with same values are equal."""
        # Use same timestamp for both
        ts = "2024-01-01T00:00:00Z"
        actor = ReceiptActor.cli()
        subject = ReceiptSubject.workspace("ws_123")
        decision = ReceiptDecision.allowed("dec_1")
        
        envelope1 = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="ws_123",
            receipt_type="workspace_create",
            authority_level="authoritative",
            advisory_only=False,
            created_at=ts,
            actor=actor,
            subject=subject,
            decision=decision,
            inputs=(),
            outputs=(),
            evidence=(),
            related_receipt_ids=(),
            related_audit_event_ids=(),
            summary="Test",
        )
        envelope2 = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="ws_123",
            receipt_type="workspace_create",
            authority_level="authoritative",
            advisory_only=False,
            created_at=ts,
            actor=actor,
            subject=subject,
            decision=decision,
            inputs=(),
            outputs=(),
            evidence=(),
            related_receipt_ids=(),
            related_audit_event_ids=(),
            summary="Test",
        )
        assert envelope1 == envelope2
    
    def test_frozen(self):
        """ReceiptEnvelope is immutable (frozen)."""
        envelope = build_receipt_envelope(receipt_id="ws_123", receipt_type="create")
        
        with pytest.raises(AttributeError):
            envelope.receipt_id = "modified"


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestBuildReceiptId:
    """Test build_receipt_id helper."""
    
    def test_simple_id(self):
        """Simple receipt ID from type."""
        receipt_id = build_receipt_id("ws_create", workspace_id="ws_123")
        assert receipt_id == "ws_create_ws_123"
    
    def test_with_additional_parts(self):
        """Receipt ID with additional parts."""
        receipt_id = build_receipt_id(
            "ws_trans",
            workspace_id="ws_123",
            additional_parts=["planned", "to", "active"],
        )
        assert receipt_id == "ws_trans_ws_123_planned_to_active"
    
    def test_no_workspace_id(self):
        """Receipt ID without workspace ID."""
        receipt_id = build_receipt_id("sync", additional_parts=["google_forms"])
        assert receipt_id == "sync_google_forms"
    
    def test_deterministic_ids(self):
        """Same inputs produce same receipt ID."""
        id1 = build_receipt_id("ws_create", workspace_id="ws_123")
        id2 = build_receipt_id("ws_create", workspace_id="ws_123")
        assert id1 == id2


class TestWriteReadReceipt:
    """Test write_receipt and read_receipt functions."""
    
    def test_write_and_read_receipt(self):
        """Write and read receipt roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            envelope = build_receipt_envelope(
                receipt_type="workspace_create",
                receipt_id="ws_test_123",
                workspace_id="ws_test_123",
                summary="Test write/read",
            )
            
            result = write_receipt(repo_root, envelope)
            
            assert result.status == "success"
            assert result.receipt_id == "ws_test_123"
            assert Path(result.receipt_path).exists()
            
            # Read it back
            read_envelope = read_receipt(Path(result.receipt_path))
            
            assert read_envelope is not None
            assert read_envelope.receipt_id == envelope.receipt_id
            assert read_envelope.receipt_type == envelope.receipt_type
    
    def test_read_nonexistent(self):
        """Read non-existent receipt returns None."""
        nonexistent = Path("/tmp/nonexistent_receipt.json")
        assert read_receipt(nonexistent) is None


class TestIndexReceipts:
    """Test index_receipts function."""
    
    def test_index_empty_directory(self):
        """Index empty directory returns empty tuple."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            entries = index_receipts(repo_root)
            assert entries == ()
    
    def test_index_multiple_receipts(self):
        """Index multiple receipts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # Write some receipts
            for i in range(3):
                envelope = build_receipt_envelope(
                    receipt_type="workspace_create",
                    receipt_id=f"ws_{i:03d}",
                    workspace_id=f"ws_{i:03d}",
                )
                write_receipt(repo_root, envelope)
            
            entries = index_receipts(repo_root)
            
            assert len(entries) == 3
            # Check they're sorted by receipt_id
            receipt_ids = [e.receipt_id for e in entries]
            assert receipt_ids == sorted(receipt_ids)


# =============================================================================
# Resolution Helper Tests
# =============================================================================

class TestResolveReceiptAuthority:
    """Test resolve_receipt_authority helper."""
    
    def test_public_sync_is_advisory_only(self):
        """Public sync receipts are always advisory only."""
        result = resolve_receipt_authority(
            receipt_type="public_sync",
            actor_kind="connector",
            subject_kind="sync",
        )
        assert result["authoritative"] is False
        assert result["advisory_only"] is True
        assert "advisory_only" in result["reason"]
    
    def test_connector_is_not_authoritative(self):
        """Connector actions are NOT authoritative."""
        result = resolve_receipt_authority(
            receipt_type="workspace_create",
            actor_kind="connector",
            subject_kind="workspace",
        )
        assert result["authoritative"] is False
        assert result["advisory_only"] is True
    
    def test_workspace_creation_is_authoritative(self):
        """Workspace creation by Rig is authoritative."""
        result = resolve_receipt_authority(
            receipt_type="workspace_create",
            actor_kind="cli",
            subject_kind="workspace",
        )
        assert result["authoritative"] is True
        assert result["advisory_only"] is False
    
    def test_workspace_apply_is_authoritative(self):
        """Workspace apply to main is authoritative."""
        result = resolve_receipt_authority(
            receipt_type="workspace_apply",
            actor_kind="cli",
            subject_kind="workspace",
        )
        assert result["authoritative"] is True
        assert result["advisory_only"] is False
    
    def test_validation_is_authoritative(self):
        """Validation by Rig is authoritative."""
        result = resolve_receipt_authority(
            receipt_type="validation",
            actor_kind="domain",
            subject_kind="validation",
        )
        assert result["authoritative"] is True
        assert result["advisory_only"] is False


class TestResolveReceiptCompleteness:
    """Test resolve_receipt_completeness helper."""
    
    def test_complete_envelope(self):
        """Complete envelope has no missing fields."""
        envelope = build_receipt_envelope(
            receipt_type="workspace_create",
            receipt_id="ws_123",
            workspace_id="ws_123",
            actor=ReceiptActor.cli(),
            subject=ReceiptSubject.workspace("ws_123"),
            decision=ReceiptDecision.allowed("dec_1"),
            summary="Complete",
        )
        
        result = resolve_receipt_completeness(envelope)
        
        assert result["complete"] is True
        assert result["missing_fields"] == ()
        assert result["completeness_score"] == 1.0
    
    def test_missing_receipt_id(self):
        """Envelope with missing receipt_id is not complete."""
        # Create a minimal envelope - receipt_id is required
        envelope = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="",  # Empty
            receipt_type="workspace_create",
            authority_level="authoritative",
            advisory_only=False,
            created_at=utc_now(),
            actor=ReceiptActor.system(),
            subject=ReceiptSubject.unknown(),
            decision=ReceiptDecision.unknown(),
            inputs=(),
            outputs=(),
            evidence=(),
            related_receipt_ids=(),
            related_audit_event_ids=(),
            summary="",
        )
        
        result = resolve_receipt_completeness(envelope)
        
        assert result["complete"] is False
        assert "receipt_id" in result["missing_fields"]
    
    def test_placeholder_actor(self):
        """Envelope with placeholder actor is not complete."""
        envelope = build_receipt_envelope(
            receipt_type="workspace_create",
            receipt_id="ws_123",
            workspace_id="ws_123",
            actor=ReceiptActor.unknown(),  # Placeholder
        )
        
        result = resolve_receipt_completeness(envelope)
        
        assert result["complete"] is False
        assert "actor" in result["placeholder_fields"]


class TestResolveReceiptProjectionSummary:
    """Test resolve_receipt_projection_summary helper."""
    
    def test_empty_envelopes(self):
        """Empty list produces placeholder values."""
        result = resolve_receipt_projection_summary([])
        
        assert result["receipt_count"] == 0
        assert result["authoritative_receipt_count"] == 0
        assert result["advisory_receipt_count"] == 0
        assert result["last_receipt_id"] == PLACEHOLDER_NO_RECEIPT
        assert result["validation_receipt_status"] == PLACEHOLDER_NOT_RUN
    
    def test_authoritative_envelopes(self):
        """Authoritative envelopes are counted correctly."""
        envelopes = [
            build_receipt_envelope(
                receipt_type="workspace_create",
                receipt_id=f"ws_{i}",
                workspace_id=f"ws_{i}",
                authoritative=True,
            )
            for i in range(3)
        ]
        
        result = resolve_receipt_projection_summary(envelopes)
        
        assert result["receipt_count"] == 3
        assert result["authoritative_receipt_count"] == 3
        assert result["advisory_receipt_count"] == 0
    
    def test_mixed_authoritative_advisory(self):
        """Mixed authoritative and advisory envelopes."""
        envelopes = [
            *[
                build_receipt_envelope(
                    receipt_type="workspace_create",
                    receipt_id=f"ws_{i}",
                    workspace_id=f"ws_{i}",
                    authoritative=True,
                )
                for i in range(2)
            ],
            build_receipt_envelope(
                receipt_type="public_sync",
                receipt_id="sync_1",
                authoritative=False,  # advisory only
            ),
        ]
        
        result = resolve_receipt_projection_summary(envelopes)
        
        assert result["receipt_count"] == 3
        assert result["authoritative_receipt_count"] == 2
        assert result["advisory_receipt_count"] == 1
    
    def test_validation_status_passed(self):
        """Validation status is resolved correctly."""
        envelopes = [
            build_receipt_envelope(
                receipt_type="validation",
                receipt_id="val_1",
                outputs=[ReceiptOutput.of("out_1", "result", "ref", status="passed")],
            ),
        ]
        
        result = resolve_receipt_projection_summary(envelopes)
        
        assert result["validation_receipt_status"] == "passed"
    
    def test_validation_status_failed(self):
        """Validation failed status."""
        envelopes = [
            build_receipt_envelope(
                receipt_type="validation",
                receipt_id="val_1",
                outputs=[ReceiptOutput.of("out_1", "result", "ref", status="failed")],
            ),
        ]
        
        result = resolve_receipt_projection_summary(envelopes)
        
        assert result["validation_receipt_status"] == "failed"
    
    def test_validation_status_not_run(self):
        """No validation envelopes."""
        envelopes = [
            build_receipt_envelope(
                receipt_type="workspace_create",
                receipt_id="ws_1",
            ),
        ]
        
        result = resolve_receipt_projection_summary(envelopes)
        
        assert result["validation_receipt_status"] == PLACEHOLDER_NOT_RUN


# =============================================================================
# Legacy Conversion Tests
# =============================================================================

class TestConvertLegacyToEnvelope:
    """Test convert_legacy_to_envelope helper."""
    
    def test_convert_workspace_create_legacy(self):
        """Convert legacy workspace create receipt to envelope."""
        legacy_data = {
            "schema_version": "rig.workspace_create_receipt.v1",
            "receipt_id": "ws_create_abc123",
            "workspace_id": "abc123",
            "task": "test task",
            "branch": "feature/test",
            "base_commit": "abc123def",
            "worktree_path": "/tmp/worktree",
            "status": "success",
            "authoritative": True,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        
        envelope = convert_legacy_to_envelope(
            legacy_data,
            receipt_type="workspace_create",
            workspace_id="abc123",
        )
        
        assert envelope.receipt_id == "ws_create_abc123"
        assert envelope.receipt_type == "workspace_create"
        assert envelope.authority_level == "authoritative"
        assert envelope.subject.subject_id == "abc123"
        assert envelope.subject.subject_kind == "workspace"
    
    def test_convert_failed_status(self):
        """Convert legacy receipt with failed status."""
        legacy_data = {
            "receipt_id": "test_123",
            "workspace_id": "ws_123",
            "status": "failed",
            "authoritative": True,
        }
        
        envelope = convert_legacy_to_envelope(
            legacy_data,
            receipt_type="validation",
        )
        
        assert envelope.decision.decision_kind == "blocked"
    
    def test_convert_advisory_only(self):
        """Convert legacy advisory receipt."""
        legacy_data = {
            "receipt_id": "sync_123",
            "workspace_id": None,
            "status": "success",
            "authoritative": False,
        }
        
        envelope = convert_legacy_to_envelope(
            legacy_data,
            receipt_type="public_sync",
        )
        
        assert envelope.advisory_only is True
        assert envelope.authority_level == "advisory_only"


# =============================================================================
# Side Effect Tests
# =============================================================================

class TestNoSideEffects:
    """Verify no side effects from receipt primitives."""
    
    def test_receipt_actor_no_side_effects(self):
        """ReceiptActor creation has no side effects."""
        before = ReceiptActor.system()
        after = ReceiptActor.system()
        assert before == after
    
    def test_receipt_envelope_no_side_effects(self):
        """ReceiptEnvelope creation has no side effects."""
        ts = "2024-01-01T00:00:00Z"
        before = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="test",
            receipt_type="test",
            authority_level="authoritative",
            advisory_only=False,
            created_at=ts,
            actor=ReceiptActor.system(),
            subject=ReceiptSubject.unknown(),
            decision=ReceiptDecision.unknown(),
            inputs=(),
            outputs=(),
            evidence=(),
            related_receipt_ids=(),
            related_audit_event_ids=(),
            summary="test",
        )
        after = ReceiptEnvelope(
            schema_version="rig.receipt_envelope.v1",
            receipt_id="test",
            receipt_type="test",
            authority_level="authoritative",
            advisory_only=False,
            created_at=ts,
            actor=ReceiptActor.system(),
            subject=ReceiptSubject.unknown(),
            decision=ReceiptDecision.unknown(),
            inputs=(),
            outputs=(),
            evidence=(),
            related_receipt_ids=(),
            related_audit_event_ids=(),
            summary="test",
        )
        assert before == after


# =============================================================================
# Integration Tests
# =============================================================================

class TestReceiptIntegration:
    """Integration tests for receipt primitives."""
    
    def test_full_workspace_lifecycle(self):
        """Test complete workspace lifecycle with receipts."""
        # Create workspace creation receipt
        create_envelope = build_receipt_envelope(
            receipt_type="workspace_create",
            receipt_id="ws_create_test",
            workspace_id="test",
            actor=ReceiptActor.cli(),
            subject=ReceiptSubject.workspace("test"),
            decision=ReceiptDecision.allowed("dec_create"),
            inputs=[ReceiptInput.of("task", "task", "Test task")],
            summary="Workspace created",
        )
        
        # Create transition receipt
        trans_envelope = build_receipt_envelope(
            receipt_type="workspace_transition",
            receipt_id="ws_trans_test_planned_to_active",
            workspace_id="test",
            actor=ReceiptActor.cli(),
            subject=ReceiptSubject.workspace("test"),
            decision=ReceiptDecision.allowed("dec_trans"),
            summary="Transitioned to active",
        )
        
        # Create apply receipt
        apply_envelope = build_receipt_envelope(
            receipt_type="workspace_apply",
            receipt_id="ws_apply_test",
            workspace_id="test",
            actor=ReceiptActor.cli(),
            subject=ReceiptSubject.workspace("test"),
            decision=ReceiptDecision.allowed("dec_apply"),
            outputs=[ReceiptOutput.of("main", "main", "abc123", status="success")],
            evidence=[ReceiptEvidence.diff("diff_1", "diff.patch")],
            summary="Workspace applied",
        )
        
        # All envelopes
        envelopes = [create_envelope, trans_envelope, apply_envelope]
        
        # Build projection summary
        summary = resolve_receipt_projection_summary(envelopes)
        
        assert summary["receipt_count"] == 3
        assert summary["authoritative_receipt_count"] == 3
        assert summary["apply_gate_receipt_status"] == "applied"
    
    def test_advisory_only_workspace_flow(self):
        """Test advisory only receipt flow."""
        # Create public sync receipt (advisory only)
        sync_envelope = build_receipt_envelope(
            receipt_type="public_sync",
            receipt_id="sync_google_forms_1",
            actor=ReceiptActor.connector("google_forms"),
            subject=ReceiptSubject.sync("sync_1", connector="google_forms"),
            decision=ReceiptDecision.advisory_only("dec_sync", "External sync data"),
            summary="Public intake sync",
            authoritative=False,
        )
        
        # Verify it's advisory only (authoritative is derived from authority_level)
        assert sync_envelope.advisory_only is True
        assert sync_envelope.authority_level == "advisory_only"
        
        # Build projection summary
        summary = resolve_receipt_projection_summary([sync_envelope])
        
        assert summary["advisory_receipt_count"] == 1
        assert summary["authoritative_receipt_count"] == 0
        
        # Verify authority resolution
        auth = resolve_receipt_authority(
            receipt_type="public_sync",
            actor_kind="connector",
            subject_kind="sync",
        )
        assert auth["authoritative"] is False
        assert auth["advisory_only"] is True


# =============================================================================
# Phase 4: Validation Receipt Integration Tests
# =============================================================================

class TestBuildValidationReceipt:
    """Test build_validation_receipt helper function."""

    def test_build_validation_receipt_passed(self):
        """Build validation receipt with passed status."""
        validation_result = {
            "status": "passed",
            "workspace_id": "test_workspace",
            "validators": [
                {"validator_id": "v1", "exit_code": 0, "required": True, "stdout_tail": "", "stderr_tail": ""},
                {"validator_id": "v2", "exit_code": 0, "required": False, "stdout_tail": "", "stderr_tail": ""},
            ],
        }
        envelope = build_validation_receipt(
            workspace_id="test_workspace",
            validation_result=validation_result,
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:01:00Z",
            authoritative=True,
        )
        assert envelope.receipt_type == "validation"
        assert envelope.subject.workspace_id == "test_workspace"
        assert envelope.actor.actor_kind == "domain"
        assert envelope.subject.subject_kind == "validation"
        assert envelope.decision.decision_kind == "allowed"
        assert len(envelope.inputs) >= 1
        assert len(envelope.outputs) >= 1
        assert envelope.authority_level == "authoritative"
        assert envelope.advisory_only is False

    def test_build_validation_receipt_failed(self):
        """Build validation receipt with failed status."""
        validation_result = {
            "status": "failed",
            "workspace_id": "test_workspace",
            "validators": [
                {"validator_id": "v1", "exit_code": 1, "required": True, "stdout_tail": "", "stderr_tail": "error"},
            ],
        }
        envelope = build_validation_receipt(
            workspace_id="test_workspace",
            validation_result=validation_result,
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:01:00Z",
            authoritative=True,
        )
        assert envelope.receipt_type == "validation"
        assert envelope.decision.decision_kind == "blocked"
        assert len(envelope.evidence) >= 1  # Should have stderr evidence

    def test_build_gate_decision_receipt_allowed(self):
        """Build gate decision receipt with allowed decision."""
        envelope = build_gate_decision_receipt(
            workspace_id="test_workspace",
            gate_name="validation_gate",
            decision="allowed",
            reason="All validators passed",
            related_receipt_ids=["validation_123"],
            authoritative=True,
        )
        assert envelope.receipt_type == "gate_decision"
        assert envelope.subject.workspace_id == "test_workspace"
        assert envelope.decision.decision_kind == "allowed"
        assert len(envelope.inputs) >= 2
        assert len(envelope.related_receipt_ids) == 1
        assert envelope.related_receipt_ids[0] == "validation_123"

    def test_build_gate_decision_receipt_blocked(self):
        """Build gate decision receipt with blocked decision."""
        envelope = build_gate_decision_receipt(
            workspace_id="test_workspace",
            gate_name="apply_gate",
            decision="blocked",
            reason="Validation failed",
            related_receipt_ids=["validation_123", "review_456"],
            authoritative=True,
        )
        assert envelope.receipt_type == "gate_decision"
        assert envelope.decision.decision_kind == "blocked"
        assert len(envelope.related_receipt_ids) == 2


# =============================================================================
# Phase 5: Review Bundle Formalization Tests
# =============================================================================

class TestBuildReviewBundleReceipt:
    """Test build_review_bundle_receipt helper function."""

    def test_build_review_bundle_receipt_eligible(self):
        """Build review bundle receipt with apply eligible."""
        review_bundle = {
            "workspace_id": "test_workspace",
            "workspace_status": "validated",
            "validation_status": "passed",
            "apply_eligibility": True,
            "known_blockers": [],
            "changed_files": ["file1.py", "file2.py"],
            "diff_hash": "abc123",
            "worktree_path": "/tmp/test",
        }
        envelope = build_review_bundle_receipt(
            workspace_id="test_workspace",
            review_bundle=review_bundle,
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:01:00Z",
            authoritative=True,
        )
        assert envelope.receipt_type == "review_bundle"
        assert envelope.subject.workspace_id == "test_workspace"
        assert envelope.decision.decision_kind == "allowed"
        assert len(envelope.outputs) >= 1
        assert len(envelope.evidence) == 2  # changed files

    def test_build_review_bundle_receipt_not_eligible(self):
        """Build review bundle receipt with apply not eligible."""
        review_bundle = {
            "workspace_id": "test_workspace",
            "workspace_status": "blocked",
            "validation_status": "failed",
            "apply_eligibility": False,
            "known_blockers": ["validation failed"],
            "changed_files": [],
            "diff_hash": "",
            "worktree_path": "/tmp/test",
        }
        envelope = build_review_bundle_receipt(
            workspace_id="test_workspace",
            review_bundle=review_bundle,
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:01:00Z",
            authoritative=True,
        )
        assert envelope.receipt_type == "review_bundle"
        assert envelope.decision.decision_kind == "blocked"


# =============================================================================
# Apply Receipt Tests
# =============================================================================

class TestBuildApplyReceipt:
    """Test build_apply_receipt helper function."""

    def test_build_apply_receipt(self):
        """Build apply receipt for workspace."""
        apply_result = {
            "workspace_id": "test_workspace",
            "base_commit": "abc123",
            "workspace_branch": "feature/test",
            "main_before": "def456",
            "main_after": "ghi789",
        }
        envelope = build_apply_receipt(
            workspace_id="test_workspace",
            apply_result=apply_result,
            started_at="2024-01-01T00:00:00Z",
            finished_at="2024-01-01T00:01:00Z",
            related_receipt_ids=["validation_123", "review_456"],
            authoritative=True,
        )
        assert envelope.receipt_type == "workspace_apply"
        assert envelope.subject.workspace_id == "test_workspace"
        assert envelope.decision.decision_kind == "allowed"
        assert len(envelope.related_receipt_ids) == 2
        assert len(envelope.outputs) >= 1


# =============================================================================
# Phase 6: Enhanced Projection Summary Tests
# =============================================================================

class TestEnhancedProjectionSummary:
    """Test enhanced resolve_receipt_projection_summary with Phase 6 fields."""

    def test_enhanced_projection_summary_all_fields(self):
        """Test projection summary has all required Phase 6 fields."""
        envelopes = [
            build_receipt_envelope(
                receipt_type="workspace_create",
                receipt_id="ws_create_1",
                workspace_id="test_workspace",
                actor=ReceiptActor.system(),
                subject=ReceiptSubject.workspace("test_workspace"),
                decision=ReceiptDecision.allowed("d1", "allowed"),
                authoritative=True,
            ),
            build_validation_receipt(
                workspace_id="test_workspace",
                validation_result={"status": "passed", "validators": []},
                started_at="2024-01-01T00:00:00Z",
                finished_at="2024-01-01T00:01:00Z",
            ),
        ]
        summary = resolve_receipt_projection_summary(envelopes)
        
        # Check all required Phase 6 fields are present
        assert "receipt_count" in summary
        assert "authoritative_receipt_count" in summary
        assert "advisory_receipt_count" in summary
        assert "missing_receipt_count" in summary
        assert "last_receipt_id" in summary
        assert "last_receipt_summary" in summary
        assert "type_counts" in summary
        assert "validation_receipt_status" in summary
        assert "review_receipt_status" in summary
        assert "apply_gate_receipt_status" in summary
        assert "gate_decision_status" in summary
        assert "next_missing_receipt_action" in summary
        assert "auditability_status" in summary
        assert "authoritative_evidence_available" in summary
        
        # Check specific values
        assert summary["receipt_count"] == 2
        assert summary["authoritative_receipt_count"] == 2
        assert summary["validation_receipt_status"] == "passed"
        assert summary["authoritative_evidence_available"] is True

    def test_enhanced_projection_summary_auditability(self):
        """Test auditability status computation."""
        # No receipts - not auditable
        summary = resolve_receipt_projection_summary([])
        assert summary["auditability_status"] == "not_auditable"
        
        # Only authoritative - minimally auditable
        envelopes = [
            build_receipt_envelope(
                receipt_type="workspace_create",
                receipt_id="ws_create_1",
                workspace_id="test_workspace",
                actor=ReceiptActor.system(),
                subject=ReceiptSubject.workspace("test_workspace"),
                decision=ReceiptDecision.allowed("d1", "allowed"),
                authoritative=True,
            ),
        ]
        summary = resolve_receipt_projection_summary(envelopes)
        assert summary["auditability_status"] == "minimally_auditable"
        
        # Authoritative + validation - partially auditable
        envelopes.append(
            build_validation_receipt(
                workspace_id="test_workspace",
                validation_result={"status": "passed", "validators": []},
                started_at="2024-01-01T00:00:00Z",
                finished_at="2024-01-01T00:01:00Z",
            )
        )
        summary = resolve_receipt_projection_summary(envelopes)
        assert summary["auditability_status"] == "partially_auditable"
        
        # Authoritative + validation + review - fully auditable
        envelopes.append(
            build_review_bundle_receipt(
                workspace_id="test_workspace",
                review_bundle={
                    "workspace_id": "test_workspace",
                    "validation_status": "passed",
                    "apply_eligibility": True,
                    "changed_files": [],
                    "diff_hash": "",
                    "worktree_path": "/tmp/test",
                },
                started_at="2024-01-01T00:00:00Z",
                finished_at="2024-01-01T00:01:00Z",
            )
        )
        summary = resolve_receipt_projection_summary(envelopes)
        assert summary["auditability_status"] == "fully_auditable"
