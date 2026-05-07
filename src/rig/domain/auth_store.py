"""Grant store and credential interfaces for Rig UI server.

This module provides process-local storage for auth grants and challenges,
along with interfaces for credential verification (Keychain, passkey, etc.).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable
from threading import Lock

from rig.domain.auth_models import (
    AuthChallenge, AuthGrant, AuthMethod, AuthScope, ClientIdentity
)

logger = logging.getLogger(__name__)


class GrantStore:
    """Process-local store for auth grants and challenges.
    
    This is a simple in-memory store suitable for development and single-process
    deployment. For multi-process deployments, this would need to be backed by
    persistent storage.
    """
    
    def __init__(self):
        self._grants: Dict[str, AuthGrant] = {}
        self._challenges: Dict[str, AuthChallenge] = {}
        self._clients: Dict[str, ClientIdentity] = {}
        self._lock = Lock()
    
    def create_challenge(self, challenge: AuthChallenge) -> AuthChallenge:
        """Store a new auth challenge."""
        with self._lock:
            self._challenges[challenge.challenge_id] = challenge
            logger.info(f"Created auth challenge {challenge.challenge_id} for client {challenge.client_id}")
        return challenge
    
    def get_challenge(self, challenge_id: str) -> Optional[AuthChallenge]:
        """Retrieve a challenge by ID."""
        with self._lock:
            challenge = self._challenges.get(challenge_id)
            if challenge and challenge.is_expired():
                # Clean up expired challenges
                del self._challenges[challenge_id]
                logger.info(f"Cleaned up expired challenge {challenge_id}")
                return None
            return challenge
    
    def update_challenge(self, challenge: AuthChallenge) -> None:
        """Update an existing challenge."""
        with self._lock:
            if challenge.challenge_id in self._challenges:
                self._challenges[challenge.challenge_id] = challenge
                logger.info(f"Updated auth challenge {challenge.challenge_id}")
    
    def complete_challenge(self, challenge_id: str, verification_token: str, verified: bool) -> Optional[AuthChallenge]:
        """Mark a challenge as completed and verified."""
        with self._lock:
            challenge = self._challenges.get(challenge_id)
            if challenge:
                if challenge.is_expired():
                    del self._challenges[challenge_id]
                    return None
                
                challenge.completed = True
                challenge.verified = verified
                challenge.verification_token = verification_token
                self._challenges[challenge_id] = challenge
                logger.info(f"Completed challenge {challenge_id}, verified={verified}")
            return challenge
    
    def consume_challenge(self, challenge_id: str) -> Optional[AuthChallenge]:
        """Get and remove a challenge (consume it for grant creation)."""
        with self._lock:
            challenge = self._challenges.pop(challenge_id, None)
            if challenge:
                logger.info(f"Consumed challenge {challenge_id}")
            return challenge
    
    def create_grant(self, grant: AuthGrant) -> AuthGrant:
        """Store a new auth grant."""
        with self._lock:
            self._grants[grant.grant_id] = grant
            logger.info(f"Created grant {grant.grant_id} for client {grant.client_id}, scope={grant.scope.value}")
        return grant
    
    def get_grant(self, grant_id: str) -> Optional[AuthGrant]:
        """Retrieve a grant by ID."""
        with self._lock:
            grant = self._grants.get(grant_id)
            if grant and grant.is_expired():
                # Clean up expired grants
                del self._grants[grant_id]
                logger.info(f"Cleaned up expired grant {grant_id}")
                return None
            return grant
    
    def get_active_grants_for_client(self, client_id: str) -> List[AuthGrant]:
        """Get all non-expired grants for a client."""
        with self._lock:
            return [
                g for g in self._grants.values()
                if g.client_id == client_id and not g.is_expired()
            ]
    
    def revoke_grant(self, grant_id: str) -> Optional[AuthGrant]:
        """Revoke a grant by ID."""
        with self._lock:
            grant = self._grants.pop(grant_id, None)
            if grant:
                logger.info(f"Revoked grant {grant_id}")
            return grant
    
    def revoke_all_grants_for_client(self, client_id: str) -> List[AuthGrant]:
        """Revoke all grants for a client."""
        with self._lock:
            revoked = []
            to_remove = []
            for grant_id, grant in self._grants.items():
                if grant.client_id == client_id:
                    to_remove.append(grant_id)
                    revoked.append(grant)
            
            for grant_id in to_remove:
                del self._grants[grant_id]
            
            if revoked:
                logger.info(f"Revoked {len(revoked)} grants for client {client_id}")
            return revoked
    
    def cleanup_expired(self) -> int:
        """Clean up all expired challenges and grants. Returns count cleaned."""
        with self._lock:
            now = datetime.now(timezone.utc)
            
            # Clean challenges
            expired_challenges = [
                cid for cid, ch in self._challenges.items()
                if datetime.fromisoformat(ch.expires_at) < now
            ]
            for cid in expired_challenges:
                del self._challenges[cid]
            
            # Clean grants
            expired_grants = [
                gid for gid, g in self._grants.items()
                if datetime.fromisoformat(g.expires_at) < now
            ]
            for gid in expired_grants:
                del self._grants[gid]
            
            count = len(expired_challenges) + len(expired_grants)
            if count > 0:
                logger.info(f"Cleaned up {count} expired auth objects")
            return count
    
    def register_client(self, identity: ClientIdentity) -> ClientIdentity:
        """Register a client identity."""
        with self._lock:
            self._clients[identity.client_id] = identity
            logger.debug(f"Registered client {identity.client_id} ({identity.client_kind})")
        return identity
    
    def get_client(self, client_id: str) -> Optional[ClientIdentity]:
        """Retrieve a client by ID."""
        with self._lock:
            return self._clients.get(client_id)
    
    def unregister_client(self, client_id: str) -> Optional[ClientIdentity]:
        """Unregister a client."""
        with self._lock:
            client = self._clients.pop(client_id, None)
            if client:
                logger.debug(f"Unregistered client {client_id}")
                # Also revoke all grants for this client (internal method that doesn't lock)
                self._revoke_all_grants_for_client_internal(client_id)
            return client
    
    def _revoke_all_grants_for_client_internal(self, client_id: str) -> List[AuthGrant]:
        """Revoke all grants for a client. Must be called with lock held."""
        revoked = []
        to_remove = []
        for grant_id, grant in self._grants.items():
            if grant.client_id == client_id:
                to_remove.append(grant_id)
                revoked.append(grant)
        
        for grant_id in to_remove:
            del self._grants[grant_id]
        
        if revoked:
            logger.info(f"Revoked {len(revoked)} grants for client {client_id}")
        return revoked


# Global grant store instance for the process
_grant_store: Optional[GrantStore] = None
_grant_store_lock = Lock()


def get_grant_store() -> GrantStore:
    """Get the global grant store instance."""
    global _grant_store
    with _grant_store_lock:
        if _grant_store is None:
            _grant_store = GrantStore()
        return _grant_store


def reset_grant_store() -> None:
    """Reset the global grant store (for testing)."""
    global _grant_store
    with _grant_store_lock:
        _grant_store = None


# ---------------------------------------------------------------------------
# Credential Verification Interfaces
# ---------------------------------------------------------------------------

@runtime_checkable
class ChallengeVerifier(Protocol):
    """Protocol for challenge verification implementations."""
    
    def can_handle(self, auth_method: AuthMethod) -> bool:
        """Check if this verifier can handle the given auth method."""
        ...
    
    def verify_challenge(
        self,
        challenge: AuthChallenge,
        verification_data: Dict[str, Any],
    ) -> bool:
        """Verify a challenge with the provided verification data.
        
        Returns True if verification succeeds, False otherwise.
        """
        ...


@runtime_checkable
class CredentialStore(Protocol):
    """Protocol for credential storage implementations."""
    
    def get_credential(self, credential_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a credential by ID."""
        ...
    
    def store_credential(self, credential_id: str, credential: Dict[str, Any]) -> None:
        """Store a credential."""
        ...
    
    def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential."""
        ...


class MockChallengeVerifier:
    """Mock verifier for development/testing.
    
    This verifier accepts any verification token that matches the challenge ID.
    This is NOT suitable for production use and is clearly labeled as mock.
    """
    
    def can_handle(self, auth_method: AuthMethod) -> bool:
        return auth_method in (AuthMethod.LOCAL_DEV, AuthMethod.MOCK_VERIFIER)
    
    def verify_challenge(
        self,
        challenge: AuthChallenge,
        verification_data: Dict[str, Any],
    ) -> bool:
        """Mock verification: accepts if token matches challenge ID prefix.
        
        This is a mock verifier for development. DO NOT USE IN PRODUCTION.
        """
        token = verification_data.get("token", "")
        # Mock verification: accept if token starts with challenge ID
        # In real usage, this would verify a passkey, Keychain item, etc.
        if token.startswith(challenge.challenge_id[:8]):
            logger.warning(
                f"MOCK VERIFIER: Accepting verification for challenge {challenge.challenge_id}. "
                f"This is NOT suitable for production!"
            )
            return True
        return False


class KeychainCredentialStore:
    """Keychain-based credential store (macOS).
    
    This is a seam for macOS Keychain integration. The actual implementation
    would use the keychain module or Security.framework.
    """
    
    def __init__(self):
        self._available = False
        try:
            import keychain  # noqa: F401
            self._available = True
        except ImportError:
            logger.debug("Keychain module not available")
    
    def is_available(self) -> bool:
        return self._available
    
    def get_credential(self, credential_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a credential from the Keychain.
        
        NOT IMPLEMENTED: This is a seam for future implementation.
        """
        logger.warning("KeychainCredentialStore.get_credential: NOT IMPLEMENTED")
        return None
    
    def store_credential(self, credential_id: str, credential: Dict[str, Any]) -> None:
        """Store a credential in the Keychain.
        
        NOT IMPLEMENTED: This is a seam for future implementation.
        """
        logger.warning("KeychainCredentialStore.store_credential: NOT IMPLEMENTED")
    
    def delete_credential(self, credential_id: str) -> bool:
        """Delete a credential from the Keychain.
        
        NOT IMPLEMENTED: This is a seam for future implementation.
        """
        logger.warning("KeychainCredentialStore.delete_credential: NOT IMPLEMENTED")
        return False


class PasskeyVerifier:
    """Passkey-based challenge verifier.
    
    This is a seam for WebAuthn/passkey verification.
    """
    
    def can_handle(self, auth_method: AuthMethod) -> bool:
        return auth_method == AuthMethod.PASSKEY
    
    def verify_challenge(
        self,
        challenge: AuthChallenge,
        verification_data: Dict[str, Any],
    ) -> bool:
        """Verify a challenge using passkey.
        
        NOT IMPLEMENTED: This is a seam for future implementation.
        """
        logger.warning("PasskeyVerifier.verify_challenge: NOT IMPLEMENTED")
        return False


class LocalAuthVerifier:
    """Local authentication verifier (macOS LocalAuthentication.framework).
    
    This is a seam for local biometric/password verification.
    """
    
    def can_handle(self, auth_method: AuthMethod) -> bool:
        return auth_method == AuthMethod.LOCAL_AUTH
    
    def verify_challenge(
        self,
        challenge: AuthChallenge,
        verification_data: Dict[str, Any],
    ) -> bool:
        """Verify a challenge using local authentication.
        
        NOT IMPLEMENTED: This is a seam for future implementation.
        """
        logger.warning("LocalAuthVerifier.verify_challenge: NOT IMPLEMENTED")
        return False


# Verifier registry
_verifiers: List[ChallengeVerifier] = []


def register_verifier(verifier: ChallengeVerifier) -> None:
    """Register a challenge verifier."""
    _verifiers.append(verifier)


def get_verifier(auth_method: AuthMethod) -> Optional[ChallengeVerifier]:
    """Get a verifier that can handle the given auth method."""
    for verifier in _verifiers:
        if verifier.can_handle(auth_method):
            return verifier
    return None


# Register default verifiers
register_verifier(MockChallengeVerifier())
register_verifier(KeychainCredentialStore())
register_verifier(PasskeyVerifier())
register_verifier(LocalAuthVerifier())
