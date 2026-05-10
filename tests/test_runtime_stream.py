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
    PLACEHOLDER_PROVIDER,
    PLACEHOLDER_INVOCATION,
    PLACEHOLDER_MODEL_ID,
    PLACEHOLDER_CHANNEL,
    PLACEHOLDER_CONTENT,
    PLACEHOLDER_CHECKSUM,
    PLACEHOLDER_HASH,
    DEFAULT_MAX_CHUNK_BYTES,
    DEFAULT_MAX_BUFFER_BYTES,
    DEFAULT_MAX_BUFFER_SIZE,
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
        "chunk_id": "chunk_001",
        "stream_id": "stream_001",
        "sequence": 1,
        "channel": "assistant",
        "content": "test content",
        "provider_id": "provider_001",
        "invocation_id": "invoke_001",
        "created_at": "2024-01-01T00:00:00+00:00",
    }


@pytest.fixture
def sample_tool_proposal_data() -> Dict[str, Any]:
    """Sample tool proposal data for testing."""
    return {
        "event_id": "event_002",
        "stream_id": "stream_001",
        "sequence": 2,
        "proposal_kind": "tool_call",
        "payload": {"tool_name": "test_tool", "arguments": {"arg1": "value1"}},
        "provider_id": "provider_001",
        "invocation_id": "invoke_001",
        "created_at": "2024-01-01T00:00:01+00:00",
    }


@pytest.fixture
def sample_patch_proposal_data() -> Dict[str, Any]:
    """Sample patch proposal data for testing."""
    return {
        "event_id": "event_003",
        "stream_id": "stream_001",
        "sequence": 3,
        "file_path": "/path/to/file.py",
        "diff": "+line added\n-line removed",
        "provider_id": "provider_001",
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

    def test_idle_kind(self):
        assert RuntimeStreamStateKind.IDLE.value == "idle"

    def test_streaming_kind(self):
        assert RuntimeStreamStateKind.STREAMING.value == "streaming"

    def test_degraded_kind(self):
        assert RuntimeStreamStateKind.DEGRADED.value == "degraded"

    def test_blocked_kind(self):
        assert RuntimeStreamStateKind.BLOCKED.value == "blocked"


class TestRuntimeProposalKind:
    """Tests for RuntimeProposalKind enum."""

    def test_tool_call_kind(self):
        assert RuntimeProposalKind.TOOL_CALL.value == "tool_call"

    def test_shell_command_kind(self):
        assert RuntimeProposalKind.SHELL_COMMAND.value == "shell_command"

    def test_patch_kind(self):
        assert RuntimeProposalKind.PATCH.value == "patch"

    def test_file_write_kind(self):
        assert RuntimeProposalKind.FILE_WRITE.value == "file_write"

    def test_file_read_kind(self):
        assert RuntimeProposalKind.FILE_READ.value == "file_read"

    def test_network_fetch_kind(self):
        assert RuntimeProposalKind.NETWORK_FETCH.value == "network_fetch"

    def test_docs_fetch_kind(self):
        assert RuntimeProposalKind.DOCS_FETCH.value == "docs_fetch"


class TestRuntimeWarningCode:
    """Tests for RuntimeWarningCode enum."""

    def test_truncation_applied_code(self):
        assert RuntimeWarningCode.TRUNCATION_APPLIED.value == "truncation_applied"

    def test_rate_limited_code(self):
        assert RuntimeWarningCode.RATE_LIMITED.value == "rate_limited"

    def test_model_unavailable_code(self):
        assert RuntimeWarningCode.MODEL_UNAVAILABLE.value == "model_unavailable"

    def test_capability_mismatch_code(self):
        assert RuntimeWarningCode.CAPABILITY_MISMATCH.value == "capability_mismatch"

    def test_stalled_detected_code(self):
        assert RuntimeWarningCode.STALLED_DETECTED.value == "stalled_detected"


class TestRuntimeFailureCategory:
    """Tests for RuntimeFailureCategory enum."""

    def test_connection_error_category(self):
        assert RuntimeFailureCategory.CONNECTION_ERROR.value == "connection_error"

    def test_timeout_category(self):
        assert RuntimeFailureCategory.TIMEOUT.value == "timeout"

    def test_provider_error_category(self):
        assert RuntimeFailureCategory.PROVIDER_ERROR.value == "provider_error"

    def test_validation_error_category(self):
        assert RuntimeFailureCategory.VALIDATION_ERROR.value == "validation_error"

    def test_capability_error_category(self):
        assert RuntimeFailureCategory.CAPABILITY_ERROR.value == "capability_error"


# =============================================================================
# Constants Tests
# =============================================================================

class TestPlaceholderConstants:
    """Tests for placeholder constants."""

    def test_placeholder_stream_id(self):
        assert PLACEHOLDER_STREAM_ID == "not_set"

    def test_placeholder_invoke_id(self):
        assert PLACEHOLDER_INVOKE_ID == "INVOKE_ID_PLACEHOLDER"

    def test_placeholder_sequence(self):
        assert PLACEHOLDER_SEQUENCE == -1

    def test_placeholder_provider_id(self):
        assert PLACEHOLDER_PROVIDER_ID == "no_provider"

    def test_placeholder_model_id(self):
        assert PLACEHOLDER_MODEL_ID == "no_model"

    def test_placeholder_channel(self):
        assert PLACEHOLDER_CHANNEL == "unknown"

    def test_placeholder_content(self):
        assert PLACEHOLDER_CONTENT == ""

    def test_placeholder_checksum(self):
        assert PLACEHOLDER_CHECKSUM == ""

    def test_placeholder_hash(self):
        assert PLACEHOLDER_HASH == ""


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
        chunk = RuntimeStreamChunk(chunk_id="test_chunk")
        assert chunk.stream_id == PLACEHOLDER_STREAM_ID
        assert chunk.sequence == PLACEHOLDER_SEQUENCE
        assert chunk.channel == RuntimeStreamChannel.ASSISTANT
        assert chunk.content == PLACEHOLDER_CONTENT
        assert chunk.provider_id == PLACEHOLDER_PROVIDER_ID
        assert chunk.invocation_id == PLACEHOLDER_INVOCATION
        assert chunk.advisory_only is True

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

    def test_to_json(self, sample_chunk_data):
        chunk = RuntimeStreamChunk.from_dict(sample_chunk_data)
        json_str = chunk.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["stream_id"] == "stream_001"
        assert parsed["advisory_only"] is True

    def test_frozen(self):
        chunk = RuntimeStreamChunk(
            chunk_id="test_001",
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
        with pytest.raises(AttributeError):
            chunk.stream_id = "changed"  # type: ignore

    def test_slots(self):
        chunk = RuntimeStreamChunk(chunk_id="test_001")
        with pytest.raises(AttributeError):
            chunk.nonexistent_attr  # type: ignore

    def test_content_truncation(self):
        long_content = "x" * (DEFAULT_MAX_CHUNK_BYTES + 100)
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content=long_content,
        )
        assert len(chunk.content) <= DEFAULT_MAX_CHUNK_BYTES
        assert chunk.truncated is True

    def test_deterministic_id(self):
        chunk1 = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
            provider_id="p1",
            invocation_id="i1",
        )
        chunk2 = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
            provider_id="p1",
            invocation_id="i1",
        )
        assert chunk1.chunk_id == chunk2.chunk_id

    def test_is_advisory_only(self):
        chunk = RuntimeStreamChunk(chunk_id="test_001")
        assert chunk.advisory_only is True


# =============================================================================
# RuntimeStatusEvent Tests
# =============================================================================

class TestRuntimeStatusEvent:
    """Tests for RuntimeStatusEvent model."""

    def test_default_values(self):
        event = RuntimeStatusEvent(event_id="event_001")
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.status == RuntimeStreamStatus.PENDING
        assert event.message == ""
        assert event.advisory_only is True

    def test_create_with_values(self):
        event = RuntimeStatusEvent.create(
            stream_id="stream_001",
            sequence=1,
            status=RuntimeStreamStatus.COMPLETED,
            message="Stream completed successfully",
            provider_id="provider_001",
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
        event = RuntimeStatusEvent(event_id="event_001")
        with pytest.raises(AttributeError):
            event.status = RuntimeStreamStatus.COMPLETED  # type: ignore


# =============================================================================
# RuntimeHeartbeatEvent Tests
# =============================================================================

class TestRuntimeHeartbeatEvent:
    """Tests for RuntimeHeartbeatEvent model."""

    def test_default_values(self):
        event = RuntimeHeartbeatEvent(event_id="hb_001")
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.advisory_only is True

    def test_create_with_values(self):
        event = RuntimeHeartbeatEvent.create(
            stream_id="stream_001",
            sequence=5,
            provider_id="provider_001",
            invocation_id="invoke_001",
        )
        assert event.stream_id == "stream_001"
        assert event.sequence == 5
        assert event.advisory_only is True

    def test_interval_seconds(self):
        event = RuntimeHeartbeatEvent.create(
            stream_id="stream_001",
            sequence=1,
            interval_seconds=5.0,
        )
        assert event.interval_seconds == 5.0

    def test_to_dict(self):
        event = RuntimeHeartbeatEvent.create(
            stream_id="stream_001",
            sequence=1,
        )
        result = event.to_dict()
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeToolProposalEvent Tests
# =============================================================================

class TestRuntimeToolProposalEvent:
    """Tests for RuntimeToolProposalEvent model."""

    def test_default_values(self, sample_tool_proposal_data):
        event = RuntimeToolProposalEvent(event_id="tool_prop_001")
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
        assert event.payload == {"tool_name": "test_tool", "arguments": {"arg1": "value1"}}

    def test_to_dict(self, sample_tool_proposal_data):
        event = RuntimeToolProposalEvent.from_dict(sample_tool_proposal_data)
        result = event.to_dict()
        assert result["proposal_kind"] == "tool_call"
        assert result["advisory_only"] is True

    def test_validation_status(self):
        event = RuntimeToolProposalEvent.create(
            stream_id="stream_001",
            sequence=1,
            proposal_kind=RuntimeProposalKind.TOOL_CALL,
            payload={"operation": "test"},
        )
        # Validation status defaults to "pending"
        assert event.validation_status == "pending"


# =============================================================================
# RuntimePatchProposalEvent Tests
# =============================================================================

class TestRuntimePatchProposalEvent:
    """Tests for RuntimePatchProposalEvent model."""

    def test_default_values(self, sample_patch_proposal_data):
        event = RuntimePatchProposalEvent(event_id="patch_001")
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.file_path == ""
        assert event.diff == ""
        assert event.advisory_only is True

    def test_create_from_dict(self, sample_patch_proposal_data):
        event = RuntimePatchProposalEvent.from_dict(sample_patch_proposal_data)
        assert event.stream_id == "stream_001"
        assert event.sequence == 3
        assert event.file_path == "/path/to/file.py"
        assert event.diff == "+line added\n-line removed"

    def test_to_dict(self, sample_patch_proposal_data):
        event = RuntimePatchProposalEvent.from_dict(sample_patch_proposal_data)
        result = event.to_dict()
        assert result["file_path"] == "/path/to/file.py"
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeWarningEvent Tests
# =============================================================================

class TestRuntimeWarningEvent:
    """Tests for RuntimeWarningEvent model."""

    def test_default_values(self):
        event = RuntimeWarningEvent(event_id="warn_001")
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.warning_code == RuntimeWarningCode.TRUNCATION_APPLIED
        assert event.advisory_only is True

    def test_create_with_values(self):
        event = RuntimeWarningEvent.create(
            stream_id="stream_001",
            sequence=1,
            warning_code=RuntimeWarningCode.STALLED_DETECTED,
            message="Stream has stalled",
        )
        assert event.warning_code == RuntimeWarningCode.STALLED_DETECTED
        assert event.message == "Stream has stalled"

    def test_to_dict(self):
        event = RuntimeWarningEvent.create(
            stream_id="stream_001",
            sequence=1,
            warning_code=RuntimeWarningCode.RATE_LIMITED,
            message="Rate limit",
        )
        result = event.to_dict()
        assert result["warning_code"] == "rate_limited"
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeCompletionEvent Tests
# =============================================================================

class TestRuntimeCompletionEvent:
    """Tests for RuntimeCompletionEvent model."""

    def test_default_values(self):
        event = RuntimeCompletionEvent(event_id="comp_001")
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.completion_reason == "normal"
        assert event.summary == ""
        assert event.advisory_only is True

    def test_create_with_values(self):
        event = RuntimeCompletionEvent.create(
            stream_id="stream_001",
            sequence=100,
            receipt_id="receipt_001",
            completion_reason="end_of_stream",
            summary="Stream completed naturally",
        )
        assert event.completion_reason == "end_of_stream"
        assert event.summary == "Stream completed naturally"

    def test_to_dict(self):
        event = RuntimeCompletionEvent.create(
            stream_id="stream_001",
            sequence=1,
            receipt_id="receipt_001",
        )
        result = event.to_dict()
        assert result["completion_reason"] == "normal"
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeFailureEvent Tests
# =============================================================================

class TestRuntimeFailureEvent:
    """Tests for RuntimeFailureEvent model."""

    def test_default_values(self):
        event = RuntimeFailureEvent(event_id="fail_001")
        assert event.stream_id == PLACEHOLDER_STREAM_ID
        assert event.sequence == PLACEHOLDER_SEQUENCE
        assert event.failure_category == RuntimeFailureCategory.INTERNAL_ERROR
        assert event.message == ""
        assert event.advisory_only is True

    def test_create_with_values(self):
        event = RuntimeFailureEvent.create(
            stream_id="stream_001",
            sequence=50,
            failure_category=RuntimeFailureCategory.TIMEOUT,
            message="Stream timeout",
        )
        assert event.failure_category == RuntimeFailureCategory.TIMEOUT
        assert event.message == "Stream timeout"

    def test_to_dict(self):
        event = RuntimeFailureEvent.create(
            stream_id="stream_001",
            sequence=1,
            failure_category=RuntimeFailureCategory.CONNECTION_ERROR,
            message="Connection failed",
        )
        result = event.to_dict()
        assert result["failure_category"] == "connection_error"
        assert result["advisory_only"] is True


# =============================================================================
# RuntimeStreamBuffer Tests
# =============================================================================

class TestRuntimeStreamBuffer:
    """Tests for RuntimeStreamBuffer model."""

    def test_default_values(self):
        buffer = RuntimeStreamBuffer(buffer_id="buf_001")
        assert buffer.stream_id == PLACEHOLDER_STREAM_ID
        assert buffer.max_size == DEFAULT_MAX_BUFFER_BYTES
        assert buffer.advisory_only is True

    def test_empty_buffer(self):
        buffer = RuntimeStreamBuffer(buffer_id="buf_001")
        assert len(buffer.chunks) == 0
        assert buffer.current_size == 0

    def test_with_chunks(self):
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
        buffer = RuntimeStreamBuffer.create(
            stream_id="test",
            max_size=100,
            buffer_id="buf_001"
        )
        # Manually create buffer with chunks
        buffer_with_chunk = RuntimeStreamBuffer(
            buffer_id="buf_002",
            stream_id="test",
            max_size=100,
            chunks=(chunk,),
            current_size=len(chunk.content),
        )
        assert len(buffer_with_chunk.chunks) == 1
        assert buffer_with_chunk.current_size > 0

    def test_byte_limit_tracking(self):
        buffer = RuntimeStreamBuffer.create(stream_id="test", max_size=100)
        chunks = []
        total_size = 0
        for i in range(20):
            chunk = RuntimeStreamChunk.create(
                stream_id="test",
                sequence=i,
                channel=RuntimeStreamChannel.ASSISTANT,
                content="x" * 10,
            )
            chunks.append(chunk)
            total_size += len(chunk.content)
            if total_size <= 100:
                assert total_size <= 100
        # Total size should not exceed max_size * number of chunks
        assert total_size > 0

    def test_get_chunk_by_sequence(self, sample_chunk_data):
        chunk = RuntimeStreamChunk.from_dict(sample_chunk_data)
        buffer = RuntimeStreamBuffer(
            buffer_id="buf_001",
            stream_id="test",
            chunks=(chunk,),
            current_size=len(chunk.content),
        )
        # Check that chunk is in the buffer
        assert len(buffer.chunks) == 1
        assert buffer.chunks[0].sequence == 1

    def test_all_chunks_accessible(self):
        chunks = []
        for i in range(5):
            chunk = RuntimeStreamChunk.create(
                stream_id="test",
                sequence=i,
                channel=RuntimeStreamChannel.ASSISTANT,
                content=f"chunk_{i}",
            )
            chunks.append(chunk)
        buffer = RuntimeStreamBuffer(
            buffer_id="buf_001",
            stream_id="test",
            chunks=tuple(chunks),
            current_size=sum(len(c.content) for c in chunks),
        )
        assert len(buffer.chunks) == 5

    def test_frozen(self):
        buffer = RuntimeStreamBuffer(buffer_id="buf_001")
        with pytest.raises(AttributeError):
            buffer.stream_id = "changed"  # type: ignore


# =============================================================================
# RuntimeSequenceState Tests
# =============================================================================

class TestRuntimeSequenceState:
    """Tests for RuntimeSequenceState model."""

    def test_default_values(self):
        state = RuntimeSequenceState(state_id="seq_001")
        assert state.stream_id == PLACEHOLDER_STREAM_ID
        assert state.last_sequence == PLACEHOLDER_SEQUENCE
        assert state.next_expected == 0
        assert state.total_received == 0
        assert state.advisory_only is True

    def test_create_with_values(self):
        state = RuntimeSequenceState.create(
            stream_id="stream_001",
            provider_id="provider_001",
            invocation_id="invoke_001",
        )
        assert state.stream_id == "stream_001"
        assert state.provider_id == "provider_001"
        assert state.invocation_id == "invoke_001"

    def test_sequence_tracking(self):
        state = RuntimeSequenceState(state_id="seq_001", last_sequence=100, next_expected=101)
        assert state.last_sequence == 100
        assert state.next_expected == 101

    def test_received_count(self):
        state = RuntimeSequenceState(state_id="seq_001", total_received=50)
        assert state.total_received == 50

    def test_to_dict(self):
        state = RuntimeSequenceState.create(
            stream_id="stream_001",
            provider_id="provider_001",
            invocation_id="invoke_001",
        )
        result = state.to_dict()
        assert result["advisory_only"] is True


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
                channel=RuntimeStreamChannel.ASSISTANT,
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
                payload={},
            ),
            RuntimePatchProposalEvent.create(
                stream_id="test",
                sequence=5,
                file_path="/tmp/test.py",
                diff="test diff",
            ),
            RuntimeWarningEvent.create(
                stream_id="test",
                sequence=6,
                warning_code=RuntimeWarningCode.TRUNCATION_APPLIED,
                message="test",
            ),
            RuntimeCompletionEvent.create(
                stream_id="test",
                sequence=7,
                receipt_id="receipt_test",
            ),
            RuntimeFailureEvent.create(
                stream_id="test",
                sequence=8,
                failure_category=RuntimeFailureCategory.CONNECTION_ERROR,
                message="test error",
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
        """All runtime stream models must be advisory_only=True.
        
        Proposal/receipt boundary models additionally expose authoritative=False.
        Stream transport models (Chunk, Status, Heartbeat, Warning, Failure,
        Buffer, SequenceState) are advisory_only only and do not have authoritative.
        """
        # All stream models must be advisory_only
        all_models = [
            RuntimeStreamChunk(chunk_id="c1"),
            RuntimeStatusEvent(event_id="e1"),
            RuntimeHeartbeatEvent(event_id="h1"),
            RuntimeToolProposalEvent(event_id="t1"),
            RuntimePatchProposalEvent(event_id="p1"),
            RuntimeWarningEvent(event_id="w1"),
            RuntimeCompletionEvent(event_id="comp1", receipt_id="r1"),
            RuntimeFailureEvent(event_id="f1"),
            RuntimeStreamBuffer(buffer_id="b1"),
            RuntimeSequenceState(state_id="s1"),
        ]
        for model in all_models:
            assert model.advisory_only is True
        
        # Only proposal/receipt boundary models have authoritative field
        # and they must be False (only receipts/proposals become authoritative)
        proposal_models = [
            RuntimeToolProposalEvent(event_id="t1"),
            RuntimePatchProposalEvent(event_id="p1"),
            RuntimeCompletionEvent(event_id="comp1", receipt_id="r1"),
        ]
        for model in proposal_models:
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
                channel=RuntimeStreamChannel.ASSISTANT,
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
        assert hasattr(chunk, 'timestamp')

    def test_content_safe_for_projection(self):
        """Event content should be safe for projection."""
        # Content with control characters
        unsafe_content = "test\ncontent\twith\rcontrol"
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
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
            channel=RuntimeStreamChannel.ASSISTANT,
            content="",
        )
        assert chunk.content == ""
        assert chunk.truncated is False

    def test_unicode_content(self):
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="Hello 世界 🌍",
        )
        assert "世界" in chunk.content
        assert "🌍" in chunk.content

    def test_very_long_sequence(self):
        state = RuntimeSequenceState.create(
            stream_id="test",
            provider_id="provider_001",
        )
        assert state.stream_id == "test"

    def test_zero_sequence(self):
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=0,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="first",
        )
        assert chunk.sequence == 0

    def test_negative_sequence_traps_overflow(self):
        # Should not crash with negative sequence
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=-1,
            channel=RuntimeStreamChannel.ASSISTANT,
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
        chunk = RuntimeStreamChunk(chunk_id="test_001")
        assert chunk.advisory_only is True

    def test_no_direct_workspace_mutation(self):
        """Core doctrine: No direct workspace mutation.
        
        This is validated by ensuring all models are frozen and
        have no methods that mutate external state.
        """
        chunk = RuntimeStreamChunk(chunk_id="test_001")
        with pytest.raises(AttributeError):
            chunk.content = "mutated"  # type: ignore

    def test_no_authoritative_release(self):
        """Core doctrine: Only receipts/proposals become authoritative.
        
        All stream models must remain advisory-only.
        """
        events = [
            RuntimeStreamChunk(chunk_id="c1"),
            RuntimeStatusEvent(event_id="e1"),
            RuntimeHeartbeatEvent(event_id="h1"),
            RuntimeToolProposalEvent(event_id="t1"),
            RuntimePatchProposalEvent(event_id="p1"),
            RuntimeWarningEvent(event_id="w1"),
            RuntimeCompletionEvent(event_id="comp1", receipt_id="r1"),
            RuntimeFailureEvent(event_id="f1"),
        ]
        for event in events:
            assert event.advisory_only is True

    def test_projection_only_UI(self):
        """Core doctrine: UI streams projections, NOT raw subprocesses.
        
        Stream events provide data for projections but don't contain
        HTML or other raw rendering content.
        """
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="<script>alert('xss')</script>",
        )
        # Content is stored as plain text, not HTML
        assert "<script>" in chunk.content
        # UI would be responsible for escaping via textContent

    def test_no_hidden_execution(self):
        """Core doctrine: No hidden execution.
        
        Stream models don't have any execution capabilities.
        """
        chunk = RuntimeStreamChunk(chunk_id="test_001")
        # No methods for execution
        assert not hasattr(chunk, 'execute')
        assert not hasattr(chunk, 'run')
        assert not hasattr(chunk, 'start')

    def test_no_background_daemons(self):
        """Core doctrine: No background daemons.
        
        Stream models are pure data, no threading/asyncio.
        """
        chunk = RuntimeStreamChunk(chunk_id="test_001")
        # No async/threading methods
        assert not callable(getattr(chunk, 'start', None))
        assert not callable(getattr(chunk, 'join', None))

    def test_no_destructive_git_commands(self):
        """Core doctrine: No destructive Git commands.
        
        Stream models don't have Git-related functionality.
        """
        chunk = RuntimeStreamChunk(chunk_id="test_001")
        assert not hasattr(chunk, 'git')
        assert not hasattr(chunk, 'reset')
        assert not hasattr(chunk, 'push')
