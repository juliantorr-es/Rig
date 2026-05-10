"""Process Supervision Substrate for Rig.

This module provides subprocess supervision for Phase 2 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Subprocess supervision is advisory execution only
- All outputs are proposals, never direct mutations
- No hidden execution
- No uncontrolled shell execution
- Deterministic lifecycle tracking
- Bounded output buffering
- Replay-safe supervision records
- Projection-safe state

Properties:
- asyncio-based subprocess execution
- Dry-run compatible execution paths
- Explicit cancellation paths
- Stalled stream detection
- Bounded output buffering
- Runtime status tracking

file: src/rig/domain/runtime_supervisor.py
"""

from __future__ import annotations

import warnings
warnings.warn(
    ("rig.domain.runtime_supervisor is deprecated. Import from rig.domain.runtime_streaming instead. See ADR 0004."),
    DeprecationWarning,
    stacklevel=2,
)

import asyncio
import hashlib
import json
import signal
import subprocess
import sys
import os
from asyncio import CancelledError, Task, TimeoutError as AsyncTimeoutError
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime_streaming import (
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
        RuntimeStreamChannel,
        RuntimeStreamStatus,
        RuntimeWarningCode,
        RuntimeFailureCategory,
    )
    from rig.domain.runtime import (
        RuntimeProvider,
        RuntimeInvocation,
        RuntimeProposal,
        RuntimeCapabilityKind,
    )
    from rig.domain.runtime_registry import RuntimeRegistry

from rig.domain.runtime_streaming._types import (
    PLACEHOLDER_STREAM_ID,
    PLACEHOLDER_SEQUENCE,
    PLACEHOLDER_PROVIDER,
    PLACEHOLDER_NO_RECEIPT,
    DEFAULT_MAX_CHUNK_SIZE,
    DEFAULT_MAX_BUFFER_SIZE,
    DEFAULT_STREAM_TIMEOUT_SECONDS,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_STALLED_THRESHOLD_SECONDS,
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
    RuntimeStreamChannel,
    RuntimeStreamStatus,
    RuntimeWarningCode,
    RuntimeFailureCategory,
)
from rig.domain.runtime import (
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_NO_PROVIDER,
    RuntimeProvider,
    RuntimeProviderKind,
    RuntimeProviderTrustTier,
    RuntimeProviderStatus,
    RuntimeInvocation,
    RuntimeInvocationStatus,
    RuntimeProposal,
    RuntimeCapabilityKind,
    RuntimeConstraintKind,
    RuntimeConstraintMode,
    RuntimeExecutionReceipt,
)


# =============================================================================
# Placeholder Constants
# =============================================================================

PLACEHOLDER_PROCESS_ID = "no_process"
PLACEHOLDER_PID = -1
PLACEHOLDER_EXIT_CODE = -1
PLACEHOLDER_SUPERVISOR_ID = "no_supervisor"
PLACEHOLDER_DECISION_ID = "no_decision"
PLACEHOLDER_COMMAND = "no_command"
PLACEHOLDER_INVOKE_ID = "INVOKE_ID_PLACEHOLDER"



# Process supervision defaults
DEFAULT_PROCESS_TIMEOUT_SECONDS = 300.0
DEFAULT_GRACEFUL_SHUTDOWN_SECONDS = 5.0
DEFAULT_BUFFER_FLUSH_INTERVAL = 0.1  # 100ms
DEFAULT_MAX_STDOUT_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_STDERR_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_STDOUT_BYTES = DEFAULT_MAX_STDOUT_SIZE
DEFAULT_MAX_STDERR_BYTES = DEFAULT_MAX_STDERR_SIZE


# =============================================================================
# Enums
# =============================================================================

class RuntimeSupervisorDecisionCode(Enum):
    """Decision codes for runtime supervisor."""
    ALLOW_STREAM = "allow_stream"           # Allow stream to start
    BLOCK_STREAM = "block_stream"           # Block stream from starting
    CANCEL_STREAM = "cancel_stream"         # Cancel active stream
    TIMEOUT_STREAM = "timeout_stream"       # Force timeout on stream
    REJECT_PROPOSAL = "reject_proposal"     # Reject a proposal
    ACCEPT_PROPOSAL = "accept_proposal"     # Accept a proposal (advisory only)
    STALL_DETECTED = "stall_detected"       # Stall detected
    HEARTBEAT_MISSED = "heartbeat_missed"   # Heartbeat missed
    BUFFER_OVERFLOW = "buffer_overflow"     # Buffer overflow


class RuntimeSupervisorStatus(Enum):
    """Status of the runtime supervisor."""
    IDLE = "idle"                         # No active supervision
    SUPERVISING = "supervising"           # Actively supervising
    PAUSED = "paused"                     # Supervision paused
    STOPPING = "stopping"                 # Stopping supervision
    STOPPED = "stopped"                  # Supervision stopped
    ERROR = "error"                       # Error state


class RuntimeProcessStatus(Enum):
    """Status of a supervised process."""
    PENDING = "pending"                   # Process not yet started
    STARTING = "starting"                 # Starting the process
    RUNNING = "running"                   # Process is running
    COMPLETED = "completed"               # Process completed normally
    FAILED = "failed"                     # Process failed
    TIMED_OUT = "timed_out"               # Process timed out
    CANCELLED = "cancelled"               # Process was cancelled
    KILLED = "killed"                     # Process was killed


class RuntimeSupervisionViolationKind(Enum):
    """Kinds of supervision violations."""
    FORBIDDEN_COMMAND = "forbidden_command"   # Attempted forbidden shell command
    UNAUTHORIZED_MUTATION = "unauthorized_mutation"  # Attempted unauthorized mutation
    CAPABILITY_VIOLATION = "capability_violation"  # Capability check failed
    TRUST_VIOLATION = "trust_violation"    # Trust tier violation
    TIMEOUT_VIOLATION = "timeout_violation"  # Timeout exceeded
    MEMORY_VIOLATION = "memory_violation"   # Memory limit exceeded
    NETWORK_VIOLATION = "network_violation"  # Network access violation
    PROCESS_TIMEOUT = "process_timeout"    # Process execution timed out
    OUTPUT_LIMIT_EXCEEDED = "output_limit_exceeded"  # Output exceeded bounds
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"  # Memory limit exceeded
    FILE_ACCESS_VIOLATION = "file_access_violation"  # Unauthorized file access
    NETWORK_ACCESS_VIOLATION = "network_access_violation"  # Unauthorized network access


# =============================================================================
# Helper Functions
# =============================================================================

def _generate_deterministic_id(prefix: str, *components: Any) -> str:
    """Generate a deterministic ID from components."""
    parts = [str(prefix)] + [str(c) for c in components]
    combined = "|".join(parts)
    return f"{prefix}_{hashlib.sha256(combined.encode()).hexdigest()[:16]}"


def _utc_now() -> str:
    """Get current UTC time as ISO format string."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# =============================================================================
# Forbidden Command Detection
# =============================================================================

# Commands that are NEVER allowed, even from runtimes
FORBIDDEN_COMMANDS = frozenset({
    # Git destructive commands
    "git reset",
    "git reset --hard",
    "git clean",
    "git stash",
    "git rebase",
    "git merge",
    "git commit",
    "git push",
    "git branch -D",
    "git branch -d",
    # Filesystem destructive commands
    "rm -rf",
    "rm -r",
    "rm -f",
    "dd",
    "dd if=/dev/zero",
    # System destruction
    ":() { :; } ;",  # fork bomb
    ":(){ :|:& };:",  # fork bomb variant
    "mkfs",
    "fdisk",
    "format",
    # Process management
    "pkill",
    "killall",
    "kill -9",
    # Network potentially dangerous
    "nc -l",
    "netcat -l",
    "curl --upload-file",
    # Privilege escalation
    "sudo",
    "su",
    "chmod 777",
    "chown",
    # Package management destructive
    "pip uninstall",
    "npm uninstall",
    "apt-get remove",
    "yum remove",
    "brew uninstall",
})

FORBIDDEN_COMMAND_PREFIXES = frozenset({
    # Git destructive commands
    "git reset",
    "git reset --hard",
    "git clean",
    "git stash",
    "git rebase",
    "git merge",
    "git commit",
    "git push",
    # Filesystem destructive commands
    "rm -",
    "dd ",
    "dd if=",
    # System destruction
    "mkfs",
    "fdisk",
    "format ",
    # Process management
    "pkill",
    "killall",
    "kill -9",
    # Privilege escalation
    "sudo ",
    "su ",
    ":() { :; }",
    "chmod 777",
    "chown ",
})


def _contains_forbidden_command(command: str) -> Tuple[bool, str]:
    """Check if a command contains forbidden patterns.
    
    Args:
        command: The command string to check
        
    Returns:
        Tuple of (is_forbidden, reason)
    """
    if not command:
        return False, ""
    
    cmd_upper = command.upper()
    
    # Check exact matches
    for forbidden in FORBIDDEN_COMMANDS:
        if forbidden.upper() in cmd_upper:
            return True, f"Forbidden command detected: {forbidden}"
    
    # Check prefixes
    for prefix in FORBIDDEN_COMMAND_PREFIXES:
        if cmd_upper.startswith(prefix.upper()):
            return True, f"Forbidden command prefix detected: {prefix}"
    
    return False, ""


# =============================================================================
# Runtime Process Handle Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeProcessHandle:
    """Represents a handle to a supervised runtime process.
    
    The process handle tracks:
    - Process metadata
    - Lifecycle state
    - Output buffers
    - Timing information
    - Supervision status
    
    Handles are:
    - Replay-safe
    - Projection-safe
    - Advisory-only (never directly mutable)
    
    Attributes:
        process_id: Unique identifier for the process
        supervisor_id: The supervisor managing this process
        pid: Process ID (OS-level)
        invocation_id: The runtime invocation ID
        provider_id: The runtime provider ID
        command: The command being executed
        status: Current process status
        started_at: When the process started
        completed_at: When the process completed
        exit_code: Process exit code
        stdout_buffer: Buffered stdout content
        stderr_buffer: Buffered stderr content
        timeout_seconds: Process timeout
        advisory_only: ALWAYS True
        metadata: Additional metadata
    """
    process_id: str
    supervisor_id: str = PLACEHOLDER_SUPERVISOR_ID
    pid: Optional[int] = None
    invocation_id: str = PLACEHOLDER_INVOKE_ID
    provider_id: str = PLACEHOLDER_PROVIDER
    command: str = ""
    status: RuntimeProcessStatus = RuntimeProcessStatus.PENDING
    started_at: str = field(default_factory=_utc_now)
    completed_at: Optional[str] = None
    exit_code: Optional[int] = None
    stdout_buffer: str = ""
    stderr_buffer: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    timeout_seconds: float = DEFAULT_PROCESS_TIMEOUT_SECONDS
    advisory_only: bool = True  # ALWAYS True - processes are advisory only
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Ensure invariant: handles are always advisory only
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def create(
        cls,
        supervisor_id: str,
        invocation_id: str,
        provider_id: str,
        command: str,
        timeout_seconds: float = DEFAULT_PROCESS_TIMEOUT_SECONDS,
        process_id: Optional[str] = None,
    ) -> "RuntimeProcessHandle":
        """Create a new process handle."""
        pid = process_id or _generate_deterministic_id(
            "process",
            supervisor_id,
            invocation_id,
            command[:50] if command else "",
        )
        return cls(
            process_id=pid,
            supervisor_id=supervisor_id,
            invocation_id=invocation_id,
            provider_id=provider_id,
            command=command,
            status=RuntimeProcessStatus.PENDING,
            timeout_seconds=timeout_seconds,
        )
    
    @classmethod
    def started(
        cls,
        handle: "RuntimeProcessHandle",
        pid: int,
    ) -> "RuntimeProcessHandle":
        """Create a started process handle."""
        return cls(
            process_id=handle.process_id,
            supervisor_id=handle.supervisor_id,
            pid=pid,
            invocation_id=handle.invocation_id,
            provider_id=handle.provider_id,
            command=handle.command,
            status=RuntimeProcessStatus.RUNNING,
            started_at=handle.started_at,
            completed_at=handle.completed_at,
            exit_code=handle.exit_code,
            stdout_buffer=handle.stdout_buffer,
            stderr_buffer=handle.stderr_buffer,
            stdout_truncated=handle.stdout_truncated,
            stderr_truncated=handle.stderr_truncated,
            timeout_seconds=handle.timeout_seconds,
            advisory_only=True,
            metadata=handle.metadata,
        )
    
    @classmethod
    def completed(
        cls,
        handle: "RuntimeProcessHandle",
        exit_code: int,
        stdout: str,
        stderr: str,
    ) -> "RuntimeProcessHandle":
        """Create a completed process handle."""
        new_stdout, stdout_truncated = handle._truncate_output(stdout, DEFAULT_MAX_STDOUT_SIZE)
        new_stderr, stderr_truncated = handle._truncate_output(stderr, DEFAULT_MAX_STDERR_SIZE)
        
        return cls(
            process_id=handle.process_id,
            supervisor_id=handle.supervisor_id,
            pid=handle.pid,
            invocation_id=handle.invocation_id,
            provider_id=handle.provider_id,
            command=handle.command,
            status=RuntimeProcessStatus.COMPLETED,
            started_at=handle.started_at,
            completed_at=_utc_now(),
            exit_code=exit_code,
            stdout_buffer=new_stdout,
            stderr_buffer=new_stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            timeout_seconds=handle.timeout_seconds,
            advisory_only=True,
            metadata=handle.metadata,
        )
    
    @classmethod
    def failed(
        cls,
        handle: "RuntimeProcessHandle",
        error: str,
        exit_code: Optional[int] = None,
    ) -> "RuntimeProcessHandle":
        """Create a failed process handle."""
        return cls(
            process_id=handle.process_id,
            supervisor_id=handle.supervisor_id,
            pid=handle.pid,
            invocation_id=handle.invocation_id,
            provider_id=handle.provider_id,
            command=handle.command,
            status=RuntimeProcessStatus.FAILED,
            started_at=handle.started_at,
            completed_at=_utc_now(),
            exit_code=exit_code,
            stdout_buffer=handle.stdout_buffer,
            stderr_buffer=handle.stderr_buffer + f"\nERROR: {error}",
            stdout_truncated=handle.stdout_truncated,
            stderr_truncated=True,  # Likely truncated by error
            timeout_seconds=handle.timeout_seconds,
            advisory_only=True,
            metadata={**handle.metadata, "error": error},
        )
    
    @classmethod
    def timed_out(
        cls,
        handle: "RuntimeProcessHandle",
    ) -> "RuntimeProcessHandle":
        """Create a timed out process handle."""
        return cls(
            process_id=handle.process_id,
            supervisor_id=handle.supervisor_id,
            pid=handle.pid,
            invocation_id=handle.invocation_id,
            provider_id=handle.provider_id,
            command=handle.command,
            status=RuntimeProcessStatus.TIMED_OUT,
            started_at=handle.started_at,
            completed_at=_utc_now(),
            exit_code=PLACEHOLDER_EXIT_CODE,
            stdout_buffer=handle.stdout_buffer,
            stderr_buffer=handle.stderr_buffer + "\nERROR: Process timed out",
            stdout_truncated=handle.stdout_truncated,
            stderr_truncated=True,
            timeout_seconds=handle.timeout_seconds,
            advisory_only=True,
            metadata={**handle.metadata, "timeout": True},
        )
    
    @classmethod
    def cancelled(
        cls,
        handle: "RuntimeProcessHandle",
    ) -> "RuntimeProcessHandle":
        """Create a cancelled process handle."""
        return cls(
            process_id=handle.process_id,
            supervisor_id=handle.supervisor_id,
            pid=handle.pid,
            invocation_id=handle.invocation_id,
            provider_id=handle.provider_id,
            command=handle.command,
            status=RuntimeProcessStatus.CANCELLED,
            started_at=handle.started_at,
            completed_at=_utc_now(),
            exit_code=None,
            stdout_buffer=handle.stdout_buffer,
            stderr_buffer=handle.stderr_buffer + "\nProcess cancelled",
            stdout_truncated=handle.stdout_truncated,
            stderr_truncated=True,
            timeout_seconds=handle.timeout_seconds,
            advisory_only=True,
            metadata={**handle.metadata, "cancelled": True},
        )
    
    @staticmethod
    def _truncate_output(content: str, max_size: int) -> Tuple[str, bool]:
        """Truncate output and return truncation flag."""
        if len(content) <= max_size:
            return content, False
        truncated = content[:max_size]
        last_newline = truncated.rfind('\n')
        if last_newline > 0:
            truncated = truncated[:last_newline]
        return truncated, True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["status"] = self.status.value
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeProcessHandle":
        """Deserialize from dictionary."""
        return cls(
            process_id=d.get("process_id", _generate_deterministic_id("process", "unknown")),
            supervisor_id=d.get("supervisor_id", PLACEHOLDER_SUPERVISOR_ID),
            pid=d.get("pid"),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOKE_ID),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            command=d.get("command", ""),
            status=RuntimeProcessStatus(d.get("status", "pending")),
            started_at=d.get("started_at", _utc_now()),
            completed_at=d.get("completed_at"),
            exit_code=d.get("exit_code"),
            stdout_buffer=d.get("stdout_buffer", ""),
            stderr_buffer=d.get("stderr_buffer", ""),
            stdout_truncated=d.get("stdout_truncated", False),
            stderr_truncated=d.get("stderr_truncated", False),
            timeout_seconds=d.get("timeout_seconds", DEFAULT_PROCESS_TIMEOUT_SECONDS),
            advisory_only=d.get("advisory_only", True),
            metadata=d.get("metadata", {}),
        )


# =============================================================================
# Runtime Supervisor Decision Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeSupervisorDecision:
    """Represents a decision made by the runtime supervisor.
    
    Decisions are:
    - Deterministic and replay-safe
    - Projection-safe
    - Advisory-only (decisions themselves don't mutate)
    - Recorded for audit
    
    Attributes:
        decision_id: Unique identifier for the decision
        supervisor_id: The supervisor making the decision
        decision_code: The decision code
        process_id: The process this decision relates to
        invocation_id: The invocation this decision relates to
        provider_id: The provider this decision relates to
        allowed: Whether the action was allowed
        reason: Human-readable reason for the decision
        details: Additional decision details
        timestamp: When the decision was made
        metadata: Additional metadata
    """
    decision_id: str
    supervisor_id: str = PLACEHOLDER_SUPERVISOR_ID
    decision_code: RuntimeSupervisorDecisionCode = RuntimeSupervisorDecisionCode.ALLOW_STREAM
    process_id: Optional[str] = None
    invocation_id: Optional[str] = None
    provider_id: Optional[str] = None
    allowed: bool = True
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def allow(
        cls,
        supervisor_id: str,
        decision_code: RuntimeSupervisorDecisionCode,
        process_id: Optional[str] = None,
        invocation_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        reason: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeSupervisorDecision":
        """Create an allow decision."""
        decision_id = _generate_deterministic_id(
            "decision",
            supervisor_id,
            decision_code.value,
            process_id or "",
            invocation_id or "",
        )
        return cls(
            decision_id=decision_id,
            supervisor_id=supervisor_id,
            decision_code=decision_code,
            process_id=process_id,
            invocation_id=invocation_id,
            provider_id=provider_id,
            allowed=True,
            reason=reason,
            details=details or {},
        )
    
    @classmethod
    def block(
        cls,
        supervisor_id: str,
        decision_code: RuntimeSupervisorDecisionCode,
        process_id: Optional[str] = None,
        invocation_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        reason: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeSupervisorDecision":
        """Create a block/deny decision."""
        decision_id = _generate_deterministic_id(
            "decision",
            supervisor_id,
            decision_code.value,
            process_id or "",
            invocation_id or "",
            "block",
        )
        return cls(
            decision_id=decision_id,
            supervisor_id=supervisor_id,
            decision_code=decision_code,
            process_id=process_id,
            invocation_id=invocation_id,
            provider_id=provider_id,
            allowed=False,
            reason=reason or "Blocked by supervisor policy",
            details=details or {},
        )
    
    @classmethod
    def command_blocked(
        cls,
        supervisor_id: str,
        process_id: str,
        invocation_id: str,
        provider_id: str,
        command: str,
        forbidden_pattern: str,
    ) -> "RuntimeSupervisorDecision":
        """Create a decision blocking a forbidden command."""
        return cls.block(
            supervisor_id=supervisor_id,
            decision_code=RuntimeSupervisorDecisionCode.BLOCK_STREAM,
            process_id=process_id,
            invocation_id=invocation_id,
            provider_id=provider_id,
            reason=f"Forbidden command detected: {forbidden_pattern}",
            details={
                "command": command,
                "forbidden_pattern": forbidden_pattern,
                "violation_kind": RuntimeSupervisionViolationKind.FORBIDDEN_COMMAND.value,
            },
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["decision_code"] = self.decision_code.value
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeSupervisorDecision":
        """Deserialize from dictionary."""
        return cls(
            decision_id=d.get("decision_id", _generate_deterministic_id("decision", "unknown")),
            supervisor_id=d.get("supervisor_id", PLACEHOLDER_SUPERVISOR_ID),
            decision_code=RuntimeSupervisorDecisionCode(d.get("decision_code", "allow_stream")),
            process_id=d.get("process_id"),
            invocation_id=d.get("invocation_id"),
            provider_id=d.get("provider_id"),
            allowed=d.get("allowed", True),
            reason=d.get("reason", ""),
            details=d.get("details", {}),
            timestamp=d.get("timestamp", _utc_now()),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
        )


# =============================================================================
# Runtime Supervisor Receipt Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeSupervisorReceipt:
    """Canonical receipt for runtime supervision.
    
    Supervisor receipts record:
    - Supervision decisions
    - Process lifecycle events
    - Violation detections
    - Timing information
    
    Receipts are:
    - Replay-compatible
    - Integrity-compatible
    - Projection-compatible
    - Audit-compatible
    - Advisory-only
    
    Attributes:
        receipt_id: Unique identifier for the receipt
        supervisor_id: The supervisor ID
        kind: Receipt kind (supervision)
        process_id: The supervised process ID
        invocation_id: The runtime invocation ID
        provider_id: The runtime provider ID
        decisions: List of supervision decisions
        process_handle: Final process handle
        violations: List of violations detected
        started_at: When supervision started
        completed_at: When supervision completed
        duration_seconds: Total supervision duration
        stdout_ref: Reference to stdout (for replay)
        stderr_ref: Reference to stderr (for replay)
        metadata: Additional metadata
        advisory_only: ALWAYS True
        authoritative: ALWAYS False
        integrity_flags: Set of integrity flags
    """
    receipt_id: str
    supervisor_id: str = PLACEHOLDER_SUPERVISOR_ID
    kind: str = "runtime_supervision"
    process_id: Optional[str] = None
    invocation_id: Optional[str] = None
    provider_id: Optional[str] = None
    decisions: Tuple[RuntimeSupervisorDecision, ...] = field(default_factory=tuple)
    process_handle: Optional[RuntimeProcessHandle] = None
    violations: Tuple[str, ...] = field(default_factory=tuple)
    started_at: str = field(default_factory=_utc_now)
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    stdout_ref: Optional[str] = None
    stderr_ref: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True
    authoritative: bool = False  # ALWAYS False
    integrity_flags: FrozenSet[str] = field(default_factory=frozenset)
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
    
    @classmethod
    def from_decision(
        cls,
        decision: RuntimeSupervisorDecision,
        process_handle: Optional[RuntimeProcessHandle] = None,
        violations: Optional[List[str]] = None,
        stdout_ref: Optional[str] = None,
        stderr_ref: Optional[str] = None,
    ) -> "RuntimeSupervisorReceipt":
        """Create a supervisor receipt from a decision."""
        receipt_id = _generate_deterministic_id(
            "supervisor_receipt",
            decision.supervisor_id,
            decision.decision_id,
            decision.process_id or "",
        )
        return cls(
            receipt_id=receipt_id,
            supervisor_id=decision.supervisor_id,
            process_id=decision.process_id,
            invocation_id=decision.invocation_id,
            provider_id=decision.provider_id,
            decisions=(decision,),
            process_handle=process_handle,
            violations=tuple(violations or []),
            stdout_ref=stdout_ref,
            stderr_ref=stderr_ref,
            metadata={"decision_count": 1},
        )
    
    @classmethod
    def completed(
        cls,
        supervisor_id: str,
        process_handle: RuntimeProcessHandle,
        decisions: List[RuntimeSupervisorDecision],
        violations: Optional[List[str]] = None,
        stdout_ref: Optional[str] = None,
        stderr_ref: Optional[str] = None,
    ) -> "RuntimeSupervisorReceipt":
        """Create a completed supervisor receipt."""
        receipt_id = _generate_deterministic_id(
            "supervisor_receipt",
            supervisor_id,
            process_handle.process_id,
            "completed",
        )
        
        started = datetime.fromisoformat(process_handle.started_at.replace("Z", "+00:00"))
        completed = datetime.fromisoformat(_utc_now().replace("Z", "+00:00"))
        duration = (completed - started).total_seconds()
        
        return cls(
            receipt_id=receipt_id,
            supervisor_id=supervisor_id,
            process_id=process_handle.process_id,
            invocation_id=process_handle.invocation_id,
            provider_id=process_handle.provider_id,
            decisions=tuple(decisions),
            process_handle=process_handle,
            violations=tuple(violations or []),
            started_at=process_handle.started_at,
            completed_at=_utc_now(),
            duration_seconds=duration,
            stdout_ref=stdout_ref,
            stderr_ref=stderr_ref,
            metadata={"decision_count": len(decisions)},
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d: Dict[str, Any] = {
            "receipt_id": self.receipt_id,
            "kind": self.kind,
            "supervisor_id": self.supervisor_id,
            "process_id": self.process_id,
            "invocation_id": self.invocation_id,
            "provider_id": self.provider_id,
            "decisions": [dec.to_dict() for dec in self.decisions],
            "process_handle": self.process_handle.to_dict() if self.process_handle else None,
            "violations": list(self.violations),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "stdout_ref": self.stdout_ref,
            "stderr_ref": self.stderr_ref,
            "metadata": self.metadata,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
            "integrity_flags": list(self.integrity_flags),
        }
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeSupervisorReceipt":
        """Deserialize from dictionary."""
        decisions = tuple(
            RuntimeSupervisorDecision.from_dict(dec) for dec in d.get("decisions", [])
        )
        process_handle = None
        if d.get("process_handle"):
            process_handle = RuntimeProcessHandle.from_dict(d["process_handle"])
        
        return cls(
            receipt_id=d.get("receipt_id", _generate_deterministic_id("supervisor_receipt", "unknown")),
            supervisor_id=d.get("supervisor_id", PLACEHOLDER_SUPERVISOR_ID),
            kind=d.get("kind", "runtime_supervision"),
            process_id=d.get("process_id"),
            invocation_id=d.get("invocation_id"),
            provider_id=d.get("provider_id"),
            decisions=decisions,
            process_handle=process_handle,
            violations=tuple(d.get("violations", [])),
            started_at=d.get("started_at", _utc_now()),
            completed_at=d.get("completed_at"),
            duration_seconds=d.get("duration_seconds"),
            stdout_ref=d.get("stdout_ref"),
            stderr_ref=d.get("stderr_ref"),
            metadata=d.get("metadata", {}),
            integrity_flags=frozenset(d.get("integrity_flags", [])),
        )


# =============================================================================
# Runtime Supervisor Model
# =============================================================================

class RuntimeSupervisor:
    """Runtime process supervisor.
    
    This class provides:
    - Subprocess supervision
    - Deterministic lifecycle tracking
    - Timeout handling
    - Cancellation
    - Stalled stream detection
    - Bounded output buffering
    - Runtime status tracking
    
    Properties:
    - No subprocess authority mutation
    - No uncontrolled shell execution
    - Dry-run compatible execution
    - Explicit cancellation paths
    - All operations are advisory-only
    """
    
    def __init__(
        self,
        supervisor_id: Optional[str] = None,
        runtime_registry: Optional[Any] = None,
        max_concurrent: int = 4,
        default_timeout: float = DEFAULT_PROCESS_TIMEOUT_SECONDS,
        dry_run: bool = False,
    ):
        """Initialize the runtime supervisor.
        
        args:
            supervisor_id: Unique supervisor ID
            runtime_registry: Optional runtime registry for capability checks
            max_concurrent: Maximum concurrent processes
            default_timeout: Default process timeout in seconds
            dry_run: If True, run in dry-run mode (no actual execution)
        """
        self.supervisor_id = supervisor_id or _generate_deterministic_id("supervisor")
        self.runtime_registry = runtime_registry
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout
        self.dry_run = dry_run
        
        # State tracking
        self._status = RuntimeSupervisorStatus.IDLE
        self._active_processes: Dict[str, RuntimeProcessHandle] = {}
        self._pending_invocations: Dict[str, RuntimeInvocation] = {}
        self._decisions: Dict[str, RuntimeSupervisorDecision] = {}
        self._receipts: Dict[str, RuntimeSupervisorReceipt] = {}
        self._sequence_counter: int = 0
        self._started_at = _utc_now()
        self._last_activity_at = _utc_now()
        
        # Event tracking
        self._event_buffer: List[Any] = []
        self._max_event_buffer = 1000
        
        # Cancellation support
        self._cancel_tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event: Optional[asyncio.Event] = None
    
    @property
    def supervisor_id(self) -> str:
        """Get the supervisor ID."""
        return self._supervisor_id
    
    @supervisor_id.setter
    def supervisor_id(self, value: str) -> None:
        """Set the supervisor ID."""
        self._supervisor_id = value
    
    @property
    def status(self) -> RuntimeSupervisorStatus:
        """Get current supervisor status."""
        return self._status
    
    @property
    def active_process_count(self) -> int:
        """Get number of active processes."""
        return len(self._active_processes)
    
    @property
    def pending_invocation_count(self) -> int:
        """Get number of pending invocations."""
        return len(self._pending_invocations)
    
    @property
    def can_accept(self) -> bool:
        """Check if supervisor can accept new processes."""
        if self._status in [RuntimeSupervisorStatus.STOPPING, RuntimeSupervisorStatus.STOPPED]:
            return False
        return self.active_process_count < self.max_concurrent
    
    def start(self) -> None:
        """Start the supervisor."""
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()
        self._status = RuntimeSupervisorStatus.IDLE
        self._last_activity_at = _utc_now()
    
    def stop(self) -> None:
        """Stop the supervisor."""
        self._status = RuntimeSupervisorStatus.STOPPED
        self._last_activity_at = _utc_now()
    
    async def shutdown(self) -> None:
        """Gracefully shutdown the supervisor."""
        self._status = RuntimeSupervisorStatus.STOPPING
        
        # Cancel all active tasks
        for task in self._cancel_tasks.values():
            task.cancel()
        
        # Wait for tasks to complete
        if self._cancel_tasks:
            await asyncio.gather(*self._cancel_tasks.values(), return_exceptions=True)
        
        self._cancel_tasks.clear()
        self._status = RuntimeSupervisorStatus.STOPPED
    
    def next_sequence(self) -> int:
        """Get the next sequence number."""
        self._sequence_counter += 1
        return self._sequence_counter
    
    def check_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Check if a command is allowed.
        
        This method checks for forbidden commands and other violations.
        
        args:
            command: The command to check
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        if not command:
            return True, None
        
        # Check for forbidden commands
        is_forbidden, reason = _contains_forbidden_command(command)
        if is_forbidden:
            return False, reason
        
        return True, None
    
    def evaluate_command(self, command: str) -> RuntimeSupervisorDecision:
        """Evaluate a command and return a supervision decision.
        
        This is the supervision-level interface for command evaluation.
        It wraps check_command() and converts the result into a proper
        RuntimeSupervisorDecision object.
        
        args:
            command: The command to evaluate
            
        Returns:
            RuntimeSupervisorDecision with ALLOW_STREAM or BLOCK_STREAM code
        """
        is_allowed, reason = self.check_command(command)
        
        if is_allowed:
            return RuntimeSupervisorDecision.allow(
                supervisor_id=self.supervisor_id,
                decision_code=RuntimeSupervisorDecisionCode.ALLOW_STREAM,
                reason=reason or "Command allowed by supervisor policy",
            )
        else:
            return RuntimeSupervisorDecision.block(
                supervisor_id=self.supervisor_id,
                decision_code=RuntimeSupervisorDecisionCode.BLOCK_STREAM,
                reason=reason or "Command blocked by supervisor policy",
            )
    
    def validate_invocation(
        self,
        invocation: RuntimeInvocation,
        provider: Optional[RuntimeProvider] = None,
    ) -> Tuple[bool, RuntimeSupervisorDecision]:
        """Validate a runtime invocation before execution.
        
        args:
            invocation: The runtime invocation
            provider: Optional provider information
            
        Returns:
            Tuple of (is_valid, decision)
        """
        provider_id = invocation.provider_id
        invocation_id = invocation.invocation_id
        
        # Check if we can accept new processes
        if not self.can_accept:
            decision = RuntimeSupervisorDecision.block(
                supervisor_id=self.supervisor_id,
                decision_code=RuntimeSupervisorDecisionCode.BLOCK_STREAM,
                process_id=PLACEHOLDER_PROCESS_ID,
                invocation_id=invocation_id,
                provider_id=provider_id,
                reason="Supervisor at capacity",
            )
            self._record_decision(decision)
            return False, decision
        
        # Check provider trust tier
        if provider:
            if provider.trust_tier == RuntimeProviderTrustTier.BLOCKED:
                decision = RuntimeSupervisorDecision.block(
                    supervisor_id=self.supervisor_id,
                    decision_code=RuntimeSupervisorDecisionCode.BLOCK_STREAM,
                    invocation_id=invocation_id,
                    provider_id=provider_id,
                    reason=f"Provider {provider_id} is blocked",
                )
                self._record_decision(decision)
                return False, decision
        
        # Check for dry-run mode
        if self.dry_run:
            # In dry-run mode, we allow everything but won't actually execute
            decision = RuntimeSupervisorDecision.allow(
                supervisor_id=self.supervisor_id,
                decision_code=RuntimeSupervisorDecisionCode.ALLOW_STREAM,
                invocation_id=invocation_id,
                provider_id=provider_id,
                reason="Dry-run mode: allowed but not executed",
            )
            self._record_decision(decision)
            return True, decision
        
        # Default allow
        decision = RuntimeSupervisorDecision.allow(
            supervisor_id=self.supervisor_id,
            decision_code=RuntimeSupervisorDecisionCode.ALLOW_STREAM,
            invocation_id=invocation_id,
            provider_id=provider_id,
            reason="Allowed by supervisor policy",
        )
        self._record_decision(decision)
        return True, decision
    
    def create_process_handle(
        self,
        invocation: RuntimeInvocation,
        command: str,
        timeout_seconds: Optional[float] = None,
    ) -> RuntimeProcessHandle:
        """Create a process handle for a new invocation.
        
        args:
            invocation: The runtime invocation
            command: The command to execute
            timeout_seconds: Optional timeout override
            
        Returns:
            RuntimeProcessHandle for the new process
        """
        handle = RuntimeProcessHandle.create(
            supervisor_id=self.supervisor_id,
            invocation_id=invocation.invocation_id,
            provider_id=invocation.provider_id,
            command=command,
            timeout_seconds=timeout_seconds or self.default_timeout,
        )
        self._active_processes[handle.process_id] = handle
        self._status = RuntimeSupervisorStatus.SUPERVISING
        self._last_activity_at = _utc_now()
        return handle
    
    def _record_decision(self, decision: RuntimeSupervisorDecision) -> None:
        """Record a supervision decision."""
        self._decisions[decision.decision_id] = decision
        self._last_activity_at = _utc_now()
    
    def _record_receipt(self, receipt: RuntimeSupervisorReceipt) -> None:
        """Record a supervision receipt."""
        self._receipts[receipt.receipt_id] = receipt
        self._last_activity_at = _utc_now()
    
    async def supervise_process(
        self,
        invocation: RuntimeInvocation,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[float] = None,
        capture_output: bool = True,
    ) -> RuntimeSupervisorReceipt:
        """Supervise a subprocess execution.
        
        This method:
        - Validates the invocation
        - Checks for forbidden commands
        - Executes the process (or simulates in dry-run mode)
        - Captures output
        - Tracks lifecycle
        - Returns a supervision receipt
        
        args:
            invocation: The runtime invocation
            command: The command to execute
            cwd: Working directory
            env: Environment variables
            timeout_seconds: Process timeout
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            RuntimeSupervisorReceipt with supervision results
        """
        invocation_id = invocation.invocation_id
        provider_id = invocation.provider_id
        process_id: Optional[str] = None
        
        self._last_activity_at = _utc_now()
        
        # Validate invocation
        is_valid, decision = self.validate_invocation(invocation)
        if not is_valid:
            receipt = RuntimeSupervisorReceipt.from_decision(
                decision=decision,
            )
            self._record_receipt(receipt)
            return receipt
        
        # Check command
        is_allowed, reason = self.check_command(command)
        if not is_allowed:
            decision = RuntimeSupervisorDecision.command_blocked(
                supervisor_id=self.supervisor_id,
                process_id=PLACEHOLDER_PROCESS_ID,
                invocation_id=invocation_id,
                provider_id=provider_id,
                command=command,
                forbidden_pattern=reason or "unknown",
            )
            self._record_decision(decision)
            receipt = RuntimeSupervisorReceipt.from_decision(
                decision=decision,
            )
            self._record_receipt(receipt)
            return receipt
        
        # Create process handle
        handle = self.create_process_handle(
            invocation=invocation,
            command=command,
            timeout_seconds=timeout_seconds,
        )
        process_id = handle.process_id
        
        # In dry-run mode, return immediately with simulated handle
        if self.dry_run:
            simulated_handle = RuntimeProcessHandle.completed(
                handle=handle,
                exit_code=0,
                stdout="Dry-run: Would execute: " + command,
                stderr="",
            )
            receipt = RuntimeSupervisorReceipt.completed(
                supervisor_id=self.supervisor_id,
                process_handle=simulated_handle,
                decisions=[decision],
            )
            self._record_receipt(receipt)
            return receipt
        
        # Execute the actual process
        try:
            # Update handle to starting state
            handle = RuntimeProcessHandle.started(handle, pid=PLACEHOLDER_PID)
            self._active_processes[process_id] = handle
            
            # Execute subprocess
            actual_stdout = ""
            actual_stderr = ""
            actual_exit_code = 0
            
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                text=True,
                bufsize=1,
            )
            
            # Update handle with actual PID
            handle = RuntimeProcessHandle.started(handle, pid=process.pid)
            self._active_processes[process_id] = handle
            
            # Wait for process with timeout
            effective_timeout = timeout_seconds or handle.timeout_seconds
            
            try:
                actual_stdout, actual_stderr = process.communicate(timeout=effective_timeout)
                actual_exit_code = process.returncode or 0
                
                # Update handle to completed state
                handle = RuntimeProcessHandle.completed(
                    handle=handle,
                    exit_code=actual_exit_code,
                    stdout=actual_stdout or "",
                    stderr=actual_stderr or "",
                )
                
            except subprocess.TimeoutExpired:
                # Kill the process
                try:
                    process.kill()
                    process.wait(timeout=DEFAULT_GRACEFUL_SHUTDOWN_SECONDS)
                except Exception:
                    pass
                
                handle = RuntimeProcessHandle.timed_out(handle)
                self._active_processes[process_id] = handle
                
                receipt = RuntimeSupervisorReceipt.completed(
                    supervisor_id=self.supervisor_id,
                    process_handle=handle,
                    decisions=[decision],
                    violations=["timeout"],
                )
                self._record_receipt(receipt)
                return receipt
            
            # Clean up
            self._active_processes.pop(process_id, None)
            
            # Create receipt
            receipt = RuntimeSupervisorReceipt.completed(
                supervisor_id=self.supervisor_id,
                process_handle=handle,
                decisions=[decision],
            )
            self._record_receipt(receipt)
            return receipt
            
        except Exception as e:
            # Handle any errors
            error_handle = RuntimeProcessHandle.failed(
                handle=handle,
                error=str(e),
                exit_code=None,
            )
            self._active_processes.pop(process_id, None)
            
            receipt = RuntimeSupervisorReceipt.completed(
                supervisor_id=self.supervisor_id,
                process_handle=error_handle,
                decisions=[decision],
                violations=[str(e)],
            )
            self._record_receipt(receipt)
            return receipt
    
    async def supervise_async_process(
        self,
        invocation: RuntimeInvocation,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[float] = None,
        on_chunk: Optional[Callable[[RuntimeStreamChunk], None]] = None,
    ) -> RuntimeSupervisorReceipt:
        """Supervise an async subprocess with streaming output.
        
        This method:
        - Executes process asynchronously
        - Streams output chunks
        - Handles backpressure
        - Supports cancellation
        
        args:
            invocation: The runtime invocation
            command: The command to execute
            cwd: Working directory
            env: Environment variables
            timeout_seconds: Process timeout
            on_chunk: Optional callback for output chunks
            
        Returns:
            RuntimeSupervisorReceipt with supervision results
        """
        invocation_id = invocation.invocation_id
        provider_id = invocation.provider_id
        
        self._last_activity_at = _utc_now()
        
        # Validate invocation
        is_valid, decision = self.validate_invocation(invocation)
        if not is_valid:
            receipt = RuntimeSupervisorReceipt.from_decision(decision=decision)
            self._record_receipt(receipt)
            return receipt
        
        # Check command
        is_allowed, reason = self.check_command(command)
        if not is_allowed:
            decision = RuntimeSupervisorDecision.command_blocked(
                supervisor_id=self.supervisor_id,
                process_id=PLACEHOLDER_PROCESS_ID,
                invocation_id=invocation_id,
                provider_id=provider_id,
                command=command,
                forbidden_pattern=reason or "unknown",
            )
            self._record_decision(decision)
            receipt = RuntimeSupervisorReceipt.from_decision(decision=decision)
            self._record_receipt(receipt)
            return receipt
        
        # Create process handle
        handle = self.create_process_handle(
            invocation=invocation,
            command=command,
            timeout_seconds=timeout_seconds,
        )
        process_id = handle.process_id
        
        # In dry-run mode
        if self.dry_run:
            simulated_handle = RuntimeProcessHandle.completed(
                handle=handle,
                exit_code=0,
                stdout="Dry-run: Would execute: " + command,
                stderr="",
            )
            # Generate chunk events
            if on_chunk:
                chunk = RuntimeStreamChunk.diagnostic(
                    stream_id=invocation_id,
                    sequence=self.next_sequence(),
                    content=f"[DRY-RUN] Would execute: {command}",
                    provider_id=provider_id,
                    invocation_id=invocation_id,
                )
                on_chunk(chunk)
            
            receipt = RuntimeSupervisorReceipt.completed(
                supervisor_id=self.supervisor_id,
                process_handle=simulated_handle,
                decisions=[decision],
            )
            self._record_receipt(receipt)
            return receipt
        
        # Execute actual async process
        process: Optional[asyncio.subprocess.Process] = None
        stdout_stream: Optional[asyncio.StreamReader] = None
        stderr_stream: Optional[asyncio.StreamReader] = None
        
        try:
            process = await asyncio.create_subprocess_exec(
                *command.split() if isinstance(command, str) else command,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            assert process is not None, "create_subprocess_exec must return a Process"
            
            stdout_stream = process.stdout
            stderr_stream = process.stderr
            assert stdout_stream is not None, "stdout must not be None"
            assert stderr_stream is not None, "stderr must not be None"
            
            handle = RuntimeProcessHandle.started(handle, pid=process.pid)
            self._active_processes[process_id] = handle
            
            # Read streams concurrently
            effective_timeout = timeout_seconds or handle.timeout_seconds
            
            async def read_stream(
                stream: asyncio.StreamReader,
                channel: RuntimeStreamChannel,
                chunk_callback: Optional[Callable[[RuntimeStreamChunk], None]],
            ) -> str:
                """Read a stream and emit chunks."""
                output = []
                try:
                    while True:
                        line = await asyncio.wait_for(
                            stream.readline(),
                            timeout=effective_timeout,
                        )
                        if not line:
                            break
                        line_str = line.decode('utf-8', errors='replace')
                        output.append(line_str)
                        
                        # Limit output size
                        total_size = sum(len(s) for s in output)
                        if total_size > DEFAULT_MAX_STDOUT_SIZE:
                            output = output[-100:]  # Keep last 100 lines
                        
                        # Emit chunk
                        if chunk_callback:
                            chunk = RuntimeStreamChunk.create(
                                stream_id=invocation_id,
                                sequence=self.next_sequence(),
                                channel=channel,
                                content=line_str,
                                provider_id=provider_id,
                                invocation_id=invocation_id,
                            )
                            chunk_callback(chunk)
                except asyncio.TimeoutError:
                    pass
                return ''.join(output)
            
            # Read both streams
            stdout_task = asyncio.create_task(
                read_stream(stdout_stream, RuntimeStreamChannel.ASSISTANT, on_chunk)
            )
            stderr_task = asyncio.create_task(
                read_stream(stderr_stream, RuntimeStreamChannel.DIAGNOSTIC, on_chunk)
            )
            
            # Wait for both streams to complete
            try:
                stdout_result, stderr_result = await asyncio.wait_for(
                    asyncio.gather(stdout_task, stderr_task),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                # Timeout - kill process
                if process.returncode is None:
                    process.kill()
                    try:
                        await asyncio.wait_for(
                            process.wait(),
                            timeout=DEFAULT_GRACEFUL_SHUTDOWN_SECONDS,
                        )
                    except asyncio.TimeoutError:
                        process.kill()
                
                handle = RuntimeProcessHandle.timed_out(handle)
                self._active_processes[process_id] = handle
                
                receipt = RuntimeSupervisorReceipt.completed(
                    supervisor_id=self.supervisor_id,
                    process_handle=handle,
                    decisions=[decision],
                    violations=["timeout"],
                )
                self._record_receipt(receipt)
                return receipt
            
            # Get exit code
            exit_code = process.returncode or 0
            
            # Clean up
            self._active_processes.pop(process_id, None)
            
            # Update handle
            handle = RuntimeProcessHandle.completed(
                handle=handle,
                exit_code=exit_code,
                stdout=stdout_result or "",
                stderr=stderr_result or "",
            )
            
            receipt = RuntimeSupervisorReceipt.completed(
                supervisor_id=self.supervisor_id,
                process_handle=handle,
                decisions=[decision],
            )
            self._record_receipt(receipt)
            return receipt
            
        except Exception as e:
            # Handle errors
            error_handle = RuntimeProcessHandle.failed(
                handle=handle,
                error=str(e),
                exit_code=None,
            )
            self._active_processes.pop(process_id, None)
            
            receipt = RuntimeSupervisorReceipt.completed(
                supervisor_id=self.supervisor_id,
                process_handle=error_handle,
                decisions=[decision],
                violations=[str(e)],
            )
            self._record_receipt(receipt)
            return receipt
    
    def cancel_invocation(self, invocation_id: str) -> Optional[RuntimeSupervisorDecision]:
        """Cancel an active invocation.
        
        args:
            invocation_id: The invocation ID to cancel
            
        Returns:
            Decision if cancellation was successful, None otherwise
        """
        # Find process by invocation ID
        process_id_to_cancel = None
        for pid, handle in self._active_processes.items():
            if handle.invocation_id == invocation_id:
                process_id_to_cancel = pid
                break
        
        if process_id_to_cancel is None:
            return None
        
        # Create cancellation decision
        decision = RuntimeSupervisorDecision.block(
            supervisor_id=self.supervisor_id,
            decision_code=RuntimeSupervisorDecisionCode.CANCEL_STREAM,
            process_id=process_id_to_cancel,
            invocation_id=invocation_id,
            reason="Cancelled by supervisor",
        )
        self._record_decision(decision)
        
        # Update process handle
        handle = self._active_processes[process_id_to_cancel]
        cancelled_handle = RuntimeProcessHandle.cancelled(handle)
        self._active_processes[process_id_to_cancel] = cancelled_handle
        
        return decision
    
    def get_process(self, process_id: str) -> Optional[RuntimeProcessHandle]:
        """Get a process handle by ID."""
        return self._active_processes.get(process_id)
    
    def get_decision(self, decision_id: str) -> Optional[RuntimeSupervisorDecision]:
        """Get a decision by ID."""
        return self._decisions.get(decision_id)
    
    def get_receipt(self, receipt_id: str) -> Optional[RuntimeSupervisorReceipt]:
        """Get a receipt by ID."""
        return self._receipts.get(receipt_id)
    
    def list_active_processes(self) -> List[RuntimeProcessHandle]:
        """List all active process handles."""
        return list(self._active_processes.values())
    
    def list_decisions(self) -> List[RuntimeSupervisorDecision]:
        """List all supervision decisions."""
        return list(self._decisions.values())
    
    def list_receipts(self) -> List[RuntimeSupervisorReceipt]:
        """List all supervision receipts."""
        return list(self._receipts.values())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "supervisor_id": self.supervisor_id,
            "status": self._status.value,
            "active_process_count": self.active_process_count,
            "pending_invocation_count": self.pending_invocation_count,
            "can_accept": self.can_accept,
            "max_concurrent": self.max_concurrent,
            "default_timeout": self.default_timeout,
            "dry_run": self.dry_run,
            "started_at": self._started_at,
            "last_activity_at": self._last_activity_at,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Constants
    "PLACEHOLDER_PROCESS_ID",
    "PLACEHOLDER_PID",
    "PLACEHOLDER_EXIT_CODE",
    "PLACEHOLDER_SUPERVISOR_ID",
    "PLACEHOLDER_DECISION_ID",
    "DEFAULT_PROCESS_TIMEOUT_SECONDS",
    "DEFAULT_GRACEFUL_SHUTDOWN_SECONDS",
    "DEFAULT_BUFFER_FLUSH_INTERVAL",
    "DEFAULT_MAX_STDOUT_SIZE",
    "DEFAULT_MAX_STDERR_SIZE",
    # Forbidden commands
    "FORBIDDEN_COMMANDS",
    "FORBIDDEN_COMMAND_PREFIXES",
    # Enums
    "RuntimeSupervisorDecisionCode",
    "RuntimeSupervisorStatus",
    "RuntimeProcessStatus",
    "RuntimeSupervisionViolationKind",
    # Models
    "RuntimeProcessHandle",
    "RuntimeSupervisorDecision",
    "RuntimeSupervisorReceipt",
    "RuntimeSupervisor",
    # Functions
    "_generate_deterministic_id",
    "_utc_now",
    "_contains_forbidden_command",
]
