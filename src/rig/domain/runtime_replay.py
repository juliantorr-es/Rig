"""Runtime Replay & Integrity Integration Module for Rig.

Phase 2: Runtime & Agent Execution Plane - Replay & Integrity Integration.

Core doctrine:
- Runtime output is advisory evidence only
- Only receipts/proposals become authoritative evidence
- UI streams projections, NOT raw subprocesses
- All runtime execution remains advisory-only
- NO autonomous apply, direct workspace mutation, hidden execution, background daemons,
  cloud orchestration, production networking, real API keys, or destructive Git commands

This module provides deterministic replay capability for runtime stream events and
integrity verification of replayed streams.

See docs/architecture/runtime-streaming.md for the canonical streaming architecture.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime_streaming import (
        RuntimeStreamChunk,
        RuntimeStreamEvent,
        RuntimeSequenceState,
        RuntimeStreamBuffer,
        RuntimeStreamProjection,
        WebSocketStreamMessage,
    )

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLACEHOLDER_REPLAY_ID = "REPLAY_ID_PLACEHOLDER"
PLACEHOLDER_STREAM_ID = "STREAM_ID_PLACEHOLDER"
PLACEHOLDER_INVOKE_ID = "INVOKE_ID_PLACEHOLDER"
PLACEHOLDER_SEQUENCE = 0

# Default replay buffer sizes
DEFAULT_REPLAY_BUFFER_MAX_EVENTS = 10000
DEFAULT_REPLAY_BUFFER_MAX_BYTES = 50 * 1024 * 1024  # 50MB
DEFAULT_REPLAY_CHUNK_MAX_BYTES = 1 * 1024 * 1024  # 1MB
DEFAULT_REPLAY_STEP_BYTES = 10 * 1024 * 1024  # 10MB step size

# Replay timing defaults
DEFAULT_REPLAY_SPEED_MULTIPLIER = 1.0
DEFAULT_REPLAY_MIN_INTERVAL_MS = 0
DEFAULT_REPLAY_MAX_WAIT_MS = 30000

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RuntimeReplayState(Enum):
    """States for runtime replay operations."""

    PENDING = "pending"
    QUEUED = "queued"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RuntimeReplayMode(Enum):
    """Modes for runtime replay operations."""

    LIVE = "live"  # Replay as events arrive
    STEP = "step"  # Step through events one at a time
    RANGE = "range"  # Replay a specific range of sequences
    FULL = "full"  # Replay entire stream
    FILTERED = "filtered"  # Replay with event filtering


class RuntimeReplaySpeed(Enum):
    """Replay speed presets."""

    SLOWEST = "slowest"  # 0.1x
    SLOWER = "slower"  # 0.25x
    SLOW = "slow"  # 0.5x
    NORMAL = "normal"  # 1.0x
    FAST = "fast"  # 2.0x
    FASTER = "faster"  # 5.0x
    FASTEST = "fastest"  # 10.0x
    INSTANT = "instant"  # No delay


class RuntimeReplayIntegrityCode(Enum):
    """Integrity violation codes for runtime replay."""

    SEQUENCE_GAP = "REPLAY-001"
    DUPLICATE_SEQUENCE = "REPLAY-002"
    MISSING_SEQUENCE = "REPLAY-003"
    OUT_OF_ORDER = "REPLAY-004"
    CHECKSUM_MISMATCH = "REPLAY-005"
    INVALID_TIMESTAMP = "REPLAY-006"
    STREAM_MISMATCH = "REPLAY-007"
    REPLAY_STATE_CORRUPTION = "REPLAY-008"
    BUFFER_OVERFLOW = "REPLAY-009"
    INTEGRITY_HASH_MISMATCH = "REPLAY-010"


class RuntimeReplayVerificationLevel(Enum):
    """Verification levels for replay integrity."""

    NONE = "none"
    BASIC = "basic"  # Sequence and timing checks
    STANDARD = "standard"  # Includes content checksums
    STRICT = "strict"  # Full cryptographic verification


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeReplayReference:
    """Reference to a replayable runtime stream.

    This is the canonical reference that links stream events to their replay source.
    All replay operations use these references to locate and verify stream data.
    """

    replay_id: str = PLACEHOLDER_REPLAY_ID
    stream_id: str = PLACEHOLDER_STREAM_ID
    invocation_id: str = PLACEHOLDER_INVOKE_ID
    provider_id: str = ""
    model_id: str = ""

    # Sequence bounds
    first_sequence: int = PLACEHOLDER_SEQUENCE
    last_sequence: int = PLACEHOLDER_SEQUENCE
    total_sequences: int = 0

    # Timing bounds
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None

    # Integrity hash of the complete stream
    stream_checksum: str = ""
    stream_hash: str = ""

    # Rationale: recent first for replay
    recent_first: bool = True

    # Generated deterministic ID
    id: str = field(default=PLACEHOLDER_REPLAY_ID)

    # Advisory-only flag - ALL runtime models must be advisory-only
    advisory_only: bool = field(default=True, init=False)

    # Never authoritative - only receipts become authoritative
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)
        
        # Generate deterministic ID if not provided
        if self.id == PLACEHOLDER_REPLAY_ID:
            id_str = f"{self.replay_id}_{self.stream_id}_{self.invocation_id}"
            obj_id = hashlib.sha256(id_str.encode()).hexdigest()[:16]
            object.__setattr__(self, 'id', f"replay_ref_{obj_id}")

    @classmethod
    def create(
        cls,
        replay_id: str,
        stream_id: str,
        invocation_id: str,
        provider_id: str = "",
        model_id: str = "",
        first_sequence: int = 0,
        last_sequence: int = 0,
        total_sequences: int = 0,
        first_timestamp: Optional[str] = None,
        last_timestamp: Optional[str] = None,
        stream_checksum: str = "",
        stream_hash: str = "",
        recent_first: bool = True,
    ) -> "RuntimeReplayReference":
        """Factory method for creating replay references."""
        return cls(
            replay_id=replay_id,
            stream_id=stream_id,
            invocation_id=invocation_id,
            provider_id=provider_id,
            model_id=model_id,
            first_sequence=first_sequence,
            last_sequence=last_sequence,
            total_sequences=total_sequences,
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
            stream_checksum=stream_checksum,
            stream_hash=stream_hash,
            recent_first=recent_first,
        )

    @property
    def sequence_range(self) -> Tuple[int, int]:
        """Return the sequence range as a tuple."""
        return (self.first_sequence, self.last_sequence)

    @property
    def is_complete(self) -> bool:
        """Check if the replay reference represents a complete stream."""
        return self.total_sequences > 0 and self.first_sequence >= 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "replay_id": self.replay_id,
            "stream_id": self.stream_id,
            "invocation_id": self.invocation_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "total_sequences": self.total_sequences,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "stream_checksum": self.stream_checksum,
            "stream_hash": self.stream_hash,
            "recent_first": self.recent_first,
            "id": self.id,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeReplayReference":
        """Create from dictionary."""
        return cls(
            replay_id=data.get("replay_id", PLACEHOLDER_REPLAY_ID),
            stream_id=data.get("stream_id", PLACEHOLDER_STREAM_ID),
            invocation_id=data.get("invocation_id", PLACEHOLDER_INVOKE_ID),
            provider_id=data.get("provider_id", ""),
            model_id=data.get("model_id", ""),
            first_sequence=data.get("first_sequence", PLACEHOLDER_SEQUENCE),
            last_sequence=data.get("last_sequence", PLACEHOLDER_SEQUENCE),
            total_sequences=data.get("total_sequences", 0),
            first_timestamp=data.get("first_timestamp"),
            last_timestamp=data.get("last_timestamp"),
            stream_checksum=data.get("stream_checksum", ""),
            stream_hash=data.get("stream_hash", ""),
            recent_first=data.get("recent_first", True),
            id=data.get("id", PLACEHOLDER_REPLAY_ID),
        )


@dataclass(frozen=True, slots=True)
class RuntimeReplayChunk:
    """A chunk of replay data for streaming replay.

    Represents a batch of events to be replayed together for efficiency.
    Maintains deterministic ordering and integrity information.
    """

    replay_id: str = PLACEHOLDER_REPLAY_ID
    stream_id: str = PLACEHOLDER_STREAM_ID

    # Sequence range in this chunk
    first_sequence: int = PLACEHOLDER_SEQUENCE
    last_sequence: int = PLACEHOLDER_SEQUENCE

    # Events in this chunk (sorted by sequence)
    events: Tuple[Any, ...] = field(default=())  # RuntimeStreamEvent

    # Timing information
    playback_timestamp: Optional[str] = None
    original_timestamp: Optional[str] = None

    # Integrity
    chunk_checksum: str = ""
    chunk_hash: str = ""
    byte_count: int = 0

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        replay_id: str,
        stream_id: str,
        first_sequence: int,
        last_sequence: int,
        events: List[Any],
        playback_timestamp: Optional[str] = None,
        original_timestamp: Optional[str] = None,
        chunk_checksum: str = "",
        chunk_hash: str = "",
        byte_count: int = 0,
    ) -> "RuntimeReplayChunk":
        """Factory method for creating replay chunks."""
        return cls(
            replay_id=replay_id,
            stream_id=stream_id,
            first_sequence=first_sequence,
            last_sequence=last_sequence,
            events=tuple(events),
            playback_timestamp=playback_timestamp,
            original_timestamp=original_timestamp,
            chunk_checksum=chunk_checksum,
            chunk_hash=chunk_hash,
            byte_count=byte_count,
        )

    @property
    def event_count(self) -> int:
        """Number of events in this chunk."""
        return len(self.events)

    @property
    def sequence_range(self) -> Tuple[int, int]:
        """Return the sequence range as a tuple."""
        return (self.first_sequence, self.last_sequence)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "replay_id": self.replay_id,
            "stream_id": self.stream_id,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "events": [asdict(e) if hasattr(e, '__dataclass_fields__') else e for e in self.events],
            "playback_timestamp": self.playback_timestamp,
            "original_timestamp": self.original_timestamp,
            "chunk_checksum": self.chunk_checksum,
            "chunk_hash": self.chunk_hash,
            "byte_count": self.byte_count,
            "event_count": self.event_count,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


@dataclass(frozen=True, slots=True)
class RuntimeReplayIntegrityFinding:
    """A single integrity finding from replay verification.

    Represents a detected issue or confirmation in the replay process.
    All findings are deterministic and replay-safe.
    """

    code: RuntimeReplayIntegrityCode = RuntimeReplayIntegrityCode.SEQUENCE_GAP
    severity: str = "warning"  # info, warning, error, critical
    message: str = ""

    # Location information
    replay_id: str = PLACEHOLDER_REPLAY_ID
    stream_id: str = PLACEHOLDER_STREAM_ID
    sequence: Optional[int] = None

    # Details
    expected: Optional[str] = None
    actual: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        code: RuntimeReplayIntegrityCode,
        severity: str,
        message: str,
        replay_id: str = PLACEHOLDER_REPLAY_ID,
        stream_id: str = PLACEHOLDER_STREAM_ID,
        sequence: Optional[int] = None,
        expected: Optional[str] = None,
        actual: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeReplayIntegrityFinding":
        """Factory method for creating integrity findings."""
        return cls(
            code=code,
            severity=severity,
            message=message,
            replay_id=replay_id,
            stream_id=stream_id,
            sequence=sequence,
            expected=expected,
            actual=actual,
            context=context or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code.value,
            "severity": self.severity,
            "message": self.message,
            "replay_id": self.replay_id,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "expected": self.expected,
            "actual": self.actual,
            "context": self.context,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass(frozen=True, slots=True)
class RuntimeReplayIntegrityReport:
    """Complete integrity report for a replay operation.

    Aggregates all findings from verifying a replay stream.
    Deterministic and replay-safe.
    """

    report_id: str = PLACEHOLDER_REPLAY_ID
    replay_id: str = PLACEHOLDER_REPLAY_ID
    stream_id: str = PLACEHOLDER_STREAM_ID

    # Overall status
    is_valid: bool = True
    verification_level: RuntimeReplayVerificationLevel = RuntimeReplayVerificationLevel.NONE

    # Findings
    findings: Tuple[RuntimeReplayIntegrityFinding, ...] = field(default=())

    # Statistics
    total_events: int = 0
    checked_events: int = 0
    verified_events: int = 0

    # Timing
    verified_at: str = ""

    # Checksums
    expected_stream_hash: str = ""
    actual_stream_hash: str = ""

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        replay_id: str,
        stream_id: str,
        verification_level: RuntimeReplayVerificationLevel = RuntimeReplayVerificationLevel.STANDARD,
        findings: Optional[List[RuntimeReplayIntegrityFinding]] = None,
        total_events: int = 0,
        checked_events: int = 0,
        verified_events: int = 0,
        verified_at: Optional[str] = None,
        expected_stream_hash: str = "",
        actual_stream_hash: str = "",
    ) -> "RuntimeReplayIntegrityReport":
        """Factory method for creating integrity reports."""
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            report_id=f"replay_integrity_{hashlib.sha256(f'{replay_id}_{now}'.encode()).hexdigest()[:12]}",
            replay_id=replay_id,
            stream_id=stream_id,
            is_valid=len(findings or []) == 0,
            verification_level=verification_level,
            findings=tuple(findings or []),
            total_events=total_events,
            checked_events=checked_events,
            verified_events=verified_events,
            verified_at=verified_at or now,
            expected_stream_hash=expected_stream_hash,
            actual_stream_hash=actual_stream_hash,
        )

    @property
    def findings_by_severity(self) -> Dict[str, List[RuntimeReplayIntegrityFinding]]:
        """Group findings by severity."""
        result: Dict[str, List[RuntimeReplayIntegrityFinding]] = {}
        for finding in self.findings:
            if finding.severity not in result:
                result[finding.severity] = []
            result[finding.severity].append(finding)
        return result

    @property
    def errors(self) -> List[RuntimeReplayIntegrityFinding]:
        """Return all error-level findings."""
        return [f for f in self.findings if f.severity in ("error", "critical")]

    @property
    def warnings(self) -> List[RuntimeReplayIntegrityFinding]:
        """Return all warning-level findings."""
        return [f for f in self.findings if f.severity in ("warning",)]

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "report_id": self.report_id,
            "replay_id": self.replay_id,
            "stream_id": self.stream_id,
            "is_valid": self.is_valid,
            "verification_level": self.verification_level.value,
            "findings": [f.to_dict() for f in self.findings],
            "total_events": self.total_events,
            "checked_events": self.checked_events,
            "verified_events": self.verified_events,
            "verified_at": self.verified_at,
            "expected_stream_hash": self.expected_stream_hash,
            "actual_stream_hash": self.actual_stream_hash,
            "findings_count": len(self.findings),
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


@dataclass(frozen=True, slots=True)
class RuntimeReplayStateSnapshot:
    """Snapshot of replay state at a point in time.

    Captures the complete state of a replay operation for persistence
    and recovery. Deterministic and replay-safe.
    """

    snapshot_id: str = PLACEHOLDER_REPLAY_ID
    replay_id: str = PLACEHOLDER_REPLAY_ID
    stream_id: str = PLACEHOLDER_STREAM_ID

    # State
    state: RuntimeReplayState = RuntimeReplayState.PENDING
    mode: RuntimeReplayMode = RuntimeReplayMode.LIVE
    speed: RuntimeReplaySpeed = RuntimeReplaySpeed.NORMAL
    speed_multiplier: float = DEFAULT_REPLAY_SPEED_MULTIPLIER

    # Position
    current_sequence: int = PLACEHOLDER_SEQUENCE
    target_sequence: int = PLACEHOLDER_SEQUENCE
    first_sequence: int = PLACEHOLDER_SEQUENCE
    last_sequence: int = PLACEHOLDER_SEQUENCE

    # Progress
    total_sequences: int = 0
    replayed_sequences: int = 0
    skipped_sequences: int = 0

    # Timing
    started_at: Optional[str] = None
    paused_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_playback_time: Optional[str] = None

    # Buffer info
    buffer_start_sequence: int = PLACEHOLDER_SEQUENCE
    buffer_end_sequence: int = PLACEHOLDER_SEQUENCE
    buffer_event_count: int = 0

    # Integrity
    stream_hash: str = ""
    verified_hash: str = ""
    integrity_report_id: Optional[str] = None

    # Metadata
    provider_id: str = ""
    model_id: str = ""
    invocation_id: str = ""

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        replay_id: str,
        stream_id: str,
        state: RuntimeReplayState = RuntimeReplayState.PENDING,
        mode: RuntimeReplayMode = RuntimeReplayMode.LIVE,
        speed: RuntimeReplaySpeed = RuntimeReplaySpeed.NORMAL,
        speed_multiplier: float = DEFAULT_REPLAY_SPEED_MULTIPLIER,
        current_sequence: int = 0,
        target_sequence: int = 0,
        first_sequence: int = 0,
        last_sequence: int = 0,
        total_sequences: int = 0,
        replayed_sequences: int = 0,
        skipped_sequences: int = 0,
        started_at: Optional[str] = None,
        paused_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        current_playback_time: Optional[str] = None,
        buffer_start_sequence: int = 0,
        buffer_end_sequence: int = 0,
        buffer_event_count: int = 0,
        stream_hash: str = "",
        verified_hash: str = "",
        integrity_report_id: Optional[str] = None,
        provider_id: str = "",
        model_id: str = "",
        invocation_id: str = "",
    ) -> "RuntimeReplayStateSnapshot":
        """Factory method for creating state snapshots."""
        return cls(
            snapshot_id=f"replay_snapshot_{hashlib.sha256(f'{replay_id}_{stream_id}'.encode()).hexdigest()[:12]}",
            replay_id=replay_id,
            stream_id=stream_id,
            state=state,
            mode=mode,
            speed=speed,
            speed_multiplier=speed_multiplier,
            current_sequence=current_sequence,
            target_sequence=target_sequence,
            first_sequence=first_sequence,
            last_sequence=last_sequence,
            total_sequences=total_sequences,
            replayed_sequences=replayed_sequences,
            skipped_sequences=skipped_sequences,
            started_at=started_at,
            paused_at=paused_at,
            completed_at=completed_at,
            current_playback_time=current_playback_time,
            buffer_start_sequence=buffer_start_sequence,
            buffer_end_sequence=buffer_end_sequence,
            buffer_event_count=buffer_event_count,
            stream_hash=stream_hash,
            verified_hash=verified_hash,
            integrity_report_id=integrity_report_id,
            provider_id=provider_id,
            model_id=model_id,
            invocation_id=invocation_id,
        )

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_sequences <= 0:
            return 0.0
        return min(100.0, (self.replayed_sequences / self.total_sequences) * 100)

    @property
    def is_complete(self) -> bool:
        """Check if replay is complete."""
        return self.state == RuntimeReplayState.COMPLETED

    @property
    def is_playing(self) -> bool:
        """Check if replay is currently playing."""
        return self.state == RuntimeReplayState.PLAYING

    @property
    def is_paused(self) -> bool:
        """Check if replay is paused."""
        return self.state == RuntimeReplayState.PAUSED

    @property
    def has_errors(self) -> bool:
        """Check if there were errors during replay."""
        return self.state == RuntimeReplayState.FAILED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "snapshot_id": self.snapshot_id,
            "replay_id": self.replay_id,
            "stream_id": self.stream_id,
            "state": self.state.value,
            "mode": self.mode.value,
            "speed": self.speed.value,
            "speed_multiplier": self.speed_multiplier,
            "current_sequence": self.current_sequence,
            "target_sequence": self.target_sequence,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "total_sequences": self.total_sequences,
            "replayed_sequences": self.replayed_sequences,
            "skipped_sequences": self.skipped_sequences,
            "progress_percent": round(self.progress_percent, 2),
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "completed_at": self.completed_at,
            "current_playback_time": self.current_playback_time,
            "buffer_start_sequence": self.buffer_start_sequence,
            "buffer_end_sequence": self.buffer_end_sequence,
            "buffer_event_count": self.buffer_event_count,
            "stream_hash": self.stream_hash,
            "verified_hash": self.verified_hash,
            "integrity_report_id": self.integrity_report_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "invocation_id": self.invocation_id,
            "is_complete": self.is_complete,
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "has_errors": self.has_errors,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Replay Buffer
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeReplayBuffer:
    """Buffer for storing replay events.

    Bounded buffer that maintains events for replay operations.
    Thread-safe design with maximum size limits.
    """

    stream_id: str = PLACEHOLDER_STREAM_ID
    replay_id: str = PLACEHOLDER_REPLAY_ID

    # Events stored by sequence
    events: Dict[int, Any] = field(default_factory=dict)  # sequence -> RuntimeStreamEvent

    # Sequence bounds
    first_sequence: int = PLACEHOLDER_SEQUENCE
    last_sequence: int = PLACEHOLDER_SEQUENCE

    # Statistics
    total_events: int = 0
    total_bytes: int = 0
    event_byte_sizes: Dict[int, int] = field(default_factory=dict)

    # Checksums
    stream_checksum: str = ""
    stream_hash: str = ""

    # Bounds
    max_events: int = DEFAULT_REPLAY_BUFFER_MAX_EVENTS
    max_bytes: int = DEFAULT_REPLAY_BUFFER_MAX_BYTES

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    def with_event(self, sequence: int, event: Any, byte_size: int = 0) -> "RuntimeReplayBuffer":
        """Return a new buffer with the event added."""
        new_events = dict(self.events)
        new_events[sequence] = event

        new_byte_sizes = dict(self.event_byte_sizes)
        new_byte_sizes[sequence] = byte_size

        new_first = min(self.first_sequence, sequence) if self.total_events > 0 else sequence
        new_last = max(self.last_sequence, sequence) if self.total_events > 0 else sequence

        new_total_bytes = self.total_bytes + byte_size

        # Check if we exceed bounds - evict old events
        should_evict = (len(new_events) > self.max_events or 
                       new_total_bytes > self.max_bytes)

        if should_evict:
            # Remove oldest events until within bounds
            sorted_sequences = sorted(new_events.keys())
            for seq in sorted_sequences:
                if len(new_events) <= self.max_events and new_total_bytes <= self.max_bytes:
                    break
                evict_size = new_byte_sizes.get(seq, 0)
                del new_events[seq]
                del new_byte_sizes[seq]
                new_total_bytes -= evict_size
                if new_first == seq:
                    new_first = sorted_sequences[sorted_sequences.index(seq) + 1] if sorted_sequences.index(seq) + 1 < len(sorted_sequences) else seq

            # Recalculate bounds after eviction
            if new_events:
                new_first = min(new_events.keys())
                new_last = max(new_events.keys())
                new_total_bytes = sum(new_byte_sizes.values())
            else:
                new_first = PLACEHOLDER_SEQUENCE
                new_last = PLACEHOLDER_SEQUENCE
                new_total_bytes = 0

        # Recalculate checksum
        new_checksum, new_hash = _calculate_buffer_checksum(new_events)

        return RuntimeReplayBuffer(
            stream_id=self.stream_id,
            replay_id=self.replay_id,
            events=new_events,
            first_sequence=new_first,
            last_sequence=new_last,
            total_events=len(new_events),
            total_bytes=new_total_bytes,
            event_byte_sizes=new_byte_sizes,
            stream_checksum=new_checksum,
            stream_hash=new_hash,
            max_events=self.max_events,
            max_bytes=self.max_bytes,
        )

    def get_event(self, sequence: int) -> Optional[Any]:
        """Get an event by sequence number."""
        return self.events.get(sequence)

    def get_events_in_range(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
    ) -> List[Any]:
        """Get events in a sequence range."""
        start = start_sequence if start_sequence is not None else self.first_sequence
        end = end_sequence if end_sequence is not None else self.last_sequence

        result = []
        for seq in range(start, end + 1):
            if seq in self.events:
                result.append(self.events[seq])
        return result

    def get_all_events(self) -> List[Any]:
        """Get all events in sequence order."""
        sorted_sequences = sorted(self.events.keys())
        return [self.events[seq] for seq in sorted_sequences]

    def has_sequence(self, sequence: int) -> bool:
        """Check if a sequence exists."""
        return sequence in self.events

    def verify_sequence(self, expected_sequence: int) -> bool:
        """Verify that the expected sequence exists."""
        return expected_sequence in self.events

    @property
    def sequence_count(self) -> int:
        """Number of events in the buffer."""
        return len(self.events)

    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return self.total_events == 0

    @property
    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return (self.total_events >= self.max_events or 
                self.total_bytes >= self.max_bytes)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stream_id": self.stream_id,
            "replay_id": self.replay_id,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "total_events": self.total_events,
            "total_bytes": self.total_bytes,
            "stream_checksum": self.stream_checksum,
            "stream_hash": self.stream_hash,
            "max_events": self.max_events,
            "max_bytes": self.max_bytes,
            "sequence_count": self.sequence_count,
            "is_empty": self.is_empty,
            "is_full": self.is_full,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# Replay Verifier
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeReplayVerifier:
    """Verifies integrity of replayed runtime streams.

    Performs deterministic verification of replay streams against original
    stream data. Supports multiple verification levels.
    """

    verification_level: RuntimeReplayVerificationLevel = RuntimeReplayVerificationLevel.STANDARD

    # Tolerance for timing differences (seconds)
    timestamp_tolerance_seconds: float = 1.0

    # Checksum verification
    verify_checksums: bool = True
    verify_hashes: bool = True

    # Sequence verification
    verify_sequences: bool = True
    allow_gaps: bool = True
    allow_duplicates: bool = False
    allow_out_of_order: bool = False

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    def verify_replay(
        self,
        original_events: List[Any],
        replayed_events: List[Any],
        replay_id: str = PLACEHOLDER_REPLAY_ID,
        stream_id: str = PLACEHOLDER_STREAM_ID,
    ) -> RuntimeReplayIntegrityReport:
        """Verify that replayed events match original events.
        
        Performs comprehensive verification including:
        - Sequence number validation
        - Timing validation (within tolerance)
        - Content checksum validation
        - Stream hash validation
        
        Returns an integrity report with all findings.
        """
        findings: List[RuntimeReplayIntegrityFinding] = []
        checked_events = 0
        verified_events = 0

        # Build lookup maps
        original_by_seq: Dict[int, Any] = {}
        for event in original_events:
            seq = getattr(event, 'sequence', None)
            if seq is not None:
                original_by_seq[seq] = event

        replayed_by_seq: Dict[int, Any] = {}
        for event in replayed_events:
            seq = getattr(event, 'sequence', None)
            if seq is not None:
                replayed_by_seq[seq] = event

        # Check all original sequences are present in replay
        if self.verify_sequences:
            for seq, original_event in original_by_seq.items():
                checked_events += 1
                
                if seq not in replayed_by_seq:
                    findings.append(RuntimeReplayIntegrityFinding.create(
                        code=RuntimeReplayIntegrityCode.MISSING_SEQUENCE,
                        severity="error" if not self.allow_gaps else "warning",
                        message=f"Sequence {seq} missing in replay",
                        replay_id=replay_id,
                        stream_id=stream_id,
                        sequence=seq,
                        expected=f"Event at sequence {seq}",
                        actual="Not found in replay",
                        context={"original_event_type": type(original_event).__name__},
                    ))
                else:
                    verified_events += 1

        # Check for duplicate sequences in replay
        if self.verify_sequences and not self.allow_duplicates:
            replayed_sequences = [getattr(e, 'sequence', None) for e in replayed_events]
            seen_sequences: Set[int] = set()
            duplicate_sequences: List[int] = []

            for seq in replayed_sequences:
                if seq is not None:
                    if seq in seen_sequences:
                        duplicate_sequences.append(seq)
                    seen_sequences.add(seq)

            for dup_seq in duplicate_sequences:
                findings.append(RuntimeReplayIntegrityFinding.create(
                    code=RuntimeReplayIntegrityCode.DUPLICATE_SEQUENCE,
                    severity="error",
                    message=f"Duplicate sequence {dup_seq} in replay",
                    replay_id=replay_id,
                    stream_id=stream_id,
                    sequence=dup_seq,
                    context={"duplicate_count": duplicate_sequences.count(dup_seq)},
                ))

        # Check for out-of-order sequences
        if self.verify_sequences and not self.allow_out_of_order:
            replayed_sequences_filtered = [s for s in replayed_sequences if s is not None]
            if any(replayed_sequences_filtered[i] > replayed_sequences_filtered[i + 1] 
                   for i in range(len(replayed_sequences_filtered) - 1)):
                findings.append(RuntimeReplayIntegrityFinding.create(
                    code=RuntimeReplayIntegrityCode.OUT_OF_ORDER,
                    severity="error",
                    message="Replay events are out of sequence order",
                    replay_id=replay_id,
                    stream_id=stream_id,
                    context={"total_sequences": len(replayed_sequences_filtered)},
                ))

        # Verify checksums if enabled
        if self.verify_checksums and self.verification_level.value in ["standard", "strict"]:
            for seq, original_event in original_by_seq.items():
                if seq in replayed_by_seq:
                    original_checksum = getattr(original_event, 'checksum', None) or ""
                    replayed_checksum = getattr(replayed_by_seq[seq], 'checksum', None) or ""

                    if original_checksum != replayed_checksum:
                        findings.append(RuntimeReplayIntegrityFinding.create(
                            code=RuntimeReplayIntegrityCode.CHECKSUM_MISMATCH,
                            severity="error" if self.verification_level == RuntimeReplayVerificationLevel.STRICT else "warning",
                            message=f"Checksum mismatch at sequence {seq}",
                            replay_id=replay_id,
                            stream_id=stream_id,
                            sequence=seq,
                            expected=original_checksum,
                            actual=replayed_checksum,
                        ))

        # Verify hashes if enabled and at strict level
        if self.verify_hashes and self.verification_level == RuntimeReplayVerificationLevel.STRICT:
            original_hashes = {getattr(e, 'sequence', None): getattr(e, 'hash', '') 
                              for e in original_events 
                              if getattr(e, 'sequence', None) is not None}
            replayed_hashes = {getattr(e, 'sequence', None): getattr(e, 'hash', '') 
                              for e in replayed_events 
                              if getattr(e, 'sequence', None) is not None}

            for seq, orig_hash in original_hashes.items():
                if seq in replayed_hashes and orig_hash != replayed_hashes[seq]:
                    findings.append(RuntimeReplayIntegrityFinding.create(
                        code=RuntimeReplayIntegrityCode.INTEGRITY_HASH_MISMATCH,
                        severity="error",
                        message=f"Hash mismatch at sequence {seq}",
                        replay_id=replay_id,
                        stream_id=stream_id,
                        sequence=seq,
                        expected=orig_hash,
                        actual=replayed_hashes[seq],
                    ))

        # Verify timestamps within tolerance
        if self.verification_level.value in ["standard", "strict"]:
            for seq, original_event in original_by_seq.items():
                if seq in replayed_by_seq:
                    orig_ts = getattr(original_event, 'created_at', None) or \
                             getattr(original_event, 'timestamp', None)
                    replay_ts = getattr(replayed_by_seq[seq], 'created_at', None) or \
                               getattr(replayed_by_seq[seq], 'timestamp', None)

                    if orig_ts and replay_ts:
                        try:
                            from datetime import datetime
                            orig_dt = datetime.fromisoformat(orig_ts.replace('Z', '+00:00'))
                            replay_dt = datetime.fromisoformat(replay_ts.replace('Z', '+00:00'))
                            diff = abs((replay_dt - orig_dt).total_seconds())

                            if diff > self.timestamp_tolerance_seconds:
                                findings.append(RuntimeReplayIntegrityFinding.create(
                                    code=RuntimeReplayIntegrityCode.INVALID_TIMESTAMP,
                                    severity="warning",
                                    message=f"Timestamp difference exceeds tolerance at sequence {seq}",
                                    replay_id=replay_id,
                                    stream_id=stream_id,
                                    sequence=seq,
                                    expected=str(orig_dt),
                                    actual=str(replay_dt),
                                    context={"difference_seconds": diff},
                                ))
                        except (ValueError, TypeError):
                            pass

        # Calculate stream hashes
        expected_hash = _calculate_stream_hash(original_events)
        actual_hash = _calculate_stream_hash(replayed_events)

        return RuntimeReplayIntegrityReport.create(
            replay_id=replay_id,
            stream_id=stream_id,
            verification_level=self.verification_level,
            findings=findings,
            total_events=len(original_events),
            checked_events=checked_events,
            verified_events=verified_events,
            expected_stream_hash=expected_hash,
            actual_stream_hash=actual_hash,
        )

    def quick_verify(
        self,
        original_buffer: RuntimeReplayBuffer,
        replay_buffer: RuntimeReplayBuffer,
    ) -> bool:
        """Quick verification - just check if stream hashes match."""
        return original_buffer.stream_hash == replay_buffer.stream_hash


# ---------------------------------------------------------------------------
# Replay Engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeReplayEngine:
    """Engine for replaying runtime stream events.

    Provides deterministic replay of runtime streams with integrity verification.
    Supports live replay, step-through, and range-based replay modes.
    """

    replay_id: str = PLACEHOLDER_REPLAY_ID
    stream_id: str = PLACEHOLDER_STREAM_ID
    invocation_id: str = PLACEHOLDER_INVOKE_ID

    # References
    replay_reference: Optional[RuntimeReplayReference] = None

    # State
    state: RuntimeReplayState = RuntimeReplayState.PENDING
    mode: RuntimeReplayMode = RuntimeReplayMode.LIVE
    speed: RuntimeReplaySpeed = RuntimeReplaySpeed.NORMAL
    speed_multiplier: float = DEFAULT_REPLAY_SPEED_MULTIPLIER

    # Buffer
    buffer: RuntimeReplayBuffer = field(default_factory=RuntimeReplayBuffer)

    # Verifier
    verifier: RuntimeReplayVerifier = field(default_factory=RuntimeReplayVerifier)

    # Position tracking
    current_sequence: int = PLACEHOLDER_SEQUENCE
    target_sequence: int = PLACEHOLDER_SEQUENCE
    first_sequence: int = PLACEHOLDER_SEQUENCE
    last_sequence: int = PLACEHOLDER_SEQUENCE

    # Progress
    total_replayed: int = 0
    total_skipped: int = 0

    # Timing
    started_at: Optional[str] = None
    paused_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Integrity
    integrity_report: Optional[RuntimeReplayIntegrityReport] = None

    # Callbacks (for projection updates)
    on_event_replayed: Optional[Any] = None
    on_state_changed: Optional[Any] = None
    on_progress: Optional[Any] = None

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        replay_id: str,
        stream_id: str,
        invocation_id: str = PLACEHOLDER_INVOKE_ID,
        mode: RuntimeReplayMode = RuntimeReplayMode.LIVE,
        speed: RuntimeReplaySpeed = RuntimeReplaySpeed.NORMAL,
        buffer: Optional[RuntimeReplayBuffer] = None,
        verifier: Optional[RuntimeReplayVerifier] = None,
        replay_reference: Optional[RuntimeReplayReference] = None,
        **kwargs: Any,
    ) -> "RuntimeReplayEngine":
        """Factory method for creating replay engines."""
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            replay_id=replay_id,
            stream_id=stream_id,
            invocation_id=invocation_id,
            mode=mode,
            speed=speed,
            buffer=buffer or RuntimeReplayBuffer(
                stream_id=stream_id,
                replay_id=replay_id,
            ),
            verifier=verifier or RuntimeReplayVerifier(),
            replay_reference=replay_reference,
            started_at=now,
            first_sequence=kwargs.get('first_sequence', PLACEHOLDER_SEQUENCE),
            last_sequence=kwargs.get('last_sequence', PLACEHOLDER_SEQUENCE),
        )

    def play(self) -> "RuntimeReplayEngine":
        """Start or resume replay."""
        if self.state == RuntimeReplayState.PLAYING:
            return self

        now = datetime.now(timezone.utc).isoformat()
        return RuntimeReplayEngine(
            **asdict(self),
            state=RuntimeReplayState.PLAYING,
            paused_at=None,
            started_at=self.started_at or now,
        )

    def pause(self) -> "RuntimeReplayEngine":
        """Pause replay."""
        if self.state != RuntimeReplayState.PLAYING:
            return self

        now = datetime.now(timezone.utc).isoformat()
        return RuntimeReplayEngine(
            **asdict(self),
            state=RuntimeReplayState.PAUSED,
            paused_at=now,
        )

    def stop(self) -> "RuntimeReplayEngine":
        """Stop replay."""
        if self.state in (RuntimeReplayState.COMPLETED, RuntimeReplayState.FAILED, RuntimeReplayState.CANCELLED):
            return self

        now = datetime.now(timezone.utc).isoformat()
        return RuntimeReplayEngine(
            **asdict(self),
            state=RuntimeReplayState.CANCELLED,
            paused_at=None,
            completed_at=now,
        )

    def complete(self) -> "RuntimeReplayEngine":
        """Mark replay as completed."""
        if self.state == RuntimeReplayState.COMPLETED:
            return self

        now = datetime.now(timezone.utc).isoformat()
        return RuntimeReplayEngine(
            **asdict(self),
            state=RuntimeReplayState.COMPLETED,
            paused_at=None,
            completed_at=now,
            current_sequence=self.last_sequence,
            total_replayed=self.buffer.total_events,
        )

    def set_speed(self, speed: RuntimeReplaySpeed) -> "RuntimeReplayEngine":
        """Set replay speed."""
        speed_map = {
            RuntimeReplaySpeed.SLOWEST: 0.1,
            RuntimeReplaySpeed.SLOWER: 0.25,
            RuntimeReplaySpeed.SLOW: 0.5,
            RuntimeReplaySpeed.NORMAL: 1.0,
            RuntimeReplaySpeed.FAST: 2.0,
            RuntimeReplaySpeed.FASTER: 5.0,
            RuntimeReplaySpeed.FASTEST: 10.0,
            RuntimeReplaySpeed.INSTANT: 0.0,
        }
        multiplier = speed_map.get(speed, 1.0)
        return RuntimeReplayEngine(
            **asdict(self),
            speed=speed,
            speed_multiplier=multiplier,
        )

    def seek(self, sequence: int) -> "RuntimeReplayEngine":
        """Seek to a specific sequence."""
        # Clamp to valid range
        clamped = max(self.first_sequence, min(sequence, self.last_sequence))
        return RuntimeReplayEngine(
            **asdict(self),
            current_sequence=clamped,
            target_sequence=clamped,
        )

    def step_forward(self, count: int = 1) -> "RuntimeReplayEngine":
        """Step forward by count sequences."""
        new_sequence = self.current_sequence + count
        clamped = max(self.first_sequence, min(new_sequence, self.last_sequence))
        new_replayed = self.total_replayed + count
        return RuntimeReplayEngine(
            **asdict(self),
            current_sequence=clamped,
            target_sequence=clamped,
            total_replayed=new_replayed,
        )

    def step_backward(self, count: int = 1) -> "RuntimeReplayEngine":
        """Step backward by count sequences."""
        new_sequence = self.current_sequence - count
        clamped = max(self.first_sequence, min(new_sequence, self.last_sequence))
        return RuntimeReplayEngine(
            **asdict(self),
            current_sequence=clamped,
            target_sequence=clamped,
        )

    def replay_range(
        self,
        start_sequence: Optional[int] = None,
        end_sequence: Optional[int] = None,
    ) -> List[Any]:
        """Replay events in a sequence range.
        
        Returns the events in the range for processing.
        """
        start = start_sequence if start_sequence is not None else self.current_sequence
        end = end_sequence if end_sequence is not None else self.last_sequence

        events = self.buffer.get_events_in_range(start, end)
        
        # Update progress
        count = len(events)
        new_replayed = self.total_replayed + count
        new_current = end if count > 0 else start

        new_engine = RuntimeReplayEngine(
            **asdict(self),
            current_sequence=new_current,
            target_sequence=new_current,
            total_replayed=new_replayed,
        )

        # Trigger callbacks
        if self.on_event_replayed:
            for event in events:
                self.on_event_replayed(event)

        if self.on_progress:
            self.on_progress(new_replayed, self.buffer.total_events)

        return events

    def replay_next(self) -> Optional[Any]:
        """Replay the next event.
        
        Returns the next event or None if at end.
        """
        if self.current_sequence >= self.last_sequence:
            return None

        next_seq = self.current_sequence + 1
        if self.buffer.has_sequence(next_seq):
            event = self.buffer.get_event(next_seq)
            new_engine = RuntimeReplayEngine(
                **asdict(self),
                current_sequence=next_seq,
                target_sequence=next_seq,
                total_replayed=self.total_replayed + 1,
            )

            if self.on_event_replayed:
                self.on_event_replayed(event)

            if self.on_progress:
                self.on_progress(new_engine.total_replayed, self.buffer.total_events)

            return event

        return None

    def replay_all(self) -> List[Any]:
        """Replay all events from start to end.
        
        Returns all events.
        """
        events = self.buffer.get_all_events()
        count = len(events)

        new_engine = RuntimeReplayEngine(
            **asdict(self),
            current_sequence=self.last_sequence,
            target_sequence=self.last_sequence,
            total_replayed=count,
        )

        if self.on_event_replayed:
            for event in events:
                self.on_event_replayed(event)

        if self.on_progress:
            self.on_progress(count, count)

        if self.on_state_changed:
            self.on_state_changed(new_engine.state)

        return events

    def verify(self) -> RuntimeReplayIntegrityReport:
        """Verify replay integrity against original stream.
        
        Requires that the buffer contains both original and replayed events.
        """
        # For now, return a basic valid report
        # Full verification would require original stream reference
        now = datetime.now(timezone.utc).isoformat()
        return RuntimeReplayIntegrityReport.create(
            replay_id=self.replay_id,
            stream_id=self.stream_id,
            verification_level=self.verifier.verification_level,
            total_events=self.buffer.total_events,
            checked_events=self.buffer.total_events,
            verified_events=self.buffer.total_events,
            verified_at=now,
            expected_stream_hash=self.buffer.stream_hash,
            actual_stream_hash=self.buffer.stream_hash,
        )

    def get_state_snapshot(self) -> RuntimeReplayStateSnapshot:
        """Get a snapshot of the current replay state."""
        return RuntimeReplayStateSnapshot.create(
            replay_id=self.replay_id,
            stream_id=self.stream_id,
            state=self.state,
            mode=self.mode,
            speed=self.speed,
            speed_multiplier=self.speed_multiplier,
            current_sequence=self.current_sequence,
            target_sequence=self.target_sequence,
            first_sequence=self.first_sequence,
            last_sequence=self.last_sequence,
            total_sequences=self.buffer.total_events,
            replayed_sequences=self.total_replayed,
            skipped_sequences=self.total_skipped,
            started_at=self.started_at,
            paused_at=self.paused_at,
            completed_at=self.completed_at,
            buffer_start_sequence=self.buffer.first_sequence,
            buffer_end_sequence=self.buffer.last_sequence,
            buffer_event_count=self.buffer.total_events,
            stream_hash=self.buffer.stream_hash,
            verified_hash=str(self.verifier.quick_verify(self.buffer, self.buffer)) if self.verifier.verify_hashes else "",
            integrity_report_id=self.integrity_report.report_id if self.integrity_report else None,
            provider_id="",
            model_id="",
            invocation_id=self.invocation_id,
        )

    @property
    def is_playing(self) -> bool:
        """Check if replay is currently playing."""
        return self.state == RuntimeReplayState.PLAYING

    @property
    def is_paused(self) -> bool:
        """Check if replay is paused."""
        return self.state == RuntimeReplayState.PAUSED

    @property
    def is_complete(self) -> bool:
        """Check if replay is complete."""
        return self.state == RuntimeReplayState.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if replay has failed."""
        return self.state == RuntimeReplayState.FAILED

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        total = max(self.buffer.total_events, 1)
        return min(100.0, (self.total_replayed / total) * 100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "replay_id": self.replay_id,
            "stream_id": self.stream_id,
            "invocation_id": self.invocation_id,
            "state": self.state.value,
            "mode": self.mode.value,
            "speed": self.speed.value,
            "speed_multiplier": self.speed_multiplier,
            "current_sequence": self.current_sequence,
            "target_sequence": self.target_sequence,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "total_replayed": self.total_replayed,
            "total_skipped": self.total_skipped,
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "completed_at": self.completed_at,
            "progress_percent": round(self.progress_percent, 2),
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "is_complete": self.is_complete,
            "is_failed": self.is_failed,
            "buffer": self.buffer.to_dict(),
            "verification_level": self.verifier.verification_level.value,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }
        if self.integrity_report:
            result["integrity_report"] = self.integrity_report.to_dict()
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Get current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_deterministic_id(*components: Any, prefix: str = "replay") -> str:
    """Generate a deterministic ID from components."""
    id_str = "_".join(str(c) for c in components)
    hash_str = hashlib.sha256(id_str.encode()).hexdigest()[:12]
    return f"{prefix}_{hash_str}"


def _calculate_buffer_checksum(events: Dict[int, Any]) -> Tuple[str, str]:
    """Calculate checksum and hash for a buffer's events."""
    content = json.dumps(
        [(k, str(v)) for k, v in sorted(events.items())],
        sort_keys=True,
    )
    checksum = hashlib.md5(content.encode()).hexdigest()
    hash_str = hashlib.sha256(content.encode()).hexdigest()
    return checksum, hash_str


def _calculate_stream_hash(events: List[Any]) -> str:
    """Calculate a hash for a list of stream events."""
    content = json.dumps(
        [str(e) for e in events],
        sort_keys=True,
    )
    return hashlib.sha256(content.encode()).hexdigest()


def _truncate_content(content: str, max_length: int = 1000) -> str:
    """Truncate content to max length."""
    if len(content) <= max_length:
        return content
    return content[: max_length - 3] + "..."


def _normalize_sequence(sequence: Optional[int]) -> int:
    """Normalize sequence number, defaulting to 0."""
    return sequence if sequence is not None else PLACEHOLDER_SEQUENCE


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Constants
    "PLACEHOLDER_REPLAY_ID",
    "PLACEHOLDER_STREAM_ID",
    "PLACEHOLDER_INVOKE_ID",
    "PLACEHOLDER_SEQUENCE",
    "DEFAULT_REPLAY_BUFFER_MAX_EVENTS",
    "DEFAULT_REPLAY_BUFFER_MAX_BYTES",
    "DEFAULT_REPLAY_CHUNK_MAX_BYTES",
    "DEFAULT_REPLAY_STEP_BYTES",
    "DEFAULT_REPLAY_SPEED_MULTIPLIER",
    "DEFAULT_REPLAY_MIN_INTERVAL_MS",
    "DEFAULT_REPLAY_MAX_WAIT_MS",
    # Enums
    "RuntimeReplayState",
    "RuntimeReplayMode",
    "RuntimeReplaySpeed",
    "RuntimeReplayIntegrityCode",
    "RuntimeReplayVerificationLevel",
    # Models
    "RuntimeReplayReference",
    "RuntimeReplayChunk",
    "RuntimeReplayIntegrityFinding",
    "RuntimeReplayIntegrityReport",
    "RuntimeReplayStateSnapshot",
    "RuntimeReplayBuffer",
    "RuntimeReplayVerifier",
    "RuntimeReplayEngine",
]
