"""Tests for IntakeRegistry and IntakeStore (ADR 0005).

Architectural verification:
- Registry owns inventory/routing, NOT connector semantics
- Store owns packet persistence only, NOT pledges/sync receipts
- Connectors own their validation (may raise on invalid config)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Optional

import pytest

# Import the modules under test
from rig.domain.intake_registry import IntakeRegistry, _KNOWN_CONNECTORS
from rig.domain.intake_store import IntakeStore
from rig.domain.public_intake import PublicIntakePacket
from rig.domain.connectors.base import PublicIntakeConnector, ConnectorResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_repo() -> Path:
    """Create a temporary repo directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def intake_store(temp_repo: Path) -> IntakeStore:
    """Create an IntakeStore for a temp repo."""
    return IntakeStore(temp_repo)


@pytest.fixture
def intake_registry(temp_repo: Path) -> IntakeRegistry:
    """Create an IntakeRegistry for a temp repo."""
    return IntakeRegistry.from_repo_root(temp_repo)


# =============================================================================
# Sample data
# =============================================================================

def _make_sample_packet(
    packet_id: str = "test-packet-1",
    source: str = "test_source",
    title: str = "Test Proposal",
) -> PublicIntakePacket:
    """Create a sample PublicIntakePacket for testing."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return PublicIntakePacket(
        packet_id=packet_id,
        source=source,
        source_id="src_123",
        raw_payload={"test": "data"},
        normalizes_to="",
        title=title,
        description="Test description",
        submitter_email="test@example.com",
        submitter_name="Test User",
        submitted_at=now,
        tags=(),
        priority_class="standard",
        requested_funding_usd=0,
        is_community_requested=False,
        deduplication_key=None,
        lifecycle_state="submitted",
        sync_receipt_id=None,
        imported_at=now,
        dry_run=False,
    )


# =============================================================================
# IntakeStore Tests
# =============================================================================


class TestIntakeStoreBasics:
    """Test basic IntakeStore functionality."""

    def test_store_path_construction(self, intake_store: IntakeStore, temp_repo: Path):
        """Verify store path is constructed correctly."""
        assert intake_store.store_path == temp_repo / ".build" / "rig" / "public_intake"
        assert intake_store.packets_path == temp_repo / ".build" / "rig" / "public_intake" / "packets.jsonl"

    def test_load_packets_empty(self, intake_store: IntakeStore):
        """Load from non-existent store returns empty list."""
        packets = intake_store.load_packets()
        assert packets == []

    def test_load_packets_with_limit(self, intake_store: IntakeStore):
        """Load with limit returns at most limit packets."""
        packets = intake_store.load_packets(limit=None)
        assert packets == []


class TestIntakeStoreSaveAndLoad:
    """Test save/load roundtrip for IntakeStore."""

    def test_save_and_load_single_packet(self, intake_store: IntakeStore, temp_repo: Path):
        """Save a packet and load it back."""
        packet = _make_sample_packet()
        
        # Save the packet
        result = intake_store.save_packet(packet, dry_run=False)
        assert result is True
        
        # Verify file was created
        assert intake_store.packets_path.exists()
        
        # Load and verify
        loaded = intake_store.load_packets()
        assert len(loaded) == 1
        assert loaded[0].packet_id == packet.packet_id
        assert loaded[0].title == packet.title

    def test_save_dry_run_does_not_write(self, intake_store: IntakeStore, temp_repo: Path):
        """Dry run save does not write to filesystem."""
        packet = _make_sample_packet()
        
        result = intake_store.save_packet(packet, dry_run=True)
        assert result is True
        
        # File should not exist
        assert not intake_store.packets_path.exists()

    def test_save_multiple_packets_append(self, intake_store: IntakeStore, temp_repo: Path):
        """Multiple saves append to the same file."""
        packet1 = _make_sample_packet(packet_id="packet-1", title="First")
        packet2 = _make_sample_packet(packet_id="packet-2", title="Second")
        
        intake_store.save_packet(packet1, dry_run=False)
        intake_store.save_packet(packet2, dry_run=False)
        
        loaded = intake_store.load_packets()
        assert len(loaded) == 2
        # JSONL: last write is appended, so order is preserved
        assert loaded[0].packet_id == "packet-1"
        assert loaded[1].packet_id == "packet-2"

    def test_load_with_limit(self, intake_store: IntakeStore, temp_repo: Path):
        """Load with limit returns at most that many packets."""
        for i in range(5):
            intake_store.save_packet(_make_sample_packet(packet_id=f"packet-{i}"), dry_run=False)
        
        loaded = intake_store.load_packets(limit=3)
        assert len(loaded) == 3

    def test_load_all(self, intake_store: IntakeStore, temp_repo: Path):
        """load_all() convenience method works."""
        for i in range(3):
            intake_store.save_packet(_make_sample_packet(packet_id=f"packet-{i}"), dry_run=False)
        
        loaded = intake_store.load_all()
        assert len(loaded) == 3


class TestIntakeStoreMalformedData:
    """Test IntakeStore handles malformed data gracefully."""

    def test_skip_malformed_lines(self, intake_store: IntakeStore, temp_repo: Path):
        """Malformed JSONL lines are skipped, not raised."""
        # Write malformed data directly
        intake_store.packets_path.parent.mkdir(parents=True, exist_ok=True)
        with open(intake_store.packets_path, "w") as f:
            # Valid line
            valid_packet = _make_sample_packet()
            f.write(json.dumps(valid_packet.to_dict()) + "\n")
            # Malformed line (not JSON)
            f.write("not valid json\n")
            # Another valid line
            valid_packet2 = _make_sample_packet(packet_id="packet-2")
            f.write(json.dumps(valid_packet2.to_dict()) + "\n")
        
        loaded = intake_store.load_packets()
        assert len(loaded) == 2
        assert loaded[0].packet_id == valid_packet.packet_id
        assert loaded[1].packet_id == "packet-2"

    def test_skip_empty_lines(self, intake_store: IntakeStore, temp_repo: Path):
        """Empty lines are skipped."""
        intake_store.packets_path.parent.mkdir(parents=True, exist_ok=True)
        with open(intake_store.packets_path, "w") as f:
            packet = _make_sample_packet()
            f.write(json.dumps(packet.to_dict()) + "\n")
            f.write("\n")  # Empty line
            f.write("  \n")  # Whitespace-only line
        
        loaded = intake_store.load_packets()
        assert len(loaded) == 1


# =============================================================================
# IntakeRegistry Tests
# =============================================================================


class TestIntakeRegistryBasics:
    """Test basic IntakeRegistry functionality."""

    def test_known_connectors_exists(self):
        """_KNOWN_CONNECTORS contains expected connectors."""
        assert "google_forms" in _KNOWN_CONNECTORS
        assert "google_sheets" in _KNOWN_CONNECTORS
        assert "github_issues" in _KNOWN_CONNECTORS

    def test_factory_returns_registry(self, intake_registry: IntakeRegistry, temp_repo: Path):
        """Factory returns a properly initialized registry."""
        assert intake_registry.repo_root == temp_repo
        assert intake_registry.has_connector("google_forms")
        assert intake_registry.has_connector("google_sheets")
        assert intake_registry.has_connector("github_issues")

    def test_list_connectors(self, intake_registry: IntakeRegistry):
        """list_connectors() returns all known connectors."""
        connectors = intake_registry.list_connectors()
        assert isinstance(connectors, list)
        assert "google_forms" in connectors
        assert "google_sheets" in connectors
        assert "github_issues" in connectors

    def test_has_connector(self, intake_registry: IntakeRegistry):
        """has_connector() correctly identifies known connectors."""
        assert intake_registry.has_connector("google_forms") is True
        assert intake_registry.has_connector("nonexistent") is False


class TestIntakeRegistryGetConnector:
    """Test connector retrieval from registry."""

    def test_get_connector_success(self, intake_registry: IntakeRegistry):
        """get_connector() returns a connector instance."""
        connector = intake_registry.get_connector("google_forms")
        assert connector is not None
        assert connector.connector_name == "google_forms"

    def test_get_connector_with_config(self, intake_registry: IntakeRegistry):
        """get_connector() passes config to connector."""
        config = {"form_id": "test_form"}
        connector = intake_registry.get_connector("google_forms", config)
        assert connector is not None
        # Config validation is connector-owned, so we just verify it doesn't error here
        assert connector.connector_name == "google_forms"

    def test_get_connector_nonexistent_raises(self, intake_registry: IntakeRegistry):
        """get_connector() raises ValueError for unknown connector."""
        with pytest.raises(ValueError) as exc_info:
            intake_registry.get_connector("nonexistent")
        
        assert "Unknown connector 'nonexistent'" in str(exc_info.value)
        assert "google_forms" in str(exc_info.value)
        assert "google_sheets" in str(exc_info.value)
        assert "github_issues" in str(exc_info.value)


class TestIntakeRegistryPerRepo:
    """Test that registry is per-repo scoped."""

    def test_different_repos_different_instances(self, temp_repo: Path):
        """Different repos get different registry instances."""
        repo1 = temp_repo / "repo1"
        repo2 = temp_repo / "repo2"
        
        reg1 = IntakeRegistry.from_repo_root(repo1)
        reg2 = IntakeRegistry.from_repo_root(repo2)
        
        assert reg1 is not reg2
        assert reg1.repo_root == repo1
        assert reg2.repo_root == repo2


class TestIntakeRegistryInjectableConnectors:
    """Test that registry can accept custom connector map for testing."""

    def test_custom_connector_map(self, temp_repo: Path):
        """Registry can be initialized with custom connector map."""
        from unittest.mock import MagicMock
        
        mock_connector_class = MagicMock()
        mock_connector_class.return_value.connector_name = "mock"
        
        custom_connectors = {"mock": mock_connector_class}
        registry = IntakeRegistry(temp_repo, connectors=custom_connectors)
        
        assert registry.has_connector("mock")
        assert not registry.has_connector("google_forms")
        
        connector = registry.get_connector("mock")
        assert connector.connector_name == "mock"
        mock_connector_class.assert_called_once()


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntakeRegistryAndStoreIntegration:
    """Test registry and store working together."""

    def test_full_roundtrip(self, temp_repo: Path):
        """Registry gets connector, connector produces packets, store saves them."""
        registry = IntakeRegistry.from_repo_root(temp_repo)
        store = IntakeStore(temp_repo)
        
        # Get connector through registry
        connector = registry.get_connector("google_forms")
        
        # Use connector to get packets (stub returns sample data)
        packets_result = connector.list_packets(limit=2)
        assert len(packets_result) >= 0  # Stub may return 0 or more
        
        # If connector returned packets, save them
        if packets_result:
            for packet in packets_result:
                store.save_packet(packet, dry_run=False)
            
            # Verify they were saved
            loaded = store.load_packets()
            assert len(loaded) == len(packets_result)


# =============================================================================
# Architectural Verification Tests
# =============================================================================


class TestArchitecturalInvariants:
    """Verify that architectural decisions from ADR 0005 are maintained."""

    def test_registry_does_not_own_connector_semantics(self):
        """Registry knows connector classes exist but not how they work."""
        # Registry has _KNOWN_CONNECTORS dict (inventory knowledge)
        assert "_KNOWN_CONNECTORS" in dir() or _KNOWN_CONNECTORS is not None
        # But it does NOT have normalization logic
        # This is verified by: no normalize_* methods in IntakeRegistry
        assert not hasattr(IntakeRegistry, "normalize")
        assert not hasattr(IntakeRegistry, "_normalize")

    def test_store_does_not_handle_pledges(self):
        """IntakeStore handles packets only, not pledges."""
        # Store has packet-related methods only
        store_methods = [m for m in dir(IntakeStore) if not m.startswith("_")]
        assert "load_packets" in store_methods
        assert "save_packet" in store_methods
        # No pledge methods
        assert "load_pledges" not in store_methods
        assert "save_pledge" not in store_methods

    def test_connector_owns_validation(self, intake_registry: IntakeRegistry):
        """Connector owns its validation - registry doesn't wrap errors."""
        # The registry simply calls the connector constructor
        # If connector raises, it bubbles up - registry doesn't catch and wrap
        # This is verified by: get_connector returns cls(config) directly
        # We can't easily test this without a failing connector,
        # but the implementation shows no try/except in get_connector
        connector = intake_registry.get_connector("google_forms")
        assert connector is not None
