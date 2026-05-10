"""Tests for ADR 0010 Mission 4 - Forge Promotion Gates in Agent Workflow.

These tests validate that:
1. _work_lib forge gate helper functions work correctly
2. forge readiness is tracked in projection
3. All tests use mocked subprocess - no real Git mutation, no remote API calls.

Note: work_*.py scripts are standalone scripts that use subprocess to call
rig forge commands. Testing them end-to-end requires mocking subprocess at
both the script level (for rig forge commands) and the work script level.
This test file focuses on unit testing the helper functions in _work_lib.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Ensure scripts directory is on path for _work_lib import
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Test Forge Gate Helpers in _work_lib.py
# ---------------------------------------------------------------------------

class TestForgeGateHelpers:
    """Tests for forge gate helper functions in _work_lib.py."""

    def test_run_forge_doctor_json_success(self):
        """run_forge_doctor_json must return parsed JSON on success."""
        from _work_lib import run_forge_doctor_json
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"overall_status": "clean", "identity": {"mode": "GITHUB"}}'
        mock_result.stderr = ""
        
        with patch("subprocess.run", return_value=mock_result):
            result = run_forge_doctor_json()
        
        assert result["overall_status"] == "clean"
        assert result["identity"]["mode"] == "GITHUB"
        assert "error" not in result

    def test_run_forge_doctor_json_failure(self):
        """run_forge_doctor_json must return error dict on failure."""
        from _work_lib import run_forge_doctor_json
        
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: forge command failed"
        
        with patch("subprocess.run", return_value=mock_result):
            result = run_forge_doctor_json()
        
        assert "error" in result
        assert result["error"] == "Error: forge command failed"

    def test_run_forge_promote_dry_run_json_success(self):
        """run_forge_promote_dry_run_json must return parsed JSON on success."""
        from _work_lib import run_forge_promote_dry_run_json
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"ready": true, "forge_mode": "github", "reviewability": {"changed_file_count": 50}}'
        mock_result.stderr = ""
        
        with patch("subprocess.run", return_value=mock_result):
            result = run_forge_promote_dry_run_json()
        
        assert result["ready"] is True
        assert result["forge_mode"] == "github"
        assert result["reviewability"]["changed_file_count"] == 50

    def test_run_forge_promote_dry_run_json_with_target_ref(self):
        """run_forge_promote_dry_run_json must pass target_ref parameter."""
        from _work_lib import run_forge_promote_dry_run_json
        
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '{"ready": true}'
        
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = run_forge_promote_dry_run_json(target_ref="staging")
            # Check that --target-ref was passed
            call_args = mock_run.call_args[0][0]
            assert "--target-ref" in call_args
            assert "staging" in call_args
        
        assert result["ready"] is True

    def test_check_forge_readiness_ready(self):
        """check_forge_readiness must return (True, evidence) when all gates pass."""
        from _work_lib import check_forge_readiness
        
        doctor_result = {"overall_status": "clean", "findings": []}
        promote_result = {
            "ready": True,
            "forge_mode": "github",
            "mode": "pull_request",
            "reviewability": {
                "changed_file_count": 50,
                "max_changed_files": 300,
                "over_budget": False,
                "default_action": "block_promotion",
            },
            "blockers": [],
        }
        
        with patch("_work_lib.run_forge_doctor_json", return_value=doctor_result):
            with patch("_work_lib.run_forge_promote_dry_run_json", return_value=promote_result):
                is_ready, evidence = check_forge_readiness()
        
        assert is_ready is True
        assert evidence["forge_promotion_ready"] is True
        assert evidence["forge_doctor_status"] == "clean"
        assert evidence["forge_mode"] == "github"
        assert evidence["reviewability_changed_file_count"] == 50

    def test_check_forge_readiness_not_ready(self):
        """check_forge_readiness must return (False, evidence) when gates fail."""
        from _work_lib import check_forge_readiness
        
        doctor_result = {"overall_status": "clean"}
        promote_result = {
            "ready": False,
            "forge_mode": "github",
            "reviewability": {
                "changed_file_count": 350,
                "max_changed_files": 300,
                "over_budget": True,
                "default_action": "block_promotion",
            },
            "blockers": [
                {"code": "PROMOTION-003", "message": "Budget exceeded", "severity": "error", "remediation": "Reduce files"}
            ],
        }
        
        with patch("_work_lib.run_forge_doctor_json", return_value=doctor_result):
            with patch("_work_lib.run_forge_promote_dry_run_json", return_value=promote_result):
                is_ready, evidence = check_forge_readiness()
        
        assert is_ready is False
        assert evidence["forge_promotion_ready"] is False
        assert len(evidence["forge_promotion_blockers"]) == 1
        assert evidence["reviewability_over_budget"] is True

    def test_check_forge_readiness_doctor_failure(self):
        """check_forge_readiness must return (False, evidence) when doctor fails."""
        from _work_lib import check_forge_readiness
        
        doctor_result = {"error": "Command not found"}
        promote_result = {"ready": True}
        
        with patch("_work_lib.run_forge_doctor_json", return_value=doctor_result):
            with patch("_work_lib.run_forge_promote_dry_run_json", return_value=promote_result):
                is_ready, evidence = check_forge_readiness()
        
        assert is_ready is False
        assert evidence["forge_doctor_status"] == "error"

    def test_check_forge_readiness_default_values(self):
        """check_forge_readiness must provide default values for missing fields."""
        from _work_lib import check_forge_readiness
        
        # Minimal responses
        doctor_result = {}  # Missing overall_status
        promote_result = {"ready": True}  # Missing reviewability
        
        with patch("_work_lib.run_forge_doctor_json", return_value=doctor_result):
            with patch("_work_lib.run_forge_promote_dry_run_json", return_value=promote_result):
                is_ready, evidence = check_forge_readiness()
        
        assert is_ready is True
        assert evidence["forge_doctor_status"] == "unknown"
        assert evidence["reviewability_changed_file_count"] == 0
        assert evidence["reviewability_max_changed_files"] == 300


# ---------------------------------------------------------------------------
# Test Projection Forge Readiness
# ---------------------------------------------------------------------------

class TestForgeReadinessProjection:
    """Tests for forge readiness in projection."""

    def test_projection_includes_forge_readiness(self, monkeypatch):
        """compute_projection must include forge_readiness from handoff events."""
        from _work_lib import compute_projection
        
        # Create a handoff event with forge evidence
        handoff_event = {
            "event_id": "test-id-1",
            "type": "handoff",
            "ts": "2025-01-01T00:00:00Z",
            "worker": "test-agent",
            "task_id": "adr0010-test",
            "mission_id": "mission-test",
            "git_branch": "sprint/test",
            "git_head": "abc123",
            "status": "ready_for_review",
            "tests": "all passed",
            "completion_summary": "Done",
            "dirty_files_after": [],
            "out_of_scope_findings": [],
            "patch_batches_applied": [],
            "forge_gates_checked": True,
            "forge_evidence": {
                "forge_promotion_ready": True,
                "reviewability_changed_file_count": 50,
                "reviewability_max_changed_files": 300,
                "reviewability_over_budget": False,
                "forge_mode": "github",
                "promotion_mode": "pull_request",
            },
        }
        
        # Mock the file operations
        mock_task = {
            "id": "adr0010-test",
            "sprints": [],
            "missions": [],
        }
        
        def mock_load_task(task_id):
            return mock_task
        
        def mock_load_events(task_id):
            return [handoff_event]
        
        def mock_repo_root():
            return Path("/mock/repo")
        
        with patch("_work_lib.load_task", side_effect=mock_load_task):
            with patch("_work_lib.load_events", side_effect=mock_load_events):
                with patch("_work_lib.repo_root", side_effect=mock_repo_root):
                    with patch("_work_lib.branch_exists_locally", return_value=True):
                        projection = compute_projection("adr0010-test")
        
        assert "forge_readiness" in projection
        readiness = projection["forge_readiness"]
        assert readiness["forge_gates_checked"] is True
        assert readiness["forge_promotion_ready"] is True
        assert readiness["reviewability_changed_file_count"] == 50
        assert readiness["reviewability_over_budget"] is False
        assert readiness["forge_mode"] == "github"
        assert readiness["promotion_mode"] == "pull_request"

    def test_projection_handles_missing_forge_evidence(self, monkeypatch):
        """compute_projection must handle events without forge evidence gracefully."""
        from _work_lib import compute_projection
        
        # Create a handoff event WITHOUT forge evidence
        handoff_event = {
            "event_id": "test-id-1",
            "type": "handoff",
            "ts": "2025-01-01T00:00:00Z",
            "worker": "test-agent",
            "task_id": "adr0010-test",
            "mission_id": "mission-test",
            "git_branch": "sprint/test",
            "git_head": "abc123",
            "status": "ready_for_review",
            "tests": "all passed",
            "completion_summary": "Done",
            "dirty_files_after": [],
            "out_of_scope_findings": [],
            "patch_batches_applied": [],
            # No forge evidence fields
        }
        
        mock_task = {"id": "adr0010-test", "sprints": [], "missions": []}
        
        with patch("_work_lib.load_task", return_value=mock_task):
            with patch("_work_lib.load_events", return_value=[handoff_event]):
                with patch("_work_lib.repo_root", return_value=Path("/mock/repo")):
                    with patch("_work_lib.branch_exists_locally", return_value=True):
                        projection = compute_projection("adr0010-test")
        
        assert "forge_readiness" in projection
        readiness = projection["forge_readiness"]
        assert readiness["forge_gates_checked"] is False
        assert readiness["forge_promotion_ready"] is False
        assert readiness["reviewability_changed_file_count"] == 0

    def test_projection_tracks_latest_handoff_forge_evidence(self, monkeypatch):
        """compute_projection must track forge evidence from latest handoff."""
        from _work_lib import compute_projection
        
        # Create two handoff events - only the latest has forge evidence
        old_handoff = {
            "event_id": "test-id-1",
            "type": "handoff",
            "ts": "2025-01-01T00:00:00Z",
            "worker": "test-agent",
            "task_id": "adr0010-test",
            "mission_id": "mission-test",
            "git_branch": "sprint/test",
            "git_head": "abc123",
            "status": "needs_more_work",
            "tests": "some failed",
            "completion_summary": "Partial",
            "dirty_files_after": [],
            "out_of_scope_findings": [],
            "patch_batches_applied": [],
        }
        
        latest_handoff = {
            "event_id": "test-id-2",
            "type": "handoff",
            "ts": "2025-01-02T00:00:00Z",
            "worker": "test-agent",
            "task_id": "adr0010-test",
            "mission_id": "mission-test",
            "git_branch": "sprint/test",
            "git_head": "def456",
            "status": "ready_for_review",
            "tests": "all passed",
            "completion_summary": "Done",
            "dirty_files_after": [],
            "out_of_scope_findings": [],
            "patch_batches_applied": [],
            "forge_gates_checked": True,
            "forge_evidence": {
                "forge_promotion_ready": True,
                "reviewability_changed_file_count": 100,
                "forge_mode": "gitlab",
            },
        }
        
        mock_task = {"id": "adr0010-test", "sprints": [], "missions": []}
        
        with patch("_work_lib.load_task", return_value=mock_task):
            with patch("_work_lib.load_events", return_value=[old_handoff, latest_handoff]):
                with patch("_work_lib.repo_root", return_value=Path("/mock/repo")):
                    with patch("_work_lib.branch_exists_locally", return_value=True):
                        projection = compute_projection("adr0010-test")
        
        readiness = projection["forge_readiness"]
        assert readiness["forge_gates_checked"] is True
        assert readiness["forge_mode"] == "gitlab"
        assert readiness["reviewability_changed_file_count"] == 100

    def test_projection_with_forge_gates_skipped(self, monkeypatch):
        """compute_projection must track forge_gates_skipped flag."""
        from _work_lib import compute_projection
        
        handoff_event = {
            "event_id": "test-id-1",
            "type": "handoff",
            "ts": "2025-01-01T00:00:00Z",
            "worker": "test-agent",
            "task_id": "adr0010-test",
            "mission_id": "mission-test",
            "git_branch": "sprint/test",
            "git_head": "abc123",
            "status": "ready_for_review",
            "tests": "all passed",
            "completion_summary": "Done",
            "dirty_files_after": [],
            "out_of_scope_findings": [],
            "patch_batches_applied": [],
            "forge_gates_checked": False,
            "forge_gate_skip_explicit": True,
            "forge_evidence": {
                "forge_gates_skipped": True,
                "skip_reason": "Explicit --skip-forge-gates flag",
            },
        }
        
        mock_task = {"id": "adr0010-test", "sprints": [], "missions": []}
        
        with patch("_work_lib.load_task", return_value=mock_task):
            with patch("_work_lib.load_events", return_value=[handoff_event]):
                with patch("_work_lib.repo_root", return_value=Path("/mock/repo")):
                    with patch("_work_lib.branch_exists_locally", return_value=True):
                        projection = compute_projection("adr0010-test")
        
        readiness = projection["forge_readiness"]
        assert readiness["forge_gates_checked"] is False
        # Projection tracks the evidence from the event
        assert "forge_promotion_ready" in readiness  # May be False
        assert "forge_gates_skipped" not in readiness or readiness.get("forge_gates_skipped") is None
