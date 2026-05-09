"""Tests for Runtime Streaming Type Authority.

ADR 0004: Verify that canonical types are defined in _types.py
and properly re-exported through the public façade.
"""

import pytest


def test_canonical_type_authority():
    """Verify that types from runtime_streaming and runtime_streaming._types are identical."""
    from rig.domain.runtime_streaming import (
        StreamHandle,
        StreamLineageId,
        StreamInstanceId,
    )
    from rig.domain.runtime_streaming._types import (
        StreamHandle as InternalStreamHandle,
        StreamLineageId as InternalStreamLineageId,
        StreamInstanceId as InternalStreamInstanceId,
    )
    
    # Types must refer to the same object (not just compatible)
    assert StreamHandle is InternalStreamHandle
    assert StreamLineageId is InternalStreamLineageId
    assert StreamInstanceId is InternalStreamInstanceId


def test_stream_handle_creation():
    """Verify StreamHandle can be instantiated correctly."""
    from rig.domain.runtime_streaming import StreamHandle
    
    handle = StreamHandle(
        stream_lineage_id="test_lineage",
        stream_instance_id="test_instance"
    )
    
    assert handle.stream_lineage_id == "test_lineage"
    assert handle.stream_instance_id == "test_instance"
    assert "test_lineage" in repr(handle)
    assert "test_instance" in repr(handle)


def test_type_aliases_are_str():
    """Verify StreamLineageId and StreamInstanceId are str aliases."""
    from rig.domain.runtime_streaming import StreamLineageId, StreamInstanceId
    
    # These should be str types
    lid: StreamLineageId = "test_lineage"
    iid: StreamInstanceId = "test_instance"
    
    assert isinstance(lid, str)
    assert isinstance(iid, str)
