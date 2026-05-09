"""Runtime Stream Projection Pipeline for Rig.

This module provides the projection pipeline for runtime stream events.

Core doctrine:
- Frontend NEVER consumes raw subprocess state directly
- UI streams projections only
- All projections are deterministic and replay-safe
- All projections are bounded in size
- All models are pure frozen dataclasses
- All models are JSON-serializable

file: src/rig/domain/runtime_projection.py
"""

from __future__ import annotations

import warnings
warnings.warn(
    ("rig.domain.runtime_projection is deprecated for streaming orchestration. Streaming refresh orchestration: import from rig.domain.runtime_streaming. Projection semantics: see ADR 0002. See ADR 0004."),
    DeprecationWarning,
    stacklevel=2,
)

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime_streaming import (
        RuntimeProposalKind,
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
    )
    from rig.domain.projections import (
        WidgetProjection,
        IntentProjection,
        UIProjection,
    )
from rig.domain.runtime_streaming._types import (
    PLACEHOLDER_STREAM_ID,
    PLACEHOLDER_SEQUENCE,
    PLACEHOLDER_PROVIDER,
    PLACEHOLDER_INVOCATION,
    PLACEHOLDER_NO_RECEIPT,
    DEFAULT_MAX_CHUNK_SIZE,
    DEFAULT_MAX_BUFFER_SIZE,
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
    RuntimeProposalKind,
    RuntimeWarningCode,
    RuntimeFailureCategory,
    RuntimeStreamEvent,
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
    RuntimeExecutionReceipt,
)
from rig.domain.projections import (
    WidgetProjection,
    IntentProjection,
    UIProjection,
    ProjectionLayout,
)


# =============================================================================
# Constants
# =============================================================================

PLACEHOLDER_PROJECTION_ID = "not_set"
PLACEHOLDER_WIDGET_ID = "no_widget"

# Projection buffer sizes
MAX_PROJECTION_CHUNKS = 100
MAX_PROJECTION_TOKENS = 10000
MAX_PROJECTION_BYTES = 100 * 1024  # 100 KB
MAX_PROPOSAL_SUMMARY_LENGTH = 512
MAX_STATUS_MESSAGE_LENGTH = 256

# Projection categories
PROJECTION_CATEGORY_STREAM = "stream"
PROJECTION_CATEGORY_STATUS = "status"
PROJECTION_CATEGORY_PROPOSAL = "proposal"
PROJECTION_CATEGORY_DIAGNOSTIC = "diagnostic"
PROJECTION_CATEGORY_SUMMARY = "summary"


# =============================================================================
# Enums
# =============================================================================

class RuntimeProjectionKind(Enum):
    """Kinds of runtime projections."""
    CHUNK = "chunk"                   # Stream chunk projection
    STATUS = "status"                 # Status update projection
    HEARTBEAT = "heartbeat"           # Heartbeat projection
    TOOL_PROPOSAL = "tool_proposal"   # Tool proposal projection
    PATCH_PROPOSAL = "patch_proposal" # Patch proposal projection
    WARNING = "warning"                # Warning projection
    COMPLETION = "completion"         # Completion projection
    FAILURE = "failure"               # Failure projection
    SUMMARY = "summary"               # Stream summary projection


class RuntimeProjectionStatus(Enum):
    """Status of a runtime projection."""
    PENDING = "pending"               # Projection not yet available
    ACTIVE = "active"                 # Projection is live
    COMPLETE = "complete"             # Projection is complete
    STALE = "stale"                  # Projection is stale
    ARCHIVED = "archived"             # Projection is archived


class RuntimeProjectionSeverity(Enum):
    """Severity levels for runtime projections."""
    DEBUG = "debug"                   # Debug information
    INFO = "info"                     # Normal information
    WARNING = "warning"                # Warning condition
    ERROR = "error"                   # Error condition
    CRITICAL = "critical"             # Critical condition


class RuntimeProjectionScope(Enum):
    """Scope of a runtime projection."""
    EPHEMERAL = "ephemeral"           # Temporary, not stored
    SESSION = "session"               # Session-scoped
    RECEIPT = "receipt"               # Backed by receipt
    REPLAY = "replay"                 # Replay-safe


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


def _truncate_text(text: str, max_length: int) -> str:
    """Truncate text to max length, preserving line boundaries where possible."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_newline = truncated.rfind('\n')
    if last_newline > max_length * 0.8:  # Only truncate at newline if we can save significant space
        truncated = truncated[:last_newline]
    if truncated.endswith('\n'):
        truncated = truncated[:-1]
    return truncated + "..." if len(truncated) < len(text) else truncated


def _safe_content(content: str) -> str:
    """Make content safe for projection (escape/remove control characters)."""
    if not content:
        return ""
    # Remove null bytes and other control characters
    safe = ''.join(
        char if 32 <= ord(char) <= 126 or char in '\n\r\t' else '?'
        for char in content
    )
    return safe


# =============================================================================
# Runtime Projection Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeStreamProjection:
    """Represents a projection of runtime stream data.
    
    Stream projections are:
    - Deterministic and replay-safe
    - Bounded in size
    - Projection-safe
    - Advisory-only
    - Never directly executable
    
    Attributes:
        projection_id: Unique identifier for the projection
        kind: The kind of projection
        stream_id: The stream this projection relates to
        invocation_id: The runtime invocation ID
        provider_id: The runtime provider ID
        sequence: Sequence number in the stream
        content: Projected content (safe/truncated)
        content_truncated: Whether content was truncated
        channel: The source channel
        timestamp: When the projection was created
        status: Projection status
        severity: Projection severity
        scope: Projection scope
        token_count: Estimated token count
        byte_count: Byte count of content
        metadata: Additional metadata
        advisory_only: ALWAYS True
        authoritative: ALWAYS False
    """
    projection_id: str
    kind: RuntimeProjectionKind = RuntimeProjectionKind.CHUNK
    stream_id: str = PLACEHOLDER_STREAM_ID
    invocation_id: str = PLACEHOLDER_INVOCATION
    provider_id: str = PLACEHOLDER_PROVIDER
    sequence: int = PLACEHOLDER_SEQUENCE
    content: str = ""
    content_truncated: bool = False
    channel: str = "assistant"
    timestamp: str = field(default_factory=_utc_now)
    status: RuntimeProjectionStatus = RuntimeProjectionStatus.PENDING
    severity: RuntimeProjectionSeverity = RuntimeProjectionSeverity.INFO
    scope: RuntimeProjectionScope = RuntimeProjectionScope.EPHEMERAL
    token_count: int = 0
    byte_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    advisory_only: bool = True  # ALWAYS True - projections are advisory only
    authoritative: bool = False  # ALWAYS False - projections are never authoritative
    
    def __post_init__(self):
        # Ensure invariants
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
        # Auto-calculate byte_count
        object.__setattr__(self, 'byte_count', len(self.content.encode('utf-8', errors='replace')))
    
    @classmethod
    def from_chunk(
        cls,
        chunk: RuntimeStreamChunk,
        max_content_length: int = MAX_PROJECTION_BYTES // 4,
    ) -> "RuntimeStreamProjection":
        """Create a projection from a stream chunk."""
        projection_id = _generate_deterministic_id(
            "stream_proj",
            chunk.stream_id,
            str(chunk.sequence),
            chunk.channel.value,
        )
        
        # Make content safe and truncate
        safe_content = _safe_content(chunk.content)
        truncated_content = _truncate_text(safe_content, max_content_length)
        was_truncated = len(truncated_content) < len(safe_content)
        
        # Estimate token count (rough estimate: 4 chars = 1 token)
        token_count = max(1, len(truncated_content) // 4)
        
        return cls(
            projection_id=projection_id,
            kind=RuntimeProjectionKind.CHUNK,
            stream_id=chunk.stream_id,
            invocation_id=chunk.invocation_id,
            provider_id=chunk.provider_id,
            sequence=chunk.sequence,
            content=truncated_content,
            content_truncated=was_truncated or chunk.truncated,
            channel=chunk.channel.value,
            timestamp=chunk.timestamp,
            status=RuntimeProjectionStatus.ACTIVE,
            severity=RuntimeProjectionSeverity.INFO,
            scope=RuntimeProjectionScope.EPHEMERAL,
            token_count=token_count,
            metadata={"original_chunk_id": chunk.chunk_id},
        )
    
    @classmethod
    def from_status(
        cls,
        event: RuntimeStatusEvent,
    ) -> "RuntimeStreamProjection":
        """Create a projection from a status event."""
        projection_id = _generate_deterministic_id(
            "status_proj",
            event.stream_id,
            str(event.sequence),
            event.status.value,
        )
        
        safe_message = _safe_content(event.message)
        truncated_message = _truncate_text(safe_message, MAX_STATUS_MESSAGE_LENGTH)
        
        severity = cls._status_to_severity(event.status)
        
        return cls(
            projection_id=projection_id,
            kind=RuntimeProjectionKind.STATUS,
            stream_id=event.stream_id,
            invocation_id=event.invocation_id,
            provider_id=event.provider_id,
            sequence=event.sequence,
            content=truncated_message or event.status.value,
            content_truncated=len(truncated_message) < len(safe_message) if safe_message else False,
            channel="status",
            timestamp=event.timestamp,
            status=RuntimeProjectionStatus.ACTIVE if event.status == RuntimeStreamStatus.ACTIVE else RuntimeProjectionStatus.COMPLETE,
            severity=severity,
            scope=RuntimeProjectionScope.EPHEMERAL,
            metadata={
                "status": event.status.value,
                "previous_status": event.previous_status.value,
                "reason": event.reason,
            },
        )
    
    @classmethod
    def from_tool_proposal(
        cls,
        event: RuntimeToolProposalEvent,
    ) -> "RuntimeStreamProjection":
        """Create a projection from a tool proposal event."""
        projection_id = _generate_deterministic_id(
            "proposal_proj",
            event.stream_id,
            str(event.sequence),
            event.proposal_kind.value,
        )
        
        # Create safe summary
        safe_payload = _safe_content(json.dumps(event.payload, default=str))
        truncated_payload = _truncate_text(safe_payload, MAX_PROPOSAL_SUMMARY_LENGTH)
        
        # Build content
        content = f"Proposal: {event.proposal_kind.value}\n{truncated_payload}"
        
        return cls(
            projection_id=projection_id,
            kind=RuntimeProjectionKind.TOOL_PROPOSAL,
            stream_id=event.stream_id,
            invocation_id=event.invocation_id,
            provider_id=event.provider_id,
            sequence=event.sequence,
            content=content,
            content_truncated=len(truncated_payload) < len(safe_payload) if safe_payload else False,
            channel="proposal",
            timestamp=event.timestamp,
            status=RuntimeProjectionStatus.ACTIVE,
            severity=RuntimeProjectionSeverity.WARNING,
            scope=RuntimeProjectionScope.RECEIPT,
            metadata={
                "proposal_id": event.proposal_id,
                "proposal_kind": event.proposal_kind.value,
                "validation_status": event.validation_status,
                "capability_ids": list(event.capability_ids),
            },
        )
    
    @classmethod
    def from_patch_proposal(
        cls,
        event: RuntimePatchProposalEvent,
    ) -> "RuntimeStreamProjection":
        """Create a projection from a patch proposal event."""
        projection_id = _generate_deterministic_id(
            "patch_proj",
            event.stream_id,
            str(event.sequence),
            event.file_path,
        )
        
        # Create safe summary
        safe_diff = _safe_content(event.diff)
        truncated_diff = _truncate_text(safe_diff, MAX_PROPOSAL_SUMMARY_LENGTH)
        
        content = f"Patch Proposal for {event.file_path}\nDiff:\n{truncated_diff}"
        
        return cls(
            projection_id=projection_id,
            kind=RuntimeProjectionKind.PATCH_PROPOSAL,
            stream_id=event.stream_id,
            invocation_id=event.invocation_id,
            provider_id=event.provider_id,
            sequence=event.sequence,
            content=content,
            content_truncated=len(truncated_diff) < len(safe_diff) if safe_diff else False,
            channel="proposal",
            timestamp=event.timestamp,
            status=RuntimeProjectionStatus.ACTIVE,
            severity=RuntimeProjectionSeverity.WARNING,
            scope=RuntimeProjectionScope.RECEIPT,
            metadata={
                "proposal_id": event.proposal_id,
                "file_path": event.file_path,
                "patch_format": event.patch_format,
                "validation_status": event.validation_status,
            },
        )
    
    @classmethod
    def from_warning(
        cls,
        event: RuntimeWarningEvent,
    ) -> "RuntimeStreamProjection":
        """Create a projection from a warning event."""
        projection_id = _generate_deterministic_id(
            "warning_proj",
            event.stream_id,
            str(event.sequence),
            event.warning_code.value,
        )
        
        safe_message = _safe_content(event.message)
        truncated_message = _truncate_text(safe_message, MAX_STATUS_MESSAGE_LENGTH)
        
        severity = cls._warning_code_to_severity(event.warning_code)
        
        content = f"Warning ({event.warning_code.value}): {truncated_message}"
        
        return cls(
            projection_id=projection_id,
            kind=RuntimeProjectionKind.WARNING,
            stream_id=event.stream_id,
            invocation_id=event.invocation_id,
            provider_id=event.provider_id,
            sequence=event.sequence,
            content=content,
            content_truncated=len(truncated_message) < len(safe_message) if safe_message else False,
            channel="warning",
            timestamp=event.timestamp,
            status=RuntimeProjectionStatus.ACTIVE,
            severity=severity,
            scope=RuntimeProjectionScope.EPHEMERAL,
            metadata={
                "warning_code": event.warning_code.value,
                "details": event.details,
            },
        )
    
    @classmethod
    def from_completion(
        cls,
        event: RuntimeCompletionEvent,
    ) -> "RuntimeStreamProjection":
        """Create a projection from a completion event."""
        projection_id = _generate_deterministic_id(
            "completion_proj",
            event.stream_id,
            str(event.sequence),
            event.receipt_id,
        )
        
        safe_summary = _safe_content(event.summary)
        truncated_summary = _truncate_text(safe_summary, MAX_STATUS_MESSAGE_LENGTH)
        
        content = f"Stream completed ({event.completion_reason})\nT+: {event.total_prompt_tokens}, TA: {event.total_assistant_tokens}, Total: {event.total_tokens}\n{truncated_summary}"
        
        return cls(
            projection_id=projection_id,
            kind=RuntimeProjectionKind.COMPLETION,
            stream_id=event.stream_id,
            invocation_id=event.invocation_id,
            provider_id=event.provider_id,
            sequence=event.sequence,
            content=content,
            content_truncated=len(truncated_summary) < len(safe_summary) if safe_summary else False,
            channel="completion",
            timestamp=event.timestamp,
            status=RuntimeProjectionStatus.COMPLETE,
            severity=RuntimeProjectionSeverity.INFO,
            scope=RuntimeProjectionScope.RECEIPT,
            metadata={
                "receipt_id": event.receipt_id,
                "completion_reason": event.completion_reason,
                "total_chunks": event.total_chunks,
                "total_tokens": event.total_tokens,
            },
        )
    
    @classmethod
    def from_failure(
        cls,
        event: RuntimeFailureEvent,
    ) -> "RuntimeStreamProjection":
        """Create a projection from a failure event."""
        projection_id = _generate_deterministic_id(
            "failure_proj",
            event.stream_id,
            str(event.sequence),
            event.failure_category.value,
        )
        
        safe_message = _safe_content(event.message)
        truncated_message = _truncate_text(safe_message, MAX_STATUS_MESSAGE_LENGTH)
        
        severity = cls._failure_category_to_severity(event.failure_category)
        
        content = f"Stream failed ({event.failure_category.value}): {truncated_message}"
        
        return cls(
            projection_id=projection_id,
            kind=RuntimeProjectionKind.FAILURE,
            stream_id=event.stream_id,
            invocation_id=event.invocation_id,
            provider_id=event.provider_id,
            sequence=event.sequence,
            content=content,
            content_truncated=len(truncated_message) < len(safe_message) if safe_message else False,
            channel="error",
            timestamp=event.timestamp,
            status=RuntimeProjectionStatus.COMPLETE,
            severity=severity,
            scope=RuntimeProjectionScope.RECEIPT,
            metadata={
                "failure_category": event.failure_category.value,
                "error_details": event.error_details,
            },
        )
    
    @staticmethod
    def _status_to_severity(status: RuntimeStreamStatus) -> RuntimeProjectionSeverity:
        """Map stream status to projection severity."""
        if status in [RuntimeStreamStatus.FAILED, RuntimeStreamStatus.TIMED_OUT]:
            return RuntimeProjectionSeverity.ERROR
        if status == RuntimeStreamStatus.STALLED:
            return RuntimeProjectionSeverity.WARNING
        if status == RuntimeStreamStatus.CONNECTING:
            return RuntimeProjectionSeverity.INFO
        return RuntimeProjectionSeverity.INFO
    
    @staticmethod
    def _warning_code_to_severity(code: RuntimeWarningCode) -> RuntimeProjectionSeverity:
        """Map warning code to projection severity."""
        if code in [RuntimeWarningCode.TOKEN_LIMIT_APPROACHING, RuntimeWarningCode.MEMORY_PRESSURE]:
            return RuntimeProjectionSeverity.WARNING
        if code in [RuntimeWarningCode.CAPABILITY_MISMATCH, RuntimeWarningCode.RATE_LIMITED]:
            return RuntimeProjectionSeverity.ERROR
        return RuntimeProjectionSeverity.WARNING
    
    @staticmethod
    def _failure_category_to_severity(category: RuntimeFailureCategory) -> RuntimeProjectionSeverity:
        """Map failure category to projection severity."""
        if category in [
            RuntimeFailureCategory.INTERNAL_ERROR,
            RuntimeFailureCategory.CONNECTION_ERROR,
        ]:
            return RuntimeProjectionSeverity.ERROR
        if category in [
            RuntimeFailureCategory.TIMEOUT,
            RuntimeFailureCategory.CAPABILITY_ERROR,
            RuntimeFailureCategory.TRUST_ERROR,
            RuntimeFailureCategory.CONSTRAINT_ERROR,
        ]:
            return RuntimeProjectionSeverity.CRITICAL
        return RuntimeProjectionSeverity.ERROR
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = asdict(self)
        d["kind"] = self.kind.value
        d["status"] = self.status.value
        d["severity"] = self.severity.value
        d["scope"] = self.scope.value
        return d
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    def to_widget(self) -> WidgetProjection:
        """Convert to a WidgetProjection for UI."""
        return WidgetProjection(
            type=f"RuntimeStream_{self.kind.value.capitalize()}",
            id=self.projection_id,
            data={
                "content": self.content,
                "truncated": self.content_truncated,
                "sequence": self.sequence,
                "timestamp": self.timestamp,
                "channel": self.channel,
                "severity": self.severity.value,
                "token_count": self.token_count,
                "byte_count": self.byte_count,
                **self.metadata,
            },
            actions=[],
        )
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeStreamProjection":
        """Deserialize from dictionary."""
        return cls(
            projection_id=d.get("projection_id", _generate_deterministic_id("stream_proj", "unknown")),
            kind=RuntimeProjectionKind(d.get("kind", "chunk")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            invocation_id=d.get("invocation_id", PLACEHOLDER_INVOCATION),
            provider_id=d.get("provider_id", PLACEHOLDER_PROVIDER),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            content=d.get("content", ""),
            content_truncated=d.get("content_truncated", False),
            channel=d.get("channel", "assistant"),
            timestamp=d.get("timestamp", _utc_now()),
            status=RuntimeProjectionStatus(d.get("status", "pending")),
            severity=RuntimeProjectionSeverity(d.get("severity", "info")),
            scope=RuntimeProjectionScope(d.get("scope", "ephemeral")),
            token_count=d.get("token_count", 0),
            byte_count=d.get("byte_count", 0),
            metadata=d.get("metadata", {}),
            advisory_only=d.get("advisory_only", True),
            authoritative=d.get("authoritative", False),
        )


# =============================================================================
# Runtime Stream Projection Buffer Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeStreamProjectionBuffer:
    """Bounded buffer for runtime stream projections.
    
    The projection buffer:
    - Enforces maximum size limits
    - Maintains projections in sequence order
    - Provides truncation awareness
    - Is replay-safe
    - Is projection-safe
    
    Attributes:
        buffer_id: Unique identifier for the buffer
        stream_id: The stream this buffer belongs to
        max_size: Maximum number of projections
        max_bytes: Maximum total bytes
        projections: List of projections in sequence order
        current_bytes: Current total bytes
        truncated: Whether the buffer was truncated
        oldest_sequence: Sequence of oldest projection
        newest_sequence: Sequence of newest projection
        evicted_count: Number of projections evicted
        created_at: When the buffer was created
        updated_at: When the buffer was last updated
    """
    buffer_id: str
    stream_id: str = PLACEHOLDER_STREAM_ID
    max_size: int = MAX_PROJECTION_CHUNKS
    max_bytes: int = MAX_PROJECTION_BYTES
    projections: Tuple[RuntimeStreamProjection, ...] = field(default_factory=tuple)
    current_bytes: int = 0
    truncated: bool = False
    oldest_sequence: int = PLACEHOLDER_SEQUENCE
    newest_sequence: int = PLACEHOLDER_SEQUENCE
    evicted_count: int = 0
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    
    def __post_init__(self):
        if self.projections:
            object.__setattr__(self, 'oldest_sequence', self.projections[0].sequence)
            object.__setattr__(self, 'newest_sequence', self.projections[-1].sequence)
            object.__setattr__(self, 'current_bytes', 
                sum(p.byte_count for p in self.projections))
    
    @classmethod
    def create(
        cls,
        stream_id: str,
        max_size: int = MAX_PROJECTION_CHUNKS,
        max_bytes: int = MAX_PROJECTION_BYTES,
    ) -> "RuntimeStreamProjectionBuffer":
        """Create a new empty projection buffer."""
        buffer_id = _generate_deterministic_id("proj_buffer", stream_id, str(max_size), str(max_bytes))
        return cls(
            buffer_id=buffer_id,
            stream_id=stream_id,
            max_size=max_size,
            max_bytes=max_bytes,
            projections=(),
            current_bytes=0,
            truncated=False,
            oldest_sequence=PLACEHOLDER_SEQUENCE,
            newest_sequence=PLACEHOLDER_SEQUENCE,
        )
    
    def add(self, projection: RuntimeStreamProjection) -> "RuntimeStreamProjectionBuffer":
        """Add a projection to the buffer, evicting old ones if needed.
        
        This method returns a NEW buffer with the projection added.
        It enforces size and byte limits.
        """
        new_projections = list(self.projections)
        new_bytes = self.current_bytes + projection.byte_count
        new_evicted = self.evicted_count
        new_truncated = self.truncated
        
        # Evict old projections if we exceed limits
        while (len(new_projections) >= self.max_size or new_bytes > self.max_bytes) and new_projections:
            oldest = new_projections.pop(0)
            new_bytes -= oldest.byte_count
            new_evicted += 1
            new_truncated = True
        
        # Add new projection
        new_projections.append(projection)
        new_bytes += projection.byte_count
        
        # Determine new sequence bounds
        if new_projections:
            new_oldest = new_projections[0].sequence
            new_newest = new_projections[-1].sequence
        else:
            new_oldest = PLACEHOLDER_SEQUENCE
            new_newest = PLACEHOLDER_SEQUENCE
        
        return type(self)(
            buffer_id=self.buffer_id,
            stream_id=self.stream_id,
            max_size=self.max_size,
            max_bytes=self.max_bytes,
            projections=tuple(new_projections),
            current_bytes=new_bytes,
            truncated=new_truncated,
            oldest_sequence=new_oldest,
            newest_sequence=new_newest,
            evicted_count=new_evicted,
            created_at=self.created_at,
            updated_at=_utc_now(),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "buffer_id": self.buffer_id,
            "stream_id": self.stream_id,
            "max_size": self.max_size,
            "max_bytes": self.max_bytes,
            "projections": [p.to_dict() for p in self.projections],
            "current_bytes": self.current_bytes,
            "truncated": self.truncated,
            "oldest_sequence": self.oldest_sequence,
            "newest_sequence": self.newest_sequence,
            "evicted_count": self.evicted_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeStreamProjectionBuffer":
        """Deserialize from dictionary."""
        projections = tuple(
            RuntimeStreamProjection.from_dict(p) for p in d.get("projections", [])
        )
        return cls(
            buffer_id=d.get("buffer_id", _generate_deterministic_id("proj_buffer", "unknown")),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            max_size=d.get("max_size", MAX_PROJECTION_CHUNKS),
            max_bytes=d.get("max_bytes", MAX_PROJECTION_BYTES),
            projections=projections,
            created_at=d.get("created_at", _utc_now()),
            updated_at=d.get("updated_at", _utc_now()),
        )


# =============================================================================
# Runtime Stream Projection Builder
# =============================================================================

class RuntimeProjectionBuilder:
    """Builder for runtime stream projections.
    
    This class:
    - Converts stream events to projections
    - Manages projection buffers
    - Handles different event types
    - Ensures projection safety
    - Provides replay compatibility
    
    Properties:
    - Pure transformation (no side effects)
    - Deterministic output
    - Replay-safe
    - Bounded memory usage
    """
    
    def __init__(
        self,
        builder_id: Optional[str] = None,
        max_buffer_size: int = MAX_PROJECTION_CHUNKS,
        max_buffer_bytes: int = MAX_PROJECTION_BYTES,
    ):
        """Initialize the projection builder.
        
        args:
            builder_id: Unique builder ID
            max_buffer_size: Maximum projections per buffer
            max_buffer_bytes: Maximum bytes per buffer
        """
        self.builder_id = builder_id or _generate_deterministic_id("proj_builder")
        self.max_buffer_size = max_buffer_size
        self.max_buffer_bytes = max_buffer_bytes
        
        # Buffer registry
        self._buffers: Dict[str, RuntimeStreamProjectionBuffer] = {}
        self._build_count = 0
    
    def _get_or_create_buffer(self, stream_id: str) -> RuntimeStreamProjectionBuffer:
        """Get or create a projection buffer for a stream."""
        if stream_id not in self._buffers:
            self._buffers[stream_id] = RuntimeStreamProjectionBuffer.create(
                stream_id=stream_id,
                max_size=self.max_buffer_size,
                max_bytes=self.max_buffer_bytes,
            )
        return self._buffers[stream_id]
    
    def build_from_chunk(
        self,
        chunk: RuntimeStreamChunk,
        stream_id: Optional[str] = None,
    ) -> RuntimeStreamProjection:
        """Build a projection from a stream chunk."""
        self._build_count += 1
        return RuntimeStreamProjection.from_chunk(chunk)
    
    def build_from_status(
        self,
        event: RuntimeStatusEvent,
    ) -> RuntimeStreamProjection:
        """Build a projection from a status event."""
        self._build_count += 1
        return RuntimeStreamProjection.from_status(event)
    
    def build_from_heartbeat(
        self,
        event: RuntimeHeartbeatEvent,
    ) -> RuntimeStreamProjection:
        """Build a projection from a heartbeat event."""
        self._build_count += 1
        # Heartbeats typically don't create visible projections
        # but we track them for completeness
        projection_id = _generate_deterministic_id(
            "heartbeat_proj",
            event.stream_id,
            str(event.sequence),
        )
        return RuntimeStreamProjection(
            projection_id=projection_id,
            kind=RuntimeProjectionKind.HEARTBEAT,
            stream_id=event.stream_id,
            invocation_id=event.invocation_id,
            provider_id=event.provider_id,
            sequence=event.sequence,
            content=f"Heartbeat (missed: {event.missed_count})",
            channel="heartbeat",
            timestamp=event.timestamp,
            status=RuntimeProjectionStatus.ACTIVE,
            severity=RuntimeProjectionSeverity.DEBUG,
            scope=RuntimeProjectionScope.EPHEMERAL,
            metadata={
                "missed_count": event.missed_count,
                "interval_seconds": event.interval_seconds,
            },
        )
    
    def build_from_tool_proposal(
        self,
        event: RuntimeToolProposalEvent,
    ) -> RuntimeStreamProjection:
        """Build a projection from a tool proposal event."""
        self._build_count += 1
        return RuntimeStreamProjection.from_tool_proposal(event)
    
    def build_from_patch_proposal(
        self,
        event: RuntimePatchProposalEvent,
    ) -> RuntimeStreamProjection:
        """Build a projection from a patch proposal event."""
        self._build_count += 1
        return RuntimeStreamProjection.from_patch_proposal(event)
    
    def build_from_warning(
        self,
        event: RuntimeWarningEvent,
    ) -> RuntimeStreamProjection:
        """Build a projection from a warning event."""
        self._build_count += 1
        return RuntimeStreamProjection.from_warning(event)
    
    def build_from_completion(
        self,
        event: RuntimeCompletionEvent,
    ) -> RuntimeStreamProjection:
        """Build a projection from a completion event."""
        self._build_count += 1
        return RuntimeStreamProjection.from_completion(event)
    
    def build_from_failure(
        self,
        event: RuntimeFailureEvent,
    ) -> RuntimeStreamProjection:
        """Build a projection from a failure event."""
        self._build_count += 1
        return RuntimeStreamProjection.from_failure(event)
    
    def build_from_event(self, event: RuntimeStreamEvent) -> RuntimeStreamProjection:
        """Build a projection from any stream event."""
        if isinstance(event, RuntimeStreamChunk):
            return self.build_from_chunk(event)
        elif isinstance(event, RuntimeStatusEvent):
            return self.build_from_status(event)
        elif isinstance(event, RuntimeHeartbeatEvent):
            return self.build_from_heartbeat(event)
        elif isinstance(event, RuntimeToolProposalEvent):
            return self.build_from_tool_proposal(event)
        elif isinstance(event, RuntimePatchProposalEvent):
            return self.build_from_patch_proposal(event)
        elif isinstance(event, RuntimeWarningEvent):
            return self.build_from_warning(event)
        elif isinstance(event, RuntimeCompletionEvent):
            return self.build_from_completion(event)
        elif isinstance(event, RuntimeFailureEvent):
            return self.build_from_failure(event)
        else:
            # Unknown event type - create generic projection
            projection_id = _generate_deterministic_id("event_proj", str(id(event)))
            return RuntimeStreamProjection(
                projection_id=projection_id,
                kind=RuntimeProjectionKind.CHUNK,
                content=f"Unknown event: {type(event).__name__}",
                channel="unknown",
                severity=RuntimeProjectionSeverity.DEBUG,
            )
    
    def build_and_buffer(
        self,
        event: RuntimeStreamEvent,
    ) -> Tuple[RuntimeStreamProjection, RuntimeStreamProjectionBuffer]:
        """Build a projection from an event and add to buffer.
        
        Returns:
            Tuple of (projection, updated_buffer)
        """
        stream_id = event.stream_id if hasattr(event, 'stream_id') else PLACEHOLDER_STREAM_ID
        projection = self.build_from_event(event)
        buffer = self._get_or_create_buffer(stream_id)
        updated_buffer = buffer.add(projection)
        self._buffers[stream_id] = updated_buffer
        return projection, updated_buffer
    
    def get_buffer(self, stream_id: str) -> Optional[RuntimeStreamProjectionBuffer]:
        """Get the projection buffer for a stream."""
        return self._buffers.get(stream_id)
    
    def list_buffers(self) -> List[RuntimeStreamProjectionBuffer]:
        """List all projection buffers."""
        return list(self._buffers.values())
    
    def clear_buffer(self, stream_id: str) -> bool:
        """Clear the projection buffer for a stream.
        
        Returns:
            True if buffer was cleared, False if not found
        """
        if stream_id in self._buffers:
            del self._buffers[stream_id]
            return True
        return False
    
    def clear_all_buffers(self) -> int:
        """Clear all projection buffers.
        
        Returns:
            Number of buffers cleared
        """
        count = len(self._buffers)
        self._buffers.clear()
        return count
    
    def build_widget_projector(
        self,
        projection: RuntimeStreamProjection,
    ) -> WidgetProjection:
        """Convert a stream projection to a WidgetProjection."""
        return projection.to_widget()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "builder_id": self.builder_id,
            "build_count": self._build_count,
            "buffer_count": len(self._buffers),
            "max_buffer_size": self.max_buffer_size,
            "max_buffer_bytes": self.max_buffer_bytes,
        }


# =============================================================================
# Runtime Projection Contract
# =============================================================================

@dataclass(frozen=True, slots=True)
class RuntimeProjectionContract:
    """Defines the contract for runtime stream projections.
    
    This contract ensures:
    - Projections are deterministic
    - Projections are replay-safe
    - Projections are bounded
    - Projections are projection-safe
    - Frontend never consumes raw subprocess state
    
    Attributes:
        contract_id: Unique contract identifier
        name: Contract name
        description: Contract description
        rules: List of contract rules
        version: Contract version
        created_at: When the contract was created
    """
    contract_id: str
    name: str = "runtime_stream_projection"
    description: str = "Contract for runtime stream projections"
    rules: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    created_at: str = field(default_factory=_utc_now)
    
    @classmethod
    def create_invariants(cls) -> "RuntimeProjectionContract":
        """Create the invariant contract for runtime projections."""
        return cls(
            contract_id=_generate_deterministic_id("proj_contract", "runtime_stream"),
            name="runtime_stream_projection",
            description="Invariant contract for runtime stream projections",
            rules=[
                # Safety rules
                "Frontend NEVER consumes raw subprocess state directly",
                "All projections must be deterministic",
                "All projections must be replay-safe",
                "All projections must be bounded in size",
                "All projections must be projection-safe",
                "All projections must be advisory-only",
                "All projections must be JSON-serializable",
                "Content must be sanitized (no control characters)",
                "Content must be truncated to bounded size",
                "Sequence numbers must be preserved",
                
                # Content rules
                f"Max content length: {MAX_PROJECTION_BYTES} bytes",
                f"Max projections per buffer: {MAX_PROJECTION_CHUNKS}",
                "Token counts must be estimated or actual",
                "Byte counts must be accurate",
                
                # Metadata rules
                "Stream ID must be preserved",
                "Invocation ID must be preserved",
                "Provider ID must be preserved",
                "Sequence number must be preserved",
                "Timestamp must be preserved",
                
                # Security rules
                "No HTTP/HTTPS URLs in content without validation",
                "No file paths in content without validation",
                "No executable commands in content without validation",
                "No sensitive data in content",
            ],
            version="1.0.0",
        )
    
    def validate_projection(
        self,
        projection: RuntimeStreamProjection,
    ) -> Tuple[bool, List[str]]:
        """Validate a projection against the contract.
        
        Returns:
            Tuple of (is_valid, list of violation messages)
        """
        violations: List[str] = []
        
        # Check invariants
        if not projection.advisory_only:
            violations.append("advisory_only must be True")
        if projection.authoritative:
            violations.append("authoritative must be False")
        if not projection.projection_id:
            violations.append("projection_id must be set")
        if not projection.stream_id:
            violations.append("stream_id must be set")
        
        # Check content bounds
        if projection.byte_count > MAX_PROJECTION_BYTES:
            violations.append(f"Content exceeds max size: {projection.byte_count} > {MAX_PROJECTION_BYTES}")
        
        # Check metadata
        if projection.metadata is None:
            violations.append("metadata must be a dict")
        
        return len(violations) == 0, violations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RuntimeProjectionContract":
        """Deserialize from dictionary."""
        return cls(
            contract_id=d.get("contract_id", _generate_deterministic_id("proj_contract", "unknown")),
            name=d.get("name", "runtime_stream_projection"),
            description=d.get("description", ""),
            rules=d.get("rules", []),
            version=d.get("version", "1.0.0"),
            created_at=d.get("created_at", _utc_now()),
        )


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Constants
    "PLACEHOLDER_PROJECTION_ID",
    "MAX_PROJECTION_CHUNKS",
    "MAX_PROJECTION_TOKENS",
    "MAX_PROJECTION_BYTES",
    "MAX_PROPOSAL_SUMMARY_LENGTH",
    "MAX_STATUS_MESSAGE_LENGTH",
    "PROJECTION_CATEGORY_STREAM",
    "PROJECTION_CATEGORY_STATUS",
    "PROJECTION_CATEGORY_PROPOSAL",
    "PROJECTION_CATEGORY_DIAGNOSTIC",
    "PROJECTION_CATEGORY_SUMMARY",
    # Enums
    "RuntimeProjectionKind",
    "RuntimeProjectionStatus",
    "RuntimeProjectionSeverity",
    "RuntimeProjectionScope",
    # Models
    "RuntimeStreamProjection",
    "RuntimeStreamProjectionBuffer",
    "RuntimeProjectionBuilder",
    "RuntimeProjectionContract",
    # Functions
    "_generate_deterministic_id",
    "_utc_now",
    "_truncate_text",
    "_safe_content",
]
