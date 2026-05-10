"""Tests for Projection Reconciliation module.

PHASE 9: Test file for projection_reconciliation.py
Validates: deterministic reconciliation, bounded cadence, oscillation prevention,
replay-safe ordering, cancellation correctness, namespace isolation, no authority mutation.
"""

from __future__ import annotations

import random
import pytest
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from rig.domain.projection_reconciliation import (
    SCHEMA_VERSION,
    ProjectionRefreshPriority,
    ProjectionRefreshTrigger,
    ProjectionRefreshConfig,
    ProjectionState,
    ProjectionRefreshStats,
    ProjectionInvalidationReason,
    ProjectionInvalidation,
    ProjectionRefreshScheduler,
    ProjectionRebuildTrigger,
    ProjectionReconciliationController,
    DEFAULT_PROJECTION_CADENCE_MIN,
    DEFAULT_PROJECTION_CADENCE_MAX,
    DEFAULT_PROJECTION_MAX_ITERATIONS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_config() -> ProjectionRefreshConfig:
    return ProjectionRefreshConfig(
        priority=ProjectionRefreshPriority.NORMAL,
        min_interval_seconds=0.5,
        max_interval_seconds=5.0,
        jitter_factor=0.1,
        max_iterations=50,
        batch_size=10,
        enabled=True,
        workspace_id="test-workspace",
    )


@pytest.fixture
def mock_scheduler(mock_config: ProjectionRefreshConfig) -> ProjectionRefreshScheduler:
    return ProjectionRefreshScheduler(config=mock_config)


@pytest.fixture
def mock_rebuild_trigger(mock_scheduler: ProjectionRefreshScheduler) -> ProjectionRebuildTrigger:
    return ProjectionRebuildTrigger(scheduler=mock_scheduler)


@pytest.fixture
def mock_controller(mock_config: ProjectionRefreshConfig) -> ProjectionReconciliationController:
    return ProjectionReconciliationController(config=mock_config)


@pytest.fixture(autouse=True)
def reset_seed():
    """Ensure deterministic behavior by resetting random seed."""
    random.seed(42)


# =============================================================================
# Constants Tests
# =============================================================================

class TestConstants:
    """Test module constants."""

    def test_schema_version(self):
        assert SCHEMA_VERSION == "rig.projection_reconciliation.v1"

    def test_default_cadence_min(self):
        assert DEFAULT_PROJECTION_CADENCE_MIN == 0.5

    def test_default_cadence_max(self):
        assert DEFAULT_PROJECTION_CADENCE_MAX == 5.0

    def test_default_max_iterations(self):
        assert DEFAULT_PROJECTION_MAX_ITERATIONS == 50


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Test enumeration types."""

    def test_projection_refresh_priority_values(self):
        assert ProjectionRefreshPriority.CRITICAL.value == "critical"
        assert ProjectionRefreshPriority.HIGH.value == "high"
        assert ProjectionRefreshPriority.NORMAL.value == "normal"
        assert ProjectionRefreshPriority.LOW.value == "low"
        assert ProjectionRefreshPriority.BACKGROUND.value == "background"

    def test_projection_refresh_trigger_values(self):
        assert ProjectionRefreshTrigger.EVENT_DRIVEN.value == "event_driven"
        assert ProjectionRefreshTrigger.SCHEDULED.value == "scheduled"
        assert ProjectionRefreshTrigger.ON_DEMAND.value == "on_demand"
        assert ProjectionRefreshTrigger.FORCED.value == "forced"

    def test_projection_invalidation_reason_values(self):
        assert ProjectionInvalidationReason.EVENT_RECEIVED.value == "event_received"
        assert ProjectionInvalidationReason.STALE.value == "stale"
        assert ProjectionInvalidationReason.ERROR.value == "error"
        assert ProjectionInvalidationReason.SCHEMA_CHANGED.value == "schema_changed"
        assert ProjectionInvalidationReason.FORCED.value == "forced"


# =============================================================================
# Config Tests
# =============================================================================

class TestProjectionRefreshConfig:
    """Test ProjectionRefreshConfig validation."""

    def test_default_config(self):
        config = ProjectionRefreshConfig()
        assert config.priority == ProjectionRefreshPriority.NORMAL
        assert config.min_interval_seconds == DEFAULT_PROJECTION_CADENCE_MIN
        assert config.max_interval_seconds == DEFAULT_PROJECTION_CADENCE_MAX
        assert config.jitter_factor == 0.1  # Default from governance
        assert config.max_iterations == DEFAULT_PROJECTION_MAX_ITERATIONS
        assert config.batch_size == 10
        assert config.enabled is True
        assert config.workspace_id is None

    def test_config_with_workspace(self):
        config = ProjectionRefreshConfig(workspace_id="ws-1")
        assert config.workspace_id == "ws-1"

    def test_config_validation_negative_min_interval(self):
        with pytest.raises(ValueError, match="min_interval_seconds must be >= 0"):
            ProjectionRefreshConfig(min_interval_seconds=-1)

    def test_config_validation_max_less_than_min(self):
        with pytest.raises(ValueError, match="max_interval_seconds must be >= min_interval_seconds"):
            ProjectionRefreshConfig(min_interval_seconds=10, max_interval_seconds=5)

    def test_config_validation_jitter_out_of_range_high(self):
        with pytest.raises(ValueError, match="jitter_factor must be in"):
            ProjectionRefreshConfig(jitter_factor=1.5)

    def test_config_validation_jitter_out_of_range_low(self):
        with pytest.raises(ValueError, match="jitter_factor must be in"):
            ProjectionRefreshConfig(jitter_factor=-0.1)

    def test_config_validation_max_iterations_zero(self):
        with pytest.raises(ValueError, match="max_iterations must be >= 1"):
            ProjectionRefreshConfig(max_iterations=0)

    def test_config_validation_batch_size_zero(self):
        with pytest.raises(ValueError, match="batch_size must be >= 1"):
            ProjectionRefreshConfig(batch_size=0)

    def test_config_is_frozen(self):
        config = ProjectionRefreshConfig()
        with pytest.raises(AttributeError):
            config.priority = ProjectionRefreshPriority.HIGH


# =============================================================================
# State Type Tests
# =============================================================================

class TestProjectionState:
    """Test ProjectionState."""

    def test_default_state(self):
        state = ProjectionState(projection_id="proj-1")
        assert state.projection_id == "proj-1"
        assert state.version == 0
        assert state.last_refresh is None
        assert state.last_event_sequence == 0
        assert state.needs_refresh is True
        assert state.pending_events == 0
        assert state.refresh_priority == ProjectionRefreshPriority.NORMAL
        assert state.is_valid is True
        assert state.error is None
        assert state.disabled_reason is None

    def test_state_to_dict(self):
        state = ProjectionState(
            projection_id="proj-1",
            version=5,
            last_refresh=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        d = state.to_dict()
        assert d["projection_id"] == "proj-1"
        assert d["version"] == 5
        assert "last_refresh" in d

    def test_state_is_frozen(self):
        state = ProjectionState(projection_id="proj-1")
        with pytest.raises(AttributeError):
            state.version = 1


class TestProjectionRefreshStats:
    """Test ProjectionRefreshStats."""

    def test_default_stats(self):
        stats = ProjectionRefreshStats()
        assert stats.total_refreshes == 0
        assert stats.successful_refreshes == 0
        assert stats.failed_refreshes == 0
        assert stats.average_refresh_time == 0.0
        assert stats.last_refresh_time is None
        assert stats.projections_needing_refresh == 0
        assert stats.high_priority_count == 0

    def test_stats_to_dict(self):
        stats = ProjectionRefreshStats(
            total_refreshes=10,
            successful_refreshes=8,
            failed_refreshes=2,
        )
        d = stats.to_dict()
        assert d["total_refreshes"] == 10
        assert d["successful_refreshes"] == 8
        assert d["failed_refreshes"] == 2


class TestProjectionInvalidation:
    """Test ProjectionInvalidation."""

    def test_default_invalidation(self):
        inv = ProjectionInvalidation(
            projection_id="proj-1",
            reason=ProjectionInvalidationReason.EVENT_RECEIVED,
        )
        assert inv.projection_id == "proj-1"
        assert inv.reason == ProjectionInvalidationReason.EVENT_RECEIVED
        assert isinstance(inv.timestamp, datetime)
        assert inv.event_sequence == 0
        assert inv.details is None

    def test_invalidation_with_details(self):
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        inv = ProjectionInvalidation(
            projection_id="proj-1",
            reason=ProjectionInvalidationReason.ERROR,
            timestamp=now,
            event_sequence=42,
            details="Test error",
        )
        assert inv.timestamp == now
        assert inv.event_sequence == 42
        assert inv.details == "Test error"

    def test_invalidation_to_dict(self):
        inv = ProjectionInvalidation(
            projection_id="proj-1",
            reason=ProjectionInvalidationReason.SCHEMA_CHANGED,
            details="Schema updated",
        )
        d = inv.to_dict()
        assert d["projection_id"] == "proj-1"
        assert d["reason"] == "schema_changed"
        assert d["details"] == "Schema updated"


# =============================================================================
# Scheduler Tests
# =============================================================================

class TestProjectionRefreshScheduler:
    """Test ProjectionRefreshScheduler."""

    def test_init(self, mock_scheduler: ProjectionRefreshScheduler):
        assert mock_scheduler.config is not None
        assert mock_scheduler.stats == ProjectionRefreshStats()
        assert mock_scheduler.projection_states == {}

    def test_register_projection(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        assert "proj-1" in mock_scheduler.projection_states
        state = mock_scheduler.projection_states["proj-1"]
        assert state.projection_id == "proj-1"
        assert state.needs_refresh is True
        assert mock_scheduler.stats.total_projections == 1

    def test_register_projection_idempotent(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.register_projection("proj-1")
        assert mock_scheduler.stats.total_projections == 1

    def test_unregister_projection(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.unregister_projection("proj-1")
        assert "proj-1" not in mock_scheduler.projection_states
        assert mock_scheduler.stats.total_projections == 0

    def test_unregister_nonexistent(self, mock_scheduler: ProjectionRefreshScheduler):
        # Should not raise
        mock_scheduler.unregister_projection("nonexistent")
        assert mock_scheduler.stats.total_projections == 0

    def test_receive_event_creates_projection(self, mock_scheduler: ProjectionRefreshScheduler):
        event = MagicMock()
        event.projection_id = "proj-1"
        event.sequence = 1
        event.event_type = "completion"

        result = mock_scheduler.receive_event(event)
        assert result is True
        assert "proj-1" in mock_scheduler.projection_states
        assert mock_scheduler.stats.projections_needing_refresh == 1

    def test_receive_event_updates_existing_projection(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")

        event1 = MagicMock()
        event1.projection_id = "proj-1"
        event1.sequence = 1
        event1.event_type = "status"

        event2 = MagicMock()
        event2.projection_id = "proj-1"
        event2.sequence = 2
        event2.event_type = "completion"

        mock_scheduler.receive_event(event1)
        state1 = mock_scheduler.projection_states["proj-1"]

        mock_scheduler.receive_event(event2)
        state2 = mock_scheduler.projection_states["proj-1"]

        assert state2.version == state1.version + 1
        assert state2.last_event_sequence >= state1.last_event_sequence
        assert state2.pending_events == state1.pending_events + 1

    def test_receive_event_non_refresh_type(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")

        event = MagicMock()
        event.projection_id = "proj-1"
        event.sequence = 1
        event.event_type = "info"

        result = mock_scheduler.receive_event(event)
        assert result is False
        state = mock_scheduler.projection_states["proj-1"]
        assert state.needs_refresh is True  # Was already True
        assert state.pending_events == 0  # Not incremented

    def test_event_requires_refresh_various_types(self, mock_scheduler: ProjectionRefreshScheduler):
        # Test various event types that should trigger refresh
        refresh_types = ["completion", "failure", "status", "delta", "update", 
                        "change", "create", "delete", "modify", "refresh", "rebuild"]
        for et in refresh_types:
            event = MagicMock()
            event.event_type = et
            assert mock_scheduler._event_requires_refresh(et) is True

    def test_event_requires_refresh_non_triggering(self, mock_scheduler: ProjectionRefreshScheduler):
        non_refresh = ["info", "debug", "heartbeat", "ping"]
        for et in non_refresh:
            assert mock_scheduler._event_requires_refresh(et) is False

    def test_get_refresh_priority_critical(self, mock_scheduler: ProjectionRefreshScheduler):
        event = MagicMock()
        event.event_type = "failure_error"
        priority = mock_scheduler._get_refresh_priority(event)
        assert priority == ProjectionRefreshPriority.CRITICAL

    def test_get_refresh_priority_high(self, mock_scheduler: ProjectionRefreshScheduler):
        event = MagicMock()
        event.event_type = "status_change_completion"
        priority = mock_scheduler._get_refresh_priority(event)
        assert priority == ProjectionRefreshPriority.HIGH

    def test_get_refresh_priority_normal(self, mock_scheduler: ProjectionRefreshScheduler):
        event = MagicMock()
        event.event_type = "update"
        priority = mock_scheduler._get_refresh_priority(event)
        assert priority == ProjectionRefreshPriority.NORMAL

    def test_schedule_refresh(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.schedule_refresh("proj-1", priority=ProjectionRefreshPriority.HIGH)
        
        assert "proj-1" in mock_scheduler.projection_states
        state = mock_scheduler.projection_states["proj-1"]
        assert state.needs_refresh is True
        assert state.refresh_priority == ProjectionRefreshPriority.HIGH
        assert mock_scheduler.stats.projections_needing_refresh == 1
        assert mock_scheduler.stats.high_priority_count == 1

    def test_schedule_refresh_critical_priority_goes_to_front(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.schedule_refresh("proj-1", priority=ProjectionRefreshPriority.NORMAL)
        mock_scheduler.schedule_refresh("proj-2", priority=ProjectionRefreshPriority.CRITICAL)
        
        queue = mock_scheduler._refresh_queue
        assert list(queue)[0] == "proj-2"  # Critical at front

    def test_get_next_refresh_batch(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.register_projection("proj-2")
        mock_scheduler.register_projection("proj-3")
        
        # Mark all as needing refresh
        for pid in ["proj-1", "proj-2", "proj-3"]:
            mock_scheduler.schedule_refresh(pid)
        
        batch = mock_scheduler.get_next_refresh_batch(max_batch_size=2)
        assert len(batch) == 2
        assert "proj-1" in batch or "proj-2" in batch or "proj-3" in batch

    def test_get_next_refresh_batch_respects_config(self, mock_scheduler: ProjectionRefreshScheduler):
        # Config has batch_size=10
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.schedule_refresh("proj-1")
        
        batch = mock_scheduler.get_next_refresh_batch()
        assert len(batch) <= 10

    def test_mark_refreshed(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.schedule_refresh("proj-1")
        
        mock_scheduler.mark_refreshed("proj-1", success=True)
        
        state = mock_scheduler.projection_states["proj-1"]
        assert state.needs_refresh is False
        assert state.last_refresh is not None
        assert state.pending_events == 0
        assert mock_scheduler.stats.total_refreshes == 1
        assert mock_scheduler.stats.successful_refreshes == 1
        assert mock_scheduler.stats.projections_needing_refresh == 0

    def test_mark_refreshed_failure(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.schedule_refresh("proj-1", priority=ProjectionRefreshPriority.HIGH)
        
        mock_scheduler.mark_refreshed("proj-1", success=False, error="Test error")
        
        state = mock_scheduler.projection_states["proj-1"]
        assert state.needs_refresh is False
        assert state.error == "Test error"
        assert state.is_valid is False
        assert mock_scheduler.stats.failed_refreshes == 1

    def test_mark_error(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        
        mock_scheduler.mark_error("proj-1", error="Build error")
        
        state = mock_scheduler.projection_states["proj-1"]
        assert state.needs_refresh is True
        assert state.is_valid is False
        assert state.error == "Build error"
        assert state.refresh_priority == ProjectionRefreshPriority.HIGH
        assert mock_scheduler.stats.failed_refreshes == 1

    def test_invalidate_projection(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        
        mock_scheduler.invalidate_projection(
            "proj-1",
            ProjectionInvalidationReason.SCHEMA_CHANGED,
            details="Schema v2",
        )
        
        state = mock_scheduler.projection_states["proj-1"]
        assert state.needs_refresh is True
        assert state.version == 1  # Was 0, incremented
        assert state.refresh_priority == ProjectionRefreshPriority.HIGH
        
        assert len(mock_scheduler._invalidations) == 1
        inv = mock_scheduler._invalidations[0]
        assert inv.reason == ProjectionInvalidationReason.SCHEMA_CHANGED
        assert inv.details == "Schema v2"

    def test_get_projections_needing_refresh(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.register_projection("proj-2")
        
        mock_scheduler.schedule_refresh("proj-1")
        
        needing = mock_scheduler.get_projections_needing_refresh()
        assert "proj-1" in needing
        assert "proj-2" not in needing

    def test_get_high_priority_projections(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.register_projection("proj-2")
        
        mock_scheduler.schedule_refresh("proj-1", priority=ProjectionRefreshPriority.HIGH)
        mock_scheduler.schedule_refresh("proj-2", priority=ProjectionRefreshPriority.NORMAL)
        
        high_priority = mock_scheduler.get_high_priority_projections()
        assert "proj-1" in high_priority
        assert "proj-2" not in high_priority

    def test_reset_stats(self, mock_scheduler: ProjectionRefreshScheduler):
        mock_scheduler.register_projection("proj-1")
        mock_scheduler.schedule_refresh("proj-1")
        mock_scheduler.mark_refreshed("proj-1")
        
        assert mock_scheduler.stats.total_refreshes > 0
        
        mock_scheduler.reset_stats()
        
        assert mock_scheduler.stats.total_refreshes == 0
        assert mock_scheduler.stats.successful_refreshes == 0

    def test_deterministic_event_processing(self, mock_scheduler: ProjectionRefreshScheduler):
        """Test that event processing is deterministic."""
        events = [
            MagicMock(projection_id="p1", sequence=i, event_type="completion")
            for i in range(10)
        ]
        
        # Process events twice
        for _ in range(2):
            mock_scheduler.reset_stats()
            for ev in events:
                mock_scheduler.receive_event(ev)
        
        # Stats should be the same both times
        assert mock_scheduler.stats.projections_needing_refresh == 1
        assert mock_scheduler.stats.total_projections == 1


# =============================================================================
# Rebuild Trigger Tests
# =============================================================================

class TestProjectionRebuildTrigger:
    """Test ProjectionRebuildTrigger."""

    def test_init(self, mock_rebuild_trigger: ProjectionRebuildTrigger):
        assert mock_rebuild_trigger._max_rebuilds_per_hour == 24
        assert mock_rebuild_trigger._rebuild_count == 0
        assert mock_rebuild_trigger._last_rebuild_time is None

    def test_check_rebuild_needed_no_error(self, mock_rebuild_trigger: ProjectionRebuildTrigger):
        mock_rebuild_trigger._scheduler.register_projection("proj-1")
        # No error on projection
        result = mock_rebuild_trigger.check_rebuild_needed("proj-1")
        assert result is False

    def test_check_rebuild_needed_with_error(self, mock_rebuild_trigger: ProjectionRebuildTrigger):
        mock_rebuild_trigger._scheduler.register_projection("proj-1")
        mock_rebuild_trigger._scheduler.mark_error("proj-1", error="Build failed")
        
        result = mock_rebuild_trigger.check_rebuild_needed("proj-1")
        assert result is True

    def test_check_rebuild_rate_limited(self, mock_rebuild_trigger: ProjectionRebuildTrigger):
        mock_rebuild_trigger._scheduler.register_projection("proj-1")
        mock_rebuild_trigger._scheduler.mark_error("proj-1", error="Build failed")
        
        # Fill up rebuild history to hit rate limit
        now = datetime.now(timezone.utc)
        for _ in range(24):
            mock_rebuild_trigger._rebuild_history.append(now)
        
        result = mock_rebuild_trigger.check_rebuild_needed("proj-1")
        assert result is False

    def test_trigger_rebuild_success(self, mock_rebuild_trigger: ProjectionRebuildTrigger):
        mock_rebuild_trigger._scheduler.register_projection("proj-1")
        mock_rebuild_trigger._scheduler.mark_error("proj-1", error="Build failed")
        
        result = mock_rebuild_trigger.trigger_rebuild("proj-1")
        assert result is True
        assert mock_rebuild_trigger._rebuild_count == 1
        assert len(mock_rebuild_trigger._rebuild_history) == 1
        
        # Check that projection was invalidated
        state = mock_rebuild_trigger._scheduler.projection_states["proj-1"]
        assert state.needs_refresh is True

    def test_trigger_rebuild_blocked(self, mock_rebuild_trigger: ProjectionRebuildTrigger):
        mock_rebuild_trigger._scheduler.register_projection("proj-1")
        # No error, so rebuild not needed
        
        result = mock_rebuild_trigger.trigger_rebuild("proj-1")
        assert result is False

    def test_deterministic_rebuild_triggering(self, mock_rebuild_trigger: ProjectionRebuildTrigger):
        """Test that rebuild triggering is deterministic."""
        mock_rebuild_trigger._scheduler.register_projection("proj-1")
        mock_rebuild_trigger._scheduler.mark_error("proj-1", error="Build failed")
        
        # Trigger rebuild twice
        result1 = mock_rebuild_trigger.trigger_rebuild("proj-1")
        # Reset for second try
        mock_rebuild_trigger._rebuild_history.clear()
        mock_rebuild_trigger._rebuild_count = 0
        
        result2 = mock_rebuild_trigger.trigger_rebuild("proj-1")
        
        assert result1 == result2


# =============================================================================
# Controller Tests
# =============================================================================

class TestProjectionReconciliationController:
    """Test ProjectionReconciliationController."""

    def test_init(self, mock_controller: ProjectionReconciliationController):
        assert mock_controller.config is not None
        assert mock_controller._scheduler is not None
        assert mock_controller._rebuild_trigger is not None
        assert mock_controller._running is False

    def test_start_stop(self, mock_controller: ProjectionReconciliationController):
        mock_controller.start()
        assert mock_controller._running is True
        
        mock_controller.stop()
        assert mock_controller._running is False

    def test_process_events(self, mock_controller: ProjectionReconciliationController):
        events = [
            MagicMock(projection_id="p1", sequence=i, event_type="completion")
            for i in range(5)
        ]
        
        result = mock_controller.process_events(events)
        
        assert result == 5  # All 5 events triggered invalidation
        assert mock_controller.stats.projections_needing_refresh == 1

    def test_tick(self, mock_controller: ProjectionReconciliationController):
        mock_controller.register_projection("proj-1")
        mock_controller.schedule_refresh("proj-1")
        
        result = mock_controller.tick()
        
        assert len(result) == 1
        assert result[0] == "proj-1"
        
        # Check projection was marked refreshed
        state = mock_controller.scheduler.projection_states["proj-1"]
        assert state.needs_refresh is False

    def test_tick_empty_queue(self, mock_controller: ProjectionReconciliationController):
        result = mock_controller.tick()
        assert result == []

    def test_property_accessors(self, mock_controller: ProjectionReconciliationController):
        assert mock_controller.scheduler is not None
        assert mock_controller.rebuild_trigger is not None
        assert mock_controller.stats is not None

    def test_deterministic_processing(self, mock_controller: ProjectionReconciliationController):
        """Test deterministic event processing."""
        events = [
            MagicMock(projection_id="p1", sequence=i, event_type="completion")
            for i in range(10)
        ]
        
        # Process twice
        for _ in range(2):
            mock_controller._scheduler.reset_stats()
            mock_controller.process_events(events)
        
        assert mock_controller.stats.projections_needing_refresh == 1


# =============================================================================
# Namespace Isolation Tests
# =============================================================================

class TestNamespaceIsolation:
    """Test namespace isolation for projection reconciliation."""

    def test_scheduler_isolates_workspaces(self):
        config1 = ProjectionRefreshConfig(workspace_id="ws-1")
        config2 = ProjectionRefreshConfig(workspace_id="ws-2")
        
        scheduler1 = ProjectionRefreshScheduler(config1)
        scheduler2 = ProjectionRefreshScheduler(config2)
        
        # Add projections to both
        scheduler1.register_projection("proj-1-ws1")
        scheduler2.register_projection("proj-1-ws2")
        
        # Each scheduler only knows about its own projections
        assert "proj-1-ws1" in scheduler1.projection_states
        assert "proj-1-ws1" not in scheduler2.projection_states
        assert "proj-1-ws2" in scheduler2.projection_states
        assert "proj-1-ws2" not in scheduler1.projection_states

    def test_events_routed_to_correct_workspace(self):
        config1 = ProjectionRefreshConfig(workspace_id="ws-1")
        config2 = ProjectionRefreshConfig(workspace_id="ws-2")
        
        scheduler1 = ProjectionRefreshScheduler(config1)
        scheduler2 = ProjectionRefreshScheduler(config2)
        
        # Event for ws-1
        event1 = MagicMock()
        event1.workspace_id = "ws-1"
        event1.sequence = 1
        event1.event_type = "completion"
        
        # Event for ws-2
        event2 = MagicMock()
        event2.workspace_id = "ws-2"
        event2.sequence = 1
        event2.event_type = "completion"
        
        scheduler1.receive_event(event1)
        scheduler2.receive_event(event2)
        
        # Each scheduler processed its own event
        assert scheduler1.stats.projections_needing_refresh == 1
        assert scheduler2.stats.projections_needing_refresh == 1
        assert "ws-1" in scheduler1.projection_states
        assert "ws-2" in scheduler2.projection_states


# =============================================================================
# Replay Safety Tests
# =============================================================================

class TestReplaySafety:
    """Test replay-safe behavior."""

    def test_replay_same_events_same_state(self):
        """Replaying the same events should produce the same state."""
        config = ProjectionRefreshConfig()
        
        # First pass
        scheduler1 = ProjectionRefreshScheduler(config)
        events = [
            MagicMock(projection_id="p1", sequence=i, event_type="completion")
            for i in range(5)
        ]
        for ev in events:
            scheduler1.receive_event(ev)
        
        state1_proj1 = scheduler1.projection_states["p1"]
        stats1 = scheduler1.stats
        
        # Second pass with new scheduler
        scheduler2 = ProjectionRefreshScheduler(config)
        for ev in events:
            scheduler2.receive_event(ev)
        
        state2_proj1 = scheduler2.projection_states["p1"]
        stats2 = scheduler2.stats
        
        # States should be identical
        assert state1_proj1.version == state2_proj1.version
        assert state1_proj1.last_event_sequence == state2_proj1.last_event_sequence
        assert state1_proj1.pending_events == state2_proj1.pending_events
        assert stats1.total_projections == stats2.total_projections
        assert stats1.projections_needing_refresh == stats2.projections_needing_refresh

    def test_replay_with_different_order_deterministic(self):
        """Events in different orders should still process deterministically."""
        config = ProjectionRefreshConfig()
        
        scheduler1 = ProjectionRefreshScheduler(config)
        scheduler2 = ProjectionRefreshScheduler(config)
        
        events = [
            MagicMock(projection_id="p1", sequence=i, event_type="completion")
            for i in range(5)
        ]
        
        # Process in order
        for ev in events:
            scheduler1.receive_event(ev)
        
        # Process in reverse order
        for ev in reversed(events):
            scheduler2.receive_event(ev)
        
        # Both should have processed all events
        # (sequence numbers ensure ordering)
        assert scheduler1.stats.total_projections == scheduler2.stats.total_projections

    def test_event_sequence_ordering(self):
        """Events with out-of-order sequences are handled correctly."""
        config = ProjectionRefreshConfig()
        scheduler = ProjectionRefreshScheduler(config)
        
        # Events out of order
        events = [
            MagicMock(projection_id="p1", sequence=5, event_type="completion"),
            MagicMock(projection_id="p1", sequence=2, event_type="completion"),
            MagicMock(projection_id="p1", sequence=8, event_type="completion"),
            MagicMock(projection_id="p1", sequence=1, event_type="completion"),
        ]
        
        for ev in events:
            scheduler.receive_event(ev)
        
        state = scheduler.projection_states["p1"]
        # Should have tracked the max sequence
        assert state.last_event_sequence == 8


# =============================================================================
# Bounded Cadence Tests
# =============================================================================

class TestBoundedCadence:
    """Test bounded cadence enforcement."""

    def test_cadence_min_max_validation(self):
        """Cadence bounds are enforced in config."""
        with pytest.raises(ValueError):
            ProjectionRefreshConfig(min_interval_seconds=10, max_interval_seconds=5)

    def test_cadence_jitter_bounded(self):
        """Jitter factor is bounded."""
        with pytest.raises(ValueError):
            ProjectionRefreshConfig(jitter_factor=1.5)
        with pytest.raises(ValueError):
            ProjectionRefreshConfig(jitter_factor=-0.1)

    def test_batch_size_bounded(self):
        """Batch size is bounded below."""
        with pytest.raises(ValueError):
            ProjectionRefreshConfig(batch_size=0)


# =============================================================================
# Oscillation Prevention Tests
# =============================================================================

class TestOscillationPrevention:
    """Test oscillation prevention mechanisms."""

    def test_damping_via_priority_decay(self):
        """High priority events don't cause infinite oscillation."""
        config = ProjectionRefreshConfig()
        scheduler = ProjectionRefreshScheduler(config)
        
        # Rapid high-priority events
        for i in range(100):
            event = MagicMock()
            event.projection_id = "osc-proj"
            event.sequence = i
            event.event_type = "failure"  # Critical priority
            
            scheduler.receive_event(event)
        
        # Should have converged to a stable state
        state = scheduler.projection_states["osc-proj"]
        assert state.version == 100  # Each event incremented version
        # But only one projection tracked
        assert len(scheduler.projection_states) == 1

    def test_queue_deduplication(self):
        """Same projection not queued multiple times."""
        config = ProjectionRefreshConfig()
        scheduler = ProjectionRefreshScheduler(config)
        
        event = MagicMock()
        event.projection_id = "p1"
        event.sequence = 1
        event.event_type = "completion"
        
        # Add same event 10 times
        for _ in range(10):
            scheduler.receive_event(event)
        
        # Should only be in queue once
        queue_count = sum(1 for pid in scheduler._refresh_queue if pid == "p1")
        assert queue_count == 1

    def test_max_iterations_bounded(self):
        """Max iterations is enforced."""
        with pytest.raises(ValueError):
            ProjectionRefreshConfig(max_iterations=0)


# =============================================================================
# Authority Boundary Tests
# =============================================================================

class TestAuthorityBoundaries:
    """Test that authority boundaries are respected."""

    def test_no_autority_inference_in_scheduler(self):
        """Scheduler does not infer authority from events."""
        config = ProjectionRefreshConfig()
        scheduler = ProjectionRefreshScheduler(config)
        
        # Event with various metadata
        event = MagicMock()
        event.projection_id = "p1"
        event.sequence = 1
        event.event_type = "completion"
        event.authority_hint = "DO NOT USE"  # Should be ignored
        event.auto_approve = True  # Should be ignored
        
        scheduler.receive_event(event)
        
        # State should only reflect event data, not authority hints
        state = scheduler.projection_states["p1"]
        assert not hasattr(state, 'authority_hint')
        assert not hasattr(state, 'auto_approve')

    def test_no_imperative_commands(self):
        """No imperative rendering commands are generated."""
        config = ProjectionRefreshConfig()
        scheduler = ProjectionRefreshScheduler(config)
        
        # Process events
        event = MagicMock()
        event.projection_id = "p1"
        event.sequence = 1
        event.event_type = "completion"
        
        scheduler.receive_event(event)
        batch = scheduler.get_next_refresh_batch()
        
        # Batch only contains projection IDs, no commands
        assert all(isinstance(pid, str) for pid in batch)

    def test_config_workspace_id_required_for_scope(self):
        """Workspace ID is used for scoping but not authority."""
        config = ProjectionRefreshConfig(workspace_id="ws-1")
        scheduler = ProjectionRefreshScheduler(config)
        
        # Events without workspace_id use fallback
        event = MagicMock()
        event.sequence = 1
        event.event_type = "completion"
        # No projection_id or workspace_id
        
        scheduler.receive_event(event)
        
        # Should have created projection with fallback ID
        assert len(scheduler.projection_states) == 1
        # The key should be the fallback ('default')
        assert "default" in scheduler.projection_states


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for projection reconciliation."""

    def test_full_workflow(self):
        """Test complete projection reconciliation workflow."""
        config = ProjectionRefreshConfig(
            workspace_id="test-ws",
            batch_size=5,
        )
        controller = ProjectionReconciliationController(config)
        
        # 1. Register projections
        controller.scheduler.register_projection("proj-a")
        controller.scheduler.register_projection("proj-b")
        
        # 2. Receive events
        events = [
            MagicMock(projection_id="proj-a", sequence=1, event_type="status"),
            MagicMock(projection_id="proj-b", sequence=1, event_type="completion"),
            MagicMock(projection_id="proj-a", sequence=2, event_type=" delta "),
        ]
        processed = controller.process_events(events)
        assert processed == 3
        
        # 3. Check stats
        assert controller.stats.projections_needing_refresh == 2
        assert controller.stats.total_projections == 2
        
        # 4. Run tick
        refreshed = controller.tick()
        assert len(refreshed) <= 5  # batch_size
        
        # 5. Verify projections
        for pid in ["proj-a", "proj-b"]:
            state = controller.scheduler.projection_states[pid]
            assert state.last_refresh is not None
            assert state.needs_refresh is False

    def test_rebuild_after_error_workflow(self):
        """Test rebuild workflow after error."""
        config = ProjectionRefreshConfig()
        controller = ProjectionReconciliationController(config)
        
        controller.scheduler.register_projection("error-proj")
        
        # Simulate error
        controller.scheduler.mark_error("error-proj", error="Build failed")
        
        # Check rebuild needed
        assert controller.rebuild_trigger.check_rebuild_needed("error-proj") is True
        
        # Trigger rebuild
        result = controller.rebuild_trigger.trigger_rebuild("error-proj")
        assert result is True
        
        # Verify projection invalidated for rebuild
        state = controller.scheduler.projection_states["error-proj"]
        assert state.needs_refresh is True

    def test_concurrent_workspaces(self):
        """Test multiple workspaces operating independently."""
        configs = [
            ProjectionRefreshConfig(workspace_id=f"ws-{i}")
            for i in range(3)
        ]
        controllers = [
            ProjectionReconciliationController(cfg) for cfg in configs
        ]
        
        # Add projections to each
        for i, ctrl in enumerate(controllers):
            ctrl.scheduler.register_projection(f"proj-{i}")
        
        # Process events for each
        for i, ctrl in enumerate(controllers):
            event = MagicMock()
            event.workspace_id = f"ws-{i}"
            eventsequence = 1
            event.event_type = "completion"
            ctrl.process_events([event])
        
        # Each should have its own state
        for i, ctrl in enumerate(controllers):
            assert ctrl.stats.total_projections == 1
            assert f"ws-{i}" in ctrl.scheduler.projection_states or f"proj-{i}" in ctrl.scheduler.projection_states
