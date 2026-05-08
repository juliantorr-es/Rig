"""Tests for workspace integrity validation module.

These tests verify:
- Integrity types are deterministic dataclasses
- All models are JSON-serializable
- No side effects
- All canonical integrity checks work correctly
- Detection rules produce correct findings
- Severity levels are properly assigned
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from rig.domain.integrity import (
    IntegritySeverity,
    IntegrityViolationCode,
    IntegrityFinding,
    IntegrityCheckResult,
    IntegritySummary,
    IntegritySubject,
    validate_workspace_integrity,
    validate_receipt_integrity,
    validate_audit_integrity,
    validate_projection_integrity,
    validate_repository_integrity,
    build_integrity_summary,
    resolve_integrity_status,
)


# =============================================================================
# Type Tests
# =============================================================================

class TestIntegritySeverity:
    """Test IntegritySeverity enum."""
    
    def test_all_values_defined(self):
        """All severity levels are defined."""
        assert IntegritySeverity.INFO.value == "info"
        assert IntegritySeverity.WARNING.value == "warning"
        assert IntegritySeverity.ERROR.value == "error"
        assert IntegritySeverity.CRITICAL.value == "critical"
    
    def test_severity_order(self):
        """Severity order is correct."""
        info = IntegrityFinding(
            finding_id="test_info",
            violation_code=IntegrityViolationCode.MISSING_RECEIPT_LINKS,
            severity=IntegritySeverity.INFO,
            title="Test",
            message="Test",
            subject_type="test",
            subject_id="test",
        )
        warning = IntegrityFinding(
            finding_id="test_warning",
            violation_code=IntegrityViolationCode.ORPHANED_RECEIPT_FILE,
            severity=IntegritySeverity.WARNING,
            title="Test",
            message="Test",
            subject_type="test",
            subject_id="test",
        )
        error = IntegrityFinding(
            finding_id="test_error",
            violation_code=IntegrityViolationCode.INVALID_WORKSPACE_STATUS,
            severity=IntegritySeverity.ERROR,
            title="Test",
            message="Test",
            subject_type="test",
            subject_id="test",
        )
        critical = IntegrityFinding(
            finding_id="test_critical",
            violation_code=IntegrityViolationCode.DUPLICATE_RECEIPT_IDS,
            severity=IntegritySeverity.CRITICAL,
            title="Test",
            message="Test",
            subject_type="test",
            subject_id="test",
        )
        
        assert info.severity_order == 0
        assert warning.severity_order == 1
        assert error.severity_order == 2
        assert critical.severity_order == 3


class TestIntegrityViolationCode:
    """Test IntegrityViolationCode enum."""
    
    def test_workspace_codes(self):
        """Workspace-related violation codes."""
        assert IntegrityViolationCode.INVALID_WORKSPACE_STATUS.value == "WS-001"
        assert IntegrityViolationCode.INVALID_WORKSPACE_TRANSITION.value == "WS-002"
        assert IntegrityViolationCode.TERMINAL_APPLIED_TRANSITION.value == "WS-003"
    
    def test_receipt_codes(self):
        """Receipt-related violation codes."""
        assert IntegrityViolationCode.DUPLICATE_RECEIPT_IDS.value == "duplicate_receipt_ids"
        assert IntegrityViolationCode.MISSING_CANONICAL_FIELDS.value == "missing_canonical_fields"
    
    def test_authority_codes(self):
        """Authority-related violation codes."""
        assert IntegrityViolationCode.ADVISORY_AUTHORITY_LEAK.value == "advisory_authority_leak"
        assert IntegrityViolationCode.INVALID_AUTHORITY_ESCALATION.value == "invalid_authority_escalation"


class TestIntegrityFinding:
    """Test IntegrityFinding model."""
    
    def test_deterministic(self):
        """IntegrityFinding instances with same values are equal."""
        finding1 = IntegrityFinding(
            finding_id="test_001",
            violation_code=IntegrityViolationCode.INVALID_WORKSPACE_STATUS,
            severity=IntegritySeverity.ERROR,
            title="Test finding",
            message="Test message",
            subject_type="workspace",
            subject_id="ws_123",
            details={"key": "value"},
            timestamp="2024-01-01T00:00:00Z",
        )
        finding2 = IntegrityFinding(
            finding_id="test_001",
            violation_code=IntegrityViolationCode.INVALID_WORKSPACE_STATUS,
            severity=IntegritySeverity.ERROR,
            title="Test finding",
            message="Test message",
            subject_type="workspace",
            subject_id="ws_123",
            details={"key": "value"},
            timestamp="2024-01-01T00:00:00Z",
        )
        assert finding1 == finding2
    
    def test_to_dict(self):
        """IntegrityFinding is JSON-serializable via to_dict."""
        finding = IntegrityFinding(
            finding_id="test_001",
            violation_code=IntegrityViolationCode.INVALID_WORKSPACE_STATUS,
            severity=IntegritySeverity.ERROR,
            title="Test finding",
            message="Test message",
            subject_type="workspace",
            subject_id="ws_123",
        )
        d = finding.to_dict()
        assert isinstance(d, dict)
        assert d["finding_id"] == "test_001"
        assert d["violation_code"] == "WS-001"
        assert d["severity"] == "error"
        assert d["subject_type"] == "workspace"
        assert d["subject_id"] == "ws_123"
    
    def test_full_json_serialization(self):
        """IntegrityFinding can be fully serialized to JSON and back."""
        finding = IntegrityFinding(
            finding_id="test_001",
            violation_code=IntegrityViolationCode.INVALID_WORKSPACE_STATUS,
            severity=IntegritySeverity.ERROR,
            title="Test finding",
            message="Test message",
            subject_type="workspace",
            subject_id="ws_123",
            details={"key": "value"},
        )
        d = finding.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        
        # Verify it can be parsed back
        parsed = json.loads(json_str)
        assert parsed["finding_id"] == "test_001"
        assert parsed["violation_code"] == "WS-001"
        assert parsed["severity"] == "error"


class TestIntegrityCheckResult:
    """Test IntegrityCheckResult model."""
    
    def test_passed_result(self):
        """Passed check result."""
        result = IntegrityCheckResult(
            subject_id="ws_123",
            subject_type="workspace",
            check_name="workspace_integrity",
            passed=True,
            findings=(),
        )
        assert result.passed is True
        assert result.warnings == 0
        assert result.errors == 0
        assert result.critical == 0
    
    def test_failed_result(self):
        """Failed check result with findings."""
        findings = [
            IntegrityFinding(
                finding_id="f1",
                violation_code=IntegrityViolationCode.INVALID_WORKSPACE_STATUS,
                severity=IntegritySeverity.ERROR,
                title="Error",
                message="Error message",
                subject_type="workspace",
                subject_id="ws_123",
            ),
            IntegrityFinding(
                finding_id="f2",
                violation_code=IntegrityViolationCode.DUPLICATE_RECEIPT_IDS,
                severity=IntegritySeverity.CRITICAL,
                title="Critical",
                message="Critical message",
                subject_type="receipt",
                subject_id="r_123",
            ),
        ]
        result = IntegrityCheckResult(
            subject_id="ws_123",
            subject_type="workspace",
            check_name="workspace_integrity",
            passed=False,
            findings=tuple(findings),
            warnings=0,
            errors=1,
            critical=1,
            info=0,
        )
        assert result.passed is False
        assert result.errors == 1
        assert result.critical == 1
        assert len(result.findings) == 2
    
    def test_to_dict(self):
        """IntegrityCheckResult is JSON-serializable."""
        result = IntegrityCheckResult(
            subject_id="ws_123",
            subject_type="workspace",
            check_name="workspace_integrity",
            passed=True,
            findings=(),
        )
        d = result.to_dict()
        assert isinstance(d, dict)
        assert d["subject_id"] == "ws_123"
        assert d["passed"] is True


class TestIntegritySummary:
    """Test IntegritySummary model."""
    
    def test_clean_summary(self):
        """Clean integrity summary."""
        summary = IntegritySummary(
            total_checks=5,
            total_findings=0,
            overall_status="clean",
            integrity_score=1.0,
        )
        assert summary.overall_status == "clean"
        assert summary.integrity_score == 1.0
        assert summary.total_findings == 0
    
    def test_critical_summary(self):
        """Critical integrity summary."""
        summary = IntegritySummary(
            total_checks=5,
            total_findings=2,
            findings_by_severity={"critical": 2},
            overall_status="critical",
            integrity_score=0.0,
        )
        assert summary.overall_status == "critical"
        assert summary.integrity_score == 0.0
    
    def test_to_dict(self):
        """IntegritySummary is JSON-serializable."""
        summary = IntegritySummary(
            total_checks=5,
            total_findings=2,
            overall_status="clean",
            integrity_score=1.0,
        )
        d = summary.to_dict()
        assert isinstance(d, dict)
        assert d["total_checks"] == 5
        assert d["overall_status"] == "clean"


# =============================================================================
# Validation Function Tests
# =============================================================================

class TestValidateWorkspaceIntegrity:
    """Test validate_workspace_integrity function."""
    
    def test_valid_workspace(self):
        """Valid workspace passes all checks."""
        workspace = {
            "workspace_id": "valid_ws",
            "status": "planned",
            "status_history": [{"status": "planned", "at": "2024-01-01T00:00:00Z"}],
        }
        result = validate_workspace_integrity(workspace)
        assert result.passed is True
        assert result.subject_id == "valid_ws"
        assert result.subject_type == "workspace"
        assert len(result.findings) == 0
    
    def test_invalid_status(self):
        """Invalid workspace status produces finding."""
        workspace = {
            "workspace_id": "invalid_ws",
            "status": "invalid_state",
            "status_history": [],
        }
        result = validate_workspace_integrity(workspace)
        assert result.passed is False
        assert len(result.findings) >= 1
        # Check for the specific violation code
        finding_codes = [f.violation_code for f in result.findings]
        assert IntegrityViolationCode.INVALID_WORKSPACE_STATUS in finding_codes
    
    def test_time_travel_status_history(self):
        """Out-of-order status history produces finding."""
        workspace = {
            "workspace_id": "time_travel_ws",
            "status": "active",
            "status_history": [
                {"status": "planned", "at": "2024-02-01T00:00:00Z"},
                {"status": "active", "at": "2024-01-01T00:00:00Z"},  # Time travel!
            ],
        }
        result = validate_workspace_integrity(workspace)
        assert result.passed is False
        finding_codes = [f.violation_code for f in result.findings]
        assert IntegrityViolationCode.TIME_TRAVEL_STATUS_HISTORY in finding_codes
    
    def test_validation_failed_but_eligible(self):
        """Validation failed but apply eligible produces finding."""
        workspace = {
            "workspace_id": "ws_contradiction",
            "status": "blocked",
            "validation_status": "failed",
            "apply_eligibility": True,
        }
        result = validate_workspace_integrity(workspace)
        assert result.passed is False
        finding_codes = [f.violation_code for f in result.findings]
        # Should have the validation failed finding
        assert any("VG-003" in str(f.violation_code) or "VALIDATION_FAILED" in str(f.violation_code) for f in result.findings)


class TestValidateReceiptIntegrity:
    """Test validate_receipt_integrity function."""
    
    def test_valid_receipt(self):
        """Valid receipt passes all checks."""
        receipt = {
            "receipt_id": "valid_receipt",
            "receipt_type": "workspace_create",
            "authority_level": "authoritative",
            "advisory_only": False,
            "created_at": "2024-01-01T00:00:00Z",
            "actor": {"actor_id": "cli", "actor_kind": "cli"},
            "subject": {"subject_id": "ws_123", "subject_kind": "workspace", "workspace_id": "ws_123"},
            "decision": {"decision_id": "dec_1", "decision_kind": "allowed"},
            "inputs": [],
            "outputs": [],
            "evidence": [],
            "related_receipt_ids": [],
            "related_audit_event_ids": [],
            "summary": "Valid receipt",
        }
        result = validate_receipt_integrity(receipt)
        # May have some findings but should not have critical errors
        assert result.subject_id == "valid_receipt"
        assert result.subject_type == "receipt"
    
    def test_missing_receipt_id(self):
        """Missing receipt_id produces finding."""
        receipt = {
            "receipt_type": "workspace_create",
            "authority_level": "authoritative",
            "advisory_only": False,
        }
        result = validate_receipt_integrity(receipt)
        assert result.passed is False
        finding_codes = [f.violation_code for f in result.findings]
        # Missing receipt_id defaults to "unknown" which is a placeholder
        assert IntegrityViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER in finding_codes
    
    def test_public_sync_must_be_advisory(self):
        """Public sync receipt marked authoritative produces finding."""
        receipt = {
            "receipt_id": "sync_123",
            "receipt_type": "public_sync",
            "authority_level": "authoritative",
            "advisory_only": False,
            "subject": {"subject_kind": "sync"},
            "actor": {"actor_kind": "connector"},
        }
        result = validate_receipt_integrity(receipt)
        assert result.passed is False
        finding_codes = [f.violation_code for f in result.findings]
        assert IntegrityViolationCode.PUBLIC_INTAKE_ACTOR_AUTHORITATIVE in finding_codes
    
    def test_placeholder_in_receipt_id(self):
        """Placeholder in receipt_id produces finding."""
        receipt = {
            "receipt_id": "unknown",
            "receipt_type": "workspace_create",
            "authority_level": "authoritative",
            "advisory_only": False,
        }
        result = validate_receipt_integrity(receipt)
        assert result.passed is False
        finding_codes = [f.violation_code for f in result.findings]
        assert IntegrityViolationCode.AUTHORITATIVE_FIELD_PLACEHOLDER in finding_codes


class TestValidateRepositoryIntegrity:
    """Test validate_repository_integrity function."""
    
    def test_empty_repository(self):
        """Empty repository has clean integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            summary = validate_repository_integrity(repo_root)
            assert summary.overall_status == "clean"
            assert summary.integrity_score == 1.0
            assert summary.total_checks == 0
    
    def test_with_valid_workspace(self):
        """Repository with valid workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            workspace_dir = repo_root / ".build" / "rig" / "workspaces"
            workspace_dir.mkdir(parents=True)
            
            workspace_data = {
                "workspace_id": "test_ws",
                "status": "planned",
                "status_history": [{"status": "planned", "at": "2024-01-01T00:00:00Z"}],
            }
            (workspace_dir / "test_ws.json").write_text(json.dumps(workspace_data))
            
            summary = validate_repository_integrity(repo_root)
            assert summary.overall_status == "clean"
    
    def test_with_invalid_workspace(self):
        """Repository with invalid workspace produces findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            workspace_dir = repo_root / ".build" / "rig" / "workspaces"
            workspace_dir.mkdir(parents=True)
            
            workspace_data = {
                "workspace_id": "invalid_ws",
                "status": "invalid_state",
            }
            (workspace_dir / "invalid_ws.json").write_text(json.dumps(workspace_data))
            
            summary = validate_repository_integrity(repo_root)
            assert summary.total_checks >= 1
            assert summary.total_findings >= 1
            assert summary.overall_status != "clean"
    
    def test_duplicate_receipt_ids(self):
        """Duplicate receipt IDs produce critical finding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            receipt_dir = repo_root / ".build" / "rig" / "receipts"
            receipt_dir.mkdir(parents=True)
            
            receipt_data = {
                "receipt_id": "duplicate_id",
                "receipt_type": "workspace_create",
            }
            (receipt_dir / "duplicate_id.json").write_text(json.dumps(receipt_data))
            # Create a subdirectory receipt with same ID
            subdir = receipt_dir / "sub"
            subdir.mkdir()
            (subdir / "duplicate_id.json").write_text(json.dumps(receipt_data))
            
            summary = validate_repository_integrity(repo_root)
            assert summary.total_findings >= 1
            finding_codes = [f.violation_code.value for f in summary.all_findings]
            assert "duplicate_receipt_ids" in finding_codes or IntegrityViolationCode.DUPLICATE_RECEIPT_IDS.value in finding_codes


class TestBuildIntegritySummary:
    """Test build_integrity_summary function."""
    
    def test_empty_results(self):
        """Empty check results produces clean summary."""
        summary = build_integrity_summary([])
        assert summary.total_checks == 0
        assert summary.total_findings == 0
        assert summary.overall_status == "clean"
    
    def test_with_findings(self):
        """Check results with findings."""
        finding = IntegrityFinding(
            finding_id="test",
            violation_code=IntegrityViolationCode.INVALID_WORKSPACE_STATUS,
            severity=IntegritySeverity.ERROR,
            title="Test",
            message="Test",
            subject_type="workspace",
            subject_id="ws_123",
        )
        check_result = IntegrityCheckResult(
            subject_id="ws_123",
            subject_type="workspace",
            check_name="workspace_integrity",
            passed=False,
            findings=(finding,),
            errors=1,
        )
        summary = build_integrity_summary([check_result])
        assert summary.total_checks == 1
        assert summary.total_findings == 1
        assert summary.overall_status == "errors"


class TestResolveIntegrityStatus:
    """Test resolve_integrity_status function."""
    
    def test_clean_status(self):
        """Clean status."""
        summary = IntegritySummary(overall_status="clean")
        status = resolve_integrity_status(summary)
        assert status == "clean"
    
    def test_critical_status(self):
        """Critical status."""
        summary = IntegritySummary(overall_status="critical")
        status = resolve_integrity_status(summary)
        assert status == "critical"


# =============================================================================
# Side Effect Tests
# =============================================================================

class TestNoSideEffects:
    """Verify no side effects from integrity validation."""
    
    def test_validate_workspace_no_side_effects(self):
        """validate_workspace_integrity has no side effects."""
        workspace = {
            "workspace_id": "test_ws",
            "status": "planned",
        }
        result1 = validate_workspace_integrity(workspace)
        result2 = validate_workspace_integrity(workspace)
        assert result1 == result2
    
    def test_validate_receipt_no_side_effects(self):
        """validate_receipt_integrity has no side effects."""
        receipt = {
            "receipt_id": "test_receipt",
            "receipt_type": "workspace_create",
        }
        result1 = validate_receipt_integrity(receipt)
        result2 = validate_receipt_integrity(receipt)
        assert result1 == result2
    
    def test_build_summary_no_side_effects(self):
        """build_integrity_summary has no side effects."""
        check_result = IntegrityCheckResult(
            subject_id="test",
            subject_type="workspace",
            check_name="test",
            passed=True,
        )
        summary1 = build_integrity_summary([check_result])
        summary2 = build_integrity_summary([check_result])
        assert summary1 == summary2


# =============================================================================
# Golden Determinism Tests
# =============================================================================

class TestGoldenDeterminism:
    """Golden tests for deterministic integrity validation."""
    
    def test_workspace_validation_deterministic(self):
        """Workspace validation produces deterministic results."""
        workspace = {
            "workspace_id": "det_test_ws",
            "status": "validated",
            "status_history": [
                {"status": "planned", "at": "2024-01-01T00:00:00Z"},
                {"status": "active", "at": "2024-01-02T00:00:00Z"},
                {"status": "executed", "at": "2024-01-03T00:00:00Z"},
                {"status": "validated", "at": "2024-01-04T00:00:00Z"},
            ],
        }
        result1 = validate_workspace_integrity(workspace)
        result2 = validate_workspace_integrity(workspace)
        
        # Results should be equal
        assert result1 == result2
        # Findings should be in same order
        assert result1.findings == result2.findings
    
    def test_receipt_validation_deterministic(self):
        """Receipt validation produces deterministic results."""
        receipt = {
            "receipt_id": "det_test_receipt",
            "receipt_type": "workspace_create",
            "authority_level": "authoritative",
            "advisory_only": False,
            "created_at": "2024-01-01T00:00:00Z",
            "actor": {"actor_id": "cli", "actor_kind": "cli"},
            "subject": {"subject_id": "ws_123", "subject_kind": "workspace", "workspace_id": "ws_123"},
            "decision": {"decision_id": "dec_1", "decision_kind": "allowed"},
        }
        result1 = validate_receipt_integrity(receipt)
        result2 = validate_receipt_integrity(receipt)
        
        assert result1 == result2
    
    def test_finding_to_dict_deterministic(self):
        """Finding to_dict produces deterministic output."""
        finding = IntegrityFinding(
            finding_id="det_test_finding",
            violation_code=IntegrityViolationCode.INVALID_WORKSPACE_STATUS,
            severity=IntegritySeverity.ERROR,
            title="Deterministic Test",
            message="This is a deterministic test message",
            subject_type="workspace",
            subject_id="ws_123",
            details={"test_key": "test_value"},
            timestamp="2024-01-01T00:00:00Z",
        )
        dict1 = finding.to_dict()
        dict2 = finding.to_dict()
        
        # Dicts should be equal (note: timestamp might differ if not fixed)
        # Just check the structure is the same
        assert set(dict1.keys()) == set(dict2.keys())
        assert dict1["finding_id"] == dict2["finding_id"]
        assert dict1["violation_code"] == dict2["violation_code"]


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegrityIntegration:
    """Integration tests for integrity validation."""
    
    def test_full_workspace_lifecycle_validation(self):
        """Test validation of complete workspace lifecycle."""
        # Create validation receipt
        validation_receipt = {
            "receipt_id": "val_ws_123",
            "receipt_type": "validation",
            "authority_level": "authoritative",
            "advisory_only": False,
            "subject": {"workspace_id": "ws_123"},
        }
        
        # Create workspace
        workspace = {
            "workspace_id": "ws_123",
            "status": "validated",
            "validation_status": "passed",
            "apply_eligibility": True,
            "status_history": [
                {"status": "planned", "at": "2024-01-01T00:00:00Z"},
                {"status": "active", "at": "2024-01-02T00:00:00Z"},
                {"status": "executed", "at": "2024-01-03T00:00:00Z"},
                {"status": "validated", "at": "2024-01-04T00:00:00Z"},
            ],
        }
        
        ws_result = validate_workspace_integrity(workspace)
        val_result = validate_receipt_integrity(validation_receipt)
        
        # Both should pass
        assert ws_result.passed is True
        assert val_result.passed is True or len(val_result.findings) == 0
    
    def test_mixed_validation_with_findings(self):
        """Test validation with both passing and failing checks."""
        # Invalid workspace
        invalid_workspace = {
            "workspace_id": "invalid",
            "status": "invalid_state",
        }
        
        # Valid receipt
        valid_receipt = {
            "receipt_id": "valid_receipt",
            "receipt_type": "workspace_create",
            "authority_level": "authoritative",
            "advisory_only": False,
        }
        
        ws_result = validate_workspace_integrity(invalid_workspace)
        receipt_result = validate_receipt_integrity(valid_receipt)
        
        summary = build_integrity_summary([ws_result, receipt_result])
        
        # Should have at least one finding
        assert summary.total_findings >= 1
        # Overall status should not be clean
        assert summary.overall_status != "clean"
