"""Auth intent handlers for Rig UI server.

This module provides the intent handlers for step-up authorization:
- begin_destructive_session: Creates a challenge
- complete_destructive_session: Completes a challenge and issues a grant
- revoke_destructive_session: Revokes a grant
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from rig.domain.intent_defs import Intent
from rig.domain.auth_models import (
    AuthChallenge, AuthGrant, AuthMethod, AuthScope, ClientIdentity
)
from rig.domain.auth_store import get_grant_store, get_verifier
from rig.domain.auth_audit import get_auth_audit_logger

logger = logging.getLogger(__name__)


class AuthIntentHandlers:
    """Handlers for auth-related intents."""
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._grant_store = get_grant_store()
        self._audit_logger = get_auth_audit_logger(repo_root)
    
    def handle_begin_destructive_session(
        self,
        intent: Intent,
        client_identity: ClientIdentity,
    ) -> Dict[str, Any]:
        """Handle rig.intent.auth.begin_destructive_session.
        
        Creates an auth challenge for step-up authorization.
        In this phase, uses MOCK_VERIFIER by default.
        """
        # Extract scope from intent target
        scope_str = (intent.target or {}).get("scope", "destructive_actions")
        
        try:
            scope = AuthScope(scope_str)
        except ValueError:
            logger.error(f"Invalid scope: {scope_str}")
            self._audit_logger.record_intent_rejected(
                client_id=client_identity.client_id,
                client_kind=client_identity.client_kind,
                intent_kind=intent.kind,
                reason=f"Invalid scope: {scope_str}",
                reason_code="INVALID_SCOPE",
            )
            return {"accepted": False, "reason": f"Invalid scope: {scope_str}"}
        
        # Get optional bindings
        workspace_id = (intent.target or {}).get("workspace_id")
        proposal_id = (intent.target or {}).get("proposal_id")
        projection_revision = (intent.target or {}).get("projection_revision")
        
        # Create challenge
        challenge = AuthChallenge.create(
            client_id=client_identity.client_id,
            scope=scope,
            auth_method=AuthMethod.MOCK_VERIFIER,  # Use mock for development
            workspace_id=workspace_id,
            proposal_id=proposal_id,
            projection_revision=projection_revision,
        )
        
        # Store challenge
        self._grant_store.create_challenge(challenge)
        
        # Audit log
        self._audit_logger.record_challenge_issued(
            challenge_id=challenge.challenge_id,
            client_id=client_identity.client_id,
            scope=scope.value,
            auth_method=challenge.auth_method.value,
        )
        
        logger.info(
            f"Created destructive session challenge {challenge.challenge_id} "
            f"for client {client_identity.client_id}, scope={scope.value}"
        )
        
        return {
            "accepted": True,
            "challenge_id": challenge.challenge_id,
            "scope": scope.value,
            "expires_at": challenge.expires_at,
            "auth_method": challenge.auth_method.value,
            "message": "Use rig.intent.auth.complete_destructive_session with verification token",
        }
    
    def handle_complete_destructive_session(
        self,
        intent: Intent,
        client_identity: ClientIdentity,
    ) -> Dict[str, Any]:
        """Handle rig.intent.auth.complete_destructive_session.
        
        Completes a challenge and issues a grant if verification succeeds.
        """
        challenge_id = (intent.target or {}).get("challenge_id")
        verification_token = (intent.target or {}).get("token", "")
        
        if not challenge_id:
            logger.error("Missing challenge_id in complete_destructive_session")
            return {"accepted": False, "reason": "Missing challenge_id"}
        
        # Retrieve challenge
        challenge = self._grant_store.get_challenge(challenge_id)
        if challenge is None:
            logger.error(f"Challenge not found: {challenge_id}")
            self._audit_logger.record_intent_rejected(
                client_id=client_identity.client_id,
                client_kind=client_identity.client_kind,
                intent_kind=intent.kind,
                reason=f"Challenge not found: {challenge_id}",
                reason_code="CHALLENGE_NOT_FOUND",
            )
            return {"accepted": False, "reason": f"Challenge not found or expired"}
        
        # Verify client matches
        if challenge.client_id != client_identity.client_id:
            logger.error(f"Challenge belongs to different client: {challenge.client_id} != {client_identity.client_id}")
            self._audit_logger.record_intent_rejected(
                client_id=client_identity.client_id,
                client_kind=client_identity.client_kind,
                intent_kind=intent.kind,
                reason="Challenge belongs to different client",
                reason_code="WRONG_CLIENT",
            )
            return {"accepted": False, "reason": "Challenge belongs to different client"}
        
        # Get verifier for this auth method
        verifier = get_verifier(challenge.auth_method)
        if verifier is None:
            logger.error(f"No verifier for auth method: {challenge.auth_method}")
            return {"accepted": False, "reason": f"No verifier for auth method: {challenge.auth_method.value}"}
        
        # Verify the challenge
        verification_data = {"token": verification_token}
        verified = verifier.verify_challenge(challenge, verification_data)
        
        # Complete the challenge
        completed_challenge = self._grant_store.complete_challenge(
            challenge_id, verification_token, verified
        )
        
        if not verified or completed_challenge is None:
            logger.error(f"Challenge verification failed for {challenge_id}")
            self._audit_logger.record_challenge_completed(
                challenge_id=challenge_id,
                client_id=client_identity.client_id,
                verified=False,
            )
            return {"accepted": False, "reason": "Verification failed"}
        
        # Create grant from challenge
        grant = AuthGrant.from_challenge(completed_challenge)
        self._grant_store.create_grant(grant)
        
        # Consume the challenge (remove it)
        self._grant_store.consume_challenge(challenge_id)
        
        # Audit log
        self._audit_logger.record_grant_issued(
            grant_id=grant.grant_id,
            client_id=client_identity.client_id,
            scope=grant.scope.value,
            auth_method=grant.auth_method.value,
        )
        self._audit_logger.record_challenge_completed(
            challenge_id=challenge_id,
            client_id=client_identity.client_id,
            verified=True,
        )
        
        logger.info(
            f"Issued grant {grant.grant_id} to client {client_identity.client_id}, "
            f"scope={grant.scope.value}, expires={grant.expires_at}"
        )
        
        return {
            "accepted": True,
            "grant_id": grant.grant_id,
            "scope": grant.scope.value,
            "expires_at": grant.expires_at,
            "message": "Destructive actions now authorized until grant expires",
        }
    
    def handle_revoke_destructive_session(
        self,
        intent: Intent,
        client_identity: ClientIdentity,
    ) -> Dict[str, Any]:
        """Handle rig.intent.auth.revoke_destructive_session.
        
        Revokes all grants for the current client.
        """
        grant_id = (intent.target or {}).get("grant_id")
        
        if grant_id:
            # Revoke specific grant
            grant = self._grant_store.revoke_grant(grant_id)
            if grant:
                if grant.client_id != client_identity.client_id:
                    logger.error(f"Grant belongs to different client")
                    return {"accepted": False, "reason": "Grant belongs to different client"}
                
                self._audit_logger.record_grant_revoked(
                    grant_id=grant.grant_id,
                    client_id=client_identity.client_id,
                )
                logger.info(f"Revoked grant {grant_id}")
                return {"accepted": True, "grant_id": grant_id, "message": "Grant revoked"}
            else:
                return {"accepted": False, "reason": f"Grant not found: {grant_id}"}
        else:
            # Revoke all grants for this client
            revoked = self._grant_store.revoke_all_grants_for_client(client_identity.client_id)
            for grant in revoked:
                self._audit_logger.record_grant_revoked(
                    grant_id=grant.grant_id,
                    client_id=client_identity.client_id,
                )
            logger.info(f"Revoked {len(revoked)} grants for client {client_identity.client_id}")
            return {"accepted": True, "revoked_count": len(revoked), "message": "All grants revoked"}


def get_auth_handlers(repo_root: Path) -> AuthIntentHandlers:
    """Get the auth intent handlers instance."""
    return AuthIntentHandlers(repo_root)
