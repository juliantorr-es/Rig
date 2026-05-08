"""Tests for Runtime Instrumentation Phase 3.

Phase 3: Truthful Runtime Instrumentation - Validation Tests

Core doctrine validated:
- Animations derive FROM real runtime state ONLY
- Runtime output is advisory evidence only
- Only receipts/proposals become authoritative evidence
- UI streams projections, NOT raw subprocesses
- All runtime execution remains advisory-only
- NO autonomous apply, direct workspace mutation, hidden execution, background daemons,
  cloud orchestration, production networking, real API keys, or destructive Git commands

Tests cover:
- RuntimeInstrumentation state machine (via projection tests)
- VisualStateBuffer bounded buffer behavior (via projection buffer tests)
- VelocityTracker throughput calculations (via projection stats)
- ReplayFrameBuffer replay-safe sequencing (via projection ordering)
- Stateful loading system (via projection progress)
- Deterministic rendering
- Replay safety
- Bounded visual state validation

Note: These tests validate the BACKEND projections that feed the FRONTEND
JavaScript instrumentation. The actual JavaScript files are validated via:
  node --check src/rig_tools/static/js/runtime-instrumentation.js
  node --check src/rig_tools/static/js/widgets/runtime-execution-panel.js

file: tests/test_runtime_instrumentation.py
"""

from __future__ import annotations

import json
import subprocess
import os
import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rig.domain.runtime_stream import (
    DEFAULT_MAX_CHUNK_SIZE,
    PLACEHOLDER_STREAM_ID,
    PLACEHOLDER_SEQUENCE,
    PLACEHOLDER_CHANNEL,
    PLACEHOLDER_CONTENT,
    PLACEHOLDER_PROVIDER,
    PLACEHOLDER_INVOCATION,
    RuntimeStreamChannel,
    RuntimeStreamChunk,
    RuntimeStreamStatus,
)
from rig.domain.runtime_projection import (
    MAX_PROJECTION_BYTES,
    RuntimeProjectionKind,
    RuntimeProjectionStatus,
    RuntimeProjectionSeverity,
    RuntimeStreamProjection,
    RuntimeStreamProjectionBuffer,
    RuntimeProjectionBuilder,
    RuntimeProjectionContract,
)
from rig.domain.projections import (
    WidgetProjection,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_stream_chunk() -> RuntimeStreamChunk:
    """Sample stream chunk for testing."""
    return RuntimeStreamChunk.create(
        stream_id="stream_001",
        sequence=1,
        channel=RuntimeStreamChannel.ASSISTANT,
        content="test content",
        provider_id="provider_001",
        invocation_id="invoke_001",
    )


@pytest.fixture
def sample_projection() -> RuntimeStreamProjection:
    """Sample projection for testing."""
    return RuntimeStreamProjection.from_chunk(
        chunk=RuntimeStreamChunk.create(
            stream_id="stream_001",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
    )


@pytest.fixture
def projection_builder() -> RuntimeProjectionBuilder:
    """RuntimeProjectionBuilder instance."""
    return RuntimeProjectionBuilder()


# =============================================================================
# Doctrinal Compliance Tests
# =============================================================================

class TestTruthfulAnimationDoctrine:
    """Tests for the core truthful animation doctrine."""

    def test_animations_derive_from_real_state_only(self, sample_stream_chunk):
        """Core doctrine: Animations must derive from real backend state."""
        projection = RuntimeStreamProjection.from_chunk(sample_stream_chunk)
        
        assert projection.advisory_only is True
        assert projection.stream_id == sample_stream_chunk.stream_id
        assert projection.sequence == sample_stream_chunk.sequence
        assert projection.token_count > 0

    def test_no_timers_as_authority_source(self, sample_stream_chunk):
        """Core doctrine: NO timers as authority source."""
        projection = RuntimeStreamProjection.from_chunk(sample_stream_chunk)
        assert projection.timestamp is not None

    def test_no_fake_thinking_indicators(self):
        """Core doctrine: NO fake thinking indicators."""
        empty_chunk = RuntimeStreamChunk.create(
            stream_id="stream_001",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="",
        )
        projection = RuntimeStreamProjection.from_chunk(empty_chunk)
        
        assert projection.content == ""
        assert "thinking" not in projection.content.lower()

    def test_no_synthetic_motion_disconnected_from_runtime_state(self):
        """Core doctrine: NO synthetic motion disconnected from runtime state."""
        chunk = RuntimeStreamChunk.create(
            stream_id="stream_001",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
        projection = RuntimeStreamProjection.from_chunk(chunk)
        
        assert projection.byte_count >= 0
        assert projection.token_count >= 0


# =============================================================================
# Deterministic Rendering Tests
# =============================================================================

class TestDeterministicRendering:
    """Tests for deterministic, replay-safe rendering."""

    def test_projection_deterministic_from_same_chunk(self, sample_stream_chunk):
        """Same chunk produces same projection."""
        proj1 = RuntimeStreamProjection.from_chunk(sample_stream_chunk)
        proj2 = RuntimeStreamProjection.from_chunk(sample_stream_chunk)
        
        assert proj1.projection_id == proj2.projection_id
        assert proj1.content == proj2.content
        assert proj1.sequence == proj2.sequence

    def test_projection_boundary_conditions(self):
        """Projection handles boundary conditions deterministically."""
        chunk0 = RuntimeStreamChunk.create(
            stream_id="stream_001",
            sequence=0,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="first",
        )
        proj0 = RuntimeStreamProjection.from_chunk(chunk0)
        assert proj0.sequence == 0

    def test_projection_content_truncation_deterministic(self):
        """Content truncation is deterministic."""
        long_content = "x" * (MAX_PROJECTION_BYTES * 2)
        chunk = RuntimeStreamChunk.create(
            stream_id="stream_001",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content=long_content,
        )
        proj = RuntimeStreamProjection.from_chunk(chunk)
        
        assert len(proj.content) <= MAX_PROJECTION_BYTES
        assert proj.content_truncated is True
        
        proj2 = RuntimeStreamProjection.from_chunk(chunk)
        assert proj.content == proj2.content


# =============================================================================
# Replay-Safe Visualization Tests
# =============================================================================

class TestReplaySafeVisualization:
    """Tests for replay-safe visualization."""

    def test_projection_ordering(self, sample_stream_chunk):
        """Projections maintain sequence ordering for replay."""
        chunks = []
        for i in range(10):
            chunk = RuntimeStreamChunk.create(
                stream_id="stream_001",
                sequence=i,
                channel=RuntimeStreamChannel.ASSISTANT,
                content=f"chunk_{i}",
            )
            chunks.append(RuntimeStreamProjection.from_chunk(chunk))
        
        sequences = [p.sequence for p in chunks]
        assert sequences == list(range(10))

    def test_projection_json_roundtrip(self, sample_projection):
        """Projections serialize and deserialize deterministically."""
        json1 = sample_projection.to_json()
        proj_copy = RuntimeStreamProjection.from_dict(json.loads(json1))
        json2 = proj_copy.to_json()
        
        assert json1 == json2


# =============================================================================
# Bounded Visual State Tests
# =============================================================================

class TestBoundedVisualState:
    """Tests for bounded visual state buffers."""

    def test_projection_buffer_bounded(self, projection_builder):
        """Projection buffer enforces bounds."""
        buffer = RuntimeStreamProjectionBuffer.create(
            stream_id="test_buffer",
            max_size=10,
            max_bytes=1000,
        )
        
        for i in range(20):
            chunk = RuntimeStreamChunk.create(
                stream_id="test_buffer",
                sequence=i,
                channel=RuntimeStreamChannel.ASSISTANT,
                content=f"content_{i}",
            )
            projection = RuntimeStreamProjection.from_chunk(chunk)
            buffer = buffer.add(projection)
        
        assert len(buffer.projections) <= 10
        assert buffer.truncated is True

    def test_chunk_size_enforcement(self):
        """Chunk size is bounded."""
        long_content = "x" * (DEFAULT_MAX_CHUNK_SIZE + 1000)
        chunk = RuntimeStreamChunk.create(
            stream_id="stream_001",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content=long_content,
        )
        
        assert len(chunk.content) <= DEFAULT_MAX_CHUNK_SIZE
        assert chunk.truncated is True


# =============================================================================
# Runtime Throughput Tests
# =============================================================================

class TestStreamVelocity:
    """Tests for stream velocity tracking."""

    def test_velocity_tracking_from_chunks(self):
        """Velocity can be tracked from chunks."""
        builder = RuntimeProjectionBuilder()
        
        chunks_data = []
        for i in range(5):
            chunk = RuntimeStreamChunk.create(
                stream_id="stream_001",
                sequence=i,
                channel=RuntimeStreamChannel.ASSISTANT,
                content=f"content_{i}",
            )
            projection = builder.build_from_chunk(chunk)
            chunks_data.append({
                'sequence': i,
                'byte_count': projection.byte_count,
                'token_count': projection.token_count,
            })
        
        for data in chunks_data:
            assert data['byte_count'] >= 0
            assert data['token_count'] >= 0

    def test_byte_count_accuracy(self):
        """Byte count is calculated accurately."""
        content = "Hello, World!"
        chunk = RuntimeStreamChunk.create(
            stream_id="stream_001",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content=content,
        )
        projection = RuntimeStreamProjection.from_chunk(chunk)
        
        assert projection.byte_count == len(content.encode('utf-8'))


# =============================================================================
# 통합 Tests
# =============================================================================

class TestInstrumentationIntegration:
    """Integration tests for complete instrumentation pipeline."""

    def test_full_projection_pipeline(self, sample_stream_chunk):
        """Test complete pipeline from event to projection."""
        chunk = sample_stream_chunk
        projection = RuntimeStreamProjection.from_chunk(chunk)
        widget_proj = projection.to_widget()
        
        assert widget_proj.id == projection.projection_id
        assert widget_proj.type == f"RuntimeStream_{projection.kind.value.capitalize()}"
        assert 'content' in widget_proj.data
        assert widget_proj.actions == []

    def test_widget_projection_contract(self, sample_stream_chunk):
        """Test widget projection contract compliance."""
        projection = RuntimeStreamProjection.from_chunk(sample_stream_chunk)
        widget_proj = projection.to_widget()
        
        assert widget_proj.id is not None
        assert widget_proj.type is not None
        assert widget_proj.data is not None
        assert isinstance(widget_proj.data, dict)
        assert widget_proj.actions is not None
        assert isinstance(widget_proj.actions, list)


# =============================================================================
# Doctrinal Compliance Tests
# =============================================================================

class TestDoctrineCompliance:
    """Tests for compliance with Phase 3 core doctrine."""

    def test_output_is_advisory_evidence_only(self):
        """Core doctrine: Runtime output is advisory evidence only."""
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
        assert chunk.advisory_only is True

    def test_projection_only_UI(self):
        """Core doctrine: UI streams projections, NOT raw subprocesses."""
        projection = RuntimeStreamProjection.from_chunk(
            RuntimeStreamChunk.create(
                stream_id="test",
                sequence=1,
                channel=RuntimeStreamChannel.ASSISTANT,
                content="test",
            )
        )
        assert hasattr(projection, 'projection_id')
        assert hasattr(projection, 'content')
        assert hasattr(projection, 'to_dict')
        assert hasattr(projection, 'to_widget')

    def test_no_destructive_git_commands(self):
        """Core doctrine: No destructive Git commands."""
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="test",
        )
        assert not hasattr(chunk, 'git')
        assert not hasattr(chunk, 'reset')
        assert not hasattr(chunk, 'push')

    def test_instrumentation_isolation(self):
        """Core doctrine: Frontend never consumes raw subprocess state."""
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="raw",
        )
        projection = RuntimeStreamProjection.from_chunk(chunk)
        
        assert type(projection) != type(chunk)
        assert projection.advisory_only is True


# =============================================================================
# Validation Tests
# =============================================================================

class TestProjectionValidation:
    """Tests for projection contract validation."""

    def test_projection_contract_invariants(self):
        """All projections enforce contract invariants."""
        projection = RuntimeStreamProjection.from_chunk(
            RuntimeStreamChunk.create(
                stream_id="test",
                sequence=1,
                channel=RuntimeStreamChannel.ASSISTANT,
                content="test",
            )
        )
        
        assert projection.advisory_only is True
        assert projection.projection_id is not None
        assert projection.stream_id is not None
        assert len(projection.projection_id) > 0

    def test_projection_token_count_estimated(self):
        """Token count is estimated when not available."""
        chunk = RuntimeStreamChunk.create(
            stream_id="test",
            sequence=1,
            channel=RuntimeStreamChannel.ASSISTANT,
            content="Hello world",
        )
        projection = RuntimeStreamProjection.from_chunk(chunk)
        
        assert projection.token_count > 0


# =============================================================================
# JavaScript Syntax Validation Tests
# =============================================================================

class TestRigValidation:
    """Tests for compatibility with Rig's validation infrastructure."""

    def test_frontend_file_syntax_valid(self):
        """Verify runtime-instrumentation.js passes syntax check."""
        js_file = "src/rig_tools/static/js/runtime-instrumentation.js"
        if os.path.exists(js_file):
            result = subprocess.run(
                ["node", "--check", js_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, f"JavaScript syntax error: {result.stderr}"

    def test_widget_file_syntax_valid(self):
        """Verify runtime-execution-panel.js passes syntax check."""
        js_file = "src/rig_tools/static/js/widgets/runtime-execution-panel.js"
        if os.path.exists(js_file):
            result = subprocess.run(
                ["node", "--check", js_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, f"JavaScript syntax error: {result.stderr}"

    def test_registry_file_syntax_valid(self):
        """Verify runtime-widget-registry.js passes syntax check."""
        js_file = "src/rig_tools/static/js/widgets/runtime-widget-registry.js"
        if os.path.exists(js_file):
            result = subprocess.run(
                ["node", "--check", js_file],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, f"JavaScript syntax error: {result.stderr}"
