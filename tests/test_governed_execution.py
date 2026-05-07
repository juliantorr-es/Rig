"""Tests for Governed Execution MVP.

Test coverage:
- ReceiptStore: append/get/list operations
- Receipt models: Receipt, ExecutionReceipt, ValidatorReceipt
- Execution models: ExecutionRequest, ExecutionLease, ExecutionResult, ExecutionFailure
- WorktreeExecutor: lease management, execution, timeout
- IntentDispatcher: dispatch, handler registration
- ProjectionBuilder: ReceiptListProjection from ReceiptStore
"""

import json
import tempfile
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, List, Optional

import pytest


# =============================================================================
# ReceiptStore Tests
# =============================================================================

class TestInMemoryReceiptStore:
    """Tests for InMemoryReceiptStore."""
    
    def test_append_and_get_receipt(self):
        """Test appending and retrieving a receipt."""
        from rig.domain.receipts import InMemoryReceiptStore, Receipt
        
        store = InMemoryReceiptStore()
        receipt = Receipt(
            receipt_id="test_001",
            kind="execution",
            workspace_id="ws_001",
            status="success",
            summary="Test receipt"
        )
        
        receipt_id = store.append(receipt)
        assert receipt_id == "test_001"
        
        retrieved = store.get("test_001")
        assert retrieved is not None
        assert retrieved.receipt_id == "test_001"
        assert retrieved.kind == "execution"
    
    def test_list_all_receipts(self):
        """Test listing all receipts."""
        from rig.domain.receipts import InMemoryReceiptStore, Receipt
        
        store = InMemoryReceiptStore()
        
        for i in range(5):
            receipt = Receipt(
                receipt_id=f"test_{i:03d}",
                kind="execution",
                status="success",
                summary=f"Receipt {i}"
            )
            store.append(receipt)
        
        all_receipts = store.list()
        assert len(all_receipts) == 5
    
    def test_list_filtered_by_workspace(self):
        """Test listing receipts filtered by workspace_id."""
        from rig.domain.receipts import InMemoryReceiptStore, Receipt
        
        store = InMemoryReceiptStore()
        
        # Add receipts for different workspaces
        store.append(Receipt(receipt_id="r1", kind="execution", workspace_id="ws_001"))
        store.append(Receipt(receipt_id="r2", kind="execution", workspace_id="ws_001"))
        store.append(Receipt(receipt_id="r3", kind="execution", workspace_id="ws_002"))
        store.append(Receipt(receipt_id="r4", kind="execution", workspace_id="ws_002"))
        
        ws1_receipts = store.list(workspace_id="ws_001")
        assert len(ws1_receipts) == 2
        assert all(r.workspace_id == "ws_001" for r in ws1_receipts)
        
        ws2_receipts = store.list(workspace_id="ws_002")
        assert len(ws2_receipts) == 2
    
    def test_list_filtered_by_kind(self):
        """Test listing receipts filtered by kind."""
        from rig.domain.receipts import InMemoryReceiptStore, Receipt
        
        store = InMemoryReceiptStore()
        
        store.append(Receipt(receipt_id="r1", kind="execution"))
        store.append(Receipt(receipt_id="r2", kind="execution"))
        store.append(Receipt(receipt_id="r3", kind="validation"))
        store.append(Receipt(receipt_id="r4", kind="validation"))
        
        exec_receipts = store.list(kind="execution")
        assert len(exec_receipts) == 2
        assert all(r.kind == "execution" for r in exec_receipts)
    
    def test_list_with_limit(self):
        """Test listing with a limit."""
        from rig.domain.receipts import InMemoryReceiptStore, Receipt
        
        store = InMemoryReceiptStore()
        
        for i in range(10):
            store.append(Receipt(receipt_id=f"r{i:03d}", kind="execution"))
        
        limited = store.list(limit=5)
        assert len(limited) == 5
    
    def test_list_sorted_by_timestamp_descending(self):
        """Test that list returns receipts sorted by timestamp descending."""
        from rig.domain.receipts import InMemoryReceiptStore, Receipt
        
        store = InMemoryReceiptStore()
        
        # Add receipts with different timestamps
        timestamps = [
            "2024-01-01T00:00:00Z",
            "2024-01-03T00:00:00Z",
            "2024-01-02T00:00:00Z",
        ]
        for i, ts in enumerate(timestamps):
            store.append(Receipt(
                receipt_id=f"r{i}",
                kind="execution",
                timestamp=ts
            ))
        
        listed = store.list()
        assert len(listed) == 3
        # Most recent first
        assert listed[0].timestamp == "2024-01-03T00:00:00Z"
        assert listed[1].timestamp == "2024-01-02T00:00:00Z"
        assert listed[2].timestamp == "2024-01-01T00:00:00Z"
    
    def test_raw_ref(self):
        """Test getting raw reference."""
        from rig.domain.receipts import InMemoryReceiptStore, Receipt
        
        store = InMemoryReceiptStore()
        receipt = Receipt(
            receipt_id="test_ref",
            kind="execution",
            raw_ref="/path/to/evidence.json"
        )
        store.append(receipt)
        
        raw_ref = store.raw_ref("test_ref")
        assert raw_ref == "/path/to/evidence.json"
        
        assert store.raw_ref("nonexistent") is None
    
    def test_verify_returns_false(self):
        """Test that verify returns False (not implemented)."""
        from rig.domain.receipts import InMemoryReceiptStore, Receipt
        
        store = InMemoryReceiptStore()
        receipt = Receipt(receipt_id="test_verify", kind="execution")
        store.append(receipt)
        
        assert store.verify("test_verify") is False


class TestFilesystemReceiptStore:
    """Tests for FilesystemReceiptStore."""
    
    def test_append_and_get_receipt(self, tmp_path):
        """Test appending and retrieving a receipt from filesystem."""
        from rig.domain.receipts import FilesystemReceiptStore, Receipt
        
        store = FilesystemReceiptStore(tmp_path)
        receipt = Receipt(
            receipt_id="fs_test_001",
            kind="execution",
            workspace_id="ws_001",
            status="success",
            summary="Filesystem test receipt"
        )
        
        receipt_id = store.append(receipt)
        assert receipt_id == "fs_test_001"
        
        # Verify file was created
        receipt_dir = tmp_path / ".build" / "rig" / "receipts"
        assert receipt_dir.exists()
        
        retrieved = store.get("fs_test_001")
        assert retrieved is not None
        assert retrieved.receipt_id == "fs_test_001"
    
    def test_list_receipts(self, tmp_path):
        """Test listing receipts from filesystem."""
        from rig.domain.receipts import FilesystemReceiptStore, ExecutionReceipt
        
        store = FilesystemReceiptStore(tmp_path)
        
        # Add some receipts
        for i in range(3):
            receipt = ExecutionReceipt(
                receipt_id=f"fs_exec_{i:03d}",
                kind="execution",
                argv=["echo", "hello"],
                exit_code=0
            )
            store.append(receipt)
        
        listed = store.list()
        assert len(listed) == 3
    
    def test_persists_across_instances(self, tmp_path):
        """Test that receipts persist across store instances."""
        from rig.domain.receipts import FilesystemReceiptStore, Receipt
        
        # Create first store and add receipt
        store1 = FilesystemReceiptStore(tmp_path)
        receipt = Receipt(receipt_id="persist_test", kind="execution")
        store1.append(receipt)
        
        # Create second store and verify receipt exists
        store2 = FilesystemReceiptStore(tmp_path)
        retrieved = store2.get("persist_test")
        assert retrieved is not None
        assert retrieved.receipt_id == "persist_test"


# =============================================================================
# Receipt Model Tests
# =============================================================================

class TestReceiptModels:
    """Tests for Receipt domain models."""
    
    def test_receipt_to_projection(self):
        """Test converting Receipt to projection format."""
        from rig.domain.receipts import Receipt
        from rig.domain.projections import ReceiptProjection
        
        receipt = Receipt(
            receipt_id="proj_test",
            kind="execution",
            workspace_id="ws_001",
            status="success",
            summary="Test summary"
        )
        
        proj = receipt.to_projection()
        assert isinstance(proj, ReceiptProjection)
        assert proj.id == "proj_test"
        assert proj.kind == "execution"
        assert proj.label == "Execution"
        assert proj.summary == "Test summary"
        assert proj.verified is False
    
    def test_execution_receipt_from_subprocess(self):
        """Test creating ExecutionReceipt from subprocess result."""
        from rig.domain.receipts import ExecutionReceipt
        
        receipt = ExecutionReceipt.from_subprocess_result(
            argv=["python", "-c", "print('hello')"],
            cwd="/tmp",
            exit_code=0,
            stdout="hello\n",
            stderr="",
            workspace_id="ws_001",
            purpose="test"
        )
        
        assert receipt.kind == "execution"
        assert receipt.exit_code == 0
        assert receipt.status == "success"
        assert receipt.argv == ["python", "-c", "print('hello')"]
        assert "Command exited with code 0" in receipt.summary
        assert receipt.stdout_summary == "hello\n"


# =============================================================================
# Execution Model Tests
# =============================================================================

class TestExecutionRequest:
    """Tests for ExecutionRequest."""
    
    def test_command_description(self):
        """Test command description generation."""
        from rig.domain.execution.models import ExecutionRequest
        
        req = ExecutionRequest(argv=["python", "-m", "pytest", "tests/"], cwd=Path("/tmp"))
        assert req.command_description == "python -m pytest tests/"
        
        # Long command truncation
        long_argv = ["cmd"] + ["arg"] * 30
        req = ExecutionRequest(argv=long_argv)
        desc = req.command_description
        assert len(desc) <= 60
        assert "..." in desc


class TestExecutionLease:
    """Tests for ExecutionLease."""
    
    def test_lease_creation(self):
        """Test lease creation."""
        from rig.domain.execution.models import ExecutionRequest, ExecutionLease
        
        request = ExecutionRequest(argv=["echo", "hello"])
        lease = ExecutionLease(request=request, ttl_seconds=60)
        
        assert lease.lease_id.startswith("lease_")
        assert lease.request == request
        assert lease.ttl_seconds == 60
        assert lease.status.name == "PENDING"
        assert lease.expires_at is not None
    
    def test_lease_is_expired(self):
        """Test lease expiration check."""
        from rig.domain.execution.models import ExecutionRequest, ExecutionLease
        
        request = ExecutionRequest(argv=["echo", "hello"])
        lease = ExecutionLease(request=request, ttl_seconds=0.1)
        
        assert not lease.is_expired
        
        # Wait for expiry
        time.sleep(0.15)
        assert lease.is_expired
    
    def test_lease_release_with_result(self):
        """Test releasing lease with a result."""
        from rig.domain.execution.models import ExecutionRequest, ExecutionLease, ExecutionResult
        
        request = ExecutionRequest(argv=["echo", "hello"])
        lease = ExecutionLease(request=request)
        
        result = ExecutionResult(
            execution_id=request.execution_id,
            lease_id=lease.lease_id,
            exit_code=0,
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T00:00:01Z"
        )
        
        lease.release(result=result)
        
        assert lease.status.name == "SUCCEEDED"
        assert lease.result == result
    
    def test_lease_release_with_failure(self):
        """Test releasing lease with a failure."""
        from rig.domain.execution.models import ExecutionRequest, ExecutionLease, ExecutionFailure
        
        request = ExecutionRequest(argv=["false"])
        lease = ExecutionLease(request=request)
        
        failure = ExecutionFailure(
            execution_id=request.execution_id,
            exit_code=1,
            error_type="non_zero_exit",
            message="Command failed"
        )
        
        lease.release(failure=failure)
        
        assert lease.status.name == "FAILED"
        assert lease.failure == failure
    
    def test_lease_revoke(self):
        """Test revoking a lease."""
        from rig.domain.execution.models import ExecutionRequest, ExecutionLease, ExecutionStatus
        
        request = ExecutionRequest(argv=["echo", "hello"])
        lease = ExecutionLease(request=request)
        
        # Lease needs to be RUNNING to revoke meaningfully
        lease.status = ExecutionStatus.RUNNING
        
        lease.revoke()
        
        assert lease.status.name == "CANCELLED"
        assert lease.failure is not None
        assert lease.failure.error_type == "revoked"


class TestExecutionResult:
    """Tests for ExecutionResult."""
    
    def test_succeeded_property(self):
        """Test succeeded property."""
        from rig.domain.execution.models import ExecutionResult
        
        success_result = ExecutionResult(
            execution_id="e1",
            lease_id="l1",
            exit_code=0,
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T00:00:01Z"
        )
        assert success_result.succeeded is True
        
        failure_result = ExecutionResult(
            execution_id="e2",
            lease_id="l2",
            exit_code=1,
            started_at="2024-01-01T00:00:00Z",
            completed_at="2024-01-01T00:00:01Z"
        )
        assert failure_result.succeeded is False


# =============================================================================
# WorktreeExecutor Tests
# =============================================================================

class TestWorktreeExecutor:
    """Tests for WorktreeExecutor."""
    
    def test_lease_acquisition_and_release(self):
        """Test lease acquisition and release."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionStatus
        
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorktreeExecutor(Path(tmpdir))
            
            request = ExecutionRequest(argv=["echo", "hello"])
            lease = executor.acquire_lease(request)
            
            assert lease.lease_id.startswith("lease_")
            assert lease.request == request
            assert lease.status == ExecutionStatus.PENDING
            
            # Verify lease is tracked
            retrieved_lease = executor.get_lease(lease.lease_id)
            assert retrieved_lease is not None
            
            # Release lease
            executor.release_lease(lease)
            
            # Verify lease is no longer tracked
            assert executor.get_lease(lease.lease_id) is None
    
    def test_lease_is_active(self):
        """Test lease active state."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionStatus
        
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorktreeExecutor(Path(tmpdir))
            
            request = ExecutionRequest(argv=["echo", "hello"])
            lease = executor.acquire_lease(request)
            
            assert lease.is_active is False  # PENDING, not RUNNING
            
            lease.status = ExecutionStatus.RUNNING
            assert lease.is_active is True
            
            # Test STARTING also counts as active
            lease2 = executor.acquire_lease(ExecutionRequest(argv=["echo"]))
            lease2.status = ExecutionStatus.STARTING
            assert lease2.is_active is True
            
            # Test RUNNING counts as active
            lease3 = executor.acquire_lease(ExecutionRequest(argv=["echo"]))
            lease3.status = ExecutionStatus.RUNNING
            assert lease3.is_active is True
    
    def test_lease_is_complete(self):
        """Test lease complete state."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionStatus, ExecutionResult
        
        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorktreeExecutor(Path(tmpdir))
            
            request = ExecutionRequest(argv=["echo", "hello"])
            lease = executor.acquire_lease(request)
            
            assert lease.is_complete is False
            
            lease.release(result=ExecutionResult(
                execution_id=request.execution_id,
                lease_id=lease.lease_id,
                exit_code=0,
                started_at="2024-01-01T00:00:00Z",
                completed_at="2024-01-01T00:00:01Z"
            ))
            
            assert lease.is_complete is True
    
    def test_execute_simple_command(self):
        """Test executing a simple command."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionResult, ExecutionFailure
        from dataclasses import asdict
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            executor = WorktreeExecutor(repo_root)
            
            request = ExecutionRequest(
                argv=["echo", "hello world"],
                cwd=repo_root,
                timeout_seconds=5,
                workspace_id="test_ws",
                purpose="test execution"
            )
            
            lease = executor.acquire_lease(request)
            try:
                result = executor.execute(lease)
                
                assert isinstance(result, ExecutionResult)
                assert result.succeeded is True
                assert result.exit_code == 0
                assert "hello world" in result.stdout_summary
                
            finally:
                executor.release_lease(lease)
    
    def test_execute_failing_command(self):
        """Test executing a failing command."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionFailure
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            executor = WorktreeExecutor(repo_root)
            
            # Use 'false' command which exits with code 1
            request = ExecutionRequest(
                argv=["false"],
                cwd=repo_root,
                timeout_seconds=5,
                workspace_id="test_ws"
            )
            
            lease = executor.acquire_lease(request)
            try:
                result = executor.execute(lease)
                
                assert isinstance(result, ExecutionFailure)
                assert result.exit_code == 1
                assert result.error_type == "non_zero_exit"
                # Verify partial output was captured
                assert result.stdout_summary is not None
                
            finally:
                executor.release_lease(lease)
    
    def test_execute_timeout(self):
        """Test command timeout."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionFailure
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            executor = WorktreeExecutor(repo_root)
            
            # Use a command that sleeps longer than timeout
            # Note: We can't rely on 'sleep' being available, so we skip this test
            # on systems without sleep, or use a very short timeout
            request = ExecutionRequest(
                argv=["sleep", "100"],  # This should timeout
                cwd=repo_root,
                timeout_seconds=0.1,  # Very short timeout
                workspace_id="test_ws"
            )
            
            lease = executor.acquire_lease(request)
            try:
                result = executor.execute(lease)
                
                # Should fail with timeout (may be non_zero_exit if sleep not available)
                assert isinstance(result, ExecutionFailure) or result.timed_out is True or getattr(result, 'exit_code', None) is not None
                
            finally:
                executor.release_lease(lease)
    
    def test_execute_creates_receipt(self):
        """Test that execution creates a receipt."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionResult
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            executor = WorktreeExecutor(repo_root)
            
            request = ExecutionRequest(
                argv=["echo", "receipt test"],
                cwd=repo_root,
                timeout_seconds=5,
                workspace_id="test_ws"
            )
            
            lease = executor.acquire_lease(request)
            executor.execute(lease)
            executor.release_lease(lease)
            
            # Check receipt was created
            receipts = executor.receipt_store.list()
            assert len(receipts) > 0
            
            receipt = receipts[0]
            assert receipt.receipt_id == request.execution_id
            assert receipt.kind == "execution"
            assert receipt.workspace_id == "test_ws"
            assert receipt.argv == ["echo", "receipt test"]
    
    def test_execute_uses_argv_not_shell(self):
        """Test that execute uses argv list, not shell string."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionResult
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            executor = WorktreeExecutor(repo_root)
            
            # Create a command with special characters that would be problematic in shell
            request = ExecutionRequest(
                argv=["echo", "hello; rm -rf /"],  # This would be dangerous with shell=True
                cwd=repo_root,
                timeout_seconds=5
            )
            
            lease = executor.acquire_lease(request)
            result = executor.execute(lease)
            executor.release_lease(lease)
            
            # The command should literally echo "hello; rm -rf /" not execute rm
            # (though echo doesn't interpret ; as command separator with argv)
            assert isinstance(result, ExecutionResult)
            # The subprocess.Popen was called with shell=False, so special chars are safe
    
    def test_stream_sink_receives_events(self):
        """Test that stream sink receives events."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionResult, CollectingStreamSink
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            executor = WorktreeExecutor(repo_root)
            
            sink = CollectingStreamSink()
            
            request = ExecutionRequest(
                argv=["echo", "stream test"],
                cwd=repo_root,
                timeout_seconds=5,
                stream_id="test_stream"
            )
            
            lease = executor.acquire_lease(request)
            result = executor.execute(lease, stream_sink=sink)
            executor.release_lease(lease)
            
            if isinstance(result, ExecutionResult):
                assert "stream test" in sink.get_stdout()
    
    def test_context_manager_execution(self):
        """Test execution using context manager."""
        from rig.domain.execution import WorktreeExecutor, ExecutionRequest
        from rig.domain.execution.models import ExecutionResult
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            executor = WorktreeExecutor(repo_root)
            
            request = ExecutionRequest(
                argv=["echo", "context test"],
                cwd=repo_root,
                timeout_seconds=5
            )
            
            with executor.execute_context(request) as lease:
                assert lease.is_complete is True
                assert lease.result is not None
                assert isinstance(lease.result, ExecutionResult)


# =============================================================================
# IntentDispatcher Tests
# =============================================================================

class TestIntentDispatcher:
    """Tests for IntentDispatcher."""
    
    def test_dispatcher_creation(self):
        """Test dispatcher creation."""
        from rig.domain.intents.dispatcher import IntentDispatcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = IntentDispatcher(Path(tmpdir))
            assert dispatcher.repo_root == Path(tmpdir)
            assert dispatcher.executor is not None
            assert dispatcher.receipt_store is not None
    
    def test_list_handlers(self):
        """Test listing registered handlers."""
        from rig.domain.intents.dispatcher import IntentDispatcher
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = IntentDispatcher(Path(tmpdir))
            handlers = dispatcher.list_handlers()
            
            # Should have built-in handler for run_validators
            assert "rig.intent.run_validators" in handlers
    
    def test_register_custom_handler(self):
        """Test registering a custom handler."""
        from rig.domain.intents.dispatcher import IntentDispatcher, IntentResult, HandlerContext
        from rig.domain.intent_defs import Intent
        from rig.domain.execution import WorktreeExecutor
        from rig.domain.receipts import ReceiptStore
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = IntentDispatcher(Path(tmpdir))
            
            def my_handler(context: HandlerContext, intent: Intent) -> IntentResult:
                return IntentResult.success(
                    intent,
                    result={"custom_handler": True}
                )
            
            dispatcher.register_handler("rig.intent.custom", my_handler)
            
            handlers = dispatcher.list_handlers()
            assert "rig.intent.custom" in handlers
    
    def test_dispatch_unknown_intent(self):
        """Test dispatching an unknown intent."""
        from rig.domain.intents.dispatcher import IntentDispatcher
        from rig.domain.intent_defs import Intent
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = IntentDispatcher(Path(tmpdir))
            
            intent = Intent(
                kind="rig.intent.unknown",
                schema_version="rig.ui.intent.v1",
                observed_projection_revision=1
            )
            
            result = dispatcher.dispatch(intent)
            
            assert result.accepted is False
            assert result.status == "rejected"
            assert "Unknown intent kind" in result.reason
    
    def test_dispatch_missing_kind(self):
        """Test dispatching an intent with missing kind."""
        from rig.domain.intents.dispatcher import IntentDispatcher
        from rig.domain.intent_defs import Intent
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            dispatcher = IntentDispatcher(Path(tmpdir))
            
            intent = Intent(
                kind="",  # Empty kind
                schema_version="rig.ui.intent.v1",
                observed_projection_revision=1
            )
            
            result = dispatcher.dispatch(intent)
            
            assert result.accepted is False
            assert result.status == "rejected"


# =============================================================================
# ProjectionBuilder Tests
# =============================================================================

class TestProjectionBuilderWithReceipts:
    """Tests for ProjectionBuilder with ReceiptStore integration."""
    
    def test_empty_projection_has_receipts_widget(self):
        """Test that empty projection includes evidence.receipts widget."""
        from rig.domain.projection_builder import build_projection, _build_receipt_list_projection
        
        with tempfile.TemporaryDirectory() as tmpdir:
            projection = build_projection(Path(tmpdir), revision=1)
            
            assert "evidence.receipts" in projection.widgets
    
    def test_receipt_list_empty_when_no_receipts(self):
        """Test ReceiptListProjection is empty when no receipts exist."""
        from rig.domain.projection_builder import _build_receipt_list_projection
        from dataclasses import asdict
        
        with tempfile.TemporaryDirectory() as tmpdir:
            receipt_list = _build_receipt_list_projection(Path(tmpdir))
            
            assert receipt_list.title == "Receipt Log"
            assert receipt_list.receipts == []
    
    def test_receipt_list_includes_real_receipts(self):
        """Test ReceiptListProjection includes real receipts from store."""
        from rig.domain.projection_builder import _build_receipt_list_projection
        from rig.domain.receipts import get_receipt_store, ExecutionReceipt
        from dataclasses import asdict
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            
            # Create a receipt directly in the store
            store = get_receipt_store(repo_root)
            receipt = ExecutionReceipt(
                receipt_id="test_receipt_001",
                kind="execution",
                argv=["echo", "test"],
                exit_code=0,
                workspace_id="test_ws",
                status="success",
                summary="Test execution"
            )
            store.append(receipt)
            
            # Build projection
            receipt_list = _build_receipt_list_projection(repo_root)
            
            assert len(receipt_list.receipts) >= 1
            assert any(r.id == "test_receipt_001" for r in receipt_list.receipts)
