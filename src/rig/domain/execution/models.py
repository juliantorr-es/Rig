"""Domain models for governed execution.

Execution models define the contract for governed process execution:
- ExecutionRequest: Input specification for what to execute
- ExecutionLease: Time-bounded authorization to execute
- ExecutionResult: Successful outcome with evidence
- ExecutionFailure: Failure outcome with evidence
- ExecutionStreamEvent: Incremental output for streaming
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable


# =============================================================================
# Enums
# =============================================================================

class ExecutionStatus(Enum):
    """Status of an execution."""
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


# =============================================================================
# Models
# =============================================================================

@dataclass
class ExecutionRequest:
    """Request to execute a command in a governed context.
    
    This is the input specification for WorktreeExecutor. It defines:
    - WHAT: command argv (no shell=True by default)
    - WHERE: cwd/worktree path
    - HOW: env overlay, timeout
    - WHY: purpose, client_id for audit
    - HOW TO TRACK: stream_id for output correlation
    
    Note: argv is a list, not a shell string. This avoids shell injection
    vulnerabilities and provides explicit command structure.
    """
    # Command specification
    argv: List[str]
    cwd: Optional[Path] = None
    
    # Environment
    env_overlay: Dict[str, str] = field(default_factory=dict)
    
    # Timeout and resource limits
    timeout_seconds: Optional[float] = None  # None = no timeout (use with caution)
    
    # Context
    workspace_id: Optional[str] = None
    purpose: str = ""
    client_id: Optional[str] = None  # Who requested this execution
    actor_id: Optional[str] = None  # What/whom is executing
    stream_id: Optional[str] = None  # For correlating stream events
    
    # Execution identity
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    
    # Options
    capture_stdout: bool = True
    capture_stderr: bool = True
    
    @property
    def command_description(self) -> str:
        """Human-readable command description."""
        if self.argv:
            cmd_str = " ".join(self.argv)
            if len(cmd_str) > 60:
                return cmd_str[:57] + "..."
            return cmd_str
        return "(no command)"


@dataclass
class ExecutionLease:
    """Time-bounded authorization to execute.
    
    A lease represents the right to execute a specific request. It:
    - Is acquired before execution starts
    - Has a TTL (time-to-live) after which it expires
    - Must be released (or auto-released on expiry)
    - Can be revoked
    - Tracks the request and result
    
    The lease pattern ensures that:
    1. Execution doesn't start without authorization
    2. Resources are bounded (time, process count)
    3. Cleanup happens even on failure
    """
    # The request being leased (required, must be provided)
    request: "ExecutionRequest"
    lease_id: str = field(default_factory=lambda: f"lease_{uuid.uuid4().hex[:12]}")
    
    # Timing
    acquired_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_seconds: float = 300.0  # 5 minutes default
    expires_at: Optional[str] = None
    
    # State
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[Any] = None
    failure: Optional["ExecutionFailure"] = None
    
    # Tracking
    process_id: Optional[int] = None  # OS process PID if applicable
    
    def __post_init__(self):
        if not self.expires_at:
            expiry = datetime.fromisoformat(self.acquired_at) + timedelta(seconds=self.ttl_seconds)
            self.expires_at = expiry.isoformat()
    
    @property
    def is_expired(self) -> bool:
        """Check if the lease has expired."""
        if not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at) < datetime.now(timezone.utc)
    
    @property
    def is_active(self) -> bool:
        """Check if the lease is currently active."""
        return (
            self.status == ExecutionStatus.RUNNING or
            self.status == ExecutionStatus.STARTING
        ) and not self.is_expired
    
    @property
    def is_complete(self) -> bool:
        """Check if the lease has completed (success or failure)."""
        return self.status in (
            ExecutionStatus.SUCCEEDED,
            ExecutionStatus.FAILED,
            ExecutionStatus.TIMED_OUT,
            ExecutionStatus.CANCELLED
        )
    
    def release(self, result: Optional[Any] = None, failure: Optional["ExecutionFailure"] = None) -> None:
        """Release the lease with a result or failure."""
        if result is not None:
            self.result = result
            self.status = ExecutionStatus.SUCCEEDED
        elif failure is not None:
            self.failure = failure
            self.status = ExecutionStatus.FAILED
        else:
            self.status = ExecutionStatus.CANCELLED
    
    def expire(self) -> None:
        """Mark the lease as expired."""
        self.status = ExecutionStatus.TIMED_OUT
    
    def revoke(self) -> None:
        """Revoke the lease."""
        if self.status == ExecutionStatus.RUNNING:
            self.status = ExecutionStatus.CANCELLED
            self.failure = ExecutionFailure(
                execution_id=self.request.execution_id,
                exit_code=None,
                error_type="revoked",
                message="Lease was revoked",
                timestamp=datetime.now(timezone.utc).isoformat()
            )


@dataclass
class ExecutionResult:
    """Result of a successful execution.
    
    Contains:
    - Exit code (should be 0 for success)
    - Timing information
    - Output summaries and references
    - Whether it was killed by timeout
    """
    execution_id: str
    lease_id: str
    exit_code: int
    
    started_at: str
    completed_at: str
    
    stdout_summary: str = ""
    stderr_summary: str = ""
    stdout_ref: Optional[str] = None  # Path or identifier for full stdout
    stderr_ref: Optional[str] = None  # Path or identifier for full stderr
    
    # Optional: if we killed the process
    timed_out: bool = False
    
    @property
    def succeeded(self) -> bool:
        """Check if execution succeeded (exit code 0)."""
        return self.exit_code == 0


@dataclass
class ExecutionFailure:
    """Failure details for an execution.
    
    Captures:
    - What went wrong (error_type, message)
    - Timing
    - Partial output if available
    """
    execution_id: str
    exit_code: Optional[int] = None
    error_type: str = "unknown"
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    stdout_summary: str = ""
    stderr_summary: str = ""
    stdout_ref: Optional[str] = None
    stderr_ref: Optional[str] = None
    
    timed_out: bool = False
    
    def __post_init__(self):
        if self.timed_out and not self.error_type:
            self.error_type = "timeout"
        if self.timed_out and not self.message:
            self.message = "Execution timed out"


@dataclass
class ExecutionStreamEvent:
    """Incremental streaming output from an execution.
    
    Used for real-time output streaming to UI/clients.
    Each event represents a chunk of output from stdout/stderr.
    """
    execution_id: str
    stream_id: str
    channel: str  # "stdout" or "stderr"
    sequence: int  # Monotonic sequence number within the stream
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "execution_id": self.execution_id,
            "stream_id": self.stream_id,
            "channel": self.channel,
            "sequence": self.sequence,
            "content": self.content,
            "timestamp": self.timestamp,
        }


# =============================================================================
# Stream Sink Protocol
# =============================================================================

@runtime_checkable
class StreamSink(Protocol):
    """Protocol for stream event sinks.
    
    Implementations receive ExecutionStreamEvent objects for real-time
    output streaming.
    """
    
    def on_stream_event(self, event: ExecutionStreamEvent) -> None:
        """Handle a stream event from an execution."""
        ...


class CollectingStreamSink:
    """Simple stream sink that collects all events in memory.
    
    Useful for testing and for capturing full output.
    """
    
    def __init__(self):
        self.stdio_events: List[ExecutionStreamEvent] = []
        self.stderr_events: List[ExecutionStreamEvent] = []
        self._all_events: List[ExecutionStreamEvent] = []
    
    def on_stream_event(self, event: ExecutionStreamEvent) -> None:
        self._all_events.append(event)
        if event.channel == "stdout":
            self.stdio_events.append(event)
        elif event.channel == "stderr":
            self.stderr_events.append(event)
    
    def get_stdout(self) -> str:
        """Get collected stdout as string."""
        return "".join(e.content for e in self.stdio_events)
    
    def get_stderr(self) -> str:
        """Get collected stderr as string."""
        return "".join(e.content for e in self.stderr_events)
    
    def clear(self) -> None:
        """Clear all collected events."""
        self.stdio_events.clear()
        self.stderr_events.clear()
        self._all_events.clear()
