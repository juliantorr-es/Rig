"""Tests for Runtime Stream Projection Pipeline.

Phase 2: Runtime & Agent Execution Plane - Projection Pipeline Tests.

Core doctrine validated:
- Runtime output is advisory evidence only
- Only receipts/proposals become authoritative evidence
- UI streams projections, NOT raw subprocesses
- All runtime execution remains advisory-only
- NO autonomous apply, direct workspace mutation, hidden execution, background daemons,
  cloud orchestration, production networking, real API keys, or destructive Git commands

Tests cover:
- RuntimeStreamProjection
- RuntimeStreamProjectionBuffer
- RuntimeProjectionBuilder
- RuntimeProjectionContract
- All enums and constants
- Deterministic serialization
- Replay safety
- Projection safety

file: tests/test_runtime_projection.py
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from rig.domain.runtime_projection import (
    # Constants
    PLACEHOLDER_WIDGET_ID,
    PLACEHOLDER_PROJECTION_ID,
    PLACEHOLDER_BUFFER_ID,
    PLACEHOLDER_STREAM_ID,
    PLACEHOLDER_INVOKE_ID,
    DEFAULT_MAX_PROJECTION_BYTES,
    DEFAULT_MAX_PROJECTION_CHUNKS,
    DEFAULT_PROJECTION_TOKEN_LIMIT,
    DEFAULT_PROJECTION_LENGTH_LIMIT,
    # Enums
    RuntimeProjectionKind,
    RuntimeProjectionStatus,
    RuntimeProjectionSeverity,
    RuntimeProjectionScope,
    # Models
    RuntimeStreamProjection,
    RuntimeStreamProjectionBuffer,
    RuntimeProjectionBuilder,
    RuntimeProjectionContract,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_projection_data() -> Dict[str, Any]:
    """Sample projection data for testing."""
    return {
        "projection_id": "proj_001",
        "widget_id": "widget_001",
        "kind": RuntimeProjectionKind.STREAM,
        "status": RuntimeProjectionStatus.ACTIVE,
        "stream_id": "stream_001",
        "invocation_id": "invoke_001",
        "sequence": 1,
        "data": {"key": "value"},
        "metadata": {"source": "runtime"},
        "created_at": "2024-01-01T00:00:00+00:00",
    }


@pytest.fixture
def sample_projection_buffer_data() -> Dict[str, Any]:
    """Sample projection buffer data for testing."""
    return {
        "buffer_id": "buf_001",
        "widget_id": "widget_001",
        "stream_id": "stream_001",
        "max_bytes": 1000000,
        "max_chunks": 100,
        "projections": {},
        "created_at": "2024-01-01T00:00:00+00:00",
    }


# =============================================================================
# Enum Tests
# =============================================================================

class TestRuntimeProjectionKind:
    """Tests for RuntimeProjectionKind enum."""

    def test_stream_kind(self):
        assert RuntimeProjectionKind.STREAM.value == "stream"

    def test_status_kind(self):
        assert RuntimeProjectionKind.STATUS.value == "status"

    def test_proposal_kind(self):
        assert RuntimeProjectionKind.PROPOSAL.value == "proposal"

    def test_console_kind(self):
        assert RuntimeProjectionKind.CONSOLE.value == "console"

    def test_diagnostic_kind(self):
        assert RuntimeProjectionKind.DIAGNOSTIC.value == "diagnostic"

    def test_summary_kind(self):
        assert RuntimeProjectionKind.SUMMARY.value == "summary"

    def test_chart_kind(self):
        assert RuntimeProjectionKind.CHART.value == "chart"

    def test_timeline_kind(self):
        assert RuntimeProjectionKind.TIMELINE.value == "timeline"


class TestRuntimeProjectionStatus:
    """Tests for RuntimeProjectionStatus enum."""

    def test_active_status(self):
        assert RuntimeProjectionStatus.ACTIVE.value == "active"

    def test_updated_status(self):
        assert RuntimeProjectionStatus.UPDATED.value == "updated"

    def test_stale_status(self):
        assert RuntimeProjectionStatus.STALE.value == "stale"

    def test_clear_status(self):
        assert RuntimeProjectionStatus.CLEAR.value == "clear"

    def test_error_status(self):
        assert RuntimeProjectionStatus.ERROR.value == "error"


class TestRuntimeProjectionSeverity:
    """Tests for RuntimeProjectionSeverity enum."""

    def test_debug_severity(self):
        assert RuntimeProjectionSeverity.DEBUG.value == "debug"

    def test_info_severity(self):
        assert RuntimeProjectionSeverity.INFO.value == "info"

    def test_warning_severity(self):
        assert RuntimeProjectionSeverity.WARNING.value == "warning"

    def test_error_severity(self):
        assert RuntimeProjectionSeverity.ERROR.value == "error"

    def test_critical_severity(self):
        assert RuntimeProjectionSeverity.CRITICAL.value == "critical"


class TestRuntimeProjectionScope:
    """Tests for RuntimeProjectionScope enum."""

    def test_event_scope(self):
        assert RuntimeProjectionScope.EVENT.value == "event"

    def test_chunk_scope(self):
        assert RuntimeProjectionScope.CHUNK.value == "chunk"

    def test_stream_scope(self):
        assert RuntimeProjectionScope.STREAM.value == "stream"

    def test_invocation_scope(self):
        assert RuntimeProjectionScope.INVOCATION.value == "invocation"

    def test_session_scope(self):
        assert RuntimeProjectionScope.SESSION.value == "session"


# =============================================================================
# Constants Tests
# =============================================================================

class TestPlaceholderConstants:
    """Tests for placeholder constants."""

    def test_placeholder_widget_id(self):
        assert PLACEHOLDER_WIDGET_ID == "WIDGET_ID_PLACEHOLDER"

    def test_placeholder_projection_id(self):
        assert PLACEHOLDER_PROJECTION_ID == "PROJECTION_ID_PLACEHOLDER"

    def test_placeholder_buffer_id(self):
        assert PLACEHOLDER_BUFFER_ID == "BUFFER_ID_PLACEHOLDER"

    def test_placeholder_stream_id(self):
        assert PLACEHOLDER_STREAM_ID == "STREAM_ID_PLACEHOLDER"

    def test_placeholder_invoke_id(self):
        assert PLACEHOLDER_INVOKE_ID == "INVOKE_ID_PLACEHOLDER"


class TestDefaultConstants:
    """Tests for default configuration constants."""

    def test_default_max_projection_bytes(self):
        assert DEFAULT_MAX_PROJECTION_BYTES == 100 * 1024  # 100KB

    def test_default_max_projection_chunks(self):
        assert DEFAULT_MAX_PROJECTION_CHUNKS == 100

    def test_default_projection_token_limit(self):
        assert DEFAULT_PROJECTION_TOKEN_LIMIT == 10000

    def test_default_projection_length_limit(self):
        assert DEFAULT_PROJECTION_LENGTH_LIMIT == 10000


# =============================================================================
# RuntimeStreamProjection Tests
# =============================================================================

class TestRuntimeStreamProjection:
    """Tests for RuntimeStreamProjection model."""

    def test_default_values(self):
        proj = RuntimeStreamProjection()
        assert proj.projection_id == PLACEHOLDER_PROJECTION_ID
        assert proj.widget_id == PLACEHOLDER_WIDGET_ID
        assert proj.kind == RuntimeProjectionKind.STREAM
        assert proj.status == RuntimeProjectionStatus.ACTIVE
        assert proj.stream_id == PLACEHOLDER_STREAM_ID
        assert proj.invocation_id == PLACEHOLDER_INVOKE_ID
        assert proj.sequence == 0
        assert proj.data == {}
        assert proj.metadata == {}
        assert proj.advisory_only is True
        assert proj.authoritative is False

    def test_create_from_dict(self, sample_projection_data):
        proj = RuntimeStreamProjection.from_dict(sample_projection_data)
        assert proj.projection_id == "proj_001"
        assert proj.widget_id == "widget_001"
        assert proj.kind == RuntimeProjectionKind.STREAM
        assert proj.status == RuntimeProjectionStatus.ACTIVE
        assert proj.stream_id == "stream_001"
        assert proj.advisory_only is True

    def test_to_dict(self, sample_projection_data):
        proj = RuntimeStreamProjection.from_dict(sample_projection_data)
        result = proj.to_dict()
        assert result["projection_id"] == "proj_001"
        assert result["widget_id"] == "widget_001"
        assert result["kind"] == "stream"
        assert result["status"] == "active"
        assert result["advisory_only"] is True
        assert result["authoritative"] is False

    def test_to_json(self, sample_projection_data):
        proj = RuntimeStreamProjection.from_dict(sample_projection_data)
        json_str = proj.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["projection_id"] == "proj_001"
        assert parsed["advisory_only"] is True

    def test_frozen(self):
        proj = RuntimeStreamProjection(
            projection_id="test",
            widget_id="widget_test",
            kind=RuntimeProjectionKind.STREAM,
        )
        with pytest.raises(AttributeError):
            proj.projection_id = "changed"  # type: ignore

    def test_slots(self):
        proj = RuntimeStreamProjection()
        with pytest.raises(AttributeError):
            proj.nonexistent_attr  # type: ignore

    def test_deterministic_id(self):
        proj1 = RuntimeStreamProjection.create(
            projection_id="test",
            widget_id="widget_001",
            kind=RuntimeProjectionKind.STREAM,
            stream_id="stream_001",
            invocation_id="invoke_001",
            sequence=1,
            created_at="2024-01-01T00:00:00+00:00",
        )
        proj2 = RuntimeStreamProjection.create(
            projection_id="test",
            widget_id="widget_001",
            kind=RuntimeProjectionKind.STREAM,
            stream_id="stream_001",
            invocation_id="invoke_001",
            sequence=1,
            created_at="2024-01-01T00:00:00+00:00",
        )
        assert proj1.id == proj2.id

    def test_metadata_preserved(self):
        proj = RuntimeStreamProjection.create(
            projection_id="test",
            widget_id="widget_001",
            metadata={"provider": "openai", "model": "gpt-4"},
        )
        assert proj.metadata["provider"] == "openai"
        assert proj.metadata["model"] == "gpt-4"

    def test_data_preserved(self):
        proj = RuntimeStreamProjection.create(
            projection_id="test",
            widget_id="widget_001",
            data={"chunks": ["a", "b", "c"], "cursor": "|"},
        )
        assert proj.data["chunks"] == ["a", "b", "c"]
        assert proj.data["cursor"] == "|"

    @property
    def scope(self) -> RuntimeProjectionScope:
        return RuntimeProjectionScope.STREAM


# =============================================================================
# RuntimeStreamProjectionBuffer Tests
# =============================================================================

class TestRuntimeStreamProjectionBuffer:
    """Tests for RuntimeStreamProjectionBuffer model."""

    def test_default_values(self):
        buffer = RuntimeStreamProjectionBuffer()
        assert buffer.buffer_id == PLACEHOLDER_BUFFER_ID
        assert buffer.widget_id == PLACEHOLDER_WIDGET_ID
        assert buffer.stream_id == PLACEHOLDER_STREAM_ID
        assert buffer.max_bytes == DEFAULT_MAX_PROJECTION_BYTES
        assert buffer.max_chunks == DEFAULT_MAX_PROJECTION_CHUNKS
        assert buffer.projections == {}
        assert buffer.advisory_only is True
        assert buffer.authoritative is False

    def test_empty_buffer(self, sample_projection_buffer_data):
        buffer = RuntimeStreamProjectionBuffer.from_dict(sample_projection_buffer_data)
        assert buffer.is_empty is True
        assert len(buffer.projections) == 0

    def test_with_projection(self, sample_projection_data):
        buffer = RuntimeStreamProjectionBuffer()
        proj = RuntimeStreamProjection.from_dict(sample_projection_data)
        new_buffer = buffer.with_projection(proj)
        assert new_buffer.is_empty is False
        assert proj.projection_id in new_buffer.projections

    def test_byte_limit(self):
        buffer = RuntimeStreamProjectionBuffer(max_bytes=100)
        for i in range(20):
            proj = RuntimeStreamProjection.create(
                projection_id=f"proj_{i}",
                widget_id="widget_001",
                data={"content": "x" * 10},
            )
            buffer = buffer.with_projection(proj)
        # Buffer should not exceed max_bytes
        assert buffer.total_bytes <= 100

    def test_chunk_limit(self):
        buffer = RuntimeStreamProjectionBuffer(max_chunks=5)
        for i in range(10):
            proj = RuntimeStreamProjection.create(
                projection_id=f"proj_{i}",
                widget_id="widget_001",
                data={"content": "x"},
            )
            buffer = buffer.with_projection(proj)
        # Buffer should not exceed max_chunks
        assert buffer.total_count <= 5

    def test_get_projection(self, sample_projection_data):
        buffer = RuntimeStreamProjectionBuffer()
        proj = RuntimeStreamProjection.from_dict(sample_projection_data)
        buffer = buffer.with_projection(proj)
        retrieved = buffer.get_projection("proj_001")
        assert retrieved is not None
        assert retrieved.projection_id == "proj_001"

    def test_get_all_projections(self, sample_projection_data):
        buffer = RuntimeStreamProjectionBuffer()
        for i in range(3):
            proj_data = dict(sample_projection_data)
            proj_data["projection_id"] = f"proj_{i}"
            proj = RuntimeStreamProjection.from_dict(proj_data)
            buffer = buffer.with_projection(proj)
        projections = buffer.get_all_projections()
        assert len(projections) == 3

    def test_frozen(self):
        buffer = RuntimeStreamProjectionBuffer()
        with pytest.raises(AttributeError):
            buffer.buffer_id = "changed"  # type: ignore


# =============================================================================
# RuntimeProjectionBuilder Tests
# =============================================================================

class TestRuntimeProjectionBuilder:
    """Tests for RuntimeProjectionBuilder model."""

    def test_default_values(self):
        builder = RuntimeProjectionBuilder()
        assert builder.builder_id == PLACEHOLDER_BUFFER_ID
        assert builder.widget_id == PLACEHOLDER_WIDGET_ID
        assert builder.stream_id == PLACEHOLDER_STREAM_ID
        assert builder.buffer == {}
        assert builder.advisory_only is True
        assert builder.authoritative is False

    def test_create_with_values(self):
        builder = RuntimeProjectionBuilder.create(
            builder_id="builder_001",
            widget_id="widget_001",
            stream_id="stream_001",
        )
        assert builder.builder_id == "builder_001"
        assert builder.widget_id == "widget_001"
        assert builder.stream_id == "stream_001"

    def test_to_dict(self):
        builder = RuntimeProjectionBuilder()
        result = builder.to_dict()
        assert result["builder_id"] == PLACEHOLDER_BUFFER_ID
        assert result["advisory_only"] is True

    def test_build_projection(self):
        builder = RuntimeProjectionBuilder.create(
            builder_id="builder_001",
            widget_id="widget_001",
            stream_id="stream_001",
        )
        
        # Add some data to the builder
        builder = builder.with_data("test_content", "assistant")
        
        # Add metadata
        builder = builder.with_metadata({"provider": "test"})
        
        # Build projection
        proj = builder.build_projection(
            projection_id="proj_001",
            sequence=1,
        )
        
        assert proj is not None
        assert proj.projection_id == "proj_001"
        assert proj.widget_id == "widget_001"
        assert proj.kind == RuntimeProjectionKind.STREAM
        assert proj.advisory_only is True

    def test_with_data(self):
        builder = RuntimeProjectionBuilder()
        new_builder = builder.with_data("content", "assistant")
        assert "assistant" in new_builder.buffer
        assert new_builder.buffer["assistant"] == ["content"]

    def test_with_metadata(self):
        builder = RuntimeProjectionBuilder()
        new_builder = builder.with_metadata({"key": "value"})
        assert new_builder.metadata["key"] == "value"

    def test_get_buffer_size(self):
        builder = RuntimeProjectionBuilder()
        builder = builder.with_data("x" * 100, "assistant")
        assert builder.get_buffer_size() >= 100


# =============================================================================
# RuntimeProjectionContract Tests
# =============================================================================

class TestRuntimeProjectionContract:
    """Tests for RuntimeProjectionContract model."""

    def test_default_values(self):
        contract = RuntimeProjectionContract()
        assert contract.contract_id == PLACEHOLDER_PROJECTION_ID
        assert contract.widget_id == PLACEHOLDER_WIDGET_ID
        assert contract.version == "1.0"
        assert contract.schema_version == "rig.projection.v1"
        assert contract.advisory_only is True
        assert contract.authoritative is False

    def test_create_with_values(self):
        contract = RuntimeProjectionContract.create(
            contract_id="contract_001",
            widget_id="widget_001",
            version="2.0",
            schema_version="rig.projection.v2",
        )
        assert contract.contract_id == "contract_001"
        assert contract.version == "2.0"
        assert contract.schema_version == "rig.projection.v2"

    def test_to_dict(self):
        contract = RuntimeProjectionContract()
        result = contract.to_dict()
        assert result["contract_id"] == PLACEHOLDER_PROJECTION_ID
        assert result["version"] == "1.0"
        assert result["advisory_only"] is True

    def test_rules(self):
        contract = RuntimeProjectionContract.create(
            contract_id="contract_001",
            rules={
                "max_bytes": 10000,
                "max_chunks": 100,
                "token_limit": 10000,
            },
        )
        assert contract.rules["max_bytes"] == 10000
        assert contract.rules["max_chunks"] == 100

    def test_validate(self):
        contract = RuntimeProjectionContract.create(
            contract_id="contract_001",
            rules={
                "max_bytes": 10000,
                "max_chunks": 100,
            },
        )
        
        # Create a projection that fits within rules
        proj = RuntimeStreamProjection.create(
            projection_id="proj_001",
            widget_id="widget_001",
            data={"content": "x" * 100},
        )
        
        result = contract.validate(proj)
        assert result["valid"] is True


# =============================================================================
# Integration Tests
# =============================================================================

class TestProjectionPipeline:
    """Tests for complete projection pipeline."""

    def test_pipeline_creation(self):
        """Test creating a projection through the full pipeline."""
        # Create contract
        contract = RuntimeProjectionContract.create(
            contract_id="contract_001",
            widget_id="widget_001",
            rules={
                "max_bytes": 1000000,
                "max_chunks": 1000,
            },
        )
        
        # Create builder
        builder = RuntimeProjectionBuilder.create(
            builder_id="builder_001",
            widget_id="widget_001",
            stream_id="stream_001",
        )
        
        # Add data
        builder = builder.with_data("Hello world", "assistant")
        builder = builder.with_data("How are you?", "assistant")
        builder = builder.with_metadata({"provider": "test", "model": "test"})
        
        # Build projection
        proj = builder.build_projection(
            projection_id="proj_001",
            sequence=1,
            stream_id="stream_001",
            invocation_id="invoke_001",
        )
        
        # Validate against contract
        result = contract.validate(proj)
        assert result["valid"] is True
        
        # Add to buffer
        buffer = RuntimeStreamProjectionBuffer.create(
            buffer_id="buf_001",
            widget_id="widget_001",
        )
        buffer = buffer.with_projection(proj)
        
        assert buffer.get_projection("proj_001") is not None

    def test_projection_lifecycle(self):
        """Test complete projection lifecycle."""
        builder = RuntimeProjectionBuilder.create(
            builder_id="builder_001",
            widget_id="widget_001",
            stream_id="stream_001",
            invocation_id="invoke_001",
        )
        
        # Add multiple data points
        for i in range(5):
            builder = builder.with_data(f"Message {i}", "assistant")
        
        # Build projection
        proj = builder.build_projection(
            projection_id="proj_001",
            sequence=1,
        )
        
        # Verify projection
        assert proj.projection_id == "proj_001"
        assert proj.widget_id == "widget_001"
        assert proj.stream_id == "stream_001"
        assert proj.invocation_id == "invoke_001"
        assert proj.sequence == 1
        assert proj.kind == RuntimeProjectionKind.STREAM
        assert proj.advisory_only is True
        
        # Verify data is preserved
        assert "assistant" in proj.data


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_data(self):
        builder = RuntimeProjectionBuilder()
        proj = builder.build_projection(
            projection_id="proj_001",
            widget_id="widget_001",
        )
        assert proj.data == {}
        assert proj.advisory_only is True

    def test_unicode_data(self):
        builder = RuntimeProjectionBuilder()
        builder = builder.with_data("Hello 世界 🌍", "assistant")
        proj = builder.build_projection(
            projection_id="proj_001",
            widget_id="widget_001",
        )
        assert "世界" in proj.data["assistant"][0]
        assert "🌍" in proj.data["assistant"][0]

    def test_very_large_data(self):
        builder = RuntimeProjectionBuilder()
        large_data = "x" * (DEFAULT_MAX_PROJECTION_BYTES + 100)
        builder = builder.with_data(large_data, "assistant")
        proj = builder.build_projection(
            projection_id="proj_001",
            widget_id="widget_001",
        )
        # Data should be truncated
        assert len(proj.to_json()) <= DEFAULT_MAX_PROJECTION_BYTES + 1000

    def test_zero_sequence(self):
        proj = RuntimeStreamProjection.create(
            projection_id="proj_001",
            sequence=0,
        )
        assert proj.sequence == 0

    def test_negative_sequence(self):
        proj = RuntimeStreamProjection.create(
            projection_id="proj_001",
            sequence=-1,
        )
        assert proj.sequence == -1

    def test_buffer_eviction(self):
        buffer = RuntimeStreamProjectionBuffer(max_bytes=100, max_chunks=5)
        for i in range(10):
            proj = RuntimeStreamProjection.create(
                projection_id=f"proj_{i}",
                widget_id="widget_001",
                data={"content": "x" * 20},  # 20 bytes per projection
            )
            buffer = buffer.with_projection(proj)
        # Buffer should have evicted old projections
        assert buffer.total_count <= 5
        assert buffer.total_bytes <= 100


# =============================================================================
# Doctrinal Compliance Tests
# =============================================================================

class TestDoctrineCompliance:
    """Tests for compliance with Phase 2 core doctrine."""

    def test_output_is_advisory_evidence_only(self):
        """Core doctrine: Runtime output is advisory evidence only."""
        proj = RuntimeStreamProjection()
        assert proj.advisory_only is True
        assert proj.authoritative is False

    def test_no_direct_workspace_mutation(self):
        """Core doctrine: No direct workspace mutation.
        
        This is validated by ensuring all models are frozen.
        """
        proj = RuntimeStreamProjection()
        with pytest.raises(AttributeError):
            proj.data = {}  # type: ignore

    def test_no_authoritative_release(self):
        """Core doctrine: Only receipts/proposals become authoritative.
        
        All projection models must remain advisory-only.
        """
        models = [
            RuntimeStreamProjection(),
            RuntimeStreamProjectionBuffer(),
            RuntimeProjectionBuilder(),
            RuntimeProjectionContract(),
        ]
        for model in models:
            assert model.authoritative is False

    def test_projection_only_UI(self):
        """Core doctrine: UI streams projections, NOT raw subprocesses.
        
        Projection models provide data for UI projections.
        """
        proj = RuntimeStreamProjection.create(
            projection_id="proj_001",
            widget_id="widget_001",
            data={"content": "test"},
        )
        assert hasattr(proj, 'widget_id')
        assert hasattr(proj, 'data')
        assert hasattr(proj, 'to_dict')

    def test_no_hidden_execution(self):
        """Core doctrine: No hidden execution.
        
        Projection models don't have any execution capabilities.
        """
        proj = RuntimeStreamProjection()
        # No methods for execution
        assert not hasattr(proj, 'execute')
        assert not hasattr(proj, 'run')
        assert not hasattr(proj, 'start')

    def test_no_background_daemons(self):
        """Core doctrine: No background daemons.
        
        Projection models are pure data, no threading/asyncio.
        """
        proj = RuntimeStreamProjection()
        # No async/threading methods
        assert not callable(getattr(proj, 'start', None))
        assert not callable(getattr(proj, 'join', None))

    def test_no_destructive_git_commands(self):
        """Core doctrine: No destructive Git commands.
        
        Projection models don't have Git-related functionality.
        """
        proj = RuntimeStreamProjection()
        assert not hasattr(proj, 'git')
        assert not hasattr(proj, 'reset')
        assert not hasattr(proj, 'push')

    def test_all_indices_are_advisory_only(self):
        """Core doctrine: All indices are advisory only."""
        buffer = RuntimeStreamProjectionBuffer()
        assert buffer.advisory_only is True
        
        builder = RuntimeProjectionBuilder()
        assert builder.advisory_only is True
        
        contract = RuntimeProjectionContract()
        assert contract.advisory_only is True
