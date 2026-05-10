"""Tests for Runtime Process Supervision Substrate.

Phase 2: Runtime & Agent Execution Plane - Process Supervision Tests.

Core doctrine validated:
- Runtime output is advisory evidence only
- Only receipts/proposals become authoritative evidence
- UI streams projections, NOT raw subprocesses
- All runtime execution remains advisory-only
- NO autonomous apply, direct workspace mutation, hidden execution, background daemons,
  cloud orchestration, production networking, real API keys, or destructive Git commands

Tests cover:
- RuntimeProcessHandle
- RuntimeSupervisorDecision
- RuntimeSupervisorReceipt
- RuntimeSupervisor
- Forbidden command detection
- Process lifecycle management
- Deterministic behavior

file: tests/test_runtime_supervisor.py
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from rig.domain.runtime_supervisor import (
    # Constants
    PLACEHOLDER_PROCESS_ID,
    PLACEHOLDER_SUPERVISOR_ID,
    PLACEHOLDER_INVOKE_ID,
    PLACEHOLDER_COMMAND,
    DEFAULT_PROCESS_TIMEOUT_SECONDS,
    DEFAULT_GRACEFUL_SHUTDOWN_SECONDS,
    DEFAULT_MAX_STDOUT_BYTES,
    DEFAULT_MAX_STDERR_BYTES,
    FORBIDDEN_COMMANDS,
    FORBIDDEN_COMMAND_PREFIXES,
    # Enums
    RuntimeSupervisorDecisionCode,
    RuntimeSupervisorStatus,
    RuntimeProcessStatus,
    RuntimeSupervisionViolationKind,
    # Models
    RuntimeProcessHandle,
    RuntimeSupervisorDecision,
    RuntimeSupervisorReceipt,
    RuntimeSupervisor,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_process_handle_data() -> Dict[str, Any]:
    """Sample process handle data for testing."""
    return {
        "process_id": "proc_001",
        "command": ["python", "-c", "print('hello')"],
        "cwd": "/tmp",
        "env": {"PYTHONPATH": "/tmp"},
        "invocation_id": "invoke_001",
        "timeout_seconds": 30,
        "created_at": "2024-01-01T00:00:00+00:00",
    }


@pytest.fixture
def sample_supervisor_decision_data() -> Dict[str, Any]:
    """Sample supervisor decision data for testing."""
    return {
        "decision_id": "dec_001",
        "code": RuntimeSupervisorDecisionCode.ALLOW_STREAM,
        "process_id": "proc_001",
        "invocation_id": "invoke_001",
        "reason": "Command allowed",
        "created_at": "2024-01-01T00:00:00+00:00",
    }


# =============================================================================
# Enum Tests
# =============================================================================

class TestRuntimeSupervisorDecisionCode:
    """Tests for RuntimeSupervisorDecisionCode enum."""

    def test_allow_stream_code(self):
        assert RuntimeSupervisorDecisionCode.ALLOW_STREAM.value == "allow_stream"

    def test_block_stream_code(self):
        assert RuntimeSupervisorDecisionCode.BLOCK_STREAM.value == "block_stream"

    def test_cancel_stream_code(self):
        assert RuntimeSupervisorDecisionCode.CANCEL_STREAM.value == "cancel_stream"

    def test_timeout_stream_code(self):
        assert RuntimeSupervisorDecisionCode.TIMEOUT_STREAM.value == "timeout_stream"

    def test_reject_proposal_code(self):
        assert RuntimeSupervisorDecisionCode.REJECT_PROPOSAL.value == "reject_proposal"

    def test_accept_proposal_code(self):
        assert RuntimeSupervisorDecisionCode.ACCEPT_PROPOSAL.value == "accept_proposal"

    def test_stall_detected_code(self):
        assert RuntimeSupervisorDecisionCode.STALL_DETECTED.value == "stall_detected"

    def test_heartbeat_missed_code(self):
        assert RuntimeSupervisorDecisionCode.HEARTBEAT_MISSED.value == "heartbeat_missed"

    def test_buffer_overflow_code(self):
        assert RuntimeSupervisorDecisionCode.BUFFER_OVERFLOW.value == "buffer_overflow"


class TestRuntimeSupervisorStatus:
    """Tests for RuntimeSupervisorStatus enum."""

    def test_idle_status(self):
        assert RuntimeSupervisorStatus.IDLE.value == "idle"

    def test_supervising_status(self):
        assert RuntimeSupervisorStatus.SUPERVISING.value == "supervising"

    def test_error_status(self):
        assert RuntimeSupervisorStatus.ERROR.value == "error"

    def test_stopping_status(self):
        assert RuntimeSupervisorStatus.STOPPING.value == "stopping"

    def test_stopped_status(self):
        assert RuntimeSupervisorStatus.STOPPED.value == "stopped"


class TestRuntimeProcessStatus:
    """Tests for RuntimeProcessStatus enum."""

    def test_pending_status(self):
        assert RuntimeProcessStatus.PENDING.value == "pending"

    def test_running_status(self):
        assert RuntimeProcessStatus.RUNNING.value == "running"

    def test_completed_status(self):
        assert RuntimeProcessStatus.COMPLETED.value == "completed"

    def test_failed_status(self):
        assert RuntimeProcessStatus.FAILED.value == "failed"

    def test_timed_out_status(self):
        assert RuntimeProcessStatus.TIMED_OUT.value == "timed_out"

    def test_killed_status(self):
        assert RuntimeProcessStatus.KILLED.value == "killed"

    def test_cancelled_status(self):
        assert RuntimeProcessStatus.CANCELLED.value == "cancelled"


class TestRuntimeSupervisionViolationKind:
    """Tests for RuntimeSupervisionViolationKind enum."""

    def test_forbidden_command_kind(self):
        assert RuntimeSupervisionViolationKind.FORBIDDEN_COMMAND.value == "forbidden_command"

    def test_process_timeout_kind(self):
        assert RuntimeSupervisionViolationKind.TIMEOUT_VIOLATION.value == "timeout_violation"

    def test_unauthorized_mutation_kind(self):
        assert RuntimeSupervisionViolationKind.UNAUTHORIZED_MUTATION.value == "unauthorized_mutation"

    def test_memory_limit_exceeded_kind(self):
        assert RuntimeSupervisionViolationKind.MEMORY_VIOLATION.value == "memory_violation"

    def test_capability_violation_kind(self):
        assert RuntimeSupervisionViolationKind.CAPABILITY_VIOLATION.value == "capability_violation"

    def test_network_access_violation_kind(self):
        assert RuntimeSupervisionViolationKind.NETWORK_VIOLATION.value == "network_violation"


# =============================================================================
# Constants Tests
# =============================================================================

class TestPlaceholderConstants:
    """Tests for placeholder constants."""

    def test_placeholder_process_id(self):
        assert PLACEHOLDER_PROCESS_ID == "no_process"

    def test_placeholder_supervisor_id(self):
        assert PLACEHOLDER_SUPERVISOR_ID == "no_supervisor"

    def test_placeholder_invoke_id(self):
        assert PLACEHOLDER_INVOKE_ID == "INVOKE_ID_PLACEHOLDER"

    def test_placeholder_command(self):
        assert PLACEHOLDER_COMMAND == "no_command"


class TestDefaultConstants:
    """Tests for default configuration constants."""

    def test_default_process_timeout_seconds(self):
        assert DEFAULT_PROCESS_TIMEOUT_SECONDS == 300

    def test_default_graceful_shutdown_seconds(self):
        assert DEFAULT_GRACEFUL_SHUTDOWN_SECONDS == 5

    def test_default_max_stdout_bytes(self):
        assert DEFAULT_MAX_STDOUT_BYTES == 10 * 1024 * 1024  # 10MB

    def test_default_max_stderr_bytes(self):
        assert DEFAULT_MAX_STDERR_BYTES == 10 * 1024 * 1024  # 10MB


class TestForbiddenCommands:
    """Tests for forbidden commands configuration."""

    def test_forbidden_commands_list(self):
        assert "git clean" in FORBIDDEN_COMMANDS
        assert "rm -rf" in FORBIDDEN_COMMANDS
        assert "dd" in FORBIDDEN_COMMANDS
        assert ":() { :; } ;" in FORBIDDEN_COMMANDS

    def test_forbidden_prefixes_list(self):
        assert "dd " in FORBIDDEN_COMMAND_PREFIXES
        assert "git reset" in FORBIDDEN_COMMAND_PREFIXES
        assert "rm -" in FORBIDDEN_COMMAND_PREFIXES


# =============================================================================
# RuntimeProcessHandle Tests
# =============================================================================

class TestRuntimeProcessHandle:
    """Tests for RuntimeProcessHandle model."""

    def test_default_values(self):
        handle = RuntimeProcessHandle(process_id=PLACEHOLDER_PROCESS_ID)
        assert handle.process_id == PLACEHOLDER_PROCESS_ID
        assert handle.command == ""
        assert handle.status == RuntimeProcessStatus.PENDING
        assert handle.invocation_id == PLACEHOLDER_INVOKE_ID
        assert handle.timeout_seconds == DEFAULT_PROCESS_TIMEOUT_SECONDS
        assert handle.advisory_only is True

    def test_create_from_dict(self, sample_process_handle_data):
        handle = RuntimeProcessHandle.from_dict(sample_process_handle_data)
        assert handle.process_id == "proc_001"
        assert handle.command == ["python", "-c", "print('hello')"]
        assert handle.advisory_only is True

    def test_to_dict(self, sample_process_handle_data):
        handle = RuntimeProcessHandle.from_dict(sample_process_handle_data)
        result = handle.to_dict()
        assert result["process_id"] == "proc_001"
        assert result["command"] == ["python", "-c", "print('hello')"]
        assert result["advisory_only"] is True

    def test_to_json(self, sample_process_handle_data):
        handle = RuntimeProcessHandle.from_dict(sample_process_handle_data)
        json_str = handle.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["process_id"] == "proc_001"
        assert parsed["advisory_only"] is True

    def test_frozen(self):
        handle = RuntimeProcessHandle(
            process_id="test",
            command=["echo", "test"],
        )
        with pytest.raises(AttributeError):
            handle.process_id = "changed"  # type: ignore

    def test_slots(self):
        handle = RuntimeProcessHandle(process_id="test")
        with pytest.raises(AttributeError):
            handle.nonexistent_attr  # type: ignore

    def test_deterministic_id(self):
        handle1 = RuntimeProcessHandle.create(
            supervisor_id="supervisor_001",
            invocation_id="invoke_001",
            provider_id="provider_001",
            command="echo test",
            process_id="test",
        )
        handle2 = RuntimeProcessHandle.create(
            supervisor_id="supervisor_001",
            invocation_id="invoke_001",
            provider_id="provider_001",
            command="echo test",
            process_id="test",
        )
        assert handle1.process_id == handle2.process_id


# =============================================================================
# RuntimeSupervisorDecision Tests
# =============================================================================

class TestRuntimeSupervisorDecision:
    """Tests for RuntimeSupervisorDecision model."""

    def test_default_values(self):
        decision = RuntimeSupervisorDecision(decision_id=PLACEHOLDER_PROCESS_ID)
        assert decision.decision_id == PLACEHOLDER_PROCESS_ID
        assert decision.decision_code == RuntimeSupervisorDecisionCode.ALLOW_STREAM
        assert decision.process_id is None
        assert decision.invocation_id is None
        assert decision.advisory_only is True

    def test_create_from_dict(self, sample_supervisor_decision_data):
        decision = RuntimeSupervisorDecision.from_dict(sample_supervisor_decision_data)
        assert decision.decision_id == "dec_001"
        assert decision.decision_code == RuntimeSupervisorDecisionCode.ALLOW_STREAM
        assert decision.process_id == "proc_001"
        assert decision.advisory_only is True

    def test_to_dict(self, sample_supervisor_decision_data):
        decision = RuntimeSupervisorDecision.from_dict(sample_supervisor_decision_data)
        result = decision.to_dict()
        assert result["decision_id"] == "dec_001"
        assert result["decision_code"] == "allow_stream"
        assert result["advisory_only"] is True

    def test_block_decision(self):
        decision = RuntimeSupervisorDecision.block(
            supervisor_id="supervisor_001",
            decision_code=RuntimeSupervisorDecisionCode.BLOCK_STREAM,
            process_id="proc_001",
            invocation_id="invoke_001",
            reason="Forbidden command",
        )
        assert decision.decision_code == RuntimeSupervisorDecisionCode.BLOCK_STREAM
        assert decision.reason == "Forbidden command"

    def test_deterministic_id(self):
        decision1 = RuntimeSupervisorDecision.allow(
            supervisor_id="supervisor_001",
            decision_code=RuntimeSupervisorDecisionCode.ALLOW_STREAM,
            process_id="proc_001",
            invocation_id="invoke_001",
        )
        decision2 = RuntimeSupervisorDecision.allow(
            supervisor_id="supervisor_001",
            decision_code=RuntimeSupervisorDecisionCode.ALLOW_STREAM,
            process_id="proc_001",
            invocation_id="invoke_001",
        )
        assert decision1.decision_id == decision2.decision_id


# =============================================================================
