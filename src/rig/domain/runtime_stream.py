"""Runtime Stream Event Models for Rig.

This module provides deterministic stream event models for Phase 2 of the
Runtime & Agent Execution Plane.

Core doctrine:
- Runtime output is advisory evidence only
- Only receipts/proposals become authoritative evidence
- UI streams projections, NOT raw subprocesses
- All stream events are deterministic and replay-safe
- All models are pure frozen dataclasses
- All models are JSON-serializable
- Explicit sequence numbers for ordering
- Bounded memory handling
- No hidden mutation
- Subprocesses remain advisory-only

file: src/rig/domain/runtime_stream.py
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    pass


# =============================================================================
# Placeholder Constants
# =============================================================================

PLACEHOLDER_STREAM_ID = "not_set"
PLACEHOLDER_SEQUENCE = -1
PLACEHOLDER_CHANNEL = "unknown"
PLACEHOLDER_CONTENT = ""
PLACEHOLDER_PROVIDER = "no_provider"
PLACEHOLDER_INVOCATION = "no_invocation"
PLACEHOLDER_RECEIPT = "no_receipt"
PLACEHOLDER_NO_RECEIPT = "no_receipt"
PLACEHOLDER_TIMESTAMP = "1970-01-01T00:00:00Z"

# Stream buffer constants
DEFAULT_MAX_CHUNK_SIZE = 1024 * 1024  # 1 MB
DEFAULT_MAX_BUFFER_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_SEQUENCE_GAP = 100
DEFAULT_STREAM_TIMEOUT_SECONDS = 300.0
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 5.0
DEFAULT_STALLED_THRESHOLD_SECONDS = 30.0


# =============================================================================
# Enums
# =============================================================================

class RuntimeStreamChannel(Enum):
    """Channels for runtime stream events."""
    ASSISTANT = "assistant"           # Assistant/model output
    USER = "user"                     # User input
    SYSTEM = "system"                 # System messages
    TOOL = "tool"                     # Tool invocation output
    PROPOSAL = "proposal"             # Proposal generation
    DIAGNOSTIC = "diagnostic"         # Diagnostic/logging output
    STATUS = "status"                 # Runtime status updates
    HEARTBEAT = "heartbeat"           # Stream heartbeat
    WARNING = "warning"                # Warning events
    ERROR = "error"                   # Error events
    COMPLETION = "completion"         # Completion events
    META = "meta"                     # Metadata events


class RuntimeStreamEventKind(Enum):
    """Kinds of runtime stream events."""
    CHUNK = "chunk"                   # Stream content chunk
    STATUS = "status"                 # Status change event
    HEARTBEAT = "heartbeat"           # Keep-alive heartbeat
    TOOL_PROPOSAL = "tool_proposal"   # Tool invocation proposal
    PATCH_PROPOSAL = "patch_proposal" # File patch proposal
    WARNING = "warning"                # Warning event
    COMPLETION = "completion"         # Stream completion
    FAILURE = "failure"               # Stream failure
    METADATA = "metadata"              # Metadata update


class RuntimeStreamStatus(Enum):
    """Status of a runtime stream."""
    PENDING = "pending"               # Stream not yet started
    CONNECTING = "connecting"         # Connecting to runtime
    ACTIVE = "active"                 # Stream is active
    PAUSED = "paused"                 # Stream is paused
    STALLED = "stalled"               # Stream is stalled (no heartbeat)
    COMPLETED = "completed"           # Stream completed successfully
    FAILED = "failed"                 # Stream failed
    CANCELLED = "cancelled"           # Stream was cancelled
    TIMED_OUT = "timed_out"           # Stream timed out


class RuntimeStreamStateKind(Enum):
    """Kinds of runtime stream states."""
    IDLE = "idle"                     # No active streams
    STREAMING = "streaming"           # One or more active streams
    DEGRADED = "degraded"            # Streams active but with issues
    BLOCKED = "blocked"              # Streams blocked


class RuntimeProposalKind(Enum):
    """Kinds of runtime proposals in stream context."""
    TOOL_CALL = "tool_call"           # Tool function call proposal
    SHELL_COMMAND = "shell_command"   # Shell command proposal
    PATCH = "patch"                   # File patch proposal
    FILE_WRITE = "file_write"         # File write proposal
    FILE_READ = "file_read"           # File read proposal
    NETWORK_FETCH = "network_fetch"   # Network fetch proposal
    DOCS_FETCH = "docs_fetch"         # Documentation fetch proposal


class RuntimeWarningCode(Enum):
    """Warning codes for runtime stream warnings."""
    TRUNCATION_APPLIED = "truncation_applied"   # Output was truncated
    RATE_LIMITED = "rate_limited"         # Provider rate limited
    MODEL_UNAVAILABLE = "model_unavailable"   # Model temporarily unavailable
    CAPABILITY_MISMATCH = "capability_mismatch"  # Capability not available
    TOKEN_LIMIT_APPROACHING = "token_limit_approaching"  # Token limit warning
    MEMORY_PRESSURE = "memory_pressure"  # High memory usage
    STALLED_DETECTED = "stalled_detected"  # Stream stall detected
    SEQUENCE_GAP = "sequence_gap"      # Sequence number gap detected
    DUPLICATE_SEQUENCE = "duplicate_sequence"  # Duplicate sequence detected


class RuntimeFailureCategory(Enum):
    """Categories of runtime stream failures."""
    CONNECTION_ERROR = "connection_error"   # Connection to provider failed
    TIMEOUT = "timeout"                     # Stream timed out
    PROVIDER_ERROR = "provider_error"       # Provider returned error
    VALIDATION_ERROR = "validation_error"   # Validation failed
    CAPABILITY_ERROR = "capability_error"   # Capability check failed
    TRUST_ERROR = "trust_error"             # Trust tier violation
    CONSTRAINT_ERROR = "constraint_error"   # Constraint violation
    INTERNAL_ERROR = "internal_error"       # Internal Rig error
    CANCELLED = "cancelled"                 # Stream was cancelled
    SEQUENCE_ERROR = "sequence_error"       # Sequence number error


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


def _serialize_enum(enum_val: Enum) -> str:
    """Serialize an enum to its value."""
    return enum_val.value if enum_val else PLACEHOLDER_CHANNEL


def _serialize_optional_enum(enum_val: Optional[Enum]) -> Optional[str]:
    """Serialize an optional enum to its value or None."""
    return enum_val.value if enum_val else None


def _truncate_content(content: str, max_length: int = DEFAULT_MAX_CHUNK_SIZE) -> Tuple[str, bool]:
    """Truncate content and return truncation flag.
    
    Args:
        content: The content to truncate
        max_length: Maximum allowed length
        
    Returns:
        Tuple of (truncated_content, was_truncated)
    """
    if not content:
        return "", False
    if len(content) <= max_length:
        return content, False
    truncated = content[:max_length]
    # Try to truncate at last newline for cleaner output
    last_newline = truncated.rfind('\n')
    if last_newline > 0:
        truncated = truncated[:last_newline]
    was_truncated = len(truncated) < len(content)
    return truncated, was_truncated


# =============================================================================
# Runtime Stream Chunk Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeStreamChunk:
    """Represents a single chunk of runtime stream output.
    
    A chunk is the smallest unit of stream data. Chunks are:
    - Deterministic and replay-safe
    - Sequentially ordered
    - Bounded in size
    - Projection-safe
    - Advisory-only
    
    Attributes:
        chunk_id: Unique identifier for this chunk
        stream_id: The stream this chunk belongs to
        sequence: Sequence number within the stream (0-indexed, increasing)
        channel: The channel this chunk came from
        content: The actual content of the chunk
        content_length: Length of content in bytes
        truncated: Whether this chunk was truncated
        timestamp: When the chunk was created
        provider_id: The runtime provider ID
        invocation_id: The invocation ID this chunk relates to
        metadata: Additional metadata for the chunk
        advisory_only: ALWAYS True - chunks are advisory only
    """
    chunk_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    channel: RuntimeStreamChannel = RuntimeStreamChannel.ASSISTANT
    content: str = PLACEHOLDER_CONTENT
    content_length: int = 0
    truncated: bool = False
    timestamp: str = field(default_factory=_utc_now)
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True - chunks are advisory only
    
    def __post_init__(self):
        # Ensure invariant: chunks are always advisory only
        object.__setattr__(self, 'advisory_only', True)
        # Auto-calculate content_length
        actual_length = len(self.content.encode('utf-8', errors='replace')) if self.content else 0
        object.__setattr__(self, 'content_length', actual_length)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        sequence: int,
        channel: RuntimeStreamChannel,
        content: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        max_content_length: int = DEFAULT_MAX_CHUNK_SIZE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeStreamChunk":
        """Create a new runtime stream chunk with truncation."""
        chunk_id = _generate_deterministic_id(
            "chunk",
            stream_id,
            str(sequence),
            channel.value,
            content[:100] if content else "",  # Use first 100 chars for ID
        )
        
        truncated_content, was_truncated = _truncate_content(content, max_content_length)
        
        return cls(
            chunk_id=chunk_id,
            stream_id=stream_id,
            sequence=sequence,
            channel=channel,
            content=truncated_content,
            truncated=was_truncated,
            provider_id=provider_id,
            invocation_id=invocation_id,
            metadata=metadata or {},
        )
    
    @classmethod
    def assistant(
        cls,
        stream_id: str,
        sequence: int,
        content: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        max_content_length: int = DEFAULT_MAX_CHUNK_SIZE,
    ) -> "RuntimeStreamChunk":
        """Create an assistant channel chunk."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            channel=RuntimeStreamChannel.ASSISTANT,
            content=content,
            provider_id=provider_id,
            invocation_id=invocation_id,
            max_content_length=max_content_length,
        )
    
    @classmethod
    def diagnostic(
        cls,
        stream_id: str,
        sequence: int,
        content: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        max_content_length: int = DEFAULT_MAX_CHUNK_SIZE,
    ) -> "RuntimeStreamChunk":
        """Create a diagnostic channel chunk."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            channel=RuntimeStreamChannel.DIAGNOSTIC,
            content=content,
            provider_id=provider_id,
            invocation_id=invocation_id,
            max_content_length=max_content_length,
        )
    
    @classmethod
    def tool_output(
        cls,
        stream_id: str,
        sequence: int,
        content: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        tool_name: str = "",
        max_content_length: int = DEFAULT_MAX_CHUNK_SIZE,
    ) -> "RuntimeStreamChunk":
        """Create a tool output channel chunk."""
        chunk = cls.create(
            stream_id=stream_id,
            sequence=sequence,
            channel=RuntimeStreamChannel.TOOL,
            content=content,
            provider_id=provider_id,
            invocation_id=invocation_id,
            max_content_length=max_content_length,
            metadata={"tool_name": tool_name},
        )
        return chunk
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["channel"] = self.channel.value
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeStreamChunk":
        """Deserialize from dictionary."""
        return cls(
            chunk_id=d.get("chunk_id", _generate_deterministic_id("chunk", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            channel=RuntimeStreamChannel(d.get("channel", "assistant")),
            content=d.get("content", PLACEHOLDER_CONTENT),
            content_length=d.get("content_length", 0),
            truncated=d.get("truncated", False),
            timestamp=d.get("timestamp", _utc_now()),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
        )


# =============================================================================
# Runtime Status Event Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeStatusEvent:
    """Represents a runtime stream status change event.
    
    Status events track the lifecycle of a runtime stream.
    They are deterministic, replay-safe, and projection-safe.
    
    Attributes:
        event_id: Unique identifier for this event
        stream_id: The stream this event belongs to
        sequence: Sequence number within the stream
        status: The new status
        previous_status: The previous status
        timestamp: When the status change occurred
        provider_id: The runtime provider ID
        invocation_id: The invocation ID
        message: Human-readable status message
        reason: Reason for the status change
        metadata: Additional metadata
    """
    event_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    status: RuntimeStreamStatus = RuntimeStreamStatus.PENDING
    previous_status: RuntimeStreamStatus = RuntimeStreamStatus.PENDING
    timestamp: str = field(default_factory=_utc_now)
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    message: str = ""
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        sequence: int,
        status: RuntimeStreamStatus,
        previous_status: RuntimeStreamStatus = RuntimeStreamStatus.PENDING,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        message: str = "",
        reason: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeStatusEvent":
        """Create a new status event."""
        event_id = _generate_deterministic_id(
            "status_event",
            stream_id,
            str(sequence),
            status.value,
        )
        return cls(
            event_id=event_id,
            stream_id=stream_id,
            sequence=sequence,
            status=status,
            previous_status=previous_status,
            provider_id=provider_id,
            invocation_id=invocation_id,
            message=message,
            reason=reason,
            metadata=metadata or {},
        )
    
    @classmethod
    def started(
        cls,
        stream_id: str,
        sequence: int,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeStatusEvent":
        """Create a stream started event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            status=RuntimeStreamStatus.ACTIVE,
            previous_status=RuntimeStreamStatus.CONNECTING,
            provider_id=provider_id,
            invocation_id=invocation_id,
            message="Stream started",
            reason="provider_connected",
        )
    
    @classmethod
    def completed(
        cls,
        stream_id: str,
        sequence: int,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        reason: str = "normal_completion",
    ) -> "RuntimeStatusEvent":
        """Create a stream completed event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            status=RuntimeStreamStatus.COMPLETED,
            previous_status=RuntimeStreamStatus.ACTIVE,
            provider_id=provider_id,
            invocation_id=invocation_id,
            message="Stream completed",
            reason=reason,
        )
    
    @classmethod
    def failed(
        cls,
        stream_id: str,
        sequence: int,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        reason: str = "unknown_error",
        message: str = "",
    ) -> "RuntimeStatusEvent":
        """Create a stream failed event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            status=RuntimeStreamStatus.FAILED,
            previous_status=RuntimeStreamStatus.ACTIVE,
            provider_id=provider_id,
            invocation_id=invocation_id,
            message=message or "Stream failed",
            reason=reason,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["status"] = self.status.value
        d["previous_status"] = self.previous_status.value
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeStatusEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=d.get("event_id", _generate_deterministic_id("status_event", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            status=RuntimeStreamStatus(d.get("status", "pending")),
            previous_status=RuntimeStreamStatus(d.get("previous_status", "pending")),
            timestamp=d.get("timestamp", _utc_now()),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            message=d.get("message", ""),
            reason=d.get("reason", ""),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
        )


# =============================================================================
# Runtime Heartbeat Event Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeHeartbeatEvent:
    """Represents a runtime stream heartbeat event.
    
    Heartbeat events are used for:
    - Detecting stalled streams
    - Maintaining connection health
    - Bounded timeout management
    
    Attributes:
        event_id: Unique identifier for this event
        stream_id: The stream this event belongs to
        sequence: Sequence number within the stream
        timestamp: When the heartbeat was sent
        provider_id: The runtime provider ID
        invocation_id: The invocation ID
        missed_count: Number of consecutive missed heartbeats
        interval_seconds: Expected heartbeat interval
    """
    event_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    timestamp: str = field(default_factory=_utc_now)
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    missed_count: int = 0
    interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    advisory_only: bool = True  # ALWAYS True
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        sequence: int,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        missed_count: int = 0,
    ) -> "RuntimeHeartbeatEvent":
        """Create a new heartbeat event."""
        event_id = _generate_deterministic_id(
            "heartbeat",
            stream_id,
            str(sequence),
        )
        return cls(
            event_id=event_id,
            stream_id=stream_id,
            sequence=sequence,
            provider_id=provider_id,
            invocation_id=invocation_id,
            missed_count=missed_count,
            interval_seconds=interval_seconds,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeHeartbeatEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=d.get("event_id", _generate_deterministic_id("heartbeat", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            timestamp=d.get("timestamp", _utc_now()),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            missed_count=d.get("missed_count", 0),
            interval_seconds=d.get("interval_seconds", DEFAULT_HEARTBEAT_INTERVAL_SECONDS),
            advisory_only=d.get("advisory_only", True),
        )


# =============================================================================
# Runtime Tool Proposal Event Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeToolProposalEvent:
    """Represents a runtime tool proposal event in the stream.
    
    Tool proposals are advisory suggestions for tool invocations.
    They NEVER directly execute - they must go through Rig's validation.
    
    Attributes:
        event_id: Unique identifier for this event
        stream_id: The stream this event belongs to
        sequence: Sequence number within the stream
        proposal_id: The proposal ID
        proposal_kind: The kind of proposal
        payload: The proposal payload
        capability_ids: Set of capability IDs required
        validation_status: Status of capability validation
        validation_errors: List of validation errors
        timestamp: When the proposal was generated
        provider_id: The runtime provider ID
        invocation_id: The invocation ID
        metadata: Additional metadata
    """
    event_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    proposal_id: str = PLACEHOLDER_NO_RECEIPT
    proposal_kind: RuntimeProposalKind = RuntimeProposalKind.TOOL_CALL
    payload: Dict[str, Any] = field(default_factory=dict)
    capability_ids: FrozenSet[str] = field(default_factory=frozenset)
    validation_status: str = "pending"  # pending, validated, rejected, blocked
    validation_errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_utc_now)
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True - proposals are advisory only
    authoritative: bool = False  # ALWAYS False - proposals are never authoritative
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        sequence: int,
        proposal_kind: RuntimeProposalKind,
        payload: Dict[str, Any],
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        capability_ids: Optional[FrozenSet[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeToolProposalEvent":
        """Create a new tool proposal event."""
        event_id = _generate_deterministic_id(
            "tool_proposal",
            stream_id,
            str(sequence),
            proposal_kind.value,
            json.dumps(payload, sort_keys=True, default=str)[:100],
        )
        proposal_id = _generate_deterministic_id(
            "proposal",
            stream_id,
            str(sequence),
            proposal_kind.value,
        )
        return cls(
            event_id=event_id,
            stream_id=stream_id,
            sequence=sequence,
            proposal_id=proposal_id,
            proposal_kind=proposal_kind,
            payload=payload,
            capability_ids=capability_ids or frozenset(),
            provider_id=provider_id,
            invocation_id=invocation_id,
            metadata=metadata or {},
        )
    
    @classmethod
    def shell_command(
        cls,
        stream_id: str,
        sequence: int,
        argv: List[str],
        cwd: Optional[str] = None,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeToolProposalEvent":
        """Create a shell command proposal event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            proposal_kind=RuntimeProposalKind.SHELL_COMMAND,
            payload={"argv": argv, "cwd": cwd},
            provider_id=provider_id,
            invocation_id=invocation_id,
        )
    
    @classmethod
    def patch(
        cls,
        stream_id: str,
        sequence: int,
        file_path: str,
        diff: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeToolProposalEvent":
        """Create a patch proposal event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            proposal_kind=RuntimeProposalKind.PATCH,
            payload={"file_path": file_path, "diff": diff},
            provider_id=provider_id,
            invocation_id=invocation_id,
        )
    
    @classmethod
    def file_write(
        cls,
        stream_id: str,
        sequence: int,
        file_path: str,
        content: str,
        mode: str = "overwrite",
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeToolProposalEvent":
        """Create a file write proposal event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            proposal_kind=RuntimeProposalKind.FILE_WRITE,
            payload={"file_path": file_path, "content": content, "mode": mode},
            provider_id=provider_id,
            invocation_id=invocation_id,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["proposal_kind"] = self.proposal_kind.value
        d["capability_ids"] = list(self.capability_ids)
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeToolProposalEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=d.get("event_id", _generate_deterministic_id("tool_proposal", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            proposal_id=d.get("proposal_id", PLACEHOLDER_NO_RECEIPT),
            proposal_kind=RuntimeProposalKind(d.get("proposal_kind", "tool_call")),
            payload=d.get("payload", {}),
            capability_ids=frozenset(d.get("capability_ids", [])),
            validation_status=d.get("validation_status", "pending"),
            validation_errors=d.get("validation_errors", []),
            timestamp=d.get("timestamp", _utc_now()),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
            authoritative=d.get("authoritative", False),
        )


# =============================================================================
# Runtime Patch Proposal Event Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimePatchProposalEvent:
    """Represents a runtime patch proposal event in the stream.
    
    Patch proposals are advisory suggestions for file modifications.
    They NEVER directly mutate files - they must go through Rig's validation.
    
    Attributes:
        event_id: Unique identifier for this event
        stream_id: The stream this event belongs to
        sequence: Sequence number within the stream
        proposal_id: The proposal ID
        file_path: The file path to patch
        diff: The patch diff content
        patch_format: The diff format (unified, git, etc.)
        capability_ids: Set of capability IDs required
        validation_status: Status of capability validation
        validation_errors: List of validation errors
        timestamp: When the proposal was generated
        provider_id: The runtime provider ID
        invocation_id: The invocation ID
        metadata: Additional metadata
    """
    event_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    proposal_id: str = PLACEHOLDER_NO_RECEIPT
    file_path: str = ""
    diff: str = ""
    patch_format: str = "unified"
    capability_ids: FrozenSet[str] = field(default_factory=frozenset)
    validation_status: str = "pending"
    validation_errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=_utc_now)
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True
    authoritative: bool = False  # ALWAYS False
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        sequence: int,
        file_path: str,
        diff: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        patch_format: str = "unified",
        capability_ids: Optional[FrozenSet[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimePatchProposalEvent":
        """Create a new patch proposal event."""
        event_id = _generate_deterministic_id(
            "patch_proposal",
            stream_id,
            str(sequence),
            file_path,
            diff[:100] if diff else "",
        )
        proposal_id = _generate_deterministic_id(
            "proposal",
            stream_id,
            str(sequence),
            "patch",
            file_path,
        )
        truncated_diff, _ = _truncate_content(diff, DEFAULT_MAX_CHUNK_SIZE)
        return cls(
            event_id=event_id,
            stream_id=stream_id,
            sequence=sequence,
            proposal_id=proposal_id,
            file_path=file_path,
            diff=truncated_diff,
            patch_format=patch_format,
            capability_ids=capability_ids or frozenset(),
            provider_id=provider_id,
            invocation_id=invocation_id,
            metadata=metadata or {},
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["capability_ids"] = list(self.capability_ids)
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimePatchProposalEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=d.get("event_id", _generate_deterministic_id("patch_proposal", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            proposal_id=d.get("proposal_id", PLACEHOLDER_NO_RECEIPT),
            file_path=d.get("file_path", ""),
            diff=d.get("diff", ""),
            patch_format=d.get("patch_format", "unified"),
            capability_ids=frozenset(d.get("capability_ids", [])),
            validation_status=d.get("validation_status", "pending"),
            validation_errors=d.get("validation_errors", []),
            timestamp=d.get("timestamp", _utc_now()),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
            authoritative=d.get("authoritative", False),
        )


# =============================================================================
# Runtime Warning Event Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeWarningEvent:
    """Represents a runtime stream warning event.
    
    Warning events indicate non-fatal issues during stream execution.
    They are advisory and do not halt the stream.
    
    Attributes:
        event_id: Unique identifier for this event
        stream_id: The stream this event belongs to
        sequence: Sequence number within the stream
        warning_code: The warning code
        message: Human-readable warning message
        details: Additional details
        timestamp: When the warning occurred
        provider_id: The runtime provider ID
        invocation_id: The invocation ID
        metadata: Additional metadata
    """
    event_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    warning_code: RuntimeWarningCode = RuntimeWarningCode.TRUNCATION_APPLIED
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now)
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        sequence: int,
        warning_code: RuntimeWarningCode,
        message: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeWarningEvent":
        """Create a new warning event."""
        event_id = _generate_deterministic_id(
            "warning",
            stream_id,
            str(sequence),
            warning_code.value,
            message[:100] if message else "",
        )
        return cls(
            event_id=event_id,
            stream_id=stream_id,
            sequence=sequence,
            warning_code=warning_code,
            message=message,
            details=details or {},
            provider_id=provider_id,
            invocation_id=invocation_id,
            metadata=metadata or {},
        )
    
    @classmethod
    def truncation(
        cls,
        stream_id: str,
        sequence: int,
        original_length: int,
        truncated_length: int,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeWarningEvent":
        """Create a truncation warning event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            warning_code=RuntimeWarningCode.TRUNCATION_APPLIED,
            message=f"Content truncated from {original_length} to {truncated_length} bytes",
            provider_id=provider_id,
            invocation_id=invocation_id,
            details={
                "original_length": original_length,
                "truncated_length": truncated_length,
            },
        )
    
    @classmethod
    def stalled(
        cls,
        stream_id: str,
        sequence: int,
        missed_heartbeats: int,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeWarningEvent":
        """Create a stalled stream warning event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            warning_code=RuntimeWarningCode.STALLED_DETECTED,
            message=f"Stream stalled: {missed_heartbeats} consecutive missed heartbeats",
            provider_id=provider_id,
            invocation_id=invocation_id,
            details={
                "missed_heartbeats": missed_heartbeats,
                "threshold": DEFAULT_STALLED_THRESHOLD_SECONDS,
            },
        )
    
    @classmethod
    def sequence_gap(
        cls,
        stream_id: str,
        sequence: int,
        expected: int,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeWarningEvent":
        """Create a sequence gap warning event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            warning_code=RuntimeWarningCode.SEQUENCE_GAP,
            message=f"Sequence gap detected: expected {expected}, got {sequence}",
            provider_id=provider_id,
            invocation_id=invocation_id,
            details={
                "expected": expected,
                "actual": sequence,
                "gap": sequence - expected,
            },
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["warning_code"] = self.warning_code.value
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeWarningEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=d.get("event_id", _generate_deterministic_id("warning", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            warning_code=RuntimeWarningCode(d.get("warning_code", "truncation_applied")),
            message=d.get("message", ""),
            details=d.get("details", {}),
            timestamp=d.get("timestamp", _utc_now()),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
        )


# =============================================================================
# Runtime Completion Event Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeCompletionEvent:
    """Represents a runtime stream completion event.
    
    Completion events mark the successful end of a stream.
    They contain final metadata and statistics.
    
    Attributes:
        event_id: Unique identifier for this event
        stream_id: The stream this event belongs to
        sequence: Sequence number within the stream
        receipt_id: The execution receipt ID for this stream
        provider_id: The runtime provider ID
        invocation_id: The invocation ID
        total_chunks: Total number of chunks in the stream
        total_assistant_tokens: Total assistant tokens generated
        total_prompt_tokens: Total prompt tokens used
        total_tokens: Total tokens (prompt + assistant)
        completion_reason: Reason for completion
        summary: Stream summary
        timestamp: When the completion occurred
        metadata: Additional metadata
    """
    event_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    receipt_id: str = PLACEHOLDER_RECEIPT
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    total_chunks: int = 0
    total_assistant_tokens: int = 0
    total_prompt_tokens: int = 0
    total_tokens: int = 0
    completion_reason: str = "normal"
    summary: str = ""
    timestamp: str = field(default_factory=_utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True
    authoritative: bool = False  # ALWAYS False
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        sequence: int,
        receipt_id: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        total_chunks: int = 0,
        total_assistant_tokens: int = 0,
        total_prompt_tokens: int = 0,
        completion_reason: str = "normal",
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeCompletionEvent":
        """Create a new completion event."""
        event_id = _generate_deterministic_id(
            "completion",
            stream_id,
            str(sequence),
            receipt_id,
        )
        total_tokens = total_prompt_tokens + total_assistant_tokens
        truncated_summary, _ = _truncate_content(summary, 1024)
        return cls(
            event_id=event_id,
            stream_id=stream_id,
            sequence=sequence,
            receipt_id=receipt_id,
            provider_id=provider_id,
            invocation_id=invocation_id,
            total_chunks=total_chunks,
            total_assistant_tokens=total_assistant_tokens,
            total_prompt_tokens=total_prompt_tokens,
            total_tokens=total_tokens,
            completion_reason=completion_reason,
            summary=truncated_summary,
            metadata=metadata or {},
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeCompletionEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=d.get("event_id", _generate_deterministic_id("completion", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            receipt_id=d.get("receipt_id", PLACEHOLDER_RECEIPT),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            total_chunks=d.get("total_chunks", 0),
            total_assistant_tokens=d.get("total_assistant_tokens", 0),
            total_prompt_tokens=d.get("total_prompt_tokens", 0),
            total_tokens=d.get("total_tokens", 0),
            completion_reason=d.get("completion_reason", "normal"),
            summary=d.get("summary", ""),
            timestamp=d.get("timestamp", _utc_now()),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
            authoritative=d.get("authoritative", False),
        )


# =============================================================================
# Runtime Failure Event Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeFailureEvent:
    """Represents a runtime stream failure event.
    
    Failure events mark the unsuccessful end of a stream.
    They contain error details and failure categorization.
    
    Attributes:
        event_id: Unique identifier for this event
        stream_id: The stream this event belongs to
        sequence: Sequence number within the stream
        failure_category: Category of the failure
        message: Human-readable error message
        error_details: Detailed error information
        timestamp: When the failure occurred
        provider_id: The runtime provider ID
        invocation_id: The invocation ID
        metadata: Additional metadata
    """
    event_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    failure_category: RuntimeFailureCategory = RuntimeFailureCategory.INTERNAL_ERROR
    message: str = ""
    error_details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now)
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        sequence: int,
        failure_category: RuntimeFailureCategory,
        message: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        error_details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeFailureEvent":
        """Create a new failure event."""
        event_id = _generate_deterministic_id(
            "failure",
            stream_id,
            str(sequence),
            failure_category.value,
            message[:100] if message else "",
        )
        truncated_message, _ = _truncate_content(message, 1024)
        return cls(
            event_id=event_id,
            stream_id=stream_id,
            sequence=sequence,
            failure_category=failure_category,
            message=truncated_message,
            error_details=error_details or {},
            provider_id=provider_id,
            invocation_id=invocation_id,
            metadata=metadata or {},
        )
    
    @classmethod
    def timeout(
        cls,
        stream_id: str,
        sequence: int,
        timeout_seconds: float,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeFailureEvent":
        """Create a timeout failure event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            failure_category=RuntimeFailureCategory.TIMEOUT,
            message=f"Stream timed out after {timeout_seconds}s",
            provider_id=provider_id,
            invocation_id=invocation_id,
            error_details={
                "timeout_seconds": timeout_seconds,
                "type": "stream_timeout",
            },
        )
    
    @classmethod
    def connection_error(
        cls,
        stream_id: str,
        sequence: int,
        error: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeFailureEvent":
        """Create a connection error failure event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            failure_category=RuntimeFailureCategory.CONNECTION_ERROR,
            message=f"Connection error: {error}",
            provider_id=provider_id,
            invocation_id=invocation_id,
            error_details={
                "error": error,
                "type": "connection_error",
            },
        )
    
    @classmethod
    def capability_error(
        cls,
        stream_id: str,
        sequence: int,
        capability_id: str,
        error: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
    ) -> "RuntimeFailureEvent":
        """Create a capability error failure event."""
        return cls.create(
            stream_id=stream_id,
            sequence=sequence,
            failure_category=RuntimeFailureCategory.CAPABILITY_ERROR,
            message=f"Capability error: {error}",
            provider_id=provider_id,
            invocation_id=invocation_id,
            error_details={
                "capability_id": capability_id,
                "error": error,
                "type": "capability_error",
            },
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["failure_category"] = self.failure_category.value
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeFailureEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=d.get("event_id", _generate_deterministic_id("failure", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            failure_category=RuntimeFailureCategory(d.get("failure_category", "internal_error")),
            message=d.get("message", ""),
            error_details=d.get("error_details", {}),
            timestamp=d.get("timestamp", _utc_now()),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
        )


# =============================================================================
# Runtime Stream Buffer Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeStreamBuffer:
    """Represents a bounded buffer for runtime stream chunks.
    
    The stream buffer:
    - Enforces maximum size limits
    - Maintains chunks in sequence order
    - Provides truncation awareness
    - Is replay-safe
    - Is projection-safe
    
    Attributes:
        buffer_id: Unique identifier for the buffer
        stream_id: The stream this buffer belongs to
        max_size: Maximum buffer size in bytes
        chunks: List of chunks in the buffer (in sequence order)
        current_size: Current buffer size in bytes
        truncated: Whether the buffer was truncated
        oldest_sequence: Sequence number of the oldest chunk
        newest_sequence: Sequence number of the newest chunk
        evicted_count: Number of chunks evicted due to size limits
        created_at: When the buffer was created
        updated_at: When the buffer was last updated
    """
    buffer_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    max_size: int = DEFAULT_MAX_BUFFER_SIZE
    chunks: Tuple[RuntimeStreamChunk, ...] = field(default_factory=tuple)
    current_size: int = 0
    truncated: bool = False
    oldest_sequence: int = PLACEHOLDER_SEQUENCE
    newest_sequence: int = PLACEHOLDER_SEQUENCE
    evicted_count: int = 0
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    advisory_only: bool = True  # ALWAYS True
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
        # Update computed fields
        if self.chunks:
            object.__setattr__(self, 'oldest_sequence', self.chunks[0].sequence)
            object.__setattr__(self, 'newest_sequence', self.chunks[-1].sequence)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        max_size: int = DEFAULT_MAX_BUFFER_SIZE,
        buffer_id: Optional[str] = None,
    ) -> "RuntimeStreamBuffer":
        """Create a new empty stream buffer."""
        bid = buffer_id or _generate_deterministic_id("buffer", stream_id, str(max_size))
        return cls(
            buffer_id=bid,
            stream_id=stream_id,
            max_size=max_size,
            chunks=(),
            current_size=0,
            truncated=False,
            oldest_sequence=PLACEHOLDER_SEQUENCE,
            newest_sequence=PLACEHOLDER_SEQUENCE,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d: Dict[str, Any] = {
            "buffer_id": self.buffer_id,
            "stream_id": self.stream_id,
            "max_size": self.max_size,
            "chunks": [c.to_dict() for c in self.chunks],
            "current_size": self.current_size,
            "truncated": self.truncated,
            "oldest_sequence": self.oldest_sequence,
            "newest_sequence": self.newest_sequence,
            "evicted_count": self.evicted_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "advisory_only": self.advisory_only,
        }
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeStreamBuffer":
        """Deserialize from dictionary."""
        chunks = tuple(
            RuntimeStreamChunk.from_dict(c) for c in d.get("chunks", [])
        )
        return cls(
            buffer_id=d.get("buffer_id", _generate_deterministic_id("buffer", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            max_size=d.get("max_size", DEFAULT_MAX_BUFFER_SIZE),
            chunks=chunks,
            current_size=d.get("current_size", 0),
            truncated=d.get("truncated", False),
            oldest_sequence=d.get("oldest_sequence", PLACEHOLDER_SEQUENCE),
            newest_sequence=d.get("newest_sequence", PLACEHOLDER_SEQUENCE),
            evicted_count=d.get("evicted_count", 0),
            created_at=d.get("created_at", _utc_now()),
            updated_at=d.get("updated_at", _utc_now()),
            advisory_only=d.get("advisory_only", True),
        )


# =============================================================================
# Runtime Sequence State Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeSequenceState:
    """Represents the sequence state of a runtime stream.
    
    Tracks:
    - Last received sequence number
    - Expected next sequence number
    - Duplicate detection
    - Gap detection
    - Integrity flags
    
    Attributes:
        state_id: Unique identifier for this state
        stream_id: The stream this state belongs to
        last_sequence: Last received sequence number
        next_expected: Next expected sequence number
        total_received: Total number of events received
        duplicates_detected: List of duplicate sequence numbers detected
        gaps_detected: List of (expected, actual) tuples for gaps
        integrity_flags: Set of integrity flags
        provider_id: The runtime provider ID
        invocation_id: The invocation ID
        created_at: When the state was created
        updated_at: When the state was last updated
    """
    state_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    last_sequence: int = PLACEHOLDER_SEQUENCE
    next_expected: int = 0
    total_received: int = 0
    duplicates_detected: Tuple[Tuple[int, int], ...] = field(default_factory=tuple)
    gaps_detected: Tuple[Tuple[int, int], ...] = field(default_factory=tuple)
    integrity_flags: FrozenSet[str] = field(default_factory=frozenset)
    provider_id: str = PLACEHOLDER_PROVIDER
    invocation_id: str = PLACEHOLDER_INVOCATION
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    advisory_only: bool = True  # ALWAYS True
    
    def __post_init__(self):
        object.__setattr__(self, 'advisory_only', True)
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        provider_id: str = PLACEHOLDER_PROVIDER,
        invocation_id: str = PLACEHOLDER_INVOCATION,
        state_id: Optional[str] = None,
    ) -> "RuntimeSequenceState":
        """Create a new sequence state."""
        sid = state_id or _generate_deterministic_id("seq_state", stream_id)
        return cls(
            state_id=sid,
            stream_id=stream_id,
            provider_id=provider_id,
            invocation_id=invocation_id,
        )
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeSequenceState":
        """Deserialize from dictionary."""
        return cls(
            state_id=d.get("state_id", _generate_deterministic_id("seq_state", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            last_sequence=d.get("last_sequence", PLACEHOLDER_SEQUENCE),
            next_expected=d.get("next_expected", 0),
            total_received=d.get("total_received", 0),
            duplicates_detected=tuple(
                tuple(pair) for pair in d.get("duplicates_detected", [])
            ),
            gaps_detected=tuple(
                tuple(pair) for pair in d.get("gaps_detected", [])
            ),
            integrity_flags=frozenset(d.get("integrity_flags", [])),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            created_at=d.get("created_at", _utc_now()),
            updated_at=d.get("updated_at", _utc_now()),
            advisory_only=d.get("advisory_only", True),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "state_id": self.state_id,
            "stream_id": self.stream_id,
            "last_sequence": self.last_sequence,
            "next_expected": self.next_expected,
            "total_received": self.total_received,
            "duplicates_detected": [list(pair) for pair in self.duplicates_detected],
            "gaps_detected": [list(pair) for pair in self.gaps_detected],
            "integrity_flags": list(self.integrity_flags),
            "provider_id": self.provider_id,
            "invocation_id": self.invocation_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "advisory_only": self.advisory_only,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


# =============================================================================
# Stream Event Type (Union-like)
# =============================================================================

# Type alias for stream events
RuntimeStreamEvent = (
    RuntimeStreamChunk |
    RuntimeStatusEvent |
    RuntimeHeartbeatEvent |
    RuntimeToolProposalEvent |
    RuntimePatchProposalEvent |
    RuntimeWarningEvent |
    RuntimeCompletionEvent |
    RuntimeFailureEvent
)


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Constants
    "PLACEHOLDER_STREAM_ID",
    "PLACEHOLDER_SEQUENCE",
    "PLACEHOLDER_CHANNEL",
    "PLACEHOLDER_CONTENT",
    "PLACEHOLDER_PROVIDER",
    "PLACEHOLDER_INVOCATION",
    "PLACEHOLDER_RECEIPT",
    "PLACEHOLDER_NO_RECEIPT",
    "PLACEHOLDER_TIMESTAMP",
    "DEFAULT_MAX_CHUNK_SIZE",
    "DEFAULT_MAX_BUFFER_SIZE",
    "DEFAULT_MAX_SEQUENCE_GAP",
    "DEFAULT_STREAM_TIMEOUT_SECONDS",
    "DEFAULT_HEARTBEAT_INTERVAL_SECONDS",
    "DEFAULT_STALLED_THRESHOLD_SECONDS",
    # Enums
    "RuntimeStreamChannel",
    "RuntimeStreamEventKind",
    "RuntimeStreamStatus",
    "RuntimeStreamStateKind",
    "RuntimeProposalKind",
    "RuntimeWarningCode",
    "RuntimeFailureCategory",
    # Models
    "RuntimeStreamChunk",
    "RuntimeStatusEvent",
    "RuntimeHeartbeatEvent",
    "RuntimeToolProposalEvent",
    "RuntimePatchProposalEvent",
    "RuntimeWarningEvent",
    "RuntimeCompletionEvent",
    "RuntimeFailureEvent",
    "RuntimeStreamBuffer",
    "RuntimeSequenceState",
    # Type alias
    "RuntimeStreamEvent",
    # Helper functions
    "_generate_deterministic_id",
    "_utc_now",
    "_serialize_enum",
    "_serialize_optional_enum",
    "_truncate_content",
]
