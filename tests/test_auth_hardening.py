"""Tests for UI server auth hardening.

These tests verify the newly implemented authentication and authorization:
- Server exposure modes
- Client identity and capabilities
- Auth challenge/grant lifecycle
- Intent preflight with grant checking
- Audit logging

Note: We import domain modules directly to avoid rig package initialization issues
with deleted TUI modules.
"""

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add src to path for direct module imports
src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
sys.path.insert(0, src_path)


class TestServerModes:
    """Test server exposure modes."""

    def test_server_exposure_modes_exist(self):
        """Test that ServerExposureMode enum exists with correct values."""
        # Import module directly, not through rig package
        from rig.domain.server_modes import ServerExposureMode
        
        assert ServerExposureMode.LOCAL_UI.value == 1
        assert ServerExposureMode.LOCAL_API.value == 2
        assert ServerExposureMode.PRIVATE_NETWORK.value == 3

    def test_capability_constants_exist(self):
        """Test that capability constants are defined."""
        from rig.domain.server_modes import (
            CAPABILITY_LOCAL_WINDOW,
            CAPABILITY_REMOTE_OBSERVER,
            CAPABILITY_REMOTE_OPERATOR,
            CAPABILITY_AUTOMATION_AGENT,
        )
        
        assert CAPABILITY_LOCAL_WINDOW == "local_window"
        assert CAPABILITY_REMOTE_OBSERVER == "remote_observer"
        assert CAPABILITY_REMOTE_OPERATOR == "remote_operator"
        assert CAPABILITY_AUTOMATION_AGENT == "automation_agent"

    def test_server_config_for_local_ui(self):
        """Test ServerConfig.for_local_ui factory."""
        from rig.domain.server_modes import ServerConfig, ServerExposureMode
        
        config = ServerConfig.for_local_ui()
        assert config.exposure_mode == ServerExposureMode.LOCAL_UI
        assert config.host == "127.0.0.1"
        assert config.allow_loopback is True
        assert config.allow_private_network is False
        assert config.allow_remote is False

    def test_server_config_allows_loopback(self):
        """Test that local UI config allows loopback addresses."""
        from rig.domain.server_modes import ServerConfig, ServerExposureMode
        
        config = ServerConfig.for_local_ui()
        assert config.allows_host("127.0.0.1") is True
        assert config.allows_host("localhost") is True
        assert config.allows_host("::1") is True
        assert config.allows_host("192.168.1.1") is False

    def test_server_config_rejects_non_loopback(self):
        """Test that local UI config rejects non-loopback addresses."""
        from rig.domain.server_modes import ServerConfig, ServerExposureMode
        
        config = ServerConfig.for_local_ui()
        assert config.allows_host("0.0.0.0") is False
        assert config.allows_host("192.168.1.1") is False
        assert config.allows_host("10.0.0.1") is False

    def test_private_ip_detection(self):
        """Test private IP address detection."""
        from rig.domain.server_modes import _is_private_ip
        
        # Loopback
        assert _is_private_ip("127.0.0.1") is True
        assert _is_private_ip("localhost") is True
        assert _is_private_ip("::1") is True
        
        # RFC 1918 private ranges
        assert _is_private_ip("10.0.0.1") is True
        assert _is_private_ip("10.255.255.255") is True
        assert _is_private_ip("172.16.0.1") is True
        assert _is_private_ip("172.31.255.255") is True
        assert _is_private_ip("192.168.0.1") is True
        assert _is_private_ip("192.168.255.255") is True
        
        # Link-local
        assert _is_private_ip("169.254.0.1") is True
        assert _is_private_ip("169.254.255.255") is True
        
        # Public IPs
        assert _is_private_ip("8.8.8.8") is False
        assert _is_private_ip("172.15.0.1") is False  # Outside 172.16.0.0/12
        assert _is_private_ip("172.32.0.1") is False  # Outside 172.16.0.0/12
        assert _is_private_ip("192.167.0.1") is False  # Outside 192.168.0.0/16

    def test_private_network_config_allows_private_ips(self):
        """Test that private network config allows private IPs."""
        from rig.domain.server_modes import ServerConfig
        
        config = ServerConfig.for_private_network("192.168.1.100", 8080, "test_token")
        assert config.allows_host("192.168.1.100") is True
        assert config.allows_host("10.0.0.5") is True
        assert config.allows_host("172.20.0.1") is True
        
    def test_origin_validation(self):
        """Test origin validation."""
        from rig.domain.server_modes import ServerConfig
        
        config = ServerConfig.for_local_ui()
        assert config.allows_origin("http://127.0.0.1:8080") is True
        assert config.allows_origin("http://localhost:8080") is True
        assert config.allows_origin("ws://127.0.0.1:8080") is True
        assert config.allows_origin("ws://localhost:8080") is True
        assert config.allows_origin("http://evil.com") is False


class TestAuthModels:
    """Test auth domain models."""

    def test_auth_scope_enum(self):
        """Test AuthScope enum values."""
        from rig.domain.auth_models import AuthScope
        
        assert AuthScope.DESTRUCTIVE_ACTIONS.value == "destructive_actions"
        assert AuthScope.APPLY_PATCH.value == "apply_patch"
        assert AuthScope.DELETE_WORKTREE.value == "delete_worktree"
        assert AuthScope.MUTATE_POLICY.value == "mutate_policy"
        assert AuthScope.REMOTE_PAIRING.value == "remote_pairing"

    def test_auth_method_enum(self):
        """Test AuthMethod enum values."""
        from rig.domain.auth_models import AuthMethod
        
        assert AuthMethod.LOCAL_DEV.value == "local_dev"
        assert AuthMethod.MOCK_VERIFIER.value == "mock_verifier"
        assert AuthMethod.KEYCHAIN.value == "keychain"
        assert AuthMethod.PASSKEY.value == "passkey"
        assert AuthMethod.LOCAL_AUTH.value == "local_auth"
        assert AuthMethod.OTP.value == "otp"

    def test_client_identity_creation(self):
        """Test ClientIdentity creation."""
        from rig.domain.auth_models import ClientIdentity
        
        identity = ClientIdentity(
            client_id="test-client-1",
            client_kind="pywebview",
            capabilities={"local_window"},
            remote_addr="127.0.0.1",
            authenticated=False,
        )
        
        assert identity.client_id == "test-client-1"
        assert identity.client_kind == "pywebview"
        assert identity.has_capability("local_window") is True
        assert identity.has_capability("remote_operator") is False

    def test_client_identity_factory_methods(self):
        """Test ClientIdentity factory methods."""
        from rig.domain.auth_models import ClientIdentity
        
        webview = ClientIdentity.for_webview("127.0.0.1")
        assert webview.client_kind == "pywebview"
        assert webview.has_capability("local_window") is True
        
        browser = ClientIdentity.for_browser("127.0.0.1")
        assert browser.client_kind == "browser"
        assert browser.has_capability("local_window") is True

    def test_auth_challenge_creation(self):
        """Test AuthChallenge creation."""
        from rig.domain.auth_models import AuthChallenge, AuthScope, AuthMethod
        from datetime import datetime, timezone
        import uuid
        
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            auth_method=AuthMethod.MOCK_VERIFIER,
            expires_in=60,
        )
        
        assert challenge.client_id == "test-client-1"
        assert challenge.scope == AuthScope.DESTRUCTIVE_ACTIONS
        assert challenge.auth_method == AuthMethod.MOCK_VERIFIER
        assert challenge.completed is False
        assert challenge.verified is False
        assert challenge.get_scope_value() == "destructive_actions"

    def test_auth_challenge_is_expired(self):
        """Test AuthChallenge expiration checking."""
        from rig.domain.auth_models import AuthChallenge, AuthScope, AuthMethod
        from datetime import datetime, timezone, timedelta
        
        # Create challenge that expires in 1 second from now
        now = datetime.now(timezone.utc)
        challenge = AuthChallenge(
            challenge_id="test-challenge-1",
            client_id="test-client-1",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            issued_at=now.isoformat(),
            expires_at=(now - timedelta(seconds=1)).isoformat(),  # Already expired
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        
        # Should be expired since expires_at is in the past
        assert challenge.is_expired() is True
        
        # Create challenge that expires in the future
        future_challenge = AuthChallenge(
            challenge_id="test-challenge-2",
            client_id="test-client-1",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=3600)).isoformat(),  # 1 hour in future
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        
        # Should not be expired
        assert future_challenge.is_expired() is False

    def test_auth_grant_creation(self):
        """Test AuthGrant creation."""
        from rig.domain.auth_models import AuthChallenge, AuthGrant, AuthScope, AuthMethod
        
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.APPLY_PATCH,
            auth_method=AuthMethod.MOCK_VERIFIER,
            expires_in=300,
        )
        
        grant = AuthGrant.from_challenge(challenge)
        
        assert grant.client_id == "test-client-1"
        assert grant.scope == AuthScope.APPLY_PATCH
        assert grant.auth_method == AuthMethod.MOCK_VERIFIER
        assert grant.is_expired() is False

    def test_auth_grant_covers_scope(self):
        """Test AuthGrant scope coverage."""
        from rig.domain.auth_models import AuthChallenge, AuthGrant, AuthScope, AuthMethod
        
        # Grant for destructive_actions should cover all destructive scopes
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        grant = AuthGrant.from_challenge(challenge)
        
        assert grant.covers_scope(AuthScope.DESTRUCTIVE_ACTIONS) is True
        assert grant.covers_scope(AuthScope.APPLY_PATCH) is True
        assert grant.covers_scope(AuthScope.DELETE_WORKTREE) is True
        assert grant.covers_scope(AuthScope.MUTATE_POLICY) is True
        
        # Grant for specific scope should only cover that scope
        challenge2 = AuthChallenge.create(
            client_id="test-client-2",
            scope=AuthScope.APPLY_PATCH,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        grant2 = AuthGrant.from_challenge(challenge2)
        
        assert grant2.covers_scope(AuthScope.APPLY_PATCH) is True
        assert grant2.covers_scope(AuthScope.DELETE_WORKTREE) is False
        assert grant2.covers_scope(AuthScope.DESTRUCTIVE_ACTIONS) is False

    def test_auth_grant_covers_intent(self):
        """Test AuthGrant intent coverage."""
        from rig.domain.auth_models import AuthChallenge, AuthGrant, AuthScope, AuthMethod
        
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        grant = AuthGrant.from_challenge(challenge)
        
        # Grant should cover known destructive intents
        assert grant.covers_intent("rig.intent.apply_patch") is True
        assert grant.covers_intent("rig.intent.delete_worktree") is True
        assert grant.covers_intent("rig.intent.mutate_policy") is True
        
        # Should not cover safe intents (not in scope map)
        assert grant.covers_intent("rig.intent.chat.submit") is False
        assert grant.covers_intent("rig.intent.refresh_projection") is False


class TestGrantStore:
    """Test grant store functionality."""

    def test_grant_store_creation(self):
        """Test GrantStore creation."""
        from rig.domain.auth_store import GrantStore
        
        store = GrantStore()
        assert store is not None

    def test_create_and_retrieve_challenge(self):
        """Test creating and retrieving a challenge."""
        from rig.domain.auth_store import GrantStore
        from rig.domain.auth_models import AuthChallenge, AuthScope, AuthMethod
        
        store = GrantStore()
        
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        
        stored = store.create_challenge(challenge)
        retrieved = store.get_challenge(challenge.challenge_id)
        
        assert retrieved is not None
        assert retrieved.client_id == challenge.client_id
        assert retrieved.scope == challenge.scope

    def test_create_and_retrieve_grant(self):
        """Test creating and retrieving a grant."""
        from rig.domain.auth_store import GrantStore
        from rig.domain.auth_models import AuthChallenge, AuthGrant, AuthScope, AuthMethod
        
        store = GrantStore()
        
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.APPLY_PATCH,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        grant = AuthGrant.from_challenge(challenge)
        
        stored = store.create_grant(grant)
        retrieved = store.get_grant(grant.grant_id)
        
        assert retrieved is not None
        assert retrieved.grant_id == grant.grant_id

    def test_revoke_grant(self):
        """Test revoking a grant."""
        from rig.domain.auth_store import GrantStore
        from rig.domain.auth_models import AuthChallenge, AuthGrant, AuthScope, AuthMethod
        
        store = GrantStore()
        
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.APPLY_PATCH,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        grant = AuthGrant.from_challenge(challenge)
        
        store.create_grant(grant)
        
        # Grant should exist
        assert store.get_grant(grant.grant_id) is not None
        
        # Revoke grant
        revoked = store.revoke_grant(grant.grant_id)
        assert revoked is not None
        assert revoked.grant_id == grant.grant_id
        
        # Grant should no longer exist
        assert store.get_grant(grant.grant_id) is None

    def test_get_active_grants_for_client(self):
        """Test getting active grants for a client."""
        from rig.domain.auth_store import GrantStore
        from rig.domain.auth_models import AuthChallenge, AuthGrant, AuthScope, AuthMethod
        
        store = GrantStore()
        
        # Create multiple grants for same client
        for i in range(3):
            challenge = AuthChallenge.create(
                client_id="test-client-1",
                scope=AuthScope.APPLY_PATCH,
                auth_method=AuthMethod.MOCK_VERIFIER,
            )
            grant = AuthGrant.from_challenge(challenge)
            store.create_grant(grant)
        
        # Create grant for different client
        challenge2 = AuthChallenge.create(
            client_id="test-client-2",
            scope=AuthScope.DELETE_WORKTREE,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        grant2 = AuthGrant.from_challenge(challenge2)
        store.create_grant(grant2)
        
        active = store.get_active_grants_for_client("test-client-1")
        assert len(active) == 3
        
        active2 = store.get_active_grants_for_client("test-client-2")
        assert len(active2) == 1

    def test_register_and_get_client(self):
        """Test client registration."""
        from rig.domain.auth_store import GrantStore
        from rig.domain.auth_models import ClientIdentity
        
        store = GrantStore()
        
        identity = ClientIdentity.for_webview("127.0.0.1")
        registered = store.register_client(identity)
        
        retrieved = store.get_client(identity.client_id)
        assert retrieved is not None
        assert retrieved.client_id == identity.client_id

    def test_unregister_client_revokes_grants(self):
        """Test that unregistering a client revokes all their grants."""
        from rig.domain.auth_store import GrantStore
        from rig.domain.auth_models import AuthChallenge, AuthGrant, AuthScope, AuthMethod, ClientIdentity
        
        store = GrantStore()
        
        identity = ClientIdentity.for_webview("127.0.0.1")
        store.register_client(identity)
        
        # Create grants for client
        for i in range(3):
            challenge = AuthChallenge.create(
                client_id=identity.client_id,
                scope=AuthScope.APPLY_PATCH,
                auth_method=AuthMethod.MOCK_VERIFIER,
            )
            grant = AuthGrant.from_challenge(challenge)
            store.create_grant(grant)
        
        # Unregister client
        store.unregister_client(identity.client_id)
        
        # Grants should be revoked
        active = store.get_active_grants_for_client(identity.client_id)
        assert len(active) == 0


class TestVerifiers:
    """Test challenge verifiers."""

    def test_mock_verifier_can_handle(self):
        """Test MockChallengeVerifier can_handle."""
        from rig.domain.auth_store import MockChallengeVerifier
        from rig.domain.auth_models import AuthMethod
        
        verifier = MockChallengeVerifier()
        assert verifier.can_handle(AuthMethod.MOCK_VERIFIER) is True
        assert verifier.can_handle(AuthMethod.LOCAL_DEV) is True
        assert verifier.can_handle(AuthMethod.PASSKEY) is False

    def test_mock_verifier_accepts_matching_token(self):
        """Test MockChallengeVerifier accepts matching tokens."""
        from rig.domain.auth_store import MockChallengeVerifier
        from rig.domain.auth_models import AuthChallenge, AuthScope, AuthMethod
        
        verifier = MockChallengeVerifier()
        
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        
        # Token that matches challenge ID prefix should succeed
        result = verifier.verify_challenge(challenge, {"token": challenge.challenge_id[:8] + "anything"})
        assert result is True

    def test_mock_verifier_rejects_non_matching_token(self):
        """Test MockChallengeVerifier rejects non-matching tokens."""
        from rig.domain.auth_store import MockChallengeVerifier
        from rig.domain.auth_models import AuthChallenge, AuthScope, AuthMethod
        
        verifier = MockChallengeVerifier()
        
        challenge = AuthChallenge.create(
            client_id="test-client-1",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            auth_method=AuthMethod.MOCK_VERIFIER,
        )
        
        # Non-matching token should fail
        result = verifier.verify_challenge(challenge, {"token": "wrongtoken"})
        assert result is False

    def test_verifier_registry(self):
        """Test verifier registration and retrieval."""
        from rig.domain.auth_store import get_verifier, register_verifier, MockChallengeVerifier
        from rig.domain.auth_models import AuthMethod
        
        # Get verifier for mock method
        verifier = get_verifier(AuthMethod.MOCK_VERIFIER)
        assert verifier is not None
        assert verifier.can_handle(AuthMethod.MOCK_VERIFIER) is True


class TestAuthAudit:
    """Test auth audit logging."""

    def test_auth_audit_event_types(self):
        """Test AuthAuditEventType enum values."""
        from rig.domain.auth_audit import AuthAuditEventType
        
        assert AuthAuditEventType.CLIENT_CONNECTED.value == "client_connected"
        assert AuthAuditEventType.CLIENT_DISCONNECTED.value == "client_disconnected"
        assert AuthAuditEventType.CLIENT_REJECTED.value == "client_rejected"
        assert AuthAuditEventType.CHALLENGE_ISSUED.value == "challenge_issued"
        assert AuthAuditEventType.GRANT_ISSUED.value == "grant_issued"
        assert AuthAuditEventType.INTENT_REJECTED.value == "intent_rejected"

    def test_auth_audit_logger_records_events(self):
        """Test AuthAuditLogger records events."""
        from rig.domain.auth_audit import AuthAuditLogger, AuthAuditEvent, AuthAuditEventType
        
        logger = AuthAuditLogger()
        
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.CLIENT_CONNECTED,
            timestamp="2024-01-01T00:00:00+00:00",
            client_id="test-client-1",
            client_kind="pywebview",
        )
        
        logger.record(event)
        
        events = logger.get_events()
        assert len(events) == 1
        assert events[0].event_type == AuthAuditEventType.CLIENT_CONNECTED

    def test_auth_audit_logger_convenience_methods(self):
        """Test AuthAuditLogger convenience methods."""
        from rig.domain.auth_audit import AuthAuditLogger
        
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuthAuditLogger(repo_root=Path(tmpdir), log_file="test_audit.jsonl")
            
            # Test client connected
            event = logger.record_client_connected("client-1", "pywebview")
            assert event.client_id == "client-1"
            assert event.client_kind == "pywebview"
            
            # Test grant issued
            event = logger.record_grant_issued("grant-1", "client-1", "destructive_actions", "mock")
            assert event.grant_id == "grant-1"
            assert event.scope == "destructive_actions"
            
            # Test intent rejected
            event = logger.record_intent_rejected("client-1", "pywebview", "rig.intent.unknown", "Not found", "UNKNOWN_INTENT")
            assert event.reason == "Not found"
            assert event.reason_code == "UNKNOWN_INTENT"

    def test_auth_audit_event_to_dict(self):
        """Test AuthAuditEvent serialization to dict."""
        from rig.domain.auth_audit import AuthAuditEvent, AuthAuditEventType
        
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.CLIENT_CONNECTED,
            timestamp="2024-01-01T00:00:00+00:00",
            client_id="test-client-1",
            client_kind="pywebview",
            remote_addr="127.0.0.1",
        )
        
        d = event.to_dict()
        assert d["event_type"] == "client_connected"
        assert d["client_id"] == "test-client-1"
        assert d["client_kind"] == "pywebview"
        assert d["remote_addr"] == "127.0.0.1"

    def test_auth_audit_event_to_json(self):
        """Test AuthAuditEvent serialization to JSON."""
        from rig.domain.auth_audit import AuthAuditEvent, AuthAuditEventType
        
        event = AuthAuditEvent(
            event_type=AuthAuditEventType.GRANT_ISSUED,
            timestamp="2024-01-01T00:00:00+00:00",
            client_id="test-client-1",
        )
        
        json_str = event.to_json()
        assert isinstance(json_str, str)
        assert "grant_issued" in json_str
        assert "test-client-1" in json_str


class TestProjectionAuth:
    """Test projection auth state."""

    def test_auth_state_from_grant(self):
        """Test AuthState creation from grant."""
        from rig.domain.projections import AuthState
        
        # With grant
        auth_state = AuthState.from_grant(
            grant_id="grant-1",
            scope="destructive_actions",
            expires_at="2024-12-31T00:00:00+00:00",
        )
        
        assert auth_state.active_grant_id == "grant-1"
        assert auth_state.active_grant_scope == "destructive_actions"
        assert auth_state.auth_state == "authorized"
        assert auth_state.destructive_actions_unlocked is True
        
        # Without grant
        auth_state2 = AuthState.from_grant()
        assert auth_state2.active_grant_id is None
        assert auth_state2.auth_state == "unauthenticated"
        assert auth_state2.destructive_actions_unlocked is False

    def test_ui_projection_has_auth_field(self):
        """Test that UIProjection has auth field."""
        from rig.domain.projections import UIProjection, AuthState
        
        projection = UIProjection()
        assert hasattr(projection, 'auth')
        assert isinstance(projection.auth, AuthState)


class TestDestructiveIntents:
    """Test destructive intent handling."""

    def test_destructive_intents_mapping(self):
        """Test that destructive intents are properly mapped to scopes."""
        from rig.domain.auth_models import AuthGrant, AuthScope, AuthMethod
        from datetime import datetime, timezone, timedelta
        
        now = datetime.now(timezone.utc)
        # Create a grant that expires in the future
        grant = AuthGrant(
            grant_id="test-grant",
            client_id="test-client",
            scope=AuthScope.DESTRUCTIVE_ACTIONS,
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(days=365)).isoformat(),
            auth_method=AuthMethod.LOCAL_DEV,
        )
        
        # Known destructive intents
        assert grant.covers_intent("rig.intent.apply_patch") is True
        assert grant.covers_intent("rig.intent.delete_worktree") is True
        assert grant.covers_intent("rig.intent.mutate_policy") is True

    def test_safe_intents(self):
        """Test that safe intents are defined."""
        from rig_tools.ui_server import SAFE_INTENTS
        
        assert "rig.intent.refresh_projection" in SAFE_INTENTS

    def test_rejection_codes(self):
        """Test common rejection reason codes."""
        # These will be used in auth audit logging
        codes = [
            "INVALID_SCOPE",
            "CHALLENGE_NOT_FOUND",
            "WRONG_CLIENT",
            "VERIFICATION_FAILED",
            "MISSING_GRANT",
            "STALE_PROJECTION",
            "DISABLED_INTENT",
            "UNKNOWN_INTENT",
            "NO_VERIFIER",
            "AUTH_REQUIRED",
        ]
        
        for code in codes:
            assert isinstance(code, str)
            assert len(code) > 0
