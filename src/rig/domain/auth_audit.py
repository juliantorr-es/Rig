"""Audit logging for UI authentication and authorization events.

This module provides audit logging for auth-related events,
recording to both memory (for testing) and persistent storage.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class AuthAuditEventType(Enum):
    """Types of auth audit events."""
    
    # Connection events
    CLIENT_CONNECTED = "client_connected"
    CLIENT_DISCONNECTED = "client_disconnected"
    CLIENT_REJECTED = "client_rejected"
    
    # Challenge events
    CHALLENGE_ISSUED = "challenge_issued"
    CHALLENGE_COMPLETED = "challenge_completed"
    CHALLENGE_EXPIRED = "challenge_expired"
    
    # Grant events
    GRANT_ISSUED = "grant_issued"
    GRANT_REVOKED = "grant_revoked"
    GRANT_EXPIRED = "grant_expired"
    
    # Intent events
    INTENT_ACCEPTED = "intent_accepted"
    INTENT_REJECTED = "intent_rejected"
    INTENT_STALE = "intent_stale"
    INTENT_DISABLED = "intent_disabled"
    INTENT_UNKNOWN = "intent_unknown"
    INTENT_MISSING_GRANT = "intent_missing_grant"


@dataclass
class AuthAuditEvent:
    """A single audit event record."""
    
    event_type: AuthAuditEventType
    timestamp: str
    client_id: Optional[str] = None
    client_kind: Optional[str] = None
    remote_addr: Optional[str] = None
    
    # Event-specific data
    challenge_id: Optional[str] = None
    grant_id: Optional[str] = None
    intent_kind: Optional[str] = None
    scope: Optional[str] = None
    reason: Optional[str] = None
    reason_code: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "client_id": self.client_id,
            "client_kind": self.client_kind,
            "remote_addr": self.remote_addr,
            "challenge_id": self.challenge_id,
            "grant_id": self.grant_id,
            "intent_kind": self.intent_kind,
            "scope": self.scope,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "details": self.details,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


class AuthAuditLogger:
    """Audit logger for auth-related events.
    
    Logs events to memory (for testing) and optionally to a file.
    """
    
    def __init__(self, repo_root: Optional[Path] = None, log_file: Optional[str] = None):
        self._repo_root = repo_root
        self._log_file = log_file
        self._events: List[AuthAuditEvent] = []
        self._lock = Lock()
        self._log_path: Optional[Path] = None
        
        if repo_root and log_file:
            self._log_path = repo_root / ".build" / "rig" / "logs" / log_file
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def record(self, event: AuthAuditEvent) -> None:
        """Record an audit event."""
        with self._lock:
            self._events.append(event)
            
            # Also log to file if configured
            if self._log_path:
                try:
                    with open(self._log_path, "a") as f:
                        f.write(event.to_json() + "\n")
                except Exception as e:
                    logger.error(f"Failed to write audit log: {e}")
            
            # Log to Python logger at appropriate level
            if event.event_type in (
                AuthAuditEventType.CLIENT_REJECTED,
                AuthAuditEventType.INTENT_REJECTED,
                AuthAuditEventType.INTENT_STALE,
                AuthAuditEventType.INTENT_DISABLED,
                AuthAuditEventType.INTENT_UNKNOWN,
                AuthAuditEventType.INTENT_MISSING_GRANT,
            ):
                logger.warning(
                    f"AUDIT: {event.event_type.value} "
                    f"client={event.client_id} intent={event.intent_kind} "
                    f"reason={event.reason}"
                )
            else:
                logger.info(
                    f"AUDIT: {event.event_type.value} "
                    f"client={event.client_id} grant={event.grant_id} "
                    f"challenge={event.challenge_id}"
                )
    
    def get_events(
        self,
        event_type: Optional[AuthAuditEventType] = None,
        client_id: Optional[str] = None,
    ) -> List[AuthAuditEvent]:
        """Retrieve recorded events optionally filtered by type or client."""
        with self._lock:
            events = self._events.copy()
            
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            
            if client_id:
                events = [e for e in events if e.client_id == client_id]
            
            return events
    
    def clear(self) -> None:
        """Clear all recorded events."""
        with self._lock:
            self._events.clear()
    
    # Convenience methods for common events
    
    def record_client_connected(
        self,
        client_id: str,
        client_kind: str,
        remote_addr: Optional[str] = None,
    ) -> AuthAuditEvent:
        """Record a client connection."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.CLIENT_CONNECTED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            client_kind=client_kind,
            remote_addr=remote_addr,
        )
        self.record(event)
        return event
    
    def record_client_disconnected(
        self,
        client_id: str,
        client_kind: str,
        reason: Optional[str] = None,
    ) -> AuthAuditEvent:
        """Record a client disconnection."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.CLIENT_DISCONNECTED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            client_kind=client_kind,
            reason=reason,
        )
        self.record(event)
        return event
    
    def record_client_rejected(
        self,
        client_id: Optional[str] = None,
        client_kind: Optional[str] = None,
        remote_addr: Optional[str] = None,
        reason: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> AuthAuditEvent:
        """Record a rejected client connection."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.CLIENT_REJECTED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            client_kind=client_kind,
            remote_addr=remote_addr,
            reason=reason,
            reason_code=reason_code,
        )
        self.record(event)
        return event
    
    def record_challenge_issued(
        self,
        challenge_id: str,
        client_id: str,
        scope: str,
        auth_method: str,
    ) -> AuthAuditEvent:
        """Record a challenge issued."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.CHALLENGE_ISSUED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            challenge_id=challenge_id,
            scope=scope,
            details={"auth_method": auth_method},
        )
        self.record(event)
        return event
    
    def record_challenge_completed(
        self,
        challenge_id: str,
        client_id: str,
        verified: bool,
    ) -> AuthAuditEvent:
        """Record a challenge completed."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.CHALLENGE_COMPLETED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            challenge_id=challenge_id,
            details={"verified": verified},
        )
        self.record(event)
        return event
    
    def record_grant_issued(
        self,
        grant_id: str,
        client_id: str,
        scope: str,
        auth_method: str,
    ) -> AuthAuditEvent:
        """Record a grant issued."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.GRANT_ISSUED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            grant_id=grant_id,
            scope=scope,
            details={"auth_method": auth_method},
        )
        self.record(event)
        return event
    
    def record_grant_revoked(
        self,
        grant_id: str,
        client_id: str,
    ) -> AuthAuditEvent:
        """Record a grant revoked."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.GRANT_REVOKED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            grant_id=grant_id,
        )
        self.record(event)
        return event
    
    def record_intent_accepted(
        self,
        client_id: str,
        client_kind: str,
        intent_kind: str,
        grant_id: Optional[str] = None,
    ) -> AuthAuditEvent:
        """Record an accepted intent."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.INTENT_ACCEPTED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            client_kind=client_kind,
            intent_kind=intent_kind,
            grant_id=grant_id,
        )
        self.record(event)
        return event
    
    def record_intent_rejected(
        self,
        client_id: str,
        client_kind: str,
        intent_kind: str,
        reason: str,
        reason_code: Optional[str] = None,
    ) -> AuthAuditEvent:
        """Record a rejected intent."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.INTENT_REJECTED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            client_kind=client_kind,
            intent_kind=intent_kind,
            reason=reason,
            reason_code=reason_code,
        )
        self.record(event)
        return event
    
    def record_intent_missing_grant(
        self,
        client_id: str,
        client_kind: str,
        intent_kind: str,
        required_scope: str,
    ) -> AuthAuditEvent:
        """Record a missing grant rejection."""
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.INTENT_MISSING_GRANT,
            timestamp=datetime.now(timezone.utc).isoformat(),
            client_id=client_id,
            client_kind=client_kind,
            intent_kind=intent_kind,
            scope=required_scope,
            reason=f"Missing grant for scope: {required_scope}",
            reason_code="MISSING_GRANT",
        )
        self.record(event)
        return event


# Global audit logger instance
_audit_logger: Optional[AuthAuditLogger] = None
_audit_logger_lock = Lock()


def get_auth_audit_logger(repo_root: Optional[Path] = None) -> AuthAuditLogger:
    """Get the global auth audit logger instance."""
    global _audit_logger
    with _audit_logger_lock:
        if _audit_logger is None:
            _audit_logger = AuthAuditLogger(repo_root=repo_root, log_file="ui_auth_audit.jsonl")
        return _audit_logger


def reset_auth_audit_logger() -> None:
    """Reset the global audit logger (for testing)."""
    global _audit_logger
    with _audit_logger_lock:
        if _audit_logger:
            _audit_logger.clear()
        _audit_logger = None
