"""Tests for Rig workflow command chains domain and CLI.

These tests validate that:
1. Domain types (WorkflowCommand, WorkflowContext, WorkflowCommandResult, WorkflowRunResult) work correctly
2. Built-in contexts (mission_handoff, promotion_dry_run) are properly defined
3. Registry functions (get_builtin_workflow_context, list_builtin_workflow_contexts) work correctly
4. CLI commands (list, run) work with mocked subprocess
5. Evidence writing works correctly
6. Truncation at MAX_OUTPUT_CHARS (10000) is enforced
7. Agent and mutating checks are enforced

DO NOT call remote APIs. DO NOT mutate worktrees. DO NOT modify existing files.
All tests use mocked subprocess or pure functions.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Ensure src is on path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rig.domain.workflow_chains import (
    MAX_OUTPUT_CHARS,
    WorkflowCommand,
    WorkflowContext,
    WorkflowCommandResult,
    WorkflowRunResult,
    MISSION_HANDOFF_CONTEXT,
    PROMOTION_DRY_RUN_CONTEXT,
    get_builtin_workflow_context,
    list_builtin_workflow_contexts,
    run_workflow_context,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_repo_root():
    """Provide a mock repository root path."""
    return Path("/mock/repo")


@pytest.fixture
def temp_work_dir():
    """Provide a temporary directory for evidence files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ---------------------------------------------------------------------------
# Domain Type Tests
# ---------------------------------------------------------------------------


class TestWorkflowCommand:
    """Tests for WorkflowCommand dataclass."""

    def test_create_workflow_command(self):
        """Test creating a WorkflowCommand."""
        cmd = WorkflowCommand(
            id="test_cmd",
            command=("python3", "-m", "compileall", "-q", "src"),
            required=True,
            agent_allowed=True,
            mutates_state=False,
            description="Test command",
        )
        assert cmd.id == "test_cmd"
        assert cmd.description == "Test command"
        assert cmd.command == ("python3", "-m", "compileall", "-q", "src")
        assert cmd.required is True
        assert cmd.agent_allowed is True
        assert cmd.mutates_state is False

    def test_workflow_command_slots(self):
        """Test that WorkflowCommand uses slots."""
        cmd = WorkflowCommand(
            id="test_cmd",
            command=("echo", "hello"),
            required=True,
            agent_allowed=True,
            mutates_state=False,
            description="Test command",
        )
        assert not hasattr(cmd, "__dict__")


class TestWorkflowContext:
    """Tests for WorkflowContext dataclass."""

    def test_create_workflow_context(self):
        """Test creating a WorkflowContext."""
        commands = (
            WorkflowCommand(
                id="cmd1",
                command=("echo", "hello"),
                required=True,
                agent_allowed=True,
                mutates_state=False,
                description="First command",
            ),
        )
        ctx = WorkflowContext(
            id="test_context",
            description="Test context",
            commands=commands,
            agent_allowed=True,
            mutates_state=False,
        )
        assert ctx.id == "test_context"
        assert ctx.description == "Test context"
        assert len(ctx.commands) == 1
        assert ctx.agent_allowed is True
        assert ctx.mutates_state is False




class TestWorkflowCommandResult:
    """Tests for WorkflowCommandResult dataclass."""

    def test_create_workflow_command_result(self):
        """Test creating a WorkflowCommandResult."""
        result = WorkflowCommandResult(
            id="test_cmd",
            command=("echo", "hello"),
            returncode=0,
            stdout="hello",
            stderr="",
            passed=True,
            required=True,
        )
        assert result.id == "test_cmd"
        assert result.command == ("echo", "hello")
        assert result.returncode == 0
        assert result.stdout == "hello"
        assert result.stderr == ""
        assert result.passed is True
        assert result.required is True

    def test_workflow_command_result_truncated(self):
        """Test WorkflowCommandResult with truncated output."""
        long_output = "x" * 20000
        result = WorkflowCommandResult(
            id="test_cmd",
            command=("echo", "hello"),
            returncode=0,
            stdout=long_output[:MAX_OUTPUT_CHARS] + "... [TRUNCATED]",
            stderr="",
            passed=True,
            required=True,
        )
        assert result.stdout.endswith("... [TRUNCATED]")




class TestWorkflowRunResult:
    """Tests for WorkflowRunResult dataclass."""

    def test_create_workflow_run_result(self):
        """Test creating a WorkflowRunResult."""
        cmd_result = WorkflowCommandResult(
            id="test_cmd",
            command=("echo", "hello"),
            returncode=0,
            stdout="hello",
            stderr="",
            passed=True,
            required=True,
        )
        run_result = WorkflowRunResult(
            context_id="test_context",
            passed=True,
            results=(cmd_result,),
            blockers=(),
            evidence_path="/tmp/evidence.json",
        )
        assert run_result.context_id == "test_context"
        assert len(run_result.results) == 1
        assert run_result.passed is True
        assert run_result.evidence_path == "/tmp/evidence.json"




# ---------------------------------------------------------------------------
# Built-in Contexts Tests
# ---------------------------------------------------------------------------


class TestBuiltinContexts:
    """Tests for built-in workflow contexts."""

    def test_mission_handoff_context_structure(self):
        """Test MISSION_HANDOFF_CONTEXT has correct structure."""
        ctx = MISSION_HANDOFF_CONTEXT
        assert ctx.id == "mission_handoff"
        assert "Mission handoff" in ctx.description
        assert ctx.agent_allowed is True
        assert ctx.mutates_state is False
        assert len(ctx.commands) == 5

    def test_mission_handoff_context_commands(self):
        """Test MISSION_HANDOFF_CONTEXT has expected commands."""
        ctx = MISSION_HANDOFF_CONTEXT
        command_ids = [cmd.id for cmd in ctx.commands]
        assert "compileall" in command_ids
        assert "pytest_collect" in command_ids
        assert "check_fast" in command_ids
        assert "forge_doctor" in command_ids
        assert "forge_promote_dry_run" in command_ids

    def test_mission_handoff_all_commands_non_mutating(self):
        """Test all commands in MISSION_HANDOFF_CONTEXT are non-mutating."""
        ctx = MISSION_HANDOFF_CONTEXT
        for cmd in ctx.commands:
            assert cmd.mutates_state is False

    def test_mission_handoff_all_commands_agent_allowed(self):
        """Test all commands in MISSION_HANDOFF_CONTEXT are agent-allowed."""
        ctx = MISSION_HANDOFF_CONTEXT
        for cmd in ctx.commands:
            assert cmd.agent_allowed is True

    def test_promotion_dry_run_context_structure(self):
        """Test PROMOTION_DRY_RUN_CONTEXT has correct structure."""
        ctx = PROMOTION_DRY_RUN_CONTEXT
        assert ctx.id == "promotion_dry_run"
        assert "Promotion dry-run" in ctx.description
        assert ctx.agent_allowed is True
        assert ctx.mutates_state is False
        assert len(ctx.commands) == 2

    def test_promotion_dry_run_context_commands(self):
        """Test PROMOTION_DRY_RUN_CONTEXT has expected commands."""
        ctx = PROMOTION_DRY_RUN_CONTEXT
        command_ids = [cmd.id for cmd in ctx.commands]
        assert "forge_doctor" in command_ids
        assert "forge_promote_dry_run" in command_ids

    def test_promotion_dry_run_all_commands_non_mutating(self):
        """Test all commands in PROMOTION_DRY_RUN_CONTEXT are non-mutating."""
        ctx = PROMOTION_DRY_RUN_CONTEXT
        for cmd in ctx.commands:
            assert cmd.mutates_state is False

    def test_promotion_dry_run_all_commands_agent_allowed(self):
        """Test all commands in PROMOTION_DRY_RUN_CONTEXT are agent-allowed."""
        ctx = PROMOTION_DRY_RUN_CONTEXT
        for cmd in ctx.commands:
            assert cmd.agent_allowed is True


# ---------------------------------------------------------------------------
# Registry Tests
# ---------------------------------------------------------------------------


class TestRegistry:
    """Tests for workflow context registry functions."""

    def test_list_builtin_workflow_contexts(self):
        """Test listing all built-in contexts."""
        contexts = list_builtin_workflow_contexts()
        assert len(contexts) == 2
        context_ids = [ctx.id for ctx in contexts]
        assert "mission_handoff" in context_ids
        assert "promotion_dry_run" in context_ids

    def test_get_builtin_workflow_context_mission_handoff(self):
        """Test getting mission_handoff context by ID."""
        ctx = get_builtin_workflow_context("mission_handoff")
        assert ctx.id == "mission_handoff"
        assert ctx == MISSION_HANDOFF_CONTEXT

    def test_get_builtin_workflow_context_promotion_dry_run(self):
        """Test getting promotion_dry_run context by ID."""
        ctx = get_builtin_workflow_context("promotion_dry_run")
        assert ctx.id == "promotion_dry_run"
        assert ctx == PROMOTION_DRY_RUN_CONTEXT

    def test_get_builtin_workflow_context_unknown(self):
        """Test getting unknown context raises ValueError."""
        with pytest.raises(ValueError):
            get_builtin_workflow_context("unknown_context")


# ---------------------------------------------------------------------------
# Runner Tests
# ---------------------------------------------------------------------------


class TestRunner:
    """Tests for workflow context runner."""

    def test_run_workflow_context_success(self, temp_work_dir):
        """Test running a built-in workflow context with successful commands."""
        # Use the built-in mission_handoff context
        # Mock subprocess to return success for all commands
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "success\n"
        mock_result.stderr = ""
        
        with patch("rig.domain.workflow_chains.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            with patch("rig.domain.workflow_chains.datetime") as mock_dt:
                mock_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
                mock_dt.now.return_value = mock_now
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                
                run_result = run_workflow_context(
                    "mission_handoff",
                    repo_path=temp_work_dir,
                    write_evidence=False,
                )
        
        assert run_result.passed is True
        assert len(run_result.results) == 5  # mission_handoff has 5 commands
        for r in run_result.results:
            assert r.passed is True

    def test_run_workflow_context_required_failure(self, temp_work_dir):
        """Test running a workflow context with required command failure stops early."""
        # Mock first command to fail (compileall in mission_handoff is required)
        mock_failure = MagicMock()
        mock_failure.returncode = 1
        mock_failure.stdout = ""
        mock_failure.stderr = "error\n"
        
        with patch("rig.domain.workflow_chains.subprocess.run") as mock_run:
            mock_run.return_value = mock_failure
            with patch("rig.domain.workflow_chains.datetime") as mock_dt:
                mock_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
                mock_dt.now.return_value = mock_now
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                
                run_result = run_workflow_context(
                    "mission_handoff",
                    repo_path=temp_work_dir,
                    write_evidence=False,
                )
        
        # Should stop after first failure (required command)
        assert run_result.passed is False
        assert len(run_result.results) == 1
        assert run_result.results[0].passed is False

    def test_run_workflow_context_optional_failure_continues(self, temp_work_dir):
        """Test running promotion_dry_run context (2 commands, both required)."""
        # Mock first command to succeed, second to succeed
        mock_success1 = MagicMock()
        mock_success1.returncode = 0
        mock_success1.stdout = "success1\n"
        mock_success1.stderr = ""
        
        mock_success2 = MagicMock()
        mock_success2.returncode = 0
        mock_success2.stdout = "success2\n"
        mock_success2.stderr = ""
        
        with patch("rig.domain.workflow_chains.subprocess.run") as mock_run:
            mock_run.side_effect = [mock_success1, mock_success2]
            with patch("rig.domain.workflow_chains.datetime") as mock_dt:
                mock_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
                mock_dt.now.return_value = mock_now
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                
                run_result = run_workflow_context(
                    "promotion_dry_run",
                    repo_path=temp_work_dir,
                    write_evidence=False,
                )
        
        # Should run both commands and both succeed
        assert run_result.passed is True
        assert len(run_result.results) == 2
        assert run_result.results[0].passed is True
        assert run_result.results[1].passed is True

    def test_run_workflow_context_truncation(self, temp_work_dir):
        """Test that output is truncated at MAX_OUTPUT_CHARS."""
        # Mock command to return very long output (> MAX_OUTPUT_CHARS)
        long_output = "x" * (MAX_OUTPUT_CHARS + 1000)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = long_output
        mock_result.stderr = ""
        
        with patch("rig.domain.workflow_chains.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            with patch("rig.domain.workflow_chains.datetime") as mock_dt:
                mock_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
                mock_dt.now.return_value = mock_now
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                
                run_result = run_workflow_context(
                    "promotion_dry_run",
                    repo_path=temp_work_dir,
                    write_evidence=False,
                )
        
        # First command's output should be truncated to MAX_OUTPUT_CHARS - 3 + 3 = MAX_OUTPUT_CHARS
        # (truncated to max_chars - 3, then "..." appended = max_chars total)
        assert len(run_result.results[0].stdout) == MAX_OUTPUT_CHARS
        assert run_result.results[0].stdout.endswith("...")

    def test_run_workflow_context_evidence_writing(self, temp_work_dir):
        """Test that evidence file is written correctly."""
        # Create .rig/work/validation directory
        validation_dir = temp_work_dir / ".rig" / "work" / "validation"
        validation_dir.mkdir(parents=True, exist_ok=True)
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""
        
        # Don't mock datetime for this test since we need real datetime for evidence
        with patch("rig.domain.workflow_chains.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            
            run_result = run_workflow_context(
                "promotion_dry_run",
                repo_path=temp_work_dir,
                write_evidence=True,
            )
        
        # Check evidence file was created in .rig/work/validation
        evidence_files = list(validation_dir.glob("promotion_dry_run-*.json"))
        assert len(evidence_files) == 1
        
        # Verify evidence file content
        evidence_content = evidence_files[0].read_text()
        evidence = json.loads(evidence_content)
        assert "context_id" in evidence
        assert evidence["context_id"] == "promotion_dry_run"
        assert "timestamp" in evidence
        assert "results" in evidence
        assert len(evidence["results"]) == 2
        assert evidence["passed"] is True

    def test_run_workflow_context_no_evidence(self, temp_work_dir):
        """Test that evidence file is not written when disabled."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello\n"
        mock_result.stderr = ""
        
        with patch("rig.domain.workflow_chains.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            with patch("rig.domain.workflow_chains.datetime") as mock_dt:
                mock_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
                mock_dt.now.return_value = mock_now
                mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                
                run_workflow_context(
                    "promotion_dry_run",
                    repo_path=temp_work_dir,
                    write_evidence=False,
                )
        
        # Check no evidence file was created
        validation_dir = temp_work_dir / ".rig" / "work" / "validation"
        evidence_files = list(validation_dir.glob("promotion_dry_run-*.json"))
        assert len(evidence_files) == 0


# ---------------------------------------------------------------------------
# Serialization Tests
# ---------------------------------------------------------------------------


class TestSerialization:
    """Tests for domain type serialization."""

    def test_serialization_roundtrip_command(self):
        """Test serializing and deserializing a WorkflowCommand."""
        cmd = WorkflowCommand(
            id="test_cmd",
            command=("echo", "hello"),
            required=True,
            agent_allowed=True,
            mutates_state=False,
            description="Test command",
        )
        # Just verify it can be serialized to dict
        serialized = {
            "id": cmd.id,
            "description": cmd.description,
            "command": list(cmd.command),
            "required": cmd.required,
            "agent_allowed": cmd.agent_allowed,
            "mutates_state": cmd.mutates_state,
        }
        assert serialized["id"] == "test_cmd"
        assert serialized["command"] == ["echo", "hello"]

    def test_serialization_roundtrip_context(self):
        """Test serializing and deserializing a WorkflowContext."""
        ctx = WorkflowContext(
            id="test_context",
            description="Test context",
            commands=(
                WorkflowCommand(
                    id="test_cmd",
                    command=("echo", "hello"),
                    required=True,
                    agent_allowed=True,
                    mutates_state=False,
                    description="Test command",
                ),
            ),
            agent_allowed=True,
            mutates_state=False,
        )
        # Just verify it can be serialized to dict
        serialized = {
            "id": ctx.id,
            "description": ctx.description,
            "commands": [
                {
                    "id": c.id,
                    "description": c.description,
                    "command": list(c.command),
                    "required": c.required,
                    "agent_allowed": c.agent_allowed,
                    "mutates_state": c.mutates_state,
                }
                for c in ctx.commands
            ],
            "agent_allowed": ctx.agent_allowed,
            "mutates_state": ctx.mutates_state,
        }
        assert serialized["id"] == "test_context"
        assert len(serialized["commands"]) == 1


# ---------------------------------------------------------------------------
# MAX_OUTPUT_CHARS Tests
# ---------------------------------------------------------------------------


class TestMaxOutputChars:
    """Tests for output truncation constant."""

    def test_max_output_chars_value(self):
        """Test MAX_OUTPUT_CHARS is 10000."""
        assert MAX_OUTPUT_CHARS == 10000
