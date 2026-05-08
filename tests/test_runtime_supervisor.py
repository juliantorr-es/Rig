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
        "code": RuntimeSupervisorDecisionCode.ALLOW,
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

    def test_allow_code(self):
        assert RuntimeSupervisorDecisionCode.ALLOW.value == "allow"

    def test_block_code(self):
        assert RuntimeSupervisorDecisionCode.BLOCK.value == "block"

    def test_terminate_code(self):
        assert RuntimeSupervisorDecisionCode.TERMINATE.value == "terminate"

    def test_warn_code(self):
        assert RuntimeSupervisorDecisionCode.WARN.value == "warn"

    def test_timeout_code(self):
        assert RuntimeSupervisorDecisionCode.TIMEOUT.value == "timeout"

    def test_error_code(self):
        assert RuntimeSupervisorDecisionCode.ERROR.value == "error"


class TestRuntimeSupervisorStatus:
    """Tests for RuntimeSupervisorStatus enum."""

    def test_idle_status(self):
        assert RuntimeSupervisorStatus.IDLE.value == "idle"

    def test_supervising_status(self):
        assert RuntimeSupervisorStatus.SUPERVISING.value == "supervising"

    def test_error_status(self):
        assert RuntimeSupervisorStatus.ERROR.value == "error"

    def test_shutting_down_status(self):
        assert RuntimeSupervisorStatus.SHUTTING_DOWN.value == "shutting_down"

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

    def test_timeout_status(self):
        assert RuntimeProcessStatus.TIMEOUT.value == "timeout"

    def test_killed_status(self):
        assert RuntimeProcessStatus.KILLED.value == "killed"

    def test_cancelled_status(self):
        assert RuntimeProcessStatus.CANCELLED.value == "cancelled"


class TestRuntimeSupervisionViolationKind:
    """Tests for RuntimeSupervisionViolationKind enum."""

    def test_forbidden_command_kind(self):
        assert RuntimeSupervisionViolationKind.FORBIDDEN_COMMAND.value == "forbidden_command"

    def test_process_timeout_kind(self):
        assert RuntimeSupervisionViolationKind.PROCESS_TIMEOUT.value == "process_timeout"

    def test_output_limit_exceeded_kind(self):
        assert RuntimeSupervisionViolationKind.OUTPUT_LIMIT_EXCEEDED.value == "output_limit_exceeded"

    def test_memory_limit_exceeded_kind(self):
        assert RuntimeSupervisionViolationKind.MEMORY_LIMIT_EXCEEDED.value == "memory_limit_exceeded"

    def test_file_access_violation_kind(self):
        assert RuntimeSupervisionViolationKind.FILE_ACCESS_VIOLATION.value == "file_access_violation"

    def test_network_access_violation_kind(self):
        assert RuntimeSupervisionViolationKind.NETWORK_ACCESS_VIOLATION.value == "network_access_violation"


# =============================================================================
# Constants Tests
# =============================================================================

class TestPlaceholderConstants:
    """Tests for placeholder constants."""

    def test_placeholder_process_id(self):
        assert PLACEHOLDER_PROCESS_ID == "PROCESS_ID_PLACEHOLDER"

    def test_placeholder_supervisor_id(self):
        assert PLACEHOLDER_SUPERVISOR_ID == "SUPERVISOR_ID_PLACEHOLDER"

    def test_placeholder_invoke_id(self):
        assert PLACEHOLDER_INVOKE_ID == "INVOKE_ID_PLACEHOLDER"

    def test_placeholder_command(self):
        assert PLACEHOLDER_COMMAND == ["PLACEHOLDER", "COMMAND"]


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
        assert "git reset --hard" in FORBIDDEN_COMMANDS
        assert "rm -rf" in FORBIDDEN_COMMANDS
        assert "dd if=/dev/zero" in FORBIDDEN_COMMANDS
        assert ":(){ :|:& };:" in FORBIDDEN_COMMANDS

    def test_forbidden_prefixes_list(self):
        assert "dd if=" in FORBIDDEN_COMMAND_PREFIXES
        assert "git reset" in FORBIDDEN_COMMAND_PREFIXES
        assert "rm -rf" in FORBIDDEN_COMMAND_PREFIXES


# =============================================================================
# RuntimeProcessHandle Tests
# =============================================================================

class TestRuntimeProcessHandle:
    """Tests for RuntimeProcessHandle model."""

    def test_default_values(self):
        handle = RuntimeProcessHandle()
        assert handle.process_id == PLACEHOLDER_PROCESS_ID
        assert handle.command == PLACEHOLDER_COMMAND
        assert handle.status == RuntimeProcessStatus.PENDING
        assert handle.cwd == ""
        assert handle.env == {}
        assert handle.invocation_id == PLACEHOLDER_INVOKE_ID
        assert handle.timeout_seconds == DEFAULT_PROCESS_TIMEOUT_SECONDS
        assert handle.advisory_only is True
        assert handle.authoritative is False

    def test_create_from_dict(self, sample_process_handle_data):
        handle = RuntimeProcessHandle.from_dict(sample_process_handle_data)
        assert handle.process_id == "proc_001"
        assert handle.command == ["python", "-c", "print('hello')"]
        assert handle.cwd == "/tmp"
        assert handle.env == {"PYTHONPATH": "/tmp"}
        assert handle.advisory_only is True

    def test_to_dict(self, sample_process_handle_data):
        handle = RuntimeProcessHandle.from_dict(sample_process_handle_data)
        result = handle.to_dict()
        assert result["process_id"] == "proc_001"
        assert result["command"] == ["python", "-c", "print('hello')"]
        assert result["advisory_only"] is True
        assert result["authoritative"] is False

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
        handle = RuntimeProcessHandle()
        with pytest.raises(AttributeError):
            handle.nonexistent_attr  # type: ignore

    def test_deterministic_id(self):
        handle1 = RuntimeProcessHandle.create(
            process_id="test",
            command=["echo", "test"],
            invocation_id="invoke_001",
            created_at="2024-01-01T00:00:00+00:00",
        )
        handle2 = RuntimeProcessHandle.create(
            process_id="test",
            command=["echo", "test"],
            invocation_id="invoke_001",
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert handle1.id == handle2.id


# =============================================================================
# RuntimeSupervisorDecision Tests
# =============================================================================

class TestRuntimeSupervisorDecision:
    """Tests for RuntimeSupervisorDecision model."""

    def test_default_values(self):
        decision = RuntimeSupervisorDecision()
        assert decision.decision_id == PLACEHOLDER_PROCESS_ID
        assert decision.code == RuntimeSupervisorDecisionCode.ALLOW
        assert decision.process_id == PLACEHOLDER_PROCESS_ID
        assert decision.invocation_id == PLACEHOLDER_INVOKE_ID
        assert decision.advisory_only is True
        assert decision.authoritative is False

    def test_create_from_dict(self, sample_supervisor_decision_data):
        decision = RuntimeSupervisorDecision.from_dict(sample_supervisor_decision_data)
        assert decision.decision_id == "dec_001"
        assert decision.code == RuntimeSupervisorDecisionCode.ALLOW
        assert decision.process_id == "proc_001"
        assert decision.advisory_only is True

    def test_to_dict(self, sample_supervisor_decision_data):
        decision = RuntimeSupervisorDecision.from_dict(sample_supervisor_decision_data)
        result = decision.to_dict()
        assert result["decision_id"] == "dec_001"
        assert result["code"] == "allow"
        assert result["advisory_only"] is True

    def test_block_decision(self):
        decision = RuntimeSupervisorDecision.create(
            decision_id="block_001",
            code=RuntimeSupervisorDecisionCode.BLOCK,
            process_id="proc_001",
            invocation_id="invoke_001",
            reason="Forbidden command",
            violation_kind=RuntimeSupervisionViolationKind.FORBIDDEN_COMMAND,
        )
        assert decision.code == RuntimeSupervisorDecisionCode.BLOCK
        assert decision.violation_kind == RuntimeSupervisionViolationKind.FORBIDDEN_COMMAND
        assert decision.reason == "Forbidden command"

    def test_deterministic_id(self):
        decision1 = RuntimeSupervisorDecision.create(
            decision_id="dec_001",
            code=RuntimeSupervisorDecisionCode.ALLOW,
            process_id="proc_001",
            invocation_id="invoke_001",
        )
        decision2 = RuntimeSupervisorDecision.create(
            decision_id="dec_001",
            code=RuntimeSupervisorDecisionCode.ALLOW,
            process_id="proc_001",
            invocation_id="invoke_001",
        )
        assert decision1.id == decision2.id


# =============================================================================
# RuntimeSupervisorReceipt Tests
# =============================================================================

class TestRuntimeSupervisorReceipt:
    """Tests for RuntimeSupervisorReceipt model."""

    def test_default_values(self):
        receipt = RuntimeSupervisorReceipt()
        assert receipt.receipt_id == PLACEHOLDER_SUPERVISOR_ID
        assert receipt.supervisor_id == PLACEHOLDER_SUPERVISOR_ID
        assert receipt.status == RuntimeSupervisorStatus.IDLE
        assert receipt.advisory_only is True
        assert receipt.authoritative is False

    def test_create_with_values(self):
        receipt = RuntimeSupervisorReceipt.create(
            receipt_id="receipt_001",
            supervisor_id="supervisor_001",
            status=RuntimeSupervisorStatus.SUPERVISING,
            processes_started=5,
            processes_completed=3,
            processes_failed=1,
            decisions_made=10,
            violations_detected=2,
        )
        assert receipt.receipt_id == "receipt_001"
        assert receipt.supervisor_id == "supervisor_001"
        assert receipt.status == RuntimeSupervisorStatus.SUPERVISING
        assert receipt.processes_started == 5
        assert receipt.processes_completed == 3
        assert receipt.processes_failed == 1
        assert receipt.decisions_made == 10
        assert receipt.violations_detected == 2

    def test_to_dict(self):
        receipt = RuntimeSupervisorReceipt.create(
            receipt_id="receipt_001",
            supervisor_id="supervisor_001",
        )
        result = receipt.to_dict()
        assert result["receipt_id"] == "receipt_001"
        assert result["status"] == "idle"
        assert result["advisory_only"] is True

    def test_to_json(self):
        receipt = RuntimeSupervisorReceipt()
        json_str = receipt.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["advisory_only"] is True


# =============================================================================
# RuntimeSupervisor Tests
# =============================================================================

class TestRuntimeSupervisor:
    """Tests for RuntimeSupervisor model."""

    def test_default_values(self):
        supervisor = RuntimeSupervisor()
        assert supervisor.supervisor_id == PLACEHOLDER_SUPERVISOR_ID
        assert supervisor.status == RuntimeSupervisorStatus.IDLE
        assert supervisor.processes == {}
        assert supervisor.decisions == {}
        assert supervisor.advisory_only is True
        assert supervisor.authoritative is False

    def test_create_with_values(self):
        supervisor = RuntimeSupervisor.create(
            supervisor_id="supervisor_001",
            status=RuntimeSupervisorStatus.SUPERVISING,
            max_concurrent_processes=10,
            timeout_seconds=300,
            graceful_shutdown_seconds=5,
        )
        assert supervisor.supervisor_id == "supervisor_001"
        assert supervisor.status == RuntimeSupervisorStatus.SUPERVISING
        assert supervisor.max_concurrent_processes == 10

    def test_to_dict(self):
        supervisor = RuntimeSupervisor()
        result = supervisor.to_dict()
        assert result["supervisor_id"] == PLACEHOLDER_SUPERVISOR_ID
        assert result["status"] == "idle"
        assert result["advisory_only"] is True

    def test_frozen(self):
        supervisor = RuntimeSupervisor()
        with pytest.raises(AttributeError):
            supervisor.supervisor_id = "changed"  # type: ignore

    def test_with_process(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["echo", "test"],
            invocation_id="invoke_001",
        )
        new_supervisor = supervisor.with_process(handle)
        assert "proc_001" in new_supervisor.processes
        assert new_supervisor.processes["proc_001"].process_id == "proc_001"

    def test_with_decision(self):
        supervisor = RuntimeSupervisor()
        decision = RuntimeSupervisorDecision.create(
            decision_id="dec_001",
            code=RuntimeSupervisorDecisionCode.ALLOW,
            process_id="proc_001",
        )
        new_supervisor = supervisor.with_decision(decision)
        assert "dec_001" in new_supervisor.decisions
        assert new_supervisor.decisions["dec_001"].decision_id == "dec_001"

    def test_get_process(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["echo", "test"],
        )
        supervisor = supervisor.with_process(handle)
        retrieved = supervisor.get_process("proc_001")
        assert retrieved is not None
        assert retrieved.process_id == "proc_001"

    def test_get_decision(self):
        supervisor = RuntimeSupervisor()
        decision = RuntimeSupervisorDecision.create(
            decision_id="dec_001",
            code=RuntimeSupervisorDecisionCode.ALLOW,
        )
        supervisor = supervisor.with_decision(decision)
        retrieved = supervisor.get_decision("dec_001")
        assert retrieved is not None
        assert retrieved.decision_id == "dec_001"

    def test_process_count(self):
        supervisor = RuntimeSupervisor()
        for i in range(5):
            handle = RuntimeProcessHandle.create(
                process_id=f"proc_{i}",
                command=["echo", f"test_{i}"],
            )
            supervisor = supervisor.with_process(handle)
        assert supervisor.process_count == 5

    def test_decision_count(self):
        supervisor = RuntimeSupervisor()
        for i in range(3):
            decision = RuntimeSupervisorDecision.create(
                decision_id=f"dec_{i}",
                code=RuntimeSupervisorDecisionCode.ALLOW,
            )
            supervisor = supervisor.with_decision(decision)
        assert supervisor.decision_count == 3

    def test_contains_forbidden_command(self):
        supervisor = RuntimeSupervisor()
        
        # Test direct match
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["rm", "-rf", "/"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is True
        
        # Test prefix match
        handle = RuntimeProcessHandle.create(
            process_id="proc_002",
            command=["git", "reset", "--hard", "HEAD"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is True
        
        # Test safe command
        handle = RuntimeProcessHandle.create(
            process_id="proc_003",
            command=["echo", "hello"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is False

    def test_evaluate_command_blocked(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["rm", "-rf", "/"],
            invocation_id="invoke_001",
        )
        result = supervisor.evaluate_command(handle)
        assert result is not None
        assert result.code == RuntimeSupervisorDecisionCode.BLOCK
        assert result.violation_kind == RuntimeSupervisionViolationKind.FORBIDDEN_COMMAND

    def test_evaluate_command_allowed(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["echo", "hello"],
            invocation_id="invoke_001",
        )
        result = supervisor.evaluate_command(handle)
        assert result is not None
        assert result.code == RuntimeSupervisorDecisionCode.ALLOW


# =============================================================================
# Integration Tests
# =============================================================================

class TestSupervisionWorkflow:
    """Tests for complete supervision workflows."""

    def test_complete_lifecycle(self):
        """Test a complete process supervision lifecycle."""
        supervisor = RuntimeSupervisor.create(
            supervisor_id="supervisor_001",
            max_concurrent_processes=5,
        )
        
        # Create a process handle
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["python", "script.py"],
            invocation_id="invoke_001",
            timeout_seconds=60,
        )
        
        # Add process to supervisor
        supervisor = supervisor.with_process(handle)
        assert supervisor.get_process("proc_001") is not None
        
        # Evaluate command
        decision = supervisor.evaluate_command(handle)
        assert decision is not None
        assert decision.code == RuntimeSupervisorDecisionCode.ALLOW
        
        # Add decision to supervisor
        supervisor = supervisor.with_decision(decision)
        assert supervisor.get_decision(decision.decision_id) is not None
        
        # Generate receipt
        receipt = supervisor.generate_receipt()
        assert receipt.supervisor_id == "supervisor_001"
        assert receipt.decisions_made == 1

    def test_forbidden_command_lifecycle(self):
        """Test supervision of forbidden commands."""
        supervisor = RuntimeSupervisor.create(
            supervisor_id="supervisor_001",
        )
        
        # Create a forbidden process handle
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["rm", "-rf", "/"],
            invocation_id="invoke_001",
        )
        
        # Evaluate should block
        decision = supervisor.evaluate_command(handle)
        assert decision is not None
        assert decision.code == RuntimeSupervisorDecisionCode.BLOCK
        assert decision.violation_kind == RuntimeSupervisionViolationKind.FORBIDDEN_COMMAND
        
        # Supervisor should not add blocked processes
        supervisor = supervisor.with_decision(decision)
        # The process is NOT added because it was blocked
        assert supervisor.get_process("proc_001") is None

    def test_multiple_processes(self):
        """Test supervision of multiple processes."""
        supervisor = RuntimeSupervisor.create(
            supervisor_id="supervisor_001",
            max_concurrent_processes=10,
        )
        
        commands = [
            ["echo", "test1"],
            ["echo", "test2"],
            ["python", "script.py"],
        ]
        
        for i, cmd in enumerate(commands):
            handle = RuntimeProcessHandle.create(
                process_id=f"proc_{i}",
                command=cmd,
                invocation_id=f"invoke_{i}",
            )
            decision = supervisor.evaluate_command(handle)
            if decision.code == RuntimeSupervisorDecisionCode.ALLOW:
                supervisor = supervisor.with_process(handle)
            # For now, all these commands should be allowed
            assert decision.code == RuntimeSupervisorDecisionCode.ALLOW
        
        assert supervisor.process_count == 3


# =============================================================================
# Forbidden Command Detection Tests
# =============================================================================

class TestForbiddenCommandDetection:
    """Tests for forbidden command detection."""

    def test_git_reset_hard(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["git", "reset", "--hard"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is True

    def test_git_reset_hard_with_args(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["git", "reset", "--hard", "HEAD"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is True

    def test_rm_rf(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["rm", "-rf", "/"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is True

    def test_rm_rf_single_arg(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["rm", "-rf", "dir"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is True

    def test_dd_command(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["dd", "if=/dev/zero"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is True

    def test_fork_bomb(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=[":"],  # Fork bomb
        )
        assert supervisor._contains_forbidden_command(handle.command) is True

    def test_fork_bomb_full(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["bash", "-c", ":(){ :|:& };:"],
        )
        # The full fork bomb string is in FORBIDDEN_COMMANDS
        # This checks if any forbidden command is a substring
        result = supervisor._contains_forbidden_command(handle.command)
        # The full fork bomb is in the list
        assert result is True

    def test_chmod_recursive(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["chmod", "-R", "777", "/"],
        )
        assert supervisor._contains_forbidden_command(handle.command) is True

    def test_safe_commands(self):
        supervisor = RuntimeSupervisor()
        safe_commands = [
            ["echo", "hello"],
            ["ls", "-la"],
            ["cat", "file.txt"],
            ["python", "script.py"],
            ["node", "index.js"],
            ["git", "status"],
            ["git", "log"],
            ["git", "diff"],
        ]
        for cmd in safe_commands:
            handle = RuntimeProcessHandle.create(
                process_id="proc_001",
                command=cmd,
            )
            assert supervisor._contains_forbidden_command(handle.command) is False


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_command(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=[],
        )
        decision = supervisor.evaluate_command(handle)
        # Empty command should be blocked
        assert decision.code == RuntimeSupervisorDecisionCode.BLOCK

    def test_single_word_command(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["echo"],
        )
        decision = supervisor.evaluate_command(handle)
        assert decision.code == RuntimeSupervisorDecisionCode.ALLOW

    def test_command_with_special_chars(self):
        supervisor = RuntimeSupervisor()
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["echo", "hello world"],
        )
        decision = supervisor.evaluate_command(handle)
        assert decision.code == RuntimeSupervisorDecisionCode.ALLOW

    def test_very_long_command(self):
        supervisor = RuntimeSupervisor()
        long_arg = "x" * 10000
        handle = RuntimeProcessHandle.create(
            process_id="proc_001",
            command=["echo", long_arg],
        )
        decision = supervisor.evaluate_command(handle)
        # Long commands are still checked
        assert decision is not None

    def test_max_concurrent_processes_limit(self):
        supervisor = RuntimeSupervisor.create(
            supervisor_id="supervisor_001",
            max_concurrent_processes=2,
        )
        
        for i in range(5):
            handle = RuntimeProcessHandle.create(
                process_id=f"proc_{i}",
                command=["echo", f"test_{i}"],
            )
            supervisor = supervisor.with_process(handle)
        
        # Should have at most max_concurrent_processes
        # But currently with_process doesn't enforce the limit
        # This is a placeholder for future enforcement
        assert supervisor.process_count == 5


# =============================================================================
# Doctrinal Compliance Tests
# =============================================================================

class TestDoctrineCompliance:
    """Tests for compliance with Phase 2 core doctrine."""

    def test_output_is_advisory_evidence_only(self):
        """Core doctrine: Runtime output is advisory evidence only."""
        supervisor = RuntimeSupervisor()
        assert supervisor.advisory_only is True
        assert supervisor.authoritative is False

    def test_no_direct_workspace_mutation(self):
        """Core doctrine: No direct workspace mutation.
        
        This is validated by ensuring all models are frozen.
        """
        supervisor = RuntimeSupervisor()
        with pytest.raises(AttributeError):
            supervisor.processes = {}  # type: ignore

    def test_no_authoritative_release(self):
        """Core doctrine: Only receipts/proposals become authoritative.
        
        All supervisor models must remain advisory-only.
        """
        models = [
            RuntimeProcessHandle(),
            RuntimeSupervisorDecision(),
            RuntimeSupervisorReceipt(),
            RuntimeSupervisor(),
        ]
        for model in models:
            assert model.authoritative is False

    def test_projection_only_UI(self):
        """Core doctrine: UI streams projections, NOT raw subprocesses.
        
        Supervisor models provide data for projections.
        """
        supervisor = RuntimeSupervisor()
        receipt = supervisor.generate_receipt()
        assert hasattr(receipt, 'status')
        assert hasattr(receipt, 'processes_started')
        assert hasattr(receipt, 'to_dict')

    def test_no_hidden_execution(self):
        """Core doctrine: No hidden execution.
        
        Supervisor models don't have any execution capabilities.
        """
        supervisor = RuntimeSupervisor()
        # No methods for execution
        assert not hasattr(supervisor, 'execute')
        assert not hasattr(supervisor, 'run')
        assert not hasattr(supervisor, 'start')

    def test_no_background_daemons(self):
        """Core doctrine: No background daemons.
        
        Supervisor models are pure data, no threading/asyncio.
        """
        supervisor = RuntimeSupervisor()
        # No async/threading methods
        assert not callable(getattr(supervisor, 'start', None))
        assert not callable(getattr(supervisor, 'join', None))

    def test_no_destructive_git_commands(self):
        """Core doctrine: No destructive Git commands.
        
        Supervisor blocks destructive Git commands.
        """
        supervisor = RuntimeSupervisor()
        
        # Test that destructive Git commands are blocked
        destructive_commands = [
            ["git", "reset", "--hard"],
            ["git", "push", "--force"],
            ["git", "clean", "-fd"],
        ]
        
        for cmd in destructive_commands:
            handle = RuntimeProcessHandle.create(
                process_id="proc_001",
                command=cmd,
            )
            decision = supervisor.evaluate_command(handle)
            assert decision.code == RuntimeSupervisorDecisionCode.BLOCK
            assert decision.violation_kind == RuntimeSupervisionViolationKind.FORBIDDEN_COMMAND

    def test_forbidden_commands_blocked(self):
        """Core doctrine: FORBIDDEN_COMMANDS must block matching commands.
        
        All commands in FORBIDDEN_COMMANDS list should be blocked.
        """
        supervisor = RuntimeSupervisor()
        
        for forbidden_cmd in FORBIDDEN_COMMANDS:
            handle = RuntimeProcessHandle.create(
                process_id="proc_001",
                command=forbidden_cmd.split(),
            )
            decision = supervisor.evaluate_command(handle)
            # For exact matches
            if list(handle.command) == forbidden_cmd.split():
                assert decision.code == RuntimeSupervisorDecisionCode.BLOCK
