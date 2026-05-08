"""Tests for Runtime Stream Event Models.

Phase 2: Runtime & Agent Execution Plane - Stream Event Models Tests.

Core doctrine validated:
- Runtime output is advisory evidence only
- Only receipts/proposals become authoritative evidence
- UI streams projections, NOT raw subprocesses
- All runtime execution remains advisory-only
- NO autonomous apply, direct workspace mutation, hidden execution, background daemons,
  cloud orchestration, production networking, real API keys, or destructive Git commands

Tests cover:
- RuntimeStreamChunk
- RuntimeStatusEvent
- RuntimeHeartbeatEvent
- RuntimeToolProposalEvent
- RuntimePatchProposalEvent
- RuntimeWarningEvent
- RuntimeCompletionEvent
- RuntimeFailureEvent
- RuntimeStreamBuffer
- RuntimeSequenceState
- All enums and constants
- Deterministic serialization
- Replay safety
- Projection safety

file: tests/test_runtime_stream.py
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rig.domain.runtime_stream import (
    # Constants
    PLACEHOLDER_STREAM_ID,
    PLACEHOLDER_INVOKE_ID,
    PLACEHOLDER_SEQUENCE,
    PLACEHOLDER_PROVIDER_ID,
    PLACEHOLDER_MODEL_ID,
    PLACEHOLDER_CHANNEL,
    PLACEHOLDER_CONTENT,
    PLACEHOLDER_CHECKSUM,
    PLACEHOLDER_HASH,
    DEFAULT_MAX_CHUNK_BYTES,
    DEFAULT_MAX_BUFFER_BYTES,
    DEFAULT_STREAM_TIMEOUT_SECONDS,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_STALLED_THRESHOLD_SECONDS,
    # Enums
    RuntimeStreamChannel,
    RuntimeStreamEventKind,
    RuntimeStreamStatus,
    RuntimeStreamStateKind,
    RuntimeProposalKind,
    RuntimeWarningCode,
    RuntimeFailureCategory,
    # Models
    RuntimeStreamChunk,
    RuntimeStatusEvent,
    RuntimeHeartbeatEvent,
    RuntimeToolProposalEvent,
    RuntimePatchProposalEvent,
    RuntimeWarningEvent,
    RuntimeCompletionEvent,
    RuntimeFailureEvent,
    RuntimeStreamBuffer,
    RuntimeSequenceState,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_chunk_data() -> Dict[str, Any]:
    """Sample chunk data for testing."""
    return {
        "stream_id": "stream_001",
        "sequence": 1,
        "channel": RuntimeStreamChannel.ASSISTANT,
        "content": "test content",
        "provider_id": "provider_001",
        "model_id": "model_001",
        "invocation_id": "invoke_001",
        "created_at": "2024-01-01T00:00:00+00:00",
    }


@pytest.fixture
def sample_tool_proposal_data() -> Dict[str, Any]:
    """Sample tool proposal data for testing."""
    return {
        "stream_id": "stream_001",
        "sequence": 2,
        "proposal_kind": RuntimeProposalKind.TOOL_CALL,
        "capability_id": "cap_001",
        "tool_name": "test_tool",
        "arguments": {"arg1": "value1"},
        "provider_id": "provider_001",
        "model_id": "model_001",
        "invocation_id": "invoke_001",
        "created_at": "2024-01-01T00:00:01+00:00",
    }


@pytest.fixture
def sample_patch_proposal_data() -> Dict[str, Any]:
    """Sample patch proposal data for testing."""
    return {
        "stream_id": "stream_001",
        "sequence": 3,
        "proposal_kind": RuntimeProposalKind.CODE_PATCH,
        "path": "/path/to/file.py",
        "diff": "+line added\n-line removed",
        "language": "python",
        "line": 10,
        "column": 5,
        "provider_id": "provider_001",
        "model_id": "model_001",
        "invocation_id": "invoke_001",
        "created_at": "2024-01-01T00:00:02+00:00",
    }


# =============================================================================
# Enum Tests
# =============================================================================

class TestRuntimeStreamChannel:
    """Tests for RuntimeStreamChannel enum."""

    def test_assistant_channel(self):
        assert RuntimeStreamChannel.ASSISTANT.value == "assistant"

    def test_user_channel(self):
        assert RuntimeStreamChannel.USER.value == "user"

    def test_system_channel(self):
        assert RuntimeStreamChannel.SYSTEM.value == "system"

    def test_tool_channel(self):
        assert RuntimeStreamChannel.TOOL.value == "tool"

    def test_proposal_channel(self):
        assert RuntimeStreamChannel.PROPOSAL.value == "proposal"

    def test_diagnostic_channel(self):
        assert RuntimeStreamChannel.DIAGNOSTIC.value == "diagnostic"

    def test_status_channel(self):
        assert RuntimeStreamChannel.STATUS.value == "status"

    def test_heartbeat_channel(self):
        assert RuntimeStreamChannel.HEARTBEAT.value == "heartbeat"

    def test_warning_channel(self):
        assert RuntimeStreamChannel.WARNING.value == "warning"

    def test_error_channel(self):
        assert RuntimeStreamChannel.ERROR.value == "error"


class TestRuntimeStreamEventKind:
    """Tests for RuntimeStreamEventKind enum."""

    def test_chunk_kind(self):
        assert RuntimeStreamEventKind.CHUNK.value == "chunk"

    def test_status_kind(self):
        assert RuntimeStreamEventKind.STATUS.value == "status"

    def test_heartbeat_kind(self):
        assert RuntimeStreamEventKind.HEARTBEAT.value == "heartbeat"

    def test_tool_proposal_kind(self):
        assert RuntimeStreamEventKind.TOOL_PROPOSAL.value == "tool_proposal"

    def test_patch_proposal_kind(self):
        assert RuntimeStreamEventKind.PATCH_PROPOSAL.value == "patch_proposal"

    def test_warning_kind(self):
        assert RuntimeStreamEventKind.WARNING.value == "warning"

    def test_completion_kind(self):
        assert RuntimeStreamEventKind.COMPLETION.value == "completion"

    def test_failure_kind(self):
        assert RuntimeStreamEventKind.FAILURE.value == "failure"


class TestRuntimeStreamStatus:
    """Tests for RuntimeStreamStatus enum."""

    def test_active_status(self):
        assert RuntimeStreamStatus.ACTIVE.value == "active"

    def test_completed_status(self):
        assert RuntimeStreamStatus.COMPLETED.value == "completed"

    def test_failed_status(self):
        assert RuntimeStreamStatus.FAILED.value == "failed"

    def test_stalled_status(self):
        assert RuntimeStreamStatus.STALLED.value == "stalled"

    def test_paused_status(self):
        assert RuntimeStreamStatus.PAUSED.value == "paused"


class TestRuntimeStreamStateKind:
    """Tests for RuntimeStreamStateKind enum."""

    def test_initial_kind(self):
        assert RuntimeStreamStateKind.INITIAL.value == "initial"

    def test_streaming_kind(self):
        assert RuntimeStreamStateKind.STREAMING.value == "streaming"

    def test_completed_kind(self):
        assert RuntimeStreamStateKind.COMPLETED.value == "completed"

    def test_failed_kind(self):
        assert RuntimeStreamStateKind.FAILED.value == "failed"

    def test_cancelled_kind(self):
        assert RuntimeStreamStateKind.CANCELLED.value == "cancelled"


class TestRuntimeProposalKind:
    """Tests for RuntimeProposalKind enum."""

    def test_tool_call_kind(self):
        assert RuntimeProposalKind.TOOL_CALL.value == "tool_call"

    def test_code_patch_kind(self):
        assert RuntimeProposalKind.CODE_PATCH.value == "code_patch"

    def test_file_create_kind(self):
        assert RuntimeProposalKind.FILE_CREATE.value == "file_create"

    def test_file_delete_kind(self):
        assert RuntimeProposalKind.FILE_DELETE.value == "file_delete"

    def test_file_move_kind(self):
        assert RuntimeProposalKind.FILE_MOVE.value == "file_move"

    def test_git_operation_kind(self):
        assert RuntimeProposalKind.GIT_OPERATION.value == "git_operation"

    def test_shell_command_kind(self):
        assert RuntimeProposalKind.SHELL_COMMAND.value == "shell_command"

    def test_file_edit_kind(self):
        assert RuntimeProposalKind.FILE_EDIT.value == "file_edit"


class TestRuntimeWarningCode:
    """Tests for RuntimeWarningCode enum."""

    def test_content_truncated_code(self):
        assert RuntimeWarningCode.CONTENT_TRUNCATED.value == "STREAM-001"

    def test_chunk_too_large_code(self):
        assert RuntimeWarningCode.CHUNK_TOO_LARGE.value == "STREAM-002"

    def test_stream_stalled_code(self):
        assert RuntimeWarningCode.STREAM_STALLED.value == "STREAM-003"

    def test_proposal_blocked_code(self):
        assert RuntimeWarningCode.PROPOSAL_BLOCKED.value == "STREAM-004"

    def test_forbidden_command_code(self):
        assert RuntimeWarningCode.FORBIDDEN_COMMAND.value == "STREAM-005"


class TestRuntimeFailureCategory:
    """Tests for RuntimeFailureCategory enum."""

    def test_stream_error_category(self):
        assert RuntimeFailureCategory.STREAM_ERROR.value == "stream_error"

    def test_proposal_error_category(self):
        assert RuntimeFailureCategory.PROPOSAL_ERROR.value == "proposal_error"

    def test_supervision_error_category(self):
        assert RuntimeFailureCategory.SUPERVISION_ERROR.value == "supervision_error"

    def test_timeout_error_category(self):
        assert RuntimeFailureCategory.TIMEOUT_ERROR.value == "timeout_error"

    def test_validation_error_category(self):
        assert RuntimeFailureCategory.VALIDATION_ERROR.value == "validation_error"


# =============================================================================
# Constants Tests
# =============================================================================

class TestPlaceholderConstants:
    """Tests for placeholder constants."""

    def test_placeholder_stream_id(self):
        assert PLACEHOLDER_STREAM_ID == "STREAM_ID_PLACEHOLDER"

    def test_placeholder_invoke_id(self):
        assert PLACEHOLDER_INVOKE_ID == "INVOKE_ID_PLACEHOLDER"

    def test_placeholder_sequence(self):
        assert PLACEHOLDER_SEQUENCE == 0

    def test_placeholder_provider_id(self):
        assert PLACEHOLDER_PROVIDER_ID == "PROVIDER_ID_PLACEHOLDER"

    def test_placeholder_model_id(self):
        assert PLACEHOLDER_MODEL_ID == "MODEL_ID_PLACEHOLDER"

    def test_placeholder_channel(self):
        assert PLACEHOLDER_CHANNEL == "CHANNEL_PLACEHOLDER"

    def test_placeholder_content(self):
        assert PLACEHOLDER_CONTENT == "CONTENT_PLACEHOLDER"

    def test_placeholder_checksum(self):
        assert PLACEHOLDER_CHECKSUM == "CHECKSUM_PLACEHOLDER"

    def test_placeholder_hash(self):
        assert PLACEHOLDER_HASH == "HASH_PLACEHOLDER"


class TestDefaultConstants:
    """Tests for default configuration constants."""

    def test_default_max_chunk_bytes(self):
        assert DEFAULT_MAX_CHUNK_BYTES == 1 * 1024 * 1024  # 1MB

    def test_default_max_buffer_bytes(self):
        assert DEFAULT_MAX_BUFFER_BYTES == 10 * 1024 * 1024  # 10MB

    def test_default_stream_timeout_seconds(self):
        assert DEFAULT_STREAM_TIMEOUT_SECONDS == 300

    def test_default_heartbeat_interval_seconds(self):
        assert DEFAULT_HEARTBEAT_INTERVAL_SECONDS == 5

    def test_default_stalled_threshold_seconds(self):
        assert DEFAULT_STALLED_THRESHOLD_SECONDS == 30


# =============================================================================
# RuntimeStreamChunk Tests
# =============================================================================

class TestRuntimeStreamChunk:
    """Tests for RuntimeStreamChunk model."""

    def test_default_values(self):
        chunk = RuntimeStreamChunk()
        assert chunk.stream_id == PLACEHOLDER_STREAM_ID
        assert chunk.sequence == PLACEHOLDER_SEQUENCE
        assert chunk.channel == PLACEHOLDER_CHANNEL
        assert chunk.content == PLACEHOLDER_CONTENT
        assert chunk.provider_id == PLACEHOLDER_PROVIDER_ID
        assert chunk.model_id == PLACEHOLDER_MODEL_ID
        assert chunk.invocation_id == PLACEHOLDER_INVOKE_ID
        assert chunk.advisory_only is True
        assert chunk.authoritative is False

    def test_create_from_dict(self, sample_chunk_data):
        chunk = RuntimeStreamChunk.from_dict(sample_chunk_data)
        assert chunk.stream_id == "stream_001"
        assert chunk.sequence == 1
        assert chunk.channel == RuntimeStreamChannel.ASSISTANT
        assert chunk.content == "test content"
        assert chunk.advisory_only is True

    def test_to_dict(self, sample_chunk_data):
        chunk = RuntimeStreamChunk.from_dict(sample_chunk_data)
        result = chunk.to_dict()
        assert result["stream_id"] == "stream_001"
        assert result["sequence"] == 1
        assert result["channel"] == "assistant"
        assert result["content"] == "test content"
        assert result["advisory_only"] is True
        assert result["authoritative"] is False

    def test_to_json(self, sample_chunk_data):
        chunk = RuntimeStreamChunk.from_dict(sample_chunk_data)
        json_str = chunk.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["stream_id"] == "stream_001"
        assert parsed["advisory_only"] is True

    def test_frozen(self):
        chunk = RuntimeStreamChunk(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
        with pytest.raises(AttributeError):
            chunk.stream_id = "changed"  # type: ignore

    def test_slots(self):
        chunk = RuntimeStreamChunk()
        with pytest.raises(AttributeError):
            chunk.nonexistent_attr  # type: ignore

    def test_content_truncation(self):
        long_content = "x" * (DEFAULT_MAX_CHUNK_BYTES + 100)
        chunk = RuntimeStreamChunk.from_dict({
            "stream_id": "test",
            "sequence": 1,
            "channel": "assistant",
            "content": long_content,
        })
        assert len(chunk.content) <= DEFAULT_MAX_CHUNK_BYTES
        assert "..." in chunk.content
        assert chunk.truncated is True

    def test_deterministic_id(self):
        chunk1 = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
            provider_id="p1",
            model_id="m1",
            invocation_id="i1",
        )
        chunk2 = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
            provider_id="p1",
            model_id="m1",
            invocation_id="i1",
        )
        assert chunk1.id == chunk2.id

    def test_is_advisory_only(self):
        chunk = RuntimeStreamChunk()
        assert chunk.advisory_only is True
        assert chunk.authoritative is False


# =============================================================================
# RuntimeStatusEvent Tests
# =============================================================================

class TestRuntimeStatusEvent:
    """Tests for RuntimeStatusEvent model."""

    def test_default_values(self):
        event = RuntimeStatusEvent()
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.status == RuntimeStreamStatus.ACTIVE
        assert event.message == ""
        assert event.advisory_only is True
        assert event.authoritative is False

    def test_create_with_values(self):
        event = RuntimeStatusEvent.create(
            stream_id="stream_001",
            sequence=1,
            status=RuntimeStreamStatus.COMPLETED,
            message="Stream completed successfully",
            provider_id="provider_001",
            model_id="model_001",
            invocation_id="invoke_001",
        )
        assert event.stream_id == "stream_001"
        assert event.sequence == 1
        assert event.status == RuntimeStreamStatus.COMPLETED
        assert event.message == "Stream completed successfully"
        assert event.advisory_only is True

    def test_to_dict(self):
        event = RuntimeStatusEvent.create(
            stream_id="stream_001",
            sequence=1,
            status=RuntimeStreamStatus.ACTIVE,
        )
        result = event.to_dict()
        assert result["stream_id"] == "stream_001"
        assert result["sequence"] == 1
        assert result["status"] == "active"
        assert result["advisory_only"] is True

    def test_frozen(self):
        event = RuntimeStatusEvent()
        with pytest.raises(AttributeError):
            event.status = RuntimeStreamStatus.COMPLETED  # type: ignore


# =============================================================================
# RuntimeHeartbeatEvent Tests
# =============================================================================

class TestRuntimeHeartbeatEvent:
    """Tests for RuntimeHeartbeatEvent model."""

    def test_default_values(self):
        event = RuntimeHeartbeatEvent()
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.advisory_only is True
        assert event.authoritative is False

    def test_create_with_values(self):
        event = RuntimeHeartbeatEvent.create(
            stream_id="stream_001",
            sequence=5,
            provider_id="provider_001",
            model_id="model_001",
            invocation_id="invoke_001",
        )
        assert event.stream_id == "stream_001"
        assert event.sequence == 5
        assert event.advisory_only is True

    def test_interval_ms(self):
        event = RuntimeHeartbeatEvent.create(
            stream_id="stream_001",
            sequence=1,
            interval_ms=5000,
        )
        assert event.interval_ms == 5000

    def test_to_dict(self):
        event = RuntimeHeartbeatEvent.create(
            stream_id="stream_001",
            sequence=1,
        )
        result = event.to_dict()
        assert result["advisory_only"] is True
        assert result["authoritative"] is False


# =============================================================================
# RuntimeToolProposalEvent Tests
# =============================================================================

class TestRuntimeToolProposalEvent:
    """Tests for RuntimeToolProposalEvent model."""

    def test_default_values(self, sample_tool_proposal_data):
        event = RuntimeToolProposalEvent()
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.proposal_kind == RuntimeProposalKind.TOOL_CALL
        assert event.advisory_only is True
        assert event.authoritative is False

    def test_create_from_dict(self, sample_tool_proposal_data):
        event = RuntimeToolProposalEvent.from_dict(sample_tool_proposal_data)
        assert event.stream_id == "stream_001"
        assert event.sequence == 2
        assert event.proposal_kind == RuntimeProposalKind.TOOL_CALL
        assert event.capability_id == "cap_001"
        assert event.tool_name == "test_tool"

    def test_to_dict(self, sample_tool_proposal_data):
        event = RuntimeToolProposalEvent.from_dict(sample_tool_proposal_data)
        result = event.to_dict()
        assert result["proposal_kind"] == "tool_call"
        assert result["advisory_only"] is True

    def test_blocked_proposal(self):
        event = RuntimeToolProposalEvent.create(
            stream_id="stream_001",
            sequence=1,
            proposal_kind=RuntimeProposalKind.TOOL_CALL,
            blocked=True,
            blocked_reason="Forbidden command detected",
        )
        assert event.blocked is True
        assert event.blocked_reason == "Forbidden command detected"


# =============================================================================
# RuntimePatchProposalEvent Tests
# =============================================================================

class TestRuntimePatchProposalEvent:
    """Tests for RuntimePatchProposalEvent model."""

    def test_default_values(self, sample_patch_proposal_data):
        event = RuntimePatchProposalEvent()
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.proposal_kind == RuntimeProposalKind.CODE_PATCH
        assert event.advisory_only is True

    def test_create_from_dict(self, sample_patch_proposal_data):
        event = RuntimePatchProposalEvent.from_dict(sample_patch_proposal_data)
        assert event.stream_id == "stream_001"
        assert event.sequence == 3
        assert event.proposal_kind == RuntimeProposalKind.CODE_PATCH
        assert event.path == "/path/to/file.py"

    def test_to_dict(self, sample_patch_proposal_data):
        event = RuntimePatchProposalEvent.from_dict(sample_patch_proposal_data)
        result = event.to_dict()
        assert result["proposal_kind"] == "code_patch"
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeWarningEvent Tests
# =============================================================================

class TestRuntimeWarningEvent:
    """Tests for RuntimeWarningEvent model."""

    def test_default_values(self):
        event = RuntimeWarningEvent()
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.code == RuntimeWarningCode.CONTENT_TRUNCATED
        assert event.advisory_only is True

    def test_create_with_values(self):
        event = RuntimeWarningEvent.create(
            stream_id="stream_001",
            sequence=1,
            code=RuntimeWarningCode.STREAM_STALLED,
            message="Stream has stalled",
        )
        assert event.code == RuntimeWarningCode.STREAM_STALLED
        assert event.message == "Stream has stalled"

    def test_to_dict(self):
        event = RuntimeWarningEvent.create(
            stream_id="stream_001",
            sequence=1,
            code=RuntimeWarningCode.PROPOSAL_BLOCKED,
        )
        result = event.to_dict()
        assert result["code"] == "STREAM-004"
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeCompletionEvent Tests
# =============================================================================

class TestRuntimeCompletionEvent:
    """Tests for RuntimeCompletionEvent model."""

    def test_default_values(self):
        event = RuntimeCompletionEvent()
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.reason == "completed"
        assert event.advisory_only is True

    def test_create_with_values(self):
        event = RuntimeCompletionEvent.create(
            stream_id="stream_001",
            sequence=100,
            reason="end_of_stream",
            summary="Stream completed naturally",
        )
        assert event.reason == "end_of_stream"
        assert event.summary == "Stream completed naturally"

    def test_to_dict(self):
        event = RuntimeCompletionEvent()
        result = event.to_dict()
        assert result["reason"] == "completed"
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeFailureEvent Tests
# =============================================================================

class TestRuntimeFailureEvent:
    """Tests for RuntimeFailureEvent model."""

    def test_default_values(self):
        event = RuntimeFailureEvent()
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.category == RuntimeFailureCategory.STREAM_ERROR
        assert event.advisory_only is True

    def test_create_with_values(self):
        event = RuntimeFailureEvent.create(
            stream_id="stream_001",
            sequence=50,
            category=RuntimeFailureCategory.TIMEOUT_ERROR,
            message="Stream timeout",
            error_code="TIMEOUT",
        )
        assert event.category == RuntimeFailureCategory.TIMEOUT_ERROR
        assert event.message == "Stream timeout"
        assert event.error_code == "TIMEOUT"

    def test_to_dict(self):
        event = RuntimeFailureEvent()
        result = event.to_dict()
        assert result["category"] == "stream_error"
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeStreamBuffer Tests
# =============================================================================

class TestRuntimeStreamBuffer:
    """Tests for RuntimeStreamBuffer model."""

    def test_default_values(self):
        buffer = RuntimeStreamBuffer()
        assert buffer.stream_id == PLACEHOLDER_STREAM_ID
        assert buffer.invocation_id == PLACEHOLDER_INVOKE_ID
        assert buffer.max_bytes == DEFAULT_MAX_BUFFER_BYTES
        assert buffer.advisory_only is True

    def test_empty_buffer(self):
        buffer = RuntimeStreamBuffer()
        assert buffer.is_empty is True
        assert len(buffer.chunks) == 0

    def test_with_chunk(self):
        buffer = RuntimeStreamBuffer()
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
        new_buffer = buffer.with_chunk(chunk)
        assert new_buffer.is_empty is False
        assert 1 in new_buffer.chunks

    def test_byte_limit(self):
        buffer = RuntimeStreamBuffer(max_bytes=100)
        for i in range(20):
            chunk = RuntimeStreamChunk.create(
                stream_id="test",
                sequence=i,
                content="x" * 10,
            )
            buffer = buffer.with_chunk(chunk)
        # Buffer should not exceed max_bytes
        assert buffer.total_bytes <= 100

    def test_get_chunk(self, sample_chunk_data):
        buffer = RuntimeStreamBuffer()
        chunk = RuntimeStreamChunk.from_dict(sample_chunk_data)
        buffer = buffer.with_chunk(chunk)
        retrieved = buffer.get_chunk(1)
        assert retrieved is not None
        assert retrieved.sequence == 1

    def test_get_all_chunks(self):
        buffer = RuntimeStreamBuffer()
        for i in range(5):
            chunk = RuntimeStreamChunk.create(
                stream_id="test",
                sequence=i,
                content=f"chunk_{i}",
            )
            buffer = buffer.with_chunk(chunk)
        chunks = buffer.get_all_chunks()
        assert len(chunks) == 5

    def test_frozen(self):
        buffer = RuntimeStreamBuffer()
        with pytest.raises(AttributeError):
            buffer.stream_id = "changed"  # type: ignore


# =============================================================================
# RuntimeSequenceState Tests
# =============================================================================

class TestRuntimeSequenceState:
    """Tests for RuntimeSequenceState model."""

    def test_default_values(self):
        state = RuntimeSequenceState()
        assert state.stream_id == PLACEHOLDER_STREAM_ID
        assert state.invocation_id == PLACEHOLDER_INVOKE_ID
        assert state.first_sequence == 0
        assert state.last_sequence == 0
        assert state.kind == RuntimeStreamStateKind.INITIAL
        assert state.advisory_only is True

    def test_create_with_values(self):
        state = RuntimeSequenceState.create(
            stream_id="stream_001",
            invocation_id="invoke_001",
            first_sequence=1,
            last_sequence=100,
            kind=RuntimeStreamStateKind.STREAMING,
        )
        assert state.first_sequence == 1
        assert state.last_sequence == 100
        assert state.kind == RuntimeStreamStateKind.STREAMING

    def test_sequence_range(self):
        state = RuntimeSequenceState.create(
            stream_id="stream_001",
            first_sequence=0,
            last_sequence=100,
        )
        assert state.sequence_range == (0, 100)

    def test_count(self):
        state = RuntimeSequenceState.create(
            stream_id="stream_001",
            first_sequence=0,
            last_sequence=99,
            total_sequences=100,
        )
        assert state.count == 100

    def test_to_dict(self):
        state = RuntimeSequenceState()
        result = state.to_dict()
        assert result["advisory_only"] is True
        assert result["authoritative"] is False


# =============================================================================
# Integration Tests
# =============================================================================

class TestStreamEventSerialization:
    """Tests for serialization consistency across all event types."""

    def test_all_events_serializable(self):
        """All event types should be JSON serializable."""
        events = [
            RuntimeStreamChunk.create(
                stream_id="test",
                sequence=1,
                content="test",
            ),
            RuntimeStatusEvent.create(
                stream_id="test",
                sequence=2,
                status=RuntimeStreamStatus.ACTIVE,
            ),
            RuntimeHeartbeatEvent.create(
                stream_id="test",
                sequence=3,
            ),
            RuntimeToolProposalEvent.create(
                stream_id="test",
                sequence=4,
                proposal_kind=RuntimeProposalKind.TOOL_CALL,
            ),
            RuntimePatchProposalEvent.create(
                stream_id="test",
                sequence=5,
                proposal_kind=RuntimeProposalKind.CODE_PATCH,
            ),
            RuntimeWarningEvent.create(
                stream_id="test",
                sequence=6,
            ),
            RuntimeCompletionEvent.create(
                stream_id="test",
                sequence=7,
            ),
            RuntimeFailureEvent.create(
                stream_id="test",
                sequence=8,
            ),
        ]
        for event in events:
            json_str = event.to_json()
            assert isinstance(json_str, str)
            parsed = json.loads(json_str)
            assert "advisory_only" in parsed
            assert parsed["advisory_only"] is True


class TestAdvisoryOnlyInvariant:
    """Tests that all models enforce advisory-only invariant."""

    def test_all_models_advisory_only(self):
        """All runtime stream models must be advisory_only=True."""
        models = [
            RuntimeStreamChunk(),
            RuntimeStatusEvent(),
            RuntimeHeartbeatEvent(),
            RuntimeToolProposalEvent(),
            RuntimePatchProposalEvent(),
            RuntimeWarningEvent(),
            RuntimeCompletionEvent(),
            RuntimeFailureEvent(),
            RuntimeStreamBuffer(),
            RuntimeSequenceState(),
        ]
        for model in models:
            assert model.advisory_only is True
            assert model.authoritative is False


class TestReplaySafety:
    """Tests for replay safety of stream events."""

    def test_deterministic_roundtrip(self):
        """Events should serialize and deserialize deterministically."""
        original_data = {
            "stream_id": "test",
            "sequence": 1,
            "channel": "assistant",
            "content": "test content",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        chunk1 = RuntimeStreamChunk.from_dict(original_data)
        json1 = chunk1.to_json()
        
        chunk2 = RuntimeStreamChunk.from_dict(json.loads(json1))
        json2 = chunk2.to_json()
        
        # JSON should be identical (sort_keys=True ensures ordering)
        assert json1 == json2

    def test_sequence_ordering(self):
        """Events should maintain sequence ordering."""
        chunks = [
            RuntimeStreamChunk.create(
                stream_id="test",
                sequence=i,
                content=f"chunk_{i}",
            )
            for i in range(10)
        ]
        sequences = [c.sequence for c in chunks]
        assert sequences == list(range(10))


class TestProjectionSafety:
    """Tests for projection safety of stream events."""

    def test_all_events_have_required_fields(self):
        """All events should have fields needed for projection."""
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
        assert hasattr(chunk, 'stream_id')
        assert hasattr(chunk, 'sequence')
        assert hasattr(chunk, 'created_at')

    def test_content_safe_for_projection(self):
        """Event content should be safe for projection."""
        # Content with control characters
        unsafe_content = "test\ncontent\twith\rcontrol"
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            content=unsafe_content,
        )
        # Content should be preserved as-is
        assert chunk.content == unsafe_content


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_content(self):
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            content="",
        )
        assert chunk.content == ""
        assert chunk.truncated is False

    def test_unicode_content(self):
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            content="Hello 世界 🌍",
        )
        assert "世界" in chunk.content
        assert "🌍" in chunk.content

    def test_very_long_sequence(self):
        state = RuntimeSequenceState.create(
            stream_id="test",
            first_sequence=0,
            last_sequence=2**63 - 1,
        )
        assert state.last_sequence == 2**63 - 1

    def test_zero_sequence(self):
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=0,
            content="first",
        )
        assert chunk.sequence == 0

    def test_negative_sequence_traps_overflow(self):
        # Should not crash with negative sequence
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=-1,
            content="test",
        )
        # Sequence is just stored as-is, overflow handling is in buffer
        assert chunk.sequence == -1


# =============================================================================
# Doctrinal Compliance Tests
# =============================================================================

class TestDoctrineCompliance:
    """Tests for compliance with Phase 2 core doctrine."""

    def test_output_is_advisory_evidence_only(self):
        """Core doctrine: Runtime output is advisory evidence only."""
        chunk = RuntimeStreamChunk()
        assert chunk.advisory_only is True
        assert chunk.authoritative is False

    def test_no_direct_workspace_mutation(self):
        """Core doctrine: No direct workspace mutation.
        
        This is validated by ensuring all models are frozen and
        have no methods that mutate external state.
        """
        chunk = RuntimeStreamChunk()
        with pytest.raises(AttributeError):
            chunk.content = "mutated"  # type: ignore

    def test_no_authoritative_release(self):
        """Core doctrine: Only receipts/proposals become authoritative.
        
        All stream models must remain advisory-only.
        """
        events = [
            RuntimeStreamChunk(),
            RuntimeStatusEvent(),
            RuntimeHeartbeatEvent(),
            RuntimeToolProposalEvent(),
            RuntimePatchProposalEvent(),
            RuntimeWarningEvent(),
            RuntimeCompletionEvent(),
            RuntimeFailureEvent(),
        ]
        for event in events:
            assert event.authoritative is False

    def test_projection_only_UI(self):
        """Core doctrine: UI streams projections, NOT raw subprocesses.
        
        Stream events provide data for projections but don't contain
        HTML or other raw rendering content.
        """
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            content="<script>alert('xss')</script>",
        )
        # Content is stored as plain text, not HTML
        assert "<script>" in chunk.content
        # UI would be responsible for escaping via textContent

    def test_no_hidden_execution(self):
        """Core doctrine: No hidden execution.
        
        Stream models don't have any execution capabilities.
        """
        chunk = RuntimeStreamChunk()
        # No methods for execution
        assert not hasattr(chunk, 'execute')
        assert not hasattr(chunk, 'run')
        assert not hasattr(chunk, 'start')

    def test_no_background_daemons(self):
        """Core doctrine: No background daemons.
        
        Stream models are pure data, no threading/asyncio.
        """
        chunk = RuntimeStreamChunk()
        # No async/threading methods
        assert not callable(getattr(chunk, 'start', None))
        assert not callable(getattr(chunk, 'join', None))

    def test_no_destructive_git_commands(self):
        """Core doctrine: No destructive Git commands.
        
        Stream models don't have Git-related functionality.
        """
        chunk = RuntimeStreamChunk()
        assert not hasattr(chunk, 'git')
        assert not hasattr(chunk, 'reset')
        assert not hasattr(chunk, 'push')
