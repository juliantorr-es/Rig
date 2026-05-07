"""Authentication and authorization models for Rig UI server.

This module defines the domain models for step-up authorization,
including grants, challenges, scopes, methods, and client identity.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import uuid


class AuthScope(Enum):
    """Authorization scopes for destructive actions."""
    
    # Broad scope covering all destructive actions
    DESTRUCTIVE_ACTIONS = "destructive_actions"
    
    # Specific destructive actions
    APPLY_PATCH = "apply_patch"
    DELETE_WORKTREE = "delete_worktree"
    MUTATE_POLICY = "mutate_policy"
    
    # System-level actions
    REMOTE_PAIRING = "remote_pairing"


class AuthMethod(Enum):
    """Authentication methods for step-up authorization."""
    
    # Local development methods
    LOCAL_DEV = "local_dev"
    MOCK_VERIFIER = "mock_verifier"
    
    # Production methods (seams for future implementation)
    KEYCHAIN = "keychain"
    PASSKEY = "passkey"
    LOCAL_AUTH = "local_auth"
    OTP = "otp"


@dataclass
class ClientIdentity:
    """Identity of a connected client."""
    
    client_id: str
    client_kind: str  # e.g., "pywebview", "swiftui", "mcp", "browser"
    capabilities: Set[str] = field(default_factory=set)
    remote_addr: Optional[str] = None
    authenticated: bool = False
    auth_method: Optional[AuthMethod] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def for_webview(cls, remote_addr: Optional[str] = None) -> "ClientIdentity":
        """Create a client identity for pywebview local window."""
        return cls(
            client_id=str(uuid.uuid4()),
            client_kind="pywebview",
            capabilities={"local_window"},
            remote_addr=remote_addr,
            authenticated=False,
            auth_method=None,
        )
    
    @classmethod
    def for_browser(cls, remote_addr: Optional[str] = None) -> "ClientIdentity":
        """Create a client identity for browser-based client."""
        return cls(
            client_id=str(uuid.uuid4()),
            client_kind="browser",
            capabilities={"local_window"},
            remote_addr=remote_addr,
            authenticated=False,
            auth_method=None,
        )
    
    def has_capability(self, capability: str) -> bool:
        """Check if client has a specific capability."""
        return capability in self.capabilities
    
    def add_capability(self, capability: str) -> None:
        """Add a capability to the client."""
        self.capabilities.add(capability)
    
    def remove_capability(self, capability: str) -> None:
        """Remove a capability from the client."""
        self.capabilities.discard(capability)


@dataclass
class AuthChallenge:
    """A challenge issued for step-up authorization."""
    
    challenge_id: str
    client_id: str
    scope: AuthScope
    issued_at: str
    expires_at: str
    auth_method: AuthMethod
    
    # Optional bindings to specific resources
    bound_workspace_id: Optional[str] = None
    bound_proposal_id: Optional[str] = None
    bound_projection_revision: Optional[int] = None
    
    # Challenge state
    completed: bool = False
    verified: bool = False
    verification_token: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        client_id: str,
        scope: AuthScope,
        auth_method: AuthMethod = AuthMethod.LOCAL_DEV,
        expires_in: int = 300,  # 5 minutes default
        workspace_id: Optional[str] = None,
        proposal_id: Optional[str] = None,
        projection_revision: Optional[int] = None,
    ) -> "AuthChallenge":
        """Create a new auth challenge."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in)
        
        return cls(
            challenge_id=str(uuid.uuid4()),
            client_id=client_id,
            scope=scope,
            issued_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            auth_method=auth_method,
            bound_workspace_id=workspace_id,
            bound_proposal_id=proposal_id,
            bound_projection_revision=projection_revision,
            completed=False,
            verified=False,
        )
    
    def is_expired(self) -> bool:
        """Check if the challenge has expired."""
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) > expires
    
    def get_scope_value(self) -> str:
        """Get the scope as a string value."""
        return self.scope.value


@dataclass
class AuthGrant:
    """A short-lived grant authorizing destructive actions."""
    
    grant_id: str
    client_id: str
    scope: AuthScope
    issued_at: str
    expires_at: str
    auth_method: AuthMethod
    
    # Optional bindings to specific resources
    bound_workspace_id: Optional[str] = None
    bound_proposal_id: Optional[str] = None
    bound_projection_revision: Optional[int] = None
    
    @classmethod
    def from_challenge(
        cls,
        challenge: AuthChallenge,
        expires_in: int = 60,  # 1 minute default
    ) -> "AuthGrant":
        """Create a grant from a completed challenge."""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in)
        
        return cls(
            grant_id=str(uuid.uuid4()),
            client_id=challenge.client_id,
            scope=challenge.scope,
            issued_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            auth_method=challenge.auth_method,
            bound_workspace_id=challenge.bound_workspace_id,
            bound_proposal_id=challenge.bound_proposal_id,
            bound_projection_revision=challenge.bound_projection_revision,
        )
    
    def is_expired(self) -> bool:
        """Check if the grant has expired."""
        expires = datetime.fromisoformat(self.expires_at)
        return datetime.now(timezone.utc) > expires
    
    def covers_scope(self, scope: AuthScope) -> bool:
        """Check if this grant covers the given scope."""
        if self.is_expired():
            return False
        
        if self.scope == AuthScope.DESTRUCTIVE_ACTIONS:
            # Broad scope covers all destructive actions
            return scope in {
                AuthScope.APPLY_PATCH,
                AuthScope.DELETE_WORKTREE,
                AuthScope.MUTATE_POLICY,
                AuthScope.DESTRUCTIVE_ACTIONS,
            }
        
        return self.scope == scope
    
    def covers_intent(self, intent_kind: str) -> bool:
        """Check if this grant covers the given intent kind."""
        # Map intent kinds to required scopes
        scope_map = {
            "rig.intent.apply_patch": AuthScope.APPLY_PATCH,
            "rig.intent.delete_worktree": AuthScope.DELETE_WORKTREE,
            "rig.intent.mutate_policy": AuthScope.MUTATE_POLICY,
        }
        
        required_scope = scope_map.get(intent_kind)
        if required_scope is None:
            return False
        
        return self.covers_scope(required_scope)
    
    def is_bound_to_workspace(self, workspace_id: str) -> bool:
        """Check if grant is bound to a specific workspace."""
        return self.bound_workspace_id == workspace_id
    
    def is_bound_to_proposal(self, proposal_id: str) -> bool:
        """Check if grant is bound to a specific proposal."""
        return self.bound_proposal_id == proposal_id
    
    def is_bound_to_revision(self, revision: int) -> bool:
        """Check if grant is bound to a specific projection revision."""
        return self.bound_projection_revision == revision


from datetime import timedelta
