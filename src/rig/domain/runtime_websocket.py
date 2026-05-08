"""Runtime WebSocket Stream Integration for Rig.

This module provides the WebSocket integration for runtime stream events.

Core doctrine:
- Frontend NEVER consumes raw subprocess state directly
- UI streams projections only
- All stream events are sent via WebSocket as deterministic, ordered messages
- Backpressure protection prevents frontend overload
- Sequence validation ensures correct ordering
- Duplicate detection prevents replay issues
- Reconnect-safe with stream recovery

Properties:
- Deterministic stream event ordering
- Sequence validation
- Backpressure protection
- Bounded chunk buffering
- Reconnect-safe stream recovery
- Duplicate sequence detection
- Stale stream cleanup

file: src/rig/domain/runtime_websocket.py
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime_stream import (
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
        RuntimeStreamEvent,
    )
    from rig.domain.runtime_projection import (
        RuntimeStreamProjection,
        RuntimeStreamProjectionBuffer,
        RuntimeProjectionBuilder,
    )
    from rig.domain.runtime_supervisor import (
        RuntimeProcessHandle,
        RuntimeSupervisor,
        RuntimeSupervisorDecision,
        RuntimeSupervisorReceipt,
    )
    from aiohttp import web

from rig.domain.runtime_stream import (
    PLACEHOLDER_STREAM_ID,
    PLACEHOLDER_SEQUENCE,
    PLACEHOLDER_PROVIDER,
    PLACEHOLDER_INVOCATION,
    PLACEHOLDER_NO_RECEIPT,
    DEFAULT_MAX_CHUNK_SIZE,
    DEFAULT_MAX_BUFFER_SIZE,
    DEFAULT_MAX_SEQUENCE_GAP,
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
    RuntimeStreamEvent,
)
from rig.domain.runtime_projection import (
    RuntimeStreamProjection,
    RuntimeStreamProjectionBuffer,
    RuntimeProjectionBuilder,
    RuntimeProjectionKind,
    RuntimeProjectionStatus,
    MAX_PROJECTION_BYTES,
)
from rig.domain.projections import (
    WidgetProjection,
    UIProjection,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

PLACEHOLDER_WS_ID = "no_ws_id"
PLACEHOLDER_SESSION_ID = "no_session"
PLACEHOLDER_CLIENT_ID = "no_client"

# WebSocket configuration
DEFAULT_WS_PING_INTERVAL = 30.0
DEFAULT_WS_PONG_WAIT = 10.0
DEFAULT_WS_MAX_MESSAGE_SIZE = 1024 * 1024  # 1 MB
DEFAULT_WS_MAX_QUEUE_SIZE = 100
DEFAULT_WS_RATE_LIMIT_PER_SECOND = 100
DEFAULT_WS_BACKPRESSURE_THRESHOLD = 50

# Message types
WS_MSG_TYPE_STREAM_CHUNK = "stream_chunk"
WS_MSG_TYPE_STREAM_STATUS = "stream_status"
WS_MSG_TYPE_STREAM_PROJECTION = "stream_projection"
WS_MSG_TYPE_STREAM_COMPLETE = "stream_complete"
WS_MSG_TYPE_STREAM_FAILURE = "stream_failure"
WS_MSG_TYPE_STREAM_HEARTBEAT = "stream_heartbeat"
WS_MSG_TYPE_STREAM_WARNING = "stream_warning"
WS_MSG_TYPE_STREAM_PROPOSAL = "stream_proposal"
WS_MSG_TYPE_STREAM_ACKnowledgement = "stream_ack"


# =============================================================================
# Enums
# =============================================================================

class WebSocketStreamEventKind(Enum):
    """Kinds of WebSocket stream events."""
    CHUNK = "chunk"                   # Stream content chunk
    STATUS = "status"                 # Stream status change
    HEARTBEAT = "heartbeat"           # Stream heartbeat
    PROPOSAL = "proposal"             # Proposal event
    WARNING = "warning"                # Warning event
    COMPLETION = "completion"         # Stream completion
    FAILURE = "failure"               # Stream failure
    PROJECTION = "projection"         # Projection event
    ACKNOWLEDGEMENT = "acknowledgement"  # Client acknowledgement


class WebSocketClientStatus(Enum):
    """Status of a WebSocket client."""
    CONNECTED = "connected"           # Client connected
    CONNECTING = "connecting"         # Client connecting
    DISCONNECTED = "disconnected"     # Client disconnected
    ERROR = "error"                   # Client error
    RECONNECTING = "reconnecting"     # Client reconnecting


class WebSocketStreamStatus(Enum):
    """Status of WebSocket streaming for a client."""
    IDLE = "idle"                     # No active streams
    STREAMING = "streaming"           # Active streams
    PAUSED = "paused"                 # Streaming paused
    STALLED = "stalled"               # Stream stalled
    BACKPRESSURED = "backpressured"   # Backpressure active


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
# WebSocket Stream Message Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class WebSocketStreamMessage:
    """Represents a WebSocket message for runtime stream events.
    
    Messages are:
    - Deterministic and replay-safe
    - Sequentially ordered
    - Bounded in size
    - JSON-serializable
    
    Attributes:
        message_id: Unique message identifier
        kind: Message kind (stream_chunk, stream_status, etc.)
        stream_id: The stream this message belongs to
        sequence: Sequence number within the stream
        client_id: The client this message is for
        session_id: The session this message belongs to
        data: Message data payload
        timestamp: When the message was created
        requires_ack: Whether this message requires acknowledgement
        metadata: Additional metadata
    """
    message_id: str
    kind: str = WS_MSG_TYPE_STREAM_CHUNK
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: int = PLACEHOLDER_SEQUENCE
    client_id: str = PLACEHOLDER_CLIENT_ID
    session_id: str = PLACEHOLDER_SESSION_ID
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utc_now)
    requires_ack: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_chunk(
        cls,
        chunk: RuntimeStreamChunk,
        client_id: str,
        session_id: str,
        requires_ack: bool = False,
    ) -> "WebSocketStreamMessage":
        """Create a message from a stream chunk."""
        message_id = _generate_deterministic_id(
            "ws_msg",
            chunk.stream_id,
            str(chunk.sequence),
            chunk.channel.value,
            client_id,
        )
        return cls(
            message_id=message_id,
            kind=WS_MSG_TYPE_STREAM_CHUNK,
            stream_id=chunk.stream_id,
            sequence=chunk.sequence,
            client_id=client_id,
            session_id=session_id,
            data={
                "content": chunk.content,
                "channel": chunk.channel.value,
                "truncated": chunk.truncated,
                "content_length": chunk.content_length,
                "metadata": chunk.metadata,
            },
            requires_ack=requires_ack,
            metadata={
                "channel": chunk.channel.value,
                "provider_id": chunk.provider_id,
                "invocation_id": chunk.invocation_id,
            },
        )
    
    @classmethod
    def from_projection(
        cls,
        projection: RuntimeStreamProjection,
        client_id: str,
        session_id: str,
        requires_ack: bool = False,
    ) -> "WebSocketStreamMessage":
        """Create a message from a stream projection."""
        message_id = _generate_deterministic_id(
            "ws_msg",
            projection.stream_id,
            str(projection.sequence),
            projection.kind.value,
            client_id,
        )
        return cls(
            message_id=message_id,
            kind=WS_MSG_TYPE_STREAM_PROJECTION,
            stream_id=projection.stream_id,
            sequence=projection.sequence,
            client_id=client_id,
            session_id=session_id,
            data={
                "projection_id": projection.projection_id,
                "kind": projection.kind.value,
                "content": projection.content,
                "truncated": projection.content_truncated,
                "channel": projection.channel,
                "severity": projection.severity.value,
                "status": projection.status.value,
                "token_count": projection.token_count,
                "byte_count": projection.byte_count,
                "metadata": projection.metadata,
            },
            requires_ack=requires_ack,
            metadata={
                "provider_id": projection.provider_id,
                "invocation_id": projection.invocation_id,
            },
        )
    
    @classmethod
    def from_status(
        cls,
        event: RuntimeStatusEvent,
        client_id: str,
        session_id: str,
        requires_ack: bool = True,
    ) -> "WebSocketStreamMessage":
        """Create a message from a status event."""
        message_id = _generate_deterministic_id(
            "ws_msg",
            event.stream_id,
            str(event.sequence),
            "status",
            client_id,
        )
        return cls(
            message_id=message_id,
            kind=WS_MSG_TYPE_STREAM_STATUS,
            stream_id=event.stream_id,
            sequence=event.sequence,
            client_id=client_id,
            session_id=session_id,
            data={
                "status": event.status.value,
                "previous_status": event.previous_status.value,
                "message": event.message,
                "reason": event.reason,
            },
            requires_ack=requires_ack,
            metadata={
                "provider_id": event.provider_id,
                "invocation_id": event.invocation_id,
            },
        )
    
    @classmethod
    def from_heartbeat(
        cls,
        event: RuntimeHeartbeatEvent,
        client_id: str,
        session_id: str,
        requires_ack: bool = False,
    ) -> "WebSocketStreamMessage":
        """Create a message from a heartbeat event."""
        message_id = _generate_deterministic_id(
            "ws_msg",
            event.stream_id,
            str(event.sequence),
            "heartbeat",
            client_id,
        )
        return cls(
            message_id=message_id,
            kind=WS_MSG_TYPE_STREAM_HEARTBEAT,
            stream_id=event.stream_id,
            sequence=event.sequence,
            client_id=client_id,
            session_id=session_id,
            data={
                "missed_count": event.missed_count,
                "interval_seconds": event.interval_seconds,
            },
            requires_ack=requires_ack,
            metadata={
                "provider_id": event.provider_id,
                "invocation_id": event.invocation_id,
            },
        )
    
    @classmethod
    def from_completion(
        cls,
        event: RuntimeCompletionEvent,
        client_id: str,
        session_id: str,
        requires_ack: bool = True,
    ) -> "WebSocketStreamMessage":
        """Create a message from a completion event."""
        message_id = _generate_deterministic_id(
            "ws_msg",
            event.stream_id,
            str(event.sequence),
            "completion",
            client_id,
        )
        return cls(
            message_id=message_id,
            kind=WS_MSG_TYPE_STREAM_COMPLETE,
            stream_id=event.stream_id,
            sequence=event.sequence,
            client_id=client_id,
            session_id=session_id,
            data={
                "receipt_id": event.receipt_id,
                "completion_reason": event.completion_reason,
                "summary": event.summary,
                "total_chunks": event.total_chunks,
                "total_tokens": event.total_tokens,
                "total_assistant_tokens": event.total_assistant_tokens,
                "total_prompt_tokens": event.total_prompt_tokens,
            },
            requires_ack=requires_ack,
            metadata={
                "provider_id": event.provider_id,
                "invocation_id": event.invocation_id,
            },
        )
    
    @classmethod
    def from_failure(
        cls,
        event: RuntimeFailureEvent,
        client_id: str,
        session_id: str,
        requires_ack: bool = True,
    ) -> "WebSocketStreamMessage":
        """Create a message from a failure event."""
        message_id = _generate_deterministic_id(
            "ws_msg",
            event.stream_id,
            str(event.sequence),
            "failure",
            client_id,
        )
        return cls(
            message_id=message_id,
            kind=WS_MSG_TYPE_STREAM_FAILURE,
            stream_id=event.stream_id,
            sequence=event.sequence,
            client_id=client_id,
            session_id=session_id,
            data={
                "failure_category": event.failure_category.value,
                "message": event.message,
                "error_details": event.error_details,
            },
            requires_ack=requires_ack,
            metadata={
                "provider_id": event.provider_id,
                "invocation_id": event.invocation_id,
            },
        )
    
    @classmethod
    def from_warning(
        cls,
        event: RuntimeWarningEvent,
        client_id: str,
        session_id: str,
        requires_ack: bool = False,
    ) -> "WebSocketStreamMessage":
        """Create a message from a warning event."""
        message_id = _generate_deterministic_id(
            "ws_msg",
            event.stream_id,
            str(event.sequence),
            "warning",
            client_id,
        )
        return cls(
            message_id=message_id,
            kind=WS_MSG_TYPE_STREAM_WARNING,
            stream_id=event.stream_id,
            sequence=event.sequence,
            client_id=client_id,
            session_id=session_id,
            data={
                "warning_code": event.warning_code.value,
                "message": event.message,
                "details": event.details,
            },
            requires_ack=requires_ack,
            metadata={
                "provider_id": event.provider_id,
                "invocation_id": event.invocation_id,
            },
        )
    
    @classmethod
    def from_proposal(
        cls,
        event: RuntimeToolProposalEvent | RuntimePatchProposalEvent,
        client_id: str,
        session_id: str,
        requires_ack: bool = True,
    ) -> "WebSocketStreamMessage":
        """Create a message from a proposal event."""
        kind_str = "shell_proposal" if isinstance(event, RuntimeToolProposalEvent) else "patch_proposal"
        message_id = _generate_deterministic_id(
            "ws_msg",
            event.stream_id,
            str(event.sequence),
            kind_str,
            client_id,
        )
        
        if isinstance(event, RuntimeToolProposalEvent):
            data = {
                "proposal_id": event.proposal_id,
                "proposal_kind": event.proposal_kind.value,
                "payload": event.payload,
                "capability_ids": list(event.capability_ids),
                "validation_status": event.validation_status,
                "validation_errors": event.validation_errors,
            }
        else:  # RuntimePatchProposalEvent
            data = {
                "proposal_id": event.proposal_id,
                "file_path": event.file_path,
                "diff": event.diff,
                "patch_format": event.patch_format,
                "capability_ids": list(event.capability_ids),
                "validation_status": event.validation_status,
                "validation_errors": event.validation_errors,
            }
        
        return cls(
            message_id=message_id,
            kind=WS_MSG_TYPE_STREAM_PROPOSAL,
            stream_id=event.stream_id,
            sequence=event.sequence,
            client_id=client_id,
            session_id=session_id,
            data=data,
            requires_ack=requires_ack,
            metadata={
                "provider_id": event.provider_id,
                "invocation_id": event.invocation_id,
            },
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)
    
    def to_websocket_payload(self) -> Dict[str, Any]:
        """Convert to WebSocket payload format."""
        return {
            "kind": self.kind,
            "message_id": self.message_id,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "data": self.data,
            "timestamp": self.timestamp,
            "requires_ack": self.requires_ack,
            "client_id": self.client_id,
            "session_id": self.session_id,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WebSocketStreamMessage":
        """Deserialize from dictionary."""
        return cls(
            message_id=d.get("message_id", _generate_deterministic_id("ws_msg", "unknown")),
            kind=d.get("kind", WS_MSG_TYPE_STREAM_CHUNK),
            stream_id=d.get("stream_id", PLACEHOLDER_STREAM_ID),
            sequence=d.get("sequence", PLACEHOLDER_SEQUENCE),
            client_id=d.get("client_id", PLACEHOLDER_CLIENT_ID),
            session_id=d.get("session_id", PLACEHOLDER_SESSION_ID),
            data=d.get("data", {}),
            timestamp=d.get("timestamp", _utc_now()),
            requires_ack=d.get("requires_ack", False),
            metadata=d.get("metadata", {}),
        )


# =============================================================================
# WebSocket Stream State Model
# =============================================================================

@dataclass(frozen=True, slots=True)
class WebSocketStreamState:
    """Tracks the streaming state for a WebSocket client.
    
    State includes:
    - Last received sequence numbers per stream
    - Pending acknowledgements
    - Backpressure status
    - Connection status
    
    Attributes:
        client_id: Unique client identifier
        session_id: Session identifier
        last_sequences: Dict mapping stream_id to last received sequence
        pending_acks: Set of message IDs awaiting acknowledgement
        backpressured: Whether backpressure is active
        last_activity_at: When the client was last active
        connected_at: When the client connected
        disconnected_at: When the client disconnected
        message_count: Total messages sent
        ack_count: Total acknowledgements received
        error_count: Total errors encountered
    """
    client_id: str
    session_id: str = PLACEHOLDER_SESSION_ID
    last_sequences: Dict[str, int] = field(default_factory=dict)
    pending_acks: FrozenSet[str] = field(default_factory=frozenset)
    backpressured: bool = False
    last_activity_at: str = field(default_factory=_utc_now)
    connected_at: str = field(default_factory=_utc_now)
    disconnected_at: Optional[str] = None
    message_count: int = 0
    ack_count: int = 0
    error_count: int = 0
    
    @classmethod
    def create(
        cls,
        client_id: str,
        session_id: str = PLACEHOLDER_SESSION_ID,
    ) -> "WebSocketStreamState":
        """Create a new stream state for a client."""
        return cls(
            client_id=client_id,
            session_id=session_id,
            last_sequences={},
            pending_acks=frozenset(),
            backpressured=False,
            connected_at=_utc_now(),
        )
    
    def with_message_sent(
        self,
        stream_id: str,
        sequence: int,
        message_id: str,
        requires_ack: bool = False,
    ) -> "WebSocketStreamState":
        """Return a new state with message sent."""
        new_last_sequences = dict(self.last_sequences)
        new_pending_acks = set(self.pending_acks)
        
        # Update last sequence for stream
        existing = new_last_sequences.get(stream_id, -1)
        if sequence > existing:
            new_last_sequences[stream_id] = sequence
        
        # Add to pending acks if required
        if requires_ack:
            new_pending_acks.add(message_id)
        
        return type(self)(
            client_id=self.client_id,
            session_id=self.session_id,
            last_sequences=new_last_sequences,
            pending_acks=frozenset(new_pending_acks),
            backpressured=self.backpressured,
            last_activity_at=_utc_now(),
            connected_at=self.connected_at,
            disconnected_at=self.disconnected_at,
            message_count=self.message_count + 1,
            ack_count=self.ack_count,
            error_count=self.error_count,
        )
    
    def with_acknowledgement(
        self,
        message_id: str,
    ) -> "WebSocketStreamState":
        """Return a new state with acknowledgement received."""
        new_pending_acks = set(self.pending_acks)
        if message_id in new_pending_acks:
            new_pending_acks.remove(message_id)
        
        return type(self)(
            client_id=self.client_id,
            session_id=self.session_id,
            last_sequences=dict(self.last_sequences),
            pending_acks=frozenset(new_pending_acks),
            backpressured=self.backpressured,
            last_activity_at=_utc_now(),
            connected_at=self.connected_at,
            disconnected_at=self.disconnected_at,
            message_count=self.message_count,
            ack_count=self.ack_count + 1,
            error_count=self.error_count,
        )
    
    def with_backpressure(self, backpressured: bool) -> "WebSocketStreamState":
        """Return a new state with backpressure status updated."""
        return type(self)(
            client_id=self.client_id,
            session_id=self.session_id,
            last_sequences=dict(self.last_sequences),
            pending_acks=self.pending_acks,
            backpressured=backpressured,
            last_activity_at=_utc_now(),
            connected_at=self.connected_at,
            disconnected_at=self.disconnected_at,
            message_count=self.message_count,
            ack_count=self.ack_count,
            error_count=self.error_count,
        )
    
    def with_error(self) -> "WebSocketStreamState":
        """Return a new state with error recorded."""
        return type(self)(
            client_id=self.client_id,
            session_id=self.session_id,
            last_sequences=dict(self.last_sequences),
            pending_acks=self.pending_acks,
            backpressured=self.backpressured,
            last_activity_at=_utc_now(),
            connected_at=self.connected_at,
            disconnected_at=self.disconnected_at,
            message_count=self.message_count,
            ack_count=self.ack_count,
            error_count=self.error_count + 1,
        )
    
    def with_disconnect(self) -> "WebSocketStreamState":
        """Return a new state with disconnect recorded."""
        return type(self)(
            client_id=self.client_id,
            session_id=self.session_id,
            last_sequences=dict(self.last_sequences),
            pending_acks=self.pending_acks,
            backpressured=self.backpressured,
            last_activity_at=_utc_now(),
            connected_at=self.connected_at,
            disconnected_at=_utc_now(),
            message_count=self.message_count,
            ack_count=self.ack_count,
            error_count=self.error_count,
        )
    
    def get_last_sequence(self, stream_id: str) -> int:
        """Get the last received sequence for a stream."""
        return self.last_sequences.get(stream_id, -1)
    
    def has_pending_acks(self) -> bool:
        """Check if there are pending acknowledgements."""
        return len(self.pending_acks) > 0
    
    def get_pending_ack_count(self) -> int:
        """Get the number of pending acknowledgements."""
        return len(self.pending_acks)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "client_id": self.client_id,
            "session_id": self.session_id,
            "last_sequences": dict(self.last_sequences),
            "pending_acks": list(self.pending_acks),
            "backpressured": self.backpressured,
            "last_activity_at": self.last_activity_at,
            "connected_at": self.connected_at,
            "disconnected_at": self.disconnected_at,
            "message_count": self.message_count,
            "ack_count": self.ack_count,
            "error_count": self.error_count,
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WebSocketStreamState":
        """Deserialize from dictionary."""
        return cls(
            client_id=d.get("client_id", PLACEHOLDER_CLIENT_ID),
            session_id=d.get("session_id", PLACEHOLDER_SESSION_ID),
            last_sequences=d.get("last_sequences", {}),
            pending_acks=frozenset(d.get("pending_acks", [])),
            backpressured=d.get("backpressured", False),
            last_activity_at=d.get("last_activity_at", _utc_now()),
            connected_at=d.get("connected_at", _utc_now()),
            disconnected_at=d.get("disconnected_at"),
            message_count=d.get("message_count", 0),
            ack_count=d.get("ack_count", 0),
            error_count=d.get("error_count", 0),
        )


# =============================================================================
# WebSocket Stream Integrator
# =============================================================================

class WebSocketStreamIntegrator:
    """Integrates runtime streams with WebSocket connections.
    
    This class:
    - Routes stream events to WebSocket clients
    - Manages client state and sequence tracking
    - Handles backpressure
    - Validates sequence ordering
    - Detects duplicate sequences
    - Provides reconnect-safe stream recovery
    
    Properties:
    - Deterministic message ordering
    - Sequence validation
    - Backpressure protection
    - Reconnect-safe
    - Duplicate detection
    - Bounded buffering
    """
    
    def __init__(
        self,
        integrator_id: Optional[str] = None,
        max_queue_size: int = DEFAULT_WS_MAX_QUEUE_SIZE,
        rate_limit_per_second: float = DEFAULT_WS_RATE_LIMIT_PER_SECOND,
        backpressure_threshold: int = DEFAULT_WS_BACKPRESSURE_THRESHOLD,
    ):
        """Initialize the WebSocket stream integrator.
        
        args:
            integrator_id: Unique integrator ID
            max_queue_size: Maximum message queue size per client
            rate_limit_per_second: Rate limit for messages per second
            backpressure_threshold: Queue size threshold for backpressure
        """
        self.integrator_id = integrator_id or _generate_deterministic_id("ws_integrator")
        self.max_queue_size = max_queue_size
        self.rate_limit_per_second = rate_limit_per_second
        self.backpressure_threshold = backpressure_threshold
        
        # Client state tracking
        self._client_states: Dict[str, WebSocketStreamState] = {}
        self._client_queues: Dict[str, asyncio.Queue] = {}
        self._client_last_sent: Dict[str, float] = {}
        self._client_message_counts: Dict[str, int] = {}
        
        # Stream tracking
        self._active_streams: Dict[str, str] = {}  # stream_id -> client_id
        self._stream_sequences: Dict[str, int] = {}  # stream_id -> last sequence
        
        # Statistics
        self._total_messages_sent = 0
        self._total_acks_received = 0
        self._total_errors = 0
        self._started_at = _utc_now()
        self._last_activity_at = _utc_now()
        
        # Rate limiting
        self._last_rate_limit_check = 0.0
        self._rate_limit_count = 0
    
    @property
    def integrator_id(self) -> str:
        """Get the integrator ID."""
        return self._integrator_id
    
    @integrator_id.setter
    def integrator_id(self, value: str) -> None:
        """Set the integrator ID."""
        self._integrator_id = value
    
    def register_client(
        self,
        client_id: str,
        session_id: str,
    ) -> None:
        """Register a new WebSocket client.
        
        args:
            client_id: Unique client identifier
            session_id: Session identifier
        """
        if client_id not in self._client_states:
            self._client_states[client_id] = WebSocketStreamState.create(
                client_id=client_id,
                session_id=session_id,
            )
            self._client_queues[client_id] = asyncio.Queue(maxsize=self.max_queue_size)
            self._client_last_sent[client_id] = 0.0
            self._client_message_counts[client_id] = 0
            self._last_activity_at = _utc_now()
    
    def unregister_client(self, client_id: str) -> None:
        """Unregister a WebSocket client.
        
        args:
            client_id: The client to unregister
        """
        if client_id in self._client_states:
            state = self._client_states[client_id].with_disconnect()
            self._client_states[client_id] = state
            
        # Clean up
        self._client_states.pop(client_id, None)
        self._client_queues.pop(client_id, None)
        self._client_last_sent.pop(client_id, None)
        self._client_message_counts.pop(client_id, None)
        self._last_activity_at = _utc_now()
    
    def get_client_state(self, client_id: str) -> Optional[WebSocketStreamState]:
        """Get the state for a client."""
        return self._client_states.get(client_id)
    
    def list_client_states(self) -> List[WebSocketStreamState]:
        """List all client states."""
        return list(self._client_states.values())
    
    async def send_stream_message(
        self,
        client_id: str,
        message: WebSocketStreamMessage,
        ws: Optional[Any] = None,
    ) -> bool:
        """Send a stream message to a client.
        
        This method:
        - Validates sequence ordering
        - Checks for duplicates
        - Applies backpressure
        - Queues message for sending
        - Returns success status
        
        args:
            client_id: The target client
            message: The message to send
            ws: Optional WebSocket connection for direct sending
            
        Returns:
            True if message was queued successfully
        """
        state = self._client_states.get(client_id)
        if state is None:
            logger.warning(f"Client {client_id} not registered")
            return False
        
        # Check rate limit
        if not self._check_rate_limit(client_id):
            # Apply backpressure
            state = state.with_backpressure(True)
            self._client_states[client_id] = state
            return False
        
        # Validate sequence
        stream_id = message.stream_id
        last_seq = state.get_last_sequence(stream_id)
        
        if message.sequence <= last_seq:
            # Sequence error - log but don't block
            if message.sequence < last_seq:
                logger.warning(
                    f"Sequence gap detected for {stream_id}: "
                    f"expected > {last_seq}, got {message.sequence}"
                )
            else:
                logger.warning(
                    f"Duplicate sequence detected for {stream_id}: {message.sequence}"
                )
        
        # Check backpressure
        queue = self._client_queues.get(client_id)
        if queue and queue.qsize() >= self.backpressure_threshold:
            state = state.with_backpressure(True)
            self._client_states[client_id] = state
            return False
        
        # Queue the message
        try:
            queue = self._client_queues.get(client_id)
            if queue:
                await queue.put(message)
                
                # Update state
                new_state = state.with_message_sent(
                    stream_id=stream_id,
                    sequence=message.sequence,
                    message_id=message.message_id,
                    requires_ack=message.requires_ack,
                )
                self._client_states[client_id] = new_state
                
                # Update tracking
                self._stream_sequences[stream_id] = message.sequence
                self._active_streams[stream_id] = client_id
                self._client_last_sent[client_id] = asyncio.get_event_loop().time()
                self._client_message_counts[client_id] = new_state.message_count
                self._total_messages_sent += 1
                self._last_activity_at = _utc_now()
                
                return True
            else:
                logger.warning(f"No queue for client {client_id}")
                return False
        except asyncio.QueueFull:
            state = state.with_backpressure(True).with_error()
            self._client_states[client_id] = state
            return False
    
    async def send_projection_message(
        self,
        client_id: str,
        projection: RuntimeStreamProjection,
        session_id: str,
        ws: Optional[Any] = None,
    ) -> bool:
        """Send a projection message to a client.
        
        This is the primary method for sending projections to the frontend.
        
        args:
            client_id: The target client
            projection: The projection to send
            session_id: The session ID
            ws: Optional WebSocket connection
            
        Returns:
            True if message was queued successfully
        """
        message = WebSocketStreamMessage.from_projection(
            projection=projection,
            client_id=client_id,
            session_id=session_id,
            requires_ack=False,  # Projections typically don't require ack
        )
        return await self.send_stream_message(client_id, message, ws)
    
    async def send_chunk_message(
        self,
        client_id: str,
        chunk: RuntimeStreamChunk,
        session_id: str,
        ws: Optional[Any] = None,
    ) -> bool:
        """Send a chunk message to a client.
        
        args:
            client_id: The target client
            chunk: The stream chunk to send
            session_id: The session ID
            ws: Optional WebSocket connection
            
        Returns:
            True if message was queued successfully
        """
        message = WebSocketStreamMessage.from_chunk(
            chunk=chunk,
            client_id=client_id,
            session_id=session_id,
            requires_ack=False,
        )
        return await self.send_stream_message(client_id, message, ws)
    
    async def send_status_message(
        self,
        client_id: str,
        event: RuntimeStatusEvent,
        session_id: str,
        ws: Optional[Any] = None,
    ) -> bool:
        """Send a status message to a client.
        
        args:
            client_id: The target client
            event: The status event to send
            session_id: The session ID
            ws: Optional WebSocket connection
            
        Returns:
            True if message was queued successfully
        """
        message = WebSocketStreamMessage.from_status(
            event=event,
            client_id=client_id,
            session_id=session_id,
            requires_ack=True,
        )
        return await self.send_stream_message(client_id, message, ws)
    
    def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limit."""
        now = asyncio.get_event_loop().time()
        
        # Reset count if it's been more than a second
        if now - self._last_rate_limit_check > 1.0:
            self._rate_limit_count = 0
            self._last_rate_limit_check = now
        
        self._rate_limit_count += 1
        return self._rate_limit_count <= self.rate_limit_per_second
    
    async def process_client_messages(
        self,
        client_id: str,
        ws: Any,
    ) -> None:
        """Process queued messages for a client.
        
        This method should be called in a background task for each client
        to send queued messages to the WebSocket.
        
        args:
            client_id: The client ID
            ws: The WebSocket connection
        """
        queue = self._client_queues.get(client_id)
        if queue is None:
            return
        
        while True:
            try:
                # Wait for message with timeout
                try:
                    message = await asyncio.wait_for(
                        queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Send the message
                try:
                    payload = message.to_websocket_payload()
                    await ws.send_json(payload)
                    
                    # Update state
                    state = self._client_states.get(client_id)
                    if state and message.requires_ack:
                        # Leave in pending_acks until ack received
                        pass
                    
                except Exception as e:
                    logger.error(f"Error sending message to {client_id}: {e}")
                    state = self._client_states.get(client_id)
                    if state:
                        state = state.with_error()
                        self._client_states[client_id] = state
                    self._total_errors += 1
                
            except Exception:
                break
    
    def handle_acknowledgement(
        self,
        client_id: str,
        message_id: str,
    ) -> bool:
        """Handle an acknowledgement from a client.
        
        args:
            client_id: The client ID
            message_id: The message ID being acknowledged
            
        Returns:
            True if acknowledgement was processed
        """
        state = self._client_states.get(client_id)
        if state is None:
            return False
        
        if message_id not in state.pending_acks:
            # Already acknowledged or not tracked
            return False
        
        new_state = state.with_acknowledgement(message_id)
        self._client_states[client_id] = new_state
        self._total_acks_received += 1
        self._last_activity_at = _utc_now()
        
        # Clear backpressure if no more pending acks
        if not new_state.has_pending_acks():
            new_state = new_state.with_backpressure(False)
            self._client_states[client_id] = new_state
        
        return True
    
    def handle_stream_chunk(
        self,
        client_id: str,
        chunk: RuntimeStreamChunk,
        session_id: str,
    ) -> bool:
        """Handle a stream chunk event.
        
        This is the entry point for new stream chunks.
        They are converted to messages and queued for the client.
        
        args:
            client_id: The target client
            chunk: The stream chunk
            session_id: The session ID
            
        Returns:
            True if chunk was handled successfully
        """
        # Validate chunk
        if not chunk.stream_id:
            logger.warning("Chunk missing stream_id")
            return False
        
        # Create and queue message
        message = WebSocketStreamMessage.from_chunk(
            chunk=chunk,
            client_id=client_id,
            session_id=session_id,
        )
        
        # Sync send (will queue internally)
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is running, queue the send
            asyncio.create_task(self.send_stream_message(client_id, message))
        else:
            # If event loop is not running, we need to handle differently
            # For now, just log
            logger.warning("Event loop not running, cannot send WebSocket message")
        
        return True
    
    def get_stream_last_sequence(self, stream_id: str) -> int:
        """Get the last sequence number for a stream."""
        return self._stream_sequences.get(stream_id, -1)
    
    def list_active_streams(self) -> List[str]:
        """List all active stream IDs."""
        return list(self._active_streams.keys())
    
    def get_active_stream_client(self, stream_id: str) -> Optional[str]:
        """Get the client ID for an active stream."""
        return self._active_streams.get(stream_id)
    
    def cleanup_stale_client(self, client_id: str) -> int:
        """Clean up resources for a stale client.
        
        Returns:
            Number of resources cleaned up
        """
        count = 0
        
        # Remove client state
        if client_id in self._client_states:
            count += 1
            del self._client_states[client_id]
        
        # Remove client queue
        if client_id in self._client_queues:
            count += 1
            queue = self._client_queues[client_id]
            # Drain queue
            while not queue.empty():
                try:
                    queue.get_nowait()
                    count += 1
                except asyncio.QueueEmpty:
                    break
            del self._client_queues[client_id]
        
        # Remove tracking
        if client_id in self._client_last_sent:
            count += 1
            del self._client_last_sent[client_id]
        if client_id in self._client_message_counts:
            count += 1
            del self._client_message_counts[client_id]
        
        # Remove streams owned by this client
        streams_to_remove = [
            stream_id for stream_id, cid in self._active_streams.items()
            if cid == client_id
        ]
        for stream_id in streams_to_remove:
            del self._active_streams[stream_id]
            del self._stream_sequences[stream_id]
            count += 2
        
        return count
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "integrator_id": self.integrator_id,
            "max_queue_size": self.max_queue_size,
            "rate_limit_per_second": self.rate_limit_per_second,
            "backpressure_threshold": self.backpressure_threshold,
            "total_messages_sent": self._total_messages_sent,
            "total_acks_received": self._total_acks_received,
            "total_errors": self._total_errors,
            "active_client_count": len(self._client_states),
            "active_stream_count": len(self._active_streams),
            "started_at": self._started_at,
            "last_activity_at": self._last_activity_at,
        }
    
    @classmethod
    def create_default(cls) -> "WebSocketStreamIntegrator":
        """Create a default WebSocket stream integrator."""
        return cls()


# =============================================================================
# WebSocket Message Normalizer
# =============================================================================

class WebSocketMessageNormalizer:
    """Normalizes WebSocket stream messages for consistent handling.
    
    This class:
    - Normalizes message formats
    - Validates message structure
    - Handles message variants
    - Provides consistent output
    """
    
    @staticmethod
    def normalize_message(message: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a WebSocket message.
        
        args:
            message: The raw message
            
        Returns:
            Normalized message
        """
        normalized: Dict[str, Any] = {
            "kind": message.get("kind", WS_MSG_TYPE_STREAM_CHUNK),
            "message_id": message.get("message_id", _generate_deterministic_id("normalized", message.get("stream_id", ""), str(message.get("sequence", 0)))),
            "stream_id": message.get("stream_id", PLACEHOLDER_STREAM_ID),
            "sequence": message.get("sequence", 0),
            "data": message.get("data", {}),
            "timestamp": message.get("timestamp", _utc_now()),
            "client_id": message.get("client_id", PLACEHOLDER_CLIENT_ID),
            "session_id": message.get("session_id", PLACEHOLDER_SESSION_ID),
            "requires_ack": message.get("requires_ack", False),
            "metadata": message.get("metadata", {}),
        }
        return normalized
    
    @staticmethod
    def validate_message(message: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate a WebSocket message.
        
        args:
            message: The message to validate
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: List[str] = []
        
        # Check required fields
        if not message.get("kind"):
            errors.append("Missing required field: kind")
        if not message.get("stream_id"):
            errors.append("Missing required field: stream_id")
        if message.get("sequence") is None:
            errors.append("Missing required field: sequence")
        if not message.get("data"):
            message["data"] = {}
        
        # Check sequence type
        sequence = message.get("sequence")
        if sequence is not None:
            if not isinstance(sequence, int):
                try:
                    int(sequence)
                except (ValueError, TypeError):
                    errors.append(f"Invalid sequence type: {type(sequence)}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def create_ack_message(
        message_id: str,
        stream_id: str,
        sequence: int,
        client_id: str,
    ) -> Dict[str, Any]:
        """Create an acknowledgement message.
        
        args:
            message_id: The message ID being acknowledged
            stream_id: The stream ID
            sequence: The sequence number
            client_id: The client ID
            
        Returns:
            Acknowledgement message
        """
        return {
            "kind": WS_MSG_TYPE_STREAM_ACKnowledgement,
            "message_id": message_id,
            "stream_id": stream_id,
            "sequence": sequence,
            "client_id": client_id,
            "timestamp": _utc_now(),
        }


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Constants
    "PLACEHOLDER_WS_ID",
    "PLACEHOLDER_SESSION_ID",
    "PLACEHOLDER_CLIENT_ID",
    "DEFAULT_WS_PING_INTERVAL",
    "DEFAULT_WS_PONG_WAIT",
    "DEFAULT_WS_MAX_MESSAGE_SIZE",
    "DEFAULT_WS_MAX_QUEUE_SIZE",
    "DEFAULT_WS_RATE_LIMIT_PER_SECOND",
    "DEFAULT_WS_BACKPRESSURE_THRESHOLD",
    "WS_MSG_TYPE_STREAM_CHUNK",
    "WS_MSG_TYPE_STREAM_STATUS",
    "WS_MSG_TYPE_STREAM_PROJECTION",
    "WS_MSG_TYPE_STREAM_COMPLETE",
    "WS_MSG_TYPE_STREAM_FAILURE",
    "WS_MSG_TYPE_STREAM_HEARTBEAT",
    "WS_MSG_TYPE_STREAM_WARNING",
    "WS_MSG_TYPE_STREAM_PROPOSAL",
    "WS_MSG_TYPE_STREAM_ACKnowledgement",
    # Enums
    "WebSocketStreamEventKind",
    "WebSocketClientStatus",
    "WebSocketStreamStatus",
    # Models
    "WebSocketStreamMessage",
    "WebSocketStreamState",
    # Integrator
    "WebSocketStreamIntegrator",
    # Normalizer
    "WebSocketMessageNormalizer",
    # Functions
    "_generate_deterministic_id",
    "_utc_now",
]
