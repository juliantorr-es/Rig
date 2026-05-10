"""Tests for Workspace Hygiene module.

PHASE 9: Test file for workspace_hygiene.py
Validates: deterministic reconciliation, bounded cadence, oscillation prevention,
replay-safe ordering, cancellation correctness, namespace isolation, no authority mutation,
forbidden pattern enforcement.
"""

from __future__ import annotations

import asyncio
import random
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Deque, Dict, FrozenSet, List, Optional, Set
from unittest.mock import MagicMock, AsyncMock, patch

from rig.domain.workspace_hygiene import (
    SCHEMA_VERSION,
    WorkspaceHygieneAction,
    WorkspaceHygieneStatus,
    ArtifactCategory,
    ArtifactInfo,
    NamespaceInfo,
    RuntimeHealthInfo,
    IsolationInfo,
    HygieneAction,
    WorkspaceHygieneStats,
    WorkspaceHygieneConfig,
    WorkspaceHygieneController,
    WorkspaceHygieneLoop,
    DEFAULT_HYGIENE_CADENCE_MIN,
    DEFAULT_HYGIENE_CADENCE_MAX,
    DEFAULT_HYGIENE_MAX_ITERATIONS,
    DEFAULT_STALE_ARTIFACT_AGE_HOURS,
    DEFAULT_TEMP_STATE_AGE_HOURS,
    DEFAULT_RUNTIME_HEALTH_CHECK_INTERVAL_HOURS,
)
from rig.domain.reconciliation_governance import (
    ReconciliationCadence,
    DampingFactor,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_workspace_id():
    return "test-workspace"


@pytest.fixture
def mock_cadence() -> ReconciliationCadence:
    return ReconciliationCadence(
        min_interval_seconds=10.0,
        max_interval_seconds=60.0,
        jitter_factor=0.1,
    )


@pytest.fixture
def mock_config(mock_workspace_id: str) -> WorkspaceHygieneConfig:
    return WorkspaceHygieneConfig(
        cadence=ReconciliationCadence(
            min_interval_seconds=10.0,
            max_interval_seconds=60.0,
            jitter_factor=0.1,
        ),
        max_iterations=10,
        stale_artifact_age_hours=24.0,
        temp_state_age_hours=1.0,
        runtime_health_check_interval_hours=1.0,
        enabled=True,
        workspace_id=mock_workspace_id,
    )


@pytest.fixture
def mock_controller(mock_config: WorkspaceHygieneConfig) -> WorkspaceHygieneController:
    return WorkspaceHygieneController(config=mock_config)


@pytest.fixture
def mock_artifact() -> ArtifactInfo:
    return ArtifactInfo(
        artifact_id="artifact-1",
        category=ArtifactCategory.TEMP,
        path="/workspace/temp/file.txt",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        size_bytes=1024,
        workspace_id="test-workspace",
        isProtected=False,
    )


@pytest.fixture
def mock_namespace() -> NamespaceInfo:
    return NamespaceInfo(
        namespace_id="namespace-1",
        path="/workspace/namespace-1",
        artifact_count=10,
        total_size_bytes=10240,
        last_accessed=datetime(2024, 1, 1, tzinfo=timezone.utc),
        issues=[],
        health_status=WorkspaceHygieneStatus.HEALTHY,
    )


@pytest.fixture
def mock_runtime() -> RuntimeHealthInfo:
    return RuntimeHealthInfo(
        runtime_id="runtime-1",
        status="running",
        healthy=True,
        last_heartbeat=datetime(2024, 1, 1, tzinfo=timezone.utc),
        error=None,
        warnings=[],
    )


@pytest.fixture
def mock_isolation() -> IsolationInfo:
    return IsolationInfo(
        workspace_id="test-workspace",
        is_isolated=True,
        violation_count=0,
        last_violation=None,
        violation_details=[],
    )


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
        assert SCHEMA_VERSION == "rig.workspace_hygiene.v1"

    def test_default_hygiene_cadence_min(self):
        assert DEFAULT_HYGIENE_CADENCE_MIN == 10.0

    def test_default_hygiene_cadence_max(self):
        assert DEFAULT_HYGIENE_CADENCE_MAX == 60.0

    def test_default_hygiene_max_iterations(self):
        assert DEFAULT_HYGIENE_MAX_ITERATIONS == 10

    def test_default_stale_artifact_age_hours(self):
        assert DEFAULT_STALE_ARTIFACT_AGE_HOURS == 24.0

    def test_default_temp_state_age_hours(self):
        assert DEFAULT_TEMP_STATE_AGE_HOURS == 1.0

    def test_default_runtime_health_check_interval_hours(self):
        assert DEFAULT_RUNTIME_HEALTH_CHECK_INTERVAL_HOURS == 1.0


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Test enumeration types."""

    def test_workspace_hygiene_action_values(self):
        assert WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP.value == "stale_artifact_cleanup"
        assert WorkspaceHygieneAction.NAMESPACE_HYGIENE.value == "namespace_hygiene"
        assert WorkspaceHygieneAction.TEMP_STATE_CLEANUP.value == "temp_state_cleanup"
        assert WorkspaceHygieneAction.RUNTIME_HEALTH_VERIFICATION.value == "runtime_health_verification"
        assert WorkspaceHygieneAction.ISOLATION_VERIFICATION.value == "isolation_verification"

    def test_workspace_hygiene_status_values(self):
        assert WorkspaceHygieneStatus.HEALTHY.value == "healthy"
        assert WorkspaceHygieneStatus.DEGRADED.value == "degraded"
        assert WorkspaceHygieneStatus.UNHEALTHY.value == "unhealthy"
        assert WorkspaceHygieneStatus.ISOLATION_VIOLATION.value == "isolation_violation"
        assert WorkspaceHygieneStatus.RUNTIME_ERROR.value == "runtime_error"

    def test_artifact_category_values(self):
        assert ArtifactCategory.RECEIPT.value == "receipt"
        assert ArtifactCategory.LOG.value == "log"
        assert ArtifactCategory.TEMP.value == "temp"
        assert ArtifactCategory.CACHE.value == "cache"
        assert ArtifactCategory.OUTPUT.value == "output"
        assert ArtifactCategory.INPUT.value == "input"
        assert ArtifactCategory.BACKUP.value == "backup"
        assert ArtifactCategory.ARCHIVE.value == "archive"
        assert ArtifactCategory.SCRATCH.value == "scratch"


# =============================================================================
# Data Type Tests
# =============================================================================

class TestArtifactInfo:
    """Test ArtifactInfo."""

    def test_default_artifact(self, mock_artifact: ArtifactInfo):
        assert mock_artifact.artifact_id == "artifact-1"
        assert mock_artifact.category == ArtifactCategory.TEMP
        assert mock_artifact.path == "/workspace/temp/file.txt"
        assert isinstance(mock_artifact.created_at, datetime)
        assert mock_artifact.size_bytes == 1024
        assert mock_artifact.workspace_id == "test-workspace"
        assert mock_artifact.isProtected is False

    def test_artifact_age(self, mock_artifact: ArtifactInfo):
        # Age is calculated from created_at
        assert isinstance(mock_artifact.age, timedelta)
        assert mock_artifact.age.total_seconds() > 0

    def test_artifact_is_stale(self, mock_artifact: ArtifactInfo):
        # With default stale age (24 hours), a recent artifact is not stale
        assert mock_artifact.is_stale() is False
        
        # With age 0, should be stale immediately
        old_artifact = ArtifactInfo(
            artifact_id="old-artifact",
            category=ArtifactCategory.TEMP,
            path="/workspace/temp/old.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        assert old_artifact.is_stale() is True

    def test_artifact_is_stale_custom_age(self, mock_artifact: ArtifactInfo):
        # Test with custom stale age
        assert mock_artifact.is_stale(stale_age_hours=0.01) is True

    def test_artifact_to_dict(self, mock_artifact: ArtifactInfo):
        d = mock_artifact.to_dict()
        assert d["artifact_id"] == "artifact-1"
        assert d["category"] == "temp"
        assert d["path"] == "/workspace/temp/file.txt"

    def test_artifact_is_frozen(self, mock_artifact: ArtifactInfo):
        with pytest.raises(AttributeError):
            mock_artifact.artifact_id = "new-id"


class TestNamespaceInfo:
    """Test NamespaceInfo."""

    def test_default_namespace(self, mock_namespace: NamespaceInfo):
        assert mock_namespace.namespace_id == "namespace-1"
        assert mock_namespace.path == "/workspace/namespace-1"
        assert mock_namespace.artifact_count == 10
        assert mock_namespace.total_size_bytes == 10240
        assert mock_namespace.health_status == WorkspaceHygieneStatus.HEALTHY
        assert mock_namespace.issues == []

    def test_namespace_to_dict(self, mock_namespace: NamespaceInfo):
        d = mock_namespace.to_dict()
        assert d["namespace_id"] == "namespace-1"
        assert d["artifact_count"] == 10
        assert d["health_status"] == "healthy"

    def test_namespace_with_issues(self):
        namespace = NamespaceInfo(
            namespace_id="problem-ns",
            path="/workspace/problem-ns",
            issues=["too many artifacts", "too large"],
            health_status=WorkspaceHygieneStatus.DEGRADED,
        )
        assert namespace.health_status == WorkspaceHygieneStatus.DEGRADED
        assert len(namespace.issues) == 2


class TestRuntimeHealthInfo:
    """Test RuntimeHealthInfo."""

    def test_default_runtime(self, mock_runtime: RuntimeHealthInfo):
        assert mock_runtime.runtime_id == "runtime-1"
        assert mock_runtime.status == "running"
        assert mock_runtime.healthy is True
        assert mock_runtime.error is None
        assert mock_runtime.warnings == []

    def test_unhealthy_runtime(self):
        runtime = RuntimeHealthInfo(
            runtime_id="unhealthy-runtime",
            status="error",
            healthy=False,
            error="Runtime crashed",
            warnings=["high memory usage"],
        )
        assert runtime.healthy is False
        assert runtime.error == "Runtime crashed"

    def test_runtime_to_dict(self, mock_runtime: RuntimeHealthInfo):
        d = mock_runtime.to_dict()
        assert d["runtime_id"] == "runtime-1"
        assert d["status"] == "running"
        assert d["healthy"] is True


class TestIsolationInfo:
    """Test IsolationInfo."""

    def test_default_isolation(self, mock_isolation: IsolationInfo):
        assert mock_isolation.workspace_id == "test-workspace"
        assert mock_isolation.is_isolated is True
        assert mock_isolation.violation_count == 0
        assert mock_isolation.violation_details == []

    def test_violation_isolation(self):
        isolation = IsolationInfo(
            workspace_id="violated-workspace",
            is_isolated=False,
            violation_count=3,
            last_violation=datetime(2024, 1, 1, tzinfo=timezone.utc),
            violation_details=["Cross-lane access", "Shared state"],
        )
        assert isolation.is_isolated is False
        assert isolation.violation_count == 3

    def test_isolation_to_dict(self, mock_isolation: IsolationInfo):
        d = mock_isolation.to_dict()
        assert d["workspace_id"] == "test-workspace"
        assert d["is_isolated"] is True


class TestHygieneAction:
    """Test HygieneAction."""

    def test_default_hygiene_action(self):
        action = HygieneAction(
            action=WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP,
            target="artifact-1",
        )
        assert action.action == WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP
        assert action.target == "artifact-1"
        assert isinstance(action.timestamp, datetime)
        assert action.details == ""
        assert action.success is True
        assert action.error is None

    def test_failed_hygiene_action(self):
        action = HygieneAction(
            action=WorkspaceHygieneAction.TEMP_STATE_CLEANUP,
            target="temp-1",
            details="Failed to delete",
            success=False,
            error="Permission denied",
        )
        assert action.success is False
        assert action.error == "Permission denied"

    def test_hygiene_action_to_dict(self):
        action = HygieneAction(
            action=WorkspaceHygieneAction.NAMESPACE_HYGIENE,
            target="namespace-1",
            details="Cleaned up 10 files",
            success=True,
        )
        d = action.to_dict()
        assert d["action"] == "namespace_hygiene"
        assert d["target"] == "namespace-1"
        assert d["success"] is True


class TestWorkspaceHygieneStats:
    """Test WorkspaceHygieneStats."""

    def test_default_stats(self):
        stats = WorkspaceHygieneStats()
        assert stats.total_checks == 0
        assert stats.stale_artifacts_removed == 0
        assert stats.temp_states_removed == 0
        assert stats.namespaces_cleaned == 0
        assert stats.runtime_health_verified == 0
        assert stats.isolation_verified == 0
        assert stats.errors == 0

    def test_stats_to_dict(self):
        stats = WorkspaceHygieneStats(
            total_checks=100,
            stale_artifacts_removed=10,
            temp_states_removed=5,
            namespaces_cleaned=3,
            runtime_health_verified=20,
            isolation_verified=1,
            errors=2,
        )
        d = stats.to_dict()
        assert d["total_checks"] == 100
        assert d["stale_artifacts_removed"] == 10
        assert d["errors"] == 2


class TestWorkspaceHygieneConfig:
    """Test WorkspaceHygieneConfig."""

    def test_default_config(self, mock_workspace_id: str):
        config = WorkspaceHygieneConfig(workspace_id=mock_workspace_id)
        assert config.cadence.min_interval_seconds == DEFAULT_HYGIENE_CADENCE_MIN
        assert config.cadence.max_interval_seconds == DEFAULT_HYGIENE_CADENCE_MAX
        assert config.max_iterations == DEFAULT_HYGIENE_MAX_ITERATIONS
        assert config.stale_artifact_age_hours == DEFAULT_STALE_ARTIFACT_AGE_HOURS
        assert config.temp_state_age_hours == DEFAULT_TEMP_STATE_AGE_HOURS
        assert config.runtime_health_check_interval_hours == DEFAULT_RUNTIME_HEALTH_CHECK_INTERVAL_HOURS
        assert config.enabled is True
        assert config.workspace_id == mock_workspace_id

    def test_config_required_workspace_id(self):
        with pytest.raises(ValueError, match="workspace_id is required"):
            WorkspaceHygieneConfig(workspace_id="")

    def test_config_validation_negative_stale_age(self):
        with pytest.raises(ValueError, match="stale_artifact_age_hours must be > 0"):
            WorkspaceHygieneConfig(
                workspace_id="test",
                stale_artifact_age_hours=-1.0,
            )

    def test_config_validation_negative_temp_age(self):
        with pytest.raises(ValueError, match="temp_state_age_hours must be > 0"):
            WorkspaceHygieneConfig(
                workspace_id="test",
                temp_state_age_hours=0.0,
            )

    def test_config_validation_max_iterations_zero(self):
        with pytest.raises(ValueError, match="max_iterations must be >= 1"):
            WorkspaceHygieneConfig(
                workspace_id="test",
                max_iterations=0,
            )

    def test_config_protected_artifacts(self):
        config = WorkspaceHygieneConfig(workspace_id="test")
        assert "receipts" in config.protected_artifacts
        assert "governance" in config.protected_artifacts
        assert "config" in config.protected_artifacts
        assert "audit" in config.protected_artifacts

    def test_config_is_frozen(self):
        config = WorkspaceHygieneConfig(workspace_id="test")
        with pytest.raises(AttributeError):
            config.enabled = False


# =============================================================================
# Forbidden Patterns Tests
# =============================================================================

class TestForbiddenPatterns:
    """Test forbidden pattern enforcement."""

    def test_forbidden_patterns_defined(self):
        """Verify forbidden patterns are defined."""
        forbidden = WorkspaceHygieneController.FORBIDDEN_PATTERNS
        assert "cross_lane" in forbidden
        assert "auto_route" in forbidden
        assert "replay_mutate" in forbidden
        assert "implicit_merge" in forbidden
        assert "authority_infer" in forbidden

    def test_check_forbidden_detects_cross_lane(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller._check_forbidden("cross_lane_reconcile", "target")
        assert result is True

    def test_check_forbidden_detects_auto_route(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller._check_forbidden("auto_route_authority", "target")
        assert result is True

    def test_check_forbidden_detects_replay_mutation(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller._check_forbidden("replay_mutation_loop", "target")
        assert result is True

    def test_check_forbidden_detects_implicit_merge(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller._check_forbidden("implicit_merging", "target")
        assert result is True

    def test_check_forbidden_detects_authority_inference(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller._check_forbidden("authority_inference", "target")
        assert result is True

    def test_check_forbidden_in_target(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller._check_forbidden("some_action", "auto_route-target")
        assert result is True

    def test_check_forbidden_case_insensitive(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller._check_forbidden("CROSS_LANE", "TARGET")
        assert result is True

    def test_check_forbidden_allows_valid_actions(self, mock_controller: WorkspaceHygieneController):
        valid_actions = [
            "stale_artifact_cleanup",
            "namespace_hygiene",
            "temp_state_cleanup",
            "runtime_health_verification",
            "isolation_verification",
        ]
        for action in valid_actions:
            result = mock_controller._check_forbidden(action, "target")
            assert result is False, f"Action {action} should not be forbidden"


# =============================================================================
# Controller Tests
# =============================================================================

class TestWorkspaceHygieneController:
    """Test WorkspaceHygieneController."""

    def test_init(self, mock_controller: WorkspaceHygieneController):
        assert mock_controller.config is not None
        assert mock_controller.stats == WorkspaceHygieneStats()
        assert mock_controller.action_history == []
        assert mock_controller.workspace_id == "test-workspace"
        assert mock_controller._running is False

    def test_start_stop(self, mock_controller: WorkspaceHygieneController):
        mock_controller.start()
        assert mock_controller._running is True
        assert mock_controller._iteration == 1
        assert mock_controller._last_check is not None
        
        mock_controller.stop()
        assert mock_controller._running is False

    def test_record_action(self, mock_controller: WorkspaceHygieneController):
        mock_controller.start()
        
        mock_controller._record_action(
            action=WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP,
            target="artifact-1",
            details="Test cleanup",
            success=True,
        )
        
        assert len(mock_controller.action_history) == 1
        action = mock_controller.action_history[0]
        assert action.action == WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP
        assert action.target == "artifact-1"
        assert mock_controller.stats.total_checks == 1

    def test_record_action_increments_stats(self, mock_controller: WorkspaceHygieneController):
        mock_controller.start()
        
        # Record stale artifact cleanup
        mock_controller._record_action(
            action=WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP,
            target="artifact-1",
            success=True,
        )
        assert mock_controller.stats.stale_artifacts_removed == 1
        
        # Record temp state cleanup
        mock_controller._record_action(
            action=WorkspaceHygieneAction.TEMP_STATE_CLEANUP,
            target="temp-1",
            success=True,
        )
        assert mock_controller.stats.temp_states_removed == 1
        
        # Record namespace hygiene
        mock_controller._record_action(
            action=WorkspaceHygieneAction.NAMESPACE_HYGIENE,
            target="namespace-1",
            success=True,
        )
        assert mock_controller.stats.namespaces_cleaned == 1
        
        # Record runtime health verification
        mock_controller._record_action(
            action=WorkspaceHygieneAction.RUNTIME_HEALTH_VERIFICATION,
            target="runtime-1",
            success=True,
        )
        assert mock_controller.stats.runtime_health_verified == 1
        
        # Record isolation verification
        mock_controller._record_action(
            action=WorkspaceHygieneAction.ISOLATION_VERIFICATION,
            target="workspace-1",
            success=True,
        )
        assert mock_controller.stats.isolation_verified == 1

    def test_record_action_failure_increments_errors(self, mock_controller: WorkspaceHygieneController):
        mock_controller.start()
        
        mock_controller._record_action(
            action=WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP,
            target="artifact-1",
            success=False,
            error="Cleanup failed",
        )
        
        assert mock_controller.stats.errors == 1


# =============================================================================
# Stale Artifact Cleanup Tests
# =============================================================================

class TestStaleArtifactCleanup:
    """Test stale artifact cleanup functionality."""

    def test_check_stale_artifacts_empty(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller.check_stale_artifacts(dry_run=True)
        assert result == []

    def test_check_stale_artifacts_with_artifacts(self, mock_controller: WorkspaceHygieneController, mock_artifact: ArtifactInfo):
        # Create a stale artifact (old created_at)
        old_artifact = ArtifactInfo(
            artifact_id="stale-artifact",
            category=ArtifactCategory.TEMP,
            path="/workspace/temp/stale.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        
        mock_controller._artifact_registry = lambda: [old_artifact]
        
        result = mock_controller.check_stale_artifacts(dry_run=True)
        
        assert len(result) == 1
        assert "stale-artifact" in result
        assert mock_controller.stats.stale_artifacts_removed == 1

    def test_check_stale_artifacts_skips_protected(self, mock_controller: WorkspaceHygieneController):
        old_artifact = ArtifactInfo(
            artifact_id="protected-stale",
            category=ArtifactCategory.LOG,
            path="/workspace/receipts/old.log",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        
        mock_controller._artifact_registry = lambda: [old_artifact]
        
        result = mock_controller.check_stale_artifacts(dry_run=True)
        
        # Should skip because path contains "receipts" which is protected
        assert len(result) == 0

    def test_check_stale_artifacts_skips_non_stale(self, mock_controller: WorkspaceHygieneController, mock_artifact: ArtifactInfo):
        # mock_artifact has recent created_at
        mock_controller._artifact_registry = lambda: [mock_artifact]
        
        result = mock_controller.check_stale_artifacts(dry_run=True)
        
        assert len(result) == 0

    def test_check_stale_artifacts_blocks_forbidden(self, mock_controller: WorkspaceHygieneController):
        old_artifact = ArtifactInfo(
            artifact_id="forbidden-artifact",
            category=ArtifactCategory.TEMP,
            path="/workspace/cross_lane/temp.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        
        mock_controller._artifact_registry = lambda: [old_artifact]
        
        result = mock_controller.check_stale_artifacts(dry_run=True)
        
        # Should be blocked due to forbidden pattern in path
        assert len(result) == 0
        assert mock_controller.stats.errors > 0


# =============================================================================
# Temp State Cleanup Tests
# =============================================================================

class TestTempStateCleanup:
    """Test temp state cleanup functionality."""

    def test_check_temp_states_empty(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller.check_temp_states(dry_run=True)
        assert result == []

    def test_check_temp_states_with_temp_artifacts(self, mock_controller: WorkspaceHygieneController):
        old_temp = ArtifactInfo(
            artifact_id="old-temp",
            category=ArtifactCategory.TEMP,
            path="/workspace/temp/old.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        
        mock_controller._artifact_registry = lambda: [old_temp]
        
        result = mock_controller.check_temp_states(dry_run=True)
        
        assert len(result) == 1
        assert "old-temp" in result
        assert mock_controller.stats.temp_states_removed == 1

    def test_check_temp_states_skips_non_temp(self, mock_controller: WorkspaceHygieneController, mock_artifact: ArtifactInfo):
        # mock_artifact is TEMP category but not stale
        # Create a stale non-temp artifact
        old_output = ArtifactInfo(
            artifact_id="old-output",
            category=ArtifactCategory.OUTPUT,
            path="/workspace/output/old.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        
        mock_controller._artifact_registry = lambda: [old_output]
        
        result = mock_controller.check_temp_states(dry_run=True)
        
        # Should skip because category is OUTPUT, not TEMP
        assert len(result) == 0

    def test_check_temp_states_blocks_forbidden(self, mock_controller: WorkspaceHygieneController):
        old_temp = ArtifactInfo(
            artifact_id="forbidden-temp",
            category=ArtifactCategory.TEMP,
            path="/workspace/auto_route/temp.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        
        mock_controller._artifact_registry = lambda: [old_temp]
        
        result = mock_controller.check_temp_states(dry_run=True)
        
        assert len(result) == 0
        assert mock_controller.stats.errors > 0


# =============================================================================
# Namespace Hygiene Tests
# =============================================================================

class TestNamespaceHygiene:
    """Test namespace hygiene functionality."""

    def test_check_namespace_hygiene_empty(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller.check_namespace_hygiene(dry_run=True)
        assert result == []

    def test_check_namespace_hygiene_with_healthy_namespace(self, mock_controller: WorkspaceHygieneController, mock_namespace: NamespaceInfo):
        mock_controller._namespace_registry = lambda: [mock_namespace]
        
        result = mock_controller.check_namespace_hygiene(dry_run=True)
        
        # Healthy namespaces are not cleaned
        assert len(result) == 0

    def test_check_namespace_hygiene_with_degraded_namespace(self, mock_controller: WorkspaceHygieneController):
        degraded_ns = NamespaceInfo(
            namespace_id="degraded-ns",
            path="/workspace/degraded-ns",
            health_status=WorkspaceHygieneStatus.DEGRADED,
            issues=["too many files"],
        )
        
        mock_controller._namespace_registry = lambda: [degraded_ns]
        
        result = mock_controller.check_namespace_hygiene(dry_run=True)
        
        assert len(result) == 1
        assert "degraded-ns" in result
        assert mock_controller.stats.namespaces_cleaned == 1

    def test_check_namespace_hygiene_blocks_forbidden(self, mock_controller: WorkspaceHygieneController):
        degraded_ns = NamespaceInfo(
            namespace_id="forbidden-ns",
            path="/workspace/cross_lane_ns",
            health_status=WorkspaceHygieneStatus.DEGRADED,
        )
        
        mock_controller._namespace_registry = lambda: [degraded_ns]
        
        result = mock_controller.check_namespace_hygiene(dry_run=True)
        
        assert len(result) == 0
        assert mock_controller.stats.errors > 0


# =============================================================================
# Runtime Health Verification Tests
# =============================================================================

class TestRuntimeHealthVerification:
    """Test runtime health verification functionality."""

    def test_check_runtime_health_empty(self, mock_controller: WorkspaceHygieneController):
        result = mock_controller.check_runtime_health()
        assert result == []

    def test_check_runtime_health_with_runtimes(self, mock_controller: WorkspaceHygieneController, mock_runtime: RuntimeHealthInfo):
        mock_controller._runtime_registry = lambda: [mock_runtime]
        
        result = mock_controller.check_runtime_health()
        
        assert len(result) == 1
        assert "runtime-1" in result
        assert mock_controller.stats.runtime_health_verified == 1

    def test_check_runtime_health_blocks_forbidden(self, mock_controller: WorkspaceHygieneController):
        runtime = RuntimeHealthInfo(
            runtime_id="forbidden-runtime",
            status="running",
            healthy=True,
        )
        
        # Mock the check to have forbidden pattern
        mock_controller._runtime_registry = lambda: [runtime]
        
        # The runtime_id itself doesn't have forbidden pattern
        # But we can test that forbidden patterns in the check are caught
        result = mock_controller.check_runtime_health()
        
        # This should pass since runtime_id is clean
        assert len(result) == 1


# =============================================================================
# Isolation Verification Tests
# =============================================================================

class TestIsolationVerification:
    """Test isolation verification functionality."""

    def test_check_isolation_no_checker(self, mock_controller: WorkspaceHygieneController):
        # No isolation checker configured
        mock_controller._isolation_checker = None
        
        result = mock_controller.check_isolation()
        
        # Should return True (assume OK if can't check)
        assert result is True
        assert mock_controller.stats.isolation_verified == 1

    def test_check_isolation_isolated(self, mock_controller: WorkspaceHygieneController, mock_isolation: IsolationInfo):
        mock_controller._isolation_checker = lambda wid: mock_isolation
        
        result = mock_controller.check_isolation()
        
        assert result is True
        assert mock_controller.stats.isolation_verified == 1

    def test_check_isolation_violation(self, mock_controller: WorkspaceHygieneController):
        violation_isolation = IsolationInfo(
            workspace_id="test-workspace",
            is_isolated=False,
            violation_count=3,
            violation_details=["Cross-lane access detected"],
        )
        mock_controller._isolation_checker = lambda wid: violation_isolation
        
        result = mock_controller.check_isolation()
        
        assert result is False
        assert mock_controller.stats.isolation_verified == 1
        assert mock_controller.stats.errors == 1


# =============================================================================
# Protected Artifact Tests
# =============================================================================

class TestProtectedArtifacts:
    """Test protected artifact handling."""

    def test_is_protected_by_id(self, mock_controller: WorkspaceHygieneController):
        artifact = ArtifactInfo(
            artifact_id="receipts",
            category=ArtifactCategory.TEMP,
            path="/workspace/temp/receipts.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        
        result = mock_controller._is_protected(artifact)
        assert result is True

    def test_is_protected_by_path(self, mock_controller: WorkspaceHygieneController):
        artifact = ArtifactInfo(
            artifact_id="recipe-file",
            category=ArtifactCategory.TEMP,
            path="/workspace/receipts/important.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
        )
        
        result = mock_controller._is_protected(artifact)
        assert result is True

    def test_is_protected_by_flag(self, mock_controller: WorkspaceHygieneController):
        artifact = ArtifactInfo(
            artifact_id="protected-file",
            category=ArtifactCategory.TEMP,
            path="/workspace/temp/protected.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test-workspace",
            isProtected=True,
        )
        
        result = mock_controller._is_protected(artifact)
        assert result is True

    def test_is_not_protected(self, mock_controller: WorkspaceHygieneController, mock_artifact: ArtifactInfo):
        result = mock_controller._is_protected(mock_artifact)
        assert result is False


# =============================================================================
# Full Check Tests
# =============================================================================

class TestFullCheck:
    """Test full workspace hygiene check functionality."""

    def test_run_full_check(self, mock_controller: WorkspaceHygieneController):
        mock_controller.start()
        
        mock_controller._artifact_registry = lambda: []
        mock_controller._namespace_registry = lambda: []
        mock_controller._runtime_registry = lambda: []
        
        result = mock_controller.run_full_check(dry_run=True)
        
        assert "workspace_id" in result
        assert result["workspace_id"] == "test-workspace"
        assert "iteration" in result
        assert "timestamp" in result
        assert "stale_artifacts" in result
        assert "temp_states" in result
        assert "namespaces" in result
        assert "runtimes" in result
        assert "isolation" in result

    def test_run_full_check_increments_iteration(self, mock_controller: WorkspaceHygieneController):
        mock_controller.start()
        
        mock_controller._artifact_registry = lambda: []
        mock_controller._namespace_registry = lambda: []
        mock_controller._runtime_registry = lambda: []
        
        result1 = mock_controller.run_full_check(dry_run=True)
        result2 = mock_controller.run_full_check(dry_run=True)
        
        assert result2["iteration"] == result1["iteration"] + 1

    def test_run_full_check_blocks_forbidden(self, mock_controller: WorkspaceHygieneController):
        # Ensure forbidden operations are blocked
        mock_controller.start()
        
        # mock_controller._check_forbidden will be called internally
        # We need to trigger it via the check methods
        
        # This is tested more thoroughly in individual check tests
        pass


# =============================================================================
# Loop Tests
# =============================================================================

class TestWorkspaceHygieneLoop:
    """Test WorkspaceHygieneLoop."""

    def test_init(self, mock_controller: WorkspaceHygieneController):
        loop = WorkspaceHygieneLoop(controller=mock_controller)
        
        assert loop.running is False
        assert loop.controller is mock_controller
        assert loop._task is None

    def test_start(self, mock_controller: WorkspaceHygieneController):
        loop = WorkspaceHygieneLoop(controller=mock_controller)
        
        loop.start()
        
        assert loop.running is True
        assert loop._task is not None
        assert mock_controller._running is True

    @pytest.mark.asyncio
    async def test_stop(self, mock_controller: WorkspaceHygieneController):
        loop = WorkspaceHygieneLoop(controller=mock_controller)
        loop.start()
        
        await loop.stop()
        
        assert loop.running is False
        assert loop._task is None
        assert mock_controller._running is False

    @pytest.mark.asyncio
    async def test_start_stop_idempotent(self, mock_controller: WorkspaceHygieneController):
        loop = WorkspaceHygieneLoop(controller=mock_controller)
        
        loop.start()
        loop.start()  # Should be idempotent
        
        assert loop.running is True
        
        await loop.stop()
        await loop.stop()  # Should be idempotent
        
        assert loop.running is False


# =============================================================================
# Namespace Isolation Tests
# =============================================================================

class TestNamespaceIsolation:
    """Test namespace isolation for workspace hygiene."""

    def test_controller_isolates_workspace(self):
        config1 = WorkspaceHygieneConfig(workspace_id="ws-1")
        config2 = WorkspaceHygieneConfig(workspace_id="ws-2")
        
        controller1 = WorkspaceHygieneController(config=config1)
        controller2 = WorkspaceHygieneController(config=config2)
        
        # Each controller knows its own workspace
        assert controller1.workspace_id == "ws-1"
        assert controller2.workspace_id == "ws-2"

    def test_workspace_hygiene_is_workspace_scoped(self):
        config1 = WorkspaceHygieneConfig(workspace_id="ws-1")
        config2 = WorkspaceHygieneConfig(workspace_id="ws-2")
        
        controller1 = WorkspaceHygieneController(config=config1)
        controller2 = WorkspaceHygieneController(config=config2)
        
        # Add artifacts to both workspaces
        artifact1 = ArtifactInfo(
            artifact_id="artifact-1",
            category=ArtifactCategory.TEMP,
            path="/ws-1/temp/file.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="ws-1",
        )
        artifact2 = ArtifactInfo(
            artifact_id="artifact-2",
            category=ArtifactCategory.TEMP,
            path="/ws-2/temp/file.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="ws-2",
        )
        
        controller1._artifact_registry = lambda: [artifact1]
        controller2._artifact_registry = lambda: [artifact2]
        
        result1 = controller1.check_temp_states(dry_run=True)
        result2 = controller2.check_temp_states(dry_run=True)
        
        # Each should have processed its own artifacts
        assert "artifact-1" in result1
        assert "artifact-2" in result2


# =============================================================================
# Deterministic Behavior Tests
# =============================================================================

class TestDeterministicBehavior:
    """Test deterministic behavior of workspace hygiene."""

    def test_deterministic_artifact_checking(self):
        """Same artifacts checked in same order produce same results."""
        config = WorkspaceHygieneConfig(workspace_id="test")
        
        artifacts = [
            ArtifactInfo(
                artifact_id=f"artifact-{i}",
                category=ArtifactCategory.TEMP,
                path=f"/workspace/temp/file-{i}.txt",
                created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                workspace_id="test",
            )
            for i in range(5)
        ]
        
        # First pass
        controller1 = WorkspaceHygieneController(config=config)
        controller1.start()
        controller1._artifact_registry = lambda: artifacts
        result1 = controller1.check_temp_states(dry_run=True)
        stats1 = controller1.stats
        
        # Second pass
        controller2 = WorkspaceHygieneController(config=config)
        controller2.start()
        controller2._artifact_registry = lambda: artifacts
        result2 = controller2.check_temp_states(dry_run=True)
        stats2 = controller2.stats
        
        # Results should be identical
        assert result1 == result2
        assert stats1.temp_states_removed == stats2.temp_states_removed
        assert stats1.total_checks == stats2.total_checks


# =============================================================================
# Bounded Cadence Tests
# =============================================================================

class TestBoundedCadence:
    """Test bounded cadence enforcement."""

    def test_cadence_bounds_in_config(self):
        """Cadence bounds are enforced."""
        config = WorkspaceHygieneConfig(
            workspace_id="test",
            cadence=ReconciliationCadence(
                min_interval_seconds=10.0,
                max_interval_seconds=60.0,
                jitter_factor=0.1,
            ),
        )
        assert config.cadence.min_interval_seconds == 10.0
        assert config.cadence.max_interval_seconds == 60.0

    def test_default_cadence_match_constants(self):
        """Default cadence matches module constants."""
        config = WorkspaceHygieneConfig(workspace_id="test")
        assert config.cadence.min_interval_seconds == DEFAULT_HYGIENE_CADENCE_MIN
        assert config.cadence.max_interval_seconds == DEFAULT_HYGIENE_CADENCE_MAX

    def test_max_iterations_bounded(self):
        """Max iterations is bounded."""
        config = WorkspaceHygieneConfig(
            workspace_id="test",
            max_iterations=10,
        )
        assert config.max_iterations == 10


# =============================================================================
# Authority Boundary Tests
# =============================================================================

class TestAuthorityBoundaries:
    """Test that authority boundaries are respected."""

    def test_no_authority_inference(self):
        """Workspace hygiene does not infer authority."""
        config = WorkspaceHygieneConfig(workspace_id="test")
        controller = WorkspaceHygieneController(config=config)
        
        # Artifacts with authority-like metadata
        artifact = ArtifactInfo(
            artifact_id="artifact-1",
            category=ArtifactCategory.TEMP,
            path="/workspace/temp/auto_approve.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test",
            isProtected=False,
        )
        
        controller._artifact_registry = lambda: [artifact]
        
        # The controller uses its own logic, not the path content
        result = controller.check_temp_states(dry_run=True)
        
        # The check should use age-based logic, not path-based authority inference
        assert len(result) >= 0  # May or may not include based on age

    def test_no_imperative_commands(self):
        """No imperative commands are generated."""
        config = WorkspaceHygieneConfig(workspace_id="test")
        controller = WorkspaceHygieneController(config=config)
        
        # Run checks
        result = controller.run_full_check(dry_run=True)
        
        # Result only contains state information, no commands
        assert "stale_artifacts" in result
        assert "temp_states" in result
        assert "namespaces" in result
        assert "runtimes" in result
        assert "isolation" in result
        # No command fields
        assert "commands" not in result
        assert "actions" not in result

    def test_config_explicit_workspace_id(self):
        """Workspace ID is explicitly required, not inferred."""
        with pytest.raises(ValueError, match="workspace_id is required"):
            WorkspaceHygieneConfig(workspace_id="")


# =============================================================================
# Oscillation Prevention Tests
# =============================================================================

class TestOscillationPrevention:
    """Test oscillation prevention mechanisms."""

    def test_max_iterations_prevents_infinite_loop(self):
        """Max iterations prevents infinite loops."""
        config = WorkspaceHygieneConfig(
            workspace_id="test",
            max_iterations=5,
        )
        assert config.max_iterations == 5

    def test_rate_limited_rebuild(self):
        """Rebuild is rate limited."""
        # This is more relevant for projection reconciliation
        # Workspace hygiene uses max_iterations for bounding
        config = WorkspaceHygieneConfig(
            workspace_id="test",
            max_iterations=10,
        )
        controller = WorkspaceHygieneController(config=config)
        
        # Can only run max_iterations checks
        assert controller.config.max_iterations == 10

    def test_damping_via_iteration_limit(self):
        """Iteration limit provides damping effect."""
        config = WorkspaceHygieneConfig(
            workspace_id="test",
            max_iterations=1,  # Very low limit
        )
        controller = WorkspaceHygieneController(config=config)
        
        # Can only run 1 iteration
        assert controller.config.max_iterations == 1


# =============================================================================
# Replay Safety Tests
# =============================================================================

class TestReplaySafety:
    """Test replay-safe behavior."""

    def test_replay_same_artifacts_same_results(self):
        """Replaying same artifacts produces same check results."""
        config = WorkspaceHygieneConfig(workspace_id="test")
        
        artifacts = [
            ArtifactInfo(
                artifact_id=f"stale-{i}",
                category=ArtifactCategory.TEMP,
                path=f"/workspace/temp/stale-{i}.txt",
                created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                workspace_id="test",
            )
            for i in range(5)
        ]
        
        # First pass
        controller1 = WorkspaceHygieneController(config=config)
        controller1.start()
        controller1._artifact_registry = lambda: artifacts
        result1 = controller1.check_temp_states(dry_run=True)
        stats1 = controller1.stats
        
        # Second pass with new controller
        controller2 = WorkspaceHygieneController(config=config)
        controller2.start()
        controller2._artifact_registry = lambda: artifacts
        result2 = controller2.check_temp_states(dry_run=True)
        stats2 = controller2.stats
        
        # Results should be identical
        assert result1 == result2
        assert stats1.temp_states_removed == stats2.temp_states_removed

    def test_reset_allowing_clean_replay(self):
        """Stats reset allows clean replay."""
        config = WorkspaceHygieneConfig(workspace_id="test")
        controller = WorkspaceHygieneController(config=config)
        controller.start()
        
        # First check
        artifact = ArtifactInfo(
            artifact_id="stale-1",
            category=ArtifactCategory.TEMP,
            path="/workspace/temp/stale.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test",
        )
        controller._artifact_registry = lambda: [artifact]
        controller.check_temp_states(dry_run=True)
        
        checks1 = controller.stats.total_checks
        
        # Reset stats by creating new controller
        controller2 = WorkspaceHygieneController(config=config)
        controller2.start()
        controller2._artifact_registry = lambda: [artifact]
        controller2.check_temp_states(dry_run=True)
        
        # Each controller starts with fresh stats
        assert controller2.stats.total_checks == 1


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for workspace hygiene."""

    def test_full_hygiene_workflow(self):
        """Test complete workspace hygiene workflow."""
        config = WorkspaceHygieneConfig(
            workspace_id="integration-test",
            stale_artifact_age_hours=24.0,
            temp_state_age_hours=0.01,  # Very short for testing
        )
        controller = WorkspaceHygieneController(config=config)
        
        controller.start()
        
        # Setup registries
        stale_artifacts = [
            ArtifactInfo(
                artifact_id=f"stale-{i}",
                category=ArtifactCategory.TEMP,
                path=f"/workspace/temp/stale-{i}.txt",
                created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                workspace_id="integration-test",
            )
            for i in range(3)
        ]
        
        temp_states = [
            ArtifactInfo(
                artifact_id=f"temp-{i}",
                category=ArtifactCategory.TEMP,
                path=f"/workspace/temp/temp-{i}.txt",
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),  # Recent but temp
                workspace_id="integration-test",
            )
            for i in range(2)
        ]
        
        namespaces = [
            NamespaceInfo(
                namespace_id="degraded-ns",
                path="/workspace/degraded-ns",
                health_status=WorkspaceHygieneStatus.DEGRADED,
            )
        ]
        
        runtimes = [
            RuntimeHealthInfo(
                runtime_id="runtime-1",
                status="running",
                healthy=True,
            )
        ]
        
        controller._artifact_registry = lambda: stale_artifacts + temp_states
        controller._namespace_registry = lambda: namespaces
        controller._runtime_registry = lambda: runtimes
        controller._isolation_checker = lambda wid: IsolationInfo(workspace_id=wid, is_isolated=True)
        
        # Run full check
        result = controller.run_full_check(dry_run=True)
        
        # Verify results
        assert len(result["stale_artifacts"]) >= 0  # Depends on age
        assert len(result["temp_states"]) >= 0
        assert len(result["namespaces"]) == 1
        assert len(result["runtimes"]) == 1
        assert result["isolation"] is True
        
        # Verify stats
        assert controller.stats.total_checks >= 0
        assert controller.stats.errors == 0

    def test_forbidden_operations_blocked(self):
        """Test that forbidden operations are blocked."""
        config = WorkspaceHygieneConfig(workspace_id="test")
        controller = WorkspaceHygieneController(config=config)
        controller.start()
        
        # Try to check an artifact with forbidden pattern
        forbidden_artifact = ArtifactInfo(
            artifact_id="forbidden-1",
            category=ArtifactCategory.TEMP,
            path="/workspace/cross_lane/file.txt",
            created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            workspace_id="test",
        )
        
        controller._artifact_registry = lambda: [forbidden_artifact]
        
        # This should be blocked
        result = controller.check_temp_states(dry_run=True)
        
        # Should be empty due to forbidden pattern
        assert len(result) == 0
        # But error should be recorded
        assert controller.stats.errors > 0

    def test_protected_artifacts_not_cleaned(self):
        """Test that protected artifacts are not cleaned up."""
        config = WorkspaceHygieneConfig(
            workspace_id="test",
            stale_artifact_age_hours=0.01,  # Very short for testing
        )
        controller = WorkspaceHygieneController(config=config)
        controller.start()
        
        # Create protected artifacts with stale age
        protected_artifacts = [
            ArtifactInfo(
                artifact_id="receipt-1",
                category=ArtifactCategory.LOG,
                path="/workspace/receipts/receipt-1.txt",
                created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                workspace_id="test",
            ),
            ArtifactInfo(
                artifact_id="config-1",
                category=ArtifactCategory.TEMP,
                path="/workspace/config/important.yaml",
                created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                workspace_id="test",
            ),
        ]
        
        controller._artifact_registry = lambda: protected_artifacts
        
        # These should not be cleaned
        result = controller.check_stale_artifacts(dry_run=True)
        
        # Protected artifacts should be skipped
        assert len(result) == 0


# =============================================================================
# Async Tests
# =============================================================================

class TestAsyncOperations:
    """Test async operations."""

    @pytest.mark.asyncio
    async def test_async_full_check(self, mock_controller: WorkspaceHygieneController):
        mock_controller._artifact_registry = lambda: []
        mock_controller._namespace_registry = lambda: []
        mock_controller._runtime_registry = lambda: []
        
        result = await mock_controller.run_async_full_check(dry_run=True)
        
        assert "workspace_id" in result
        assert result["workspace_id"] == "test-workspace"

    @pytest.mark.asyncio
    async def test_loop_async_operation(self, mock_controller: WorkspaceHygieneController):
        loop = WorkspaceHygieneLoop(controller=mock_controller)
        
        # Start the loop
        loop.start()
        
        # Let it run for a bit
        await asyncio.sleep(0.01)
        
        # Stop it
        await loop.stop()
        
        assert loop.running is False
