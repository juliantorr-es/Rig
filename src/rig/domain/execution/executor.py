"""WorktreeExecutor - Governed execution with leases and receipts.

The WorktreeExecutor provides governed process execution:
- Acquires ExecutionLease before execution
- Enforces timeout
- Captures stdout/stderr
- Streams output to optional StreamSink
- Creates ExecutionReceipt through ReceiptStore
- Releases lease and performs cleanup in finally block
- Does NOT use shell=True by default (avoids shell injection)
- Runs in worktree/cwd context

This is the domain-level execution authority. Lower-level process helpers
in rig_tools.core.process should be used directly only for simple cases.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import threading
import time
from contextlib import contextmanager, asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from rig.domain.execution.models import (
    ExecutionRequest,
    ExecutionLease,
    ExecutionResult,
    ExecutionFailure,
    ExecutionStreamEvent,
    ExecutionStatus,
    StreamSink,
    CollectingStreamSink,
)
from rig.domain.receipts import ReceiptStore, ExecutionReceipt, get_receipt_store

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ExecutorConfig:
    """Configuration for WorktreeExecutor."""
    
    # Default timeout if not specified in request
    default_timeout_seconds: float = 30.0
    
    # Maximum allowed timeout
    max_timeout_seconds: float = 300.0  # 5 minutes
    
    # Lease TTL (slightly longer than timeout to allow cleanup)
    lease_ttl_seconds: float = 310.0
    
    # Maximum stdout/stderr capture size
    maxOutputBytes: int = 1_000_000  # 1MB per channel
    
    # Stream chunk size for incremental streaming
    stream_chunk_size: int = 4096


DEFAULT_CONFIG = ExecutorConfig()


# =============================================================================
# WorktreeExecutor
# =============================================================================

class WorktreeExecutor:
    """Governed executor for worktree-scoped process execution.
    
    Provides:
    - Lease acquisition/release lifecycle
    - Timeout enforcement
    - stdout/stderr capture
    - Optional streaming to StreamSink
    - ExecutionReceipt creation via ReceiptStore
    - Worktree/cwd context
    - No shell=True by default (security)
    
    Usage:
        executor = WorktreeExecutor(repo_root)
        
        request = ExecutionRequest(
            argv=["python", "-m", "pytest"],
            cwd=Path("/path/to/project"),
            timeout_seconds=60,
            workspace_id="ws_123",
            purpose="run tests"
        )
        
        lease = executor.acquire_lease(request)
        try:
            result = executor.execute(lease, stream_sink=my_sink)
            # result is ExecutionResult on success
        except ExecutionFailure as e:
            # Handle failure
        finally:
            executor.release_lease(lease)  # Or use context manager
        
    Or with context manager:
        with executor.execute_context(request, stream_sink=my_sink) as lease:
            result = lease.result  # Available after execution
    """
    
    def __init__(
        self,
        repo_root: Path,
        receipt_store: Optional[ReceiptStore] = None,
        config: Optional[ExecutorConfig] = None
    ):
        self.repo_root = repo_root
        self._receipt_store = receipt_store or get_receipt_store(repo_root)
        self._config = config or DEFAULT_CONFIG
        self._active_leases: Dict[str, ExecutionLease] = {}
        self._lease_lock = threading.Lock()
    
    @property
    def receipt_store(self) -> ReceiptStore:
        return self._receipt_store
    
    # -------------------------------------------------------------------------
    # Lease Management
    # -------------------------------------------------------------------------
    
    def acquire_lease(self, request: ExecutionRequest) -> ExecutionLease:
        """Acquire an execution lease for a request.
        
        The lease:
        - Tracks the request
        - Has a TTL based on config.lease_ttl_seconds (or request timeout + buffer)
        - Is registered for cleanup tracking
        - Must be released after execution
        
        Args:
            request: The execution request to lease
            
        Returns:
            ExecutionLease ready for execution
        """
        from rig.domain.receipts import get_receipt_store
        
        timeout = request.timeout_seconds or self._config.default_timeout_seconds
        # Lease TTL is execution timeout + buffer for cleanup
        lease_ttl = min(timeout + 10, self._config.lease_ttl_seconds) if timeout else self._config.lease_ttl_seconds
        
        lease = ExecutionLease(
            request=request,
            ttl_seconds=lease_ttl
        )
        
        with self._lease_lock:
            self._active_leases[lease.lease_id] = lease
        
        logger.debug(f"Lease acquired: {lease.lease_id} for {request.command_description}")
        return lease
    
    def release_lease(self, lease: ExecutionLease) -> None:
        """Release a lease after execution.
        
        This should be called in a finally block to ensure cleanup.
        If the lease already has a result/failure, it's already been marked.
        
        Args:
            lease: The lease to release
        """
        with self._lease_lock:
            lease_id = lease.lease_id
            if lease_id in self._active_leases:
                del self._active_leases[lease_id]
        
        # If lease completed but wasn't properly released, mark it now
        if lease.is_complete:
            logger.debug(f"Lease already complete: {lease.lease_id}, status={lease.status}")
        else:
            # Mark as cancelled if still pending
            lease.revoke()
            logger.debug(f"Lease revoked/cancelled: {lease.lease_id}")
    
    def get_lease(self, lease_id: str) -> Optional[ExecutionLease]:
        """Get an active lease by ID."""
        with self._lease_lock:
            return self._active_leases.get(lease_id)
    
    def revoke_lease(self, lease_id: str) -> bool:
        """Revoke a lease by ID.
        
        Returns True if lease was found and revoked, False otherwise.
        """
        lease = self.get_lease(lease_id)
        if lease:
            lease.revoke()
            self.release_lease(lease)
            logger.info(f"Lease revoked: {lease_id}")
            return True
        return False
    
    def cleanup_expired_leases(self) -> int:
        """Clean up expired leases.
        
        Returns number of leases cleaned up.
        """
        expired = []
        with self._lease_lock:
            for lease_id, lease in self._active_leases.items():
                if lease.is_expired:
                    expired.append(lease_id)
            
            for lease_id in expired:
                lease = self._active_leases.pop(lease_id)
                lease.expire()
                logger.warning(f"Lease expired and cleaned up: {lease_id}")
        
        return len(expired)
    
    # -------------------------------------------------------------------------
    # Execution - Synchronous
    # -------------------------------------------------------------------------
    
    def execute(
        self,
        lease: ExecutionLease,
        stream_sink: Optional[StreamSink] = None
    ) -> Union[ExecutionResult, ExecutionFailure]:
        """Execute a command under a lease.
        
        This is the main execution method. It:
        - Validates the lease
        - Creates the receipt
        - Runs the subprocess
        - Captures output
        - Streams to sink if provided
        - Handles timeout
        - Creates and stores receipt
        - Returns result or raises failure
        
        Args:
            lease: The execution lease
            stream_sink: Optional sink for real-time output
            
        Returns:
            ExecutionResult on success
            
        Raises:
            ExecutionFailure: On failure or timeout (wrapped in result structure)
        """
        request = lease.request
        
        # Validate lease
        if lease.is_expired:
            lease.expire()
            return ExecutionFailure(
                execution_id=request.execution_id,
                error_type="lease_expired",
                message=f"Lease {lease.lease_id} expired before execution",
            )
        
        # Mark as starting
        lease.status = ExecutionStatus.STARTING
        
        # Prepare environment
        env = os.environ.copy()
        env.update(request.env_overlay)
        
        # Prepare command
        argv = request.argv
        if not argv:
            lease.release(failure=ExecutionFailure(
                execution_id=request.execution_id,
                error_type="invalid_request",
                message="No command specified in request"
            ))
            return lease.failure
        
        cwd = request.cwd or self.repo_root
        timeout = request.timeout_seconds or self._config.default_timeout_seconds
        
        # Clamp timeout to max
        timeout = min(timeout, self._config.max_timeout_seconds) if timeout else self._config.max_timeout_seconds
        
        started_at = datetime.now(timezone.utc).isoformat()
        lease.process_id = None
        timed_out = False
        
        # Prepare output capture
        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []
        stdout_bytes = 0
        stderr_bytes = 0
        max_bytes = self._config.maxOutputBytes
        
        # Track for streaming
        stream_sequence = 0
        
        try:
            lease.status = ExecutionStatus.RUNNING
            lease.acquired_at = started_at
            
            # Use Popen for incremental reading
            with subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,  # NEVER use shell=True by default
                text=True,
            ) as process:
                lease.process_id = process.pid
                logger.info(f"Executing: {request.command_description} (pid={process.pid}, lease={lease.lease_id})")
                
                # Function to read from a pipe incrementally
                def read_pipe(pipe, channel: str, chunks: List[str], Bytes_count: int) -> int:
                    """Read from a process pipe incrementally, streaming to sink."""
                    nonlocal stream_sequence
                    try:
                        for line in pipe:
                            if line:
                                # Track bytes
                                line_bytes = len(line.encode('utf-8'))
                                if Bytes_count + line_bytes <= max_bytes:
                                    chunks.append(line)
                                    Bytes_count += line_bytes
                                    
                                    # Stream to sink if provided
                                    if stream_sink and request.stream_id:
                                        stream_sequence += 1
                                        event = ExecutionStreamEvent(
                                            execution_id=request.execution_id,
                                            stream_id=request.stream_id or request.execution_id,
                                            channel=channel,
                                            sequence=stream_sequence,
                                            content=line,
                                        )
                                        try:
                                            stream_sink.on_stream_event(event)
                                        except Exception as sink_err:
                                            logger.warning(f"Stream sink error: {sink_err}")
                                else:
                                    # Truncate message
                                    truncated = "... [output truncated] ..."
                                    if truncated not in chunks:
                                        chunks.append(truncated)
                                    break
                    except Exception:
                        pass
                    return Bytes_count
                
                # Read stdout and stderr concurrently using threads
                stdout_thread = threading.Thread(
                    target=read_pipe,
                    args=(process.stdout, "stdout", stdout_chunks, stdout_bytes)
                )
                stderr_thread = threading.Thread(
                    target=read_pipe,
                    args=(process.stderr, "stderr", stderr_chunks, stderr_bytes)
                )
                
                stdout_thread.start()
                stderr_thread.start()
                
                # Wait for process with timeout
                try:
                    return_code = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    process.kill()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    return_code = None
                
                # Wait for readers to finish
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)
                
                completed_at = datetime.now(timezone.utc).isoformat()
                
                # Build results
                stdout = "".join(stdout_chunks)
                stderr = "".join(stderr_chunks)
                
                if timed_out:
                    failure = ExecutionFailure(
                        execution_id=request.execution_id,
                        exit_code=None,
                        error_type="timeout",
                        message=f"Execution timed out after {timeout}s",
                        timed_out=True,
                        stdout_summary=stdout[:500],
                        stderr_summary=stderr[:500],
                    )
                    lease.release(failure=failure)
                    
                    # Create receipt for timeout
                    self._create_receipt(lease, failure)
                    
                    return failure
                
                # Success or failure based on exit code
                if return_code == 0:
                    result = ExecutionResult(
                        execution_id=request.execution_id,
                        lease_id=lease.lease_id,
                        exit_code=return_code,
                        started_at=started_at,
                        completed_at=completed_at,
                        stdout_summary=stdout[:500],
                        stderr_summary=stderr[:500],
                        timed_out=False,
                    )
                    lease.release(result=result)
                    
                    # Create receipt
                    self._create_receipt(lease, result)
                    
                    return result
                else:
                    failure = ExecutionFailure(
                        execution_id=request.execution_id,
                        exit_code=return_code,
                        error_type="non_zero_exit",
                        message=f"Command exited with code {return_code}",
                        timed_out=False,
                        stdout_summary=stdout[:500],
                        stderr_summary=stderr[:500],
                    )
                    lease.release(failure=failure)
                    
                    # Create receipt
                    self._create_receipt(lease, failure)
                    
                    return failure
                    
        except Exception as e:
            # Handle unexpected errors
            failure = ExecutionFailure(
                execution_id=request.execution_id,
                exit_code=None,
                error_type="execution_error",
                message=str(e),
                timed_out=False,
            )
            lease.release(failure=failure)
            self._create_receipt(lease, failure)
            return failure
        
        finally:
            # Always ensure lease is released
            if lease.status == ExecutionStatus.RUNNING:
                lease.release()
    
    def _create_receipt(
        self,
        lease: ExecutionLease,
        result_or_failure: Union[ExecutionResult, ExecutionFailure]
    ) -> Optional[str]:
        """Create and store an ExecutionReceipt from a completed execution."""
        request = lease.request
        
        try:
            if isinstance(result_or_failure, ExecutionResult):
                receipt = ExecutionReceipt(
                    receipt_id=request.execution_id,
                    kind="execution",
                    workspace_id=request.workspace_id,
                    actor_id=request.actor_id or request.client_id,
                    status="success",
                    summary=f"Command '{request.command_description}' completed successfully",
                    argv=request.argv,
                    cwd=str(request.cwd) if request.cwd else None,
                    exit_code=result_or_failure.exit_code,
                    started_at=result_or_failure.started_at,
                    completed_at=result_or_failure.completed_at,
                    stdout_summary=result_or_failure.stdout_summary,
                    stderr_summary=result_or_failure.stderr_summary,
                    purpose=request.purpose,
                    stream_id=request.stream_id,
                )
            else:
                # It's a failure
                receipt = ExecutionReceipt(
                    receipt_id=request.execution_id,
                    kind="execution",
                    workspace_id=request.workspace_id,
                    actor_id=request.actor_id or request.client_id,
                    status="failed",
                    summary=result_or_failure.message or "Execution failed",
                    argv=request.argv,
                    cwd=str(request.cwd) if request.cwd else None,
                    exit_code=result_or_failure.exit_code,
                    started_at=result_or_failure.started_at or result_or_failure.timestamp,
                    completed_at=result_or_failure.completed_at if hasattr(result_or_failure, 'completed_at') else result_or_failure.timestamp,
                    stdout_summary=result_or_failure.stdout_summary,
                    stderr_summary=result_or_failure.stderr_summary,
                    purpose=request.purpose,
                    stream_id=request.stream_id,
                )
            
            receipt_id = self._receipt_store.append(receipt)
            logger.debug(f"Receipt created: {receipt_id}")
            return receipt_id
            
        except Exception as e:
            logger.error(f"Failed to create receipt: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # Context Managers
    # -------------------------------------------------------------------------
    
    @contextmanager
    def execute_context(
        self,
        request: ExecutionRequest,
        stream_sink: Optional[StreamSink] = None
    ):
        """Context manager for execution with automatic lease management.
        
        Usage:
            with executor.execute_context(request, stream_sink=sink) as lease:
                # Execution is complete
                if lease.result:
                    print(f"Success: {lease.result.exit_code}")
                elif lease.failure:
                    print(f"Failed: {lease.failure.message}")
        
        Args:
            request: The execution request
            stream_sink: Optional sink for streaming output
            
        Yields:
            ExecutionLease with result or failure populated
        """
        lease = self.acquire_lease(request)
        try:
            result_or_failure = self.execute(lease, stream_sink=stream_sink)
            
            if isinstance(result_or_failure, ExecutionResult):
                lease.release(result=result_or_failure)
            elif isinstance(result_or_failure, ExecutionFailure):
                lease.release(failure=result_or_failure)
            
            yield lease
            
        except Exception as e:
            # Any exception during execute will already have released the lease
            # But we still want to raise for the caller
            lease.release(failure=ExecutionFailure(
                execution_id=request.execution_id,
                error_type="context_error",
                message=str(e)
            ))
            raise
        finally:
            # Ensure cleanup
            self.release_lease(lease)
    
    @asynccontextmanager
    async def execute_context_async(
        self,
        request: ExecutionRequest,
        stream_sink: Optional[StreamSink] = None
    ):
        """Async context manager for execution.
        
        Note: The synchronous execute() is used, wrapped for async contexts.
        
        Usage:
            async with executor.execute_context_async(request) as lease:
                # handle result/failure
        """
        lease = self.acquire_lease(request)
        try:
            loop = asyncio.get_event_loop()
            # Run sync execute in executor thread
            result_or_failure = await loop.run_in_executor(
                None, self.execute, lease, stream_sink
            )
            
            if isinstance(result_or_failure, ExecutionResult):
                lease.release(result=result_or_failure)
            elif isinstance(result_or_failure, ExecutionFailure):
                lease.release(failure=result_or_failure)
            
            yield lease
            
        except Exception as e:
            lease.release(failure=ExecutionFailure(
                execution_id=request.execution_id,
                error_type="async_context_error",
                message=str(e)
            ))
            raise
        finally:
            self.release_lease(lease)
