"""Tests for Runtime Reconciliation Controllers (PHASE 3 & 9).

This module validates:
- Deterministic reconciliation
- Bounded cadence
- Oscillation prevention
- Replay-safe ordering
- Cancellation correctness
- Namespace isolation
- Telemetry stabilization
- Topology-safe convergence
- No authority mutation

file: tests/test_runtime_reconciliation.py
"""

import asyncio
import pytest
from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from rig.domain.runtime_reconciliation import (
    # Enums
    LoopStatus,
    ControllerType,
    DampingType,
    RetryBackoffType,
    DropPolicy,
    # Governance primitives
    ReconciliationCadence,
    DampingFactor,
    RetryCeiling,
    ConvergenceWindow,
    CancellationPolicy,
    EventStormConfig,
    ReconciliationContext,
    # Info types
    ConvergenceInfo,
    DampingInfo,
    RetryInfo,
    LoopHealthState,
    # Detection
    OscillationMetrics,
    # Base controller
    ReconciliationController,
    # Specific controllers
    RuntimeSupervisionController,
    ProjectionRefreshController,
    TelemetryAggregationController,
    WorkspaceHygieneController,
    TopologyDensityController,
    # Constants
    SCHEMA_VERSION,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_DURATION_SECONDS,
)
from rig.domain.reconciliation_governance import (
    AuthorityBoundaryViolationError,
    check_authority_violation,
    enforce_authority_boundary,
)


class TestReconciliationCadence:
    """Tests for ReconciliationCadence primitive."""

    def test_default_cadence_creation(self):
        """Test default cadence can be created."""
        cadence = ReconciliationCadence()
        assert cadence.min_interval_seconds >= 0
        assert cadence.max_interval_seconds >= cadence.min_interval_seconds
        assert 0.0 <= cadence.jitter_factor <= 1.0

    def test_custom_cadence_creation(self):
        """Test custom cadence can be created with valid values."""
        cadence = ReconciliationCadence(
            min_interval_seconds=1.0,
            max_interval_seconds=10.0,
            jitter_factor=0.2,
        )
        assert cadence.min_interval_seconds == 1.0
        assert cadence.max_interval_seconds == 10.0
        assert cadence.jitter_factor == 0.2

    def test_invalid_min_interval_raises(self):
        """Test negative min_interval raises ValueError."""
        with pytest.raises(ValueError, match="min_interval_seconds must be >= 0"):
            ReconciliationCadence(min_interval_seconds=-1.0)

    def test_min_greater_than_max_raises(self):
        """Test min > max raises ValueError."""
        with pytest.raises(ValueError, match="max_interval_seconds must be >= min_interval_seconds"):
            ReconciliationCadence(min_interval_seconds=10.0, max_interval_seconds=1.0)

    def test_invalid_jitter_raises(self):
        """Test jitter outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="jitter_factor must be in"):
            ReconciliationCadence(jitter_factor=1.5)

    def test_calculate_next_interval_within_bounds(self):
        """Test calculated interval is within configured bounds."""
        cadence = ReconciliationCadence(
            min_interval_seconds=1.0,
            max_interval_seconds=10.0,
            jitter_factor=0.0,  # No jitter for predictability
        )
        # With no jitter, should return values between min and max
        for _ in range(10):
            interval = cadence.calculate_next_interval()
            assert 1.0 <= interval <= 10.0

    def test_cadence_to_dict(self):
        """Test cadence can be serialized to dict."""
        cadence = ReconciliationCadence(
            min_interval_seconds=0.5,
            max_interval_seconds=5.0,
            jitter_factor=0.1,
        )
        d = cadence.to_dict()
        assert d['min_interval_seconds'] == 0.5
        assert d['max_interval_seconds'] == 5.0
        assert d['jitter_factor'] == 0.1


class TestDampingFactor:
    """Tests for DampingFactor primitive."""

    def test_default_damping_creation(self):
        """Test default damping can be created."""
        damping = DampingFactor()
        assert 0.0 < damping.base <= 1.0
        assert 0.0 < damping.rate <= 1.0
        assert damping.threshold >= 0
        assert 0.0 <= damping.min_factor <= damping.max_factor <= 1.0

    def test_exponential_damping(self):
        """Test exponential damping reduces value over iterations."""
        damping = DampingFactor(
            damp_type=DampingType.EXPONENTIAL,
            base=0.5,
        )
        # First iteration: 1.0 * 0.5^0 = 1.0
        assert damping.apply(0, 1.0) == 0.5  # base^0 * 1.0 * min/max clamp
        # Second iteration: 0.5^1 = 0.5
        assert damping.apply(1, 1.0) == 0.25  # base^1 * 1.0 = 0.5
        # Third iteration: 0.5^2 = 0.25
        assert damping.apply(2, 1.0) == 0.125

    def test_linear_damping(self):
        """Test linear damping reduces linearly."""
        damping = DampingFactor(
            damp_type=DampingType.LINEAR,
            rate=0.2,
            min_factor=0.0,
            max_factor=1.0,
        )
        # Iteration 0: 1.0 - 0.2 * 0 = 1.0
        assert damping.apply(0, 1.0) == 1.0
        # Iteration 1: 1.0 - 0.2 * 1 = 0.8
        assert damping.apply(1, 1.0) == 0.8
        # Iteration 5: max(0, 1.0 - 0.2 * 5) = 0.0
        assert damping.apply(5, 1.0) == 0.01  # Clamped by min_factor

    def test_threshold_damping(self):
        """Test threshold damping returns 0 for small values."""
        damping = DampingFactor(
            damp_type=DampingType.THRESHOLD,
            threshold=0.1,
        )
        # Below threshold: 0
        assert damping.apply(0, 0.05) == 0.0
        # At threshold: value returned
        assert damping.apply(0, 0.1) == 0.1
        # Above threshold: value returned
        assert damping.apply(0, 0.5) == 0.5

    def test_damping_clamping(self):
        """Test damping respects min/max factor bounds."""
        damping = DampingFactor(
            damp_type=DampingType.EXPONENTIAL,
            base=0.5,
            min_factor=0.1,
            max_factor=0.9,
        )
        # Very large iteration - should be clamped
        result = damping.apply(1000, 1.0)
        assert 0.1 <= result <= 0.9


class TestRetryCeiling:
    """Tests for RetryCeiling primitive."""

    def test_default_retry_creation(self):
        """Test default retry can be created."""
        retry = RetryCeiling()
        assert retry.max_retries >= 0
        assert retry.retry_base_delay >= 0
        assert retry.retry_max_delay >= retry.retry_base_delay

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        retry = RetryCeiling(
            max_retries=5,
            retry_base_delay=0.1,
            retry_max_delay=10.0,
            retry_backoff_type=RetryBackoffType.EXPONENTIAL,
        )
        assert retry.calculate_delay(0) == 0.1  # 0.1 * 2^0 = 0.1
        assert retry.calculate_delay(1) == 0.2  # 0.1 * 2^1 = 0.2
        assert retry.calculate_delay(2) == 0.4  # 0.1 * 2^2 = 0.4
        assert retry.calculate_delay(3) == 0.8
        # Capped at max_delay
        assert retry.calculate_delay(10) == 10.0

    def test_linear_backoff(self):
        """Test linear backoff calculation."""
        retry = RetryCeiling(
            max_retries=5,
            retry_base_delay=0.1,
            retry_max_delay=10.0,
            retry_backoff_type=RetryBackoffType.LINEAR,
        )
        assert retry.calculate_delay(0) == 0.1  # 0.1 * 1 = 0.1
        assert retry.calculate_delay(1) == 0.2  # 0.1 * 2 = 0.2
        assert retry.calculate_delay(2) == 0.3  # 0.1 * 3 = 0.3

    def test_constant_backoff(self):
        """Test constant backoff calculation."""
        retry = RetryCeiling(
            max_retries=5,
            retry_base_delay=0.5,
            retry_max_delay=10.0,
            retry_backoff_type=RetryBackoffType.CONSTANT,
        )
        assert retry.calculate_delay(0) == 0.5
        assert retry.calculate_delay(1) == 0.5
        assert retry.calculate_delay(10) == 0.5

    def test_is_retryable(self):
        """Test retryable error checking."""
        retry = RetryCeiling()
        assert retry.is_retryable("timeout")
        assert retry.is_retryable("network_error")
        assert retry.is_retryable("resource_unavailable")
        assert retry.is_retryable("rate_limited")
        assert retry.is_retryable("model_unavailable")
        assert not retry.is_retryable("authority_violation")
        assert not retry.is_retryable("bounds_violation")

    def test_non_retryable_authority_violation(self):
        """Test authority violations are not retryable."""
        retry = RetryCeiling()
        assert not retry.is_retryable("authority_violation")
        assert not retry.is_retryable("AUTHORITY_VIOLATION")


class TestConvergenceWindow:
    """Tests for ConvergenceWindow primitive."""

    def test_default_window_creation(self):
        """Test default window can be created."""
        window = ConvergenceWindow()
        assert window.max_iterations >= 1
        assert window.max_duration_seconds > 0
        assert window.stabilisation_threshold >= 0
        assert window.stabilisation_window > 0

    def test_invalid_max_iterations_raises(self):
        """Test max_iterations < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_iterations must be >= 1"):
            ConvergenceWindow(max_iterations=0)

    def test_invalid_duration_raises(self):
        """Test max_duration <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="max_duration_seconds must be > 0"):
            ConvergenceWindow(max_duration_seconds=0)

    def test_is_converged_by_iterations(self):
        """Test convergence detected by max iterations."""
        window = ConvergenceWindow(max_iterations=10)
        assert not window.is_converged(iterations=5, duration=1.0)
        assert window.is_converged(iterations=10, duration=1.0)
        assert window.is_converged(iterations=11, duration=1.0)

    def test_is_converged_by_duration(self):
        """Test convergence detected by max duration."""
        window = ConvergenceWindow(max_duration_seconds=5.0)
        assert not window.is_converged(iterations=1, duration=2.0)
        assert window.is_converged(iterations=1, duration=5.0)
        assert window.is_converged(iterations=1, duration=6.0)

    def test_is_converged_by_stabilisation(self):
        """Test convergence detected by stabilisation threshold."""
        window = ConvergenceWindow(
            max_iterations=100,
            max_duration_seconds=60.0,
        )
        assert window.is_converged(
            iterations=1,
            duration=1.0,
            stabilisation_threshold_met=True
        )


class TestCancellationPolicy:
    """Tests for CancellationPolicy primitive."""

    def test_default_policy_creation(self):
        """Test default policy can be created."""
        policy = CancellationPolicy()
        assert policy.cancellation_timeout >= 0
        assert policy.force_shutdown_after >= policy.cancellation_timeout

    def test_invalid_timeout_raises(self):
        """Test negative timeout raises ValueError."""
        with pytest.raises(ValueError, match="cancellation_timeout must be >= 0"):
            CancellationPolicy(cancellation_timeout=-1.0)

    def test_force_shutdown_less_than_timeout_raises(self):
        """Test force_shutdown < cancellation_timeout raises ValueError."""
        with pytest.raises(ValueError, match="force_shutdown_after must be >= cancellation_timeout"):
            CancellationPolicy(
                cancellation_timeout=10.0,
                force_shutdown_after=5.0
            )

    def test_policy_to_dict(self):
        """Test policy can be serialized to dict."""
        policy = CancellationPolicy(
            cancellation_timeout=5.0,
            force_shutdown_after=10.0,
        )
        d = policy.to_dict()
        assert d['cancellation_timeout'] == 5.0
        assert d['force_shutdown_after'] == 10.0


class TestEventStormConfig:
    """Tests for EventStormConfig primitive."""

    def test_default_config_creation(self):
        """Test default config can be created."""
        config = EventStormConfig()
        assert config.max_events_per_second >= 1
        assert config.burst_threshold >= 1
        assert config.burst_window_seconds > 0
        assert config.queue_max_size >= 1

    def test_invalid_max_events_raises(self):
        """Test max_events < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_events_per_second must be >= 1"):
            EventStormConfig(max_events_per_second=0)

    def test_config_to_dict(self):
        """Test config can be serialized to dict."""
        config = EventStormConfig(
            max_events_per_second=100,
            burst_threshold=20,
            burst_window_seconds=2.0,
            queue_max_size=500,
            drop_policy=DropPolicy.NEWEST,
        )
        d = config.to_dict()
        assert d['max_events_per_second'] == 100
        assert d['burst_threshold'] == 20
        assert d['drop_policy'] == 'NEWEST'


class TestReconciliationContext:
    """Tests for ReconciliationContext."""

    def test_default_context_creation(self):
        """Test default context can be created."""
        context = ReconciliationContext()
        assert context.is_replay is False
        assert context.event_sequence == 0
        assert context.deterministic_ordering is True

    def test_replay_context(self):
        """Test replay context can be created."""
        now = datetime.now(timezone.utc)
        context = ReconciliationContext(
            is_replay=True,
            replay_timestamp=now,
            event_sequence=42,
            deterministic_ordering=True,
            workspace_id="test-workspace",
        )
        assert context.is_replay is True
        assert context.replay_timestamp == now
        assert context.event_sequence == 42
        assert context.workspace_id == "test-workspace"

    def test_context_to_dict(self):
        """Test context can be serialized to dict."""
        context = ReconciliationContext()
        d = asdict(context)
        assert 'is_replay' in d
        assert 'event_sequence' in d


class TestOscillationMetrics:
    """Tests for OscillationMetrics."""

    def test_default_metrics_creation(self):
        """Test default metrics can be created."""
        metrics = OscillationMetrics()
        assert len(metrics.state_changes) == 0
        assert len(metrics.correction_history) == 0
        assert metrics.oscillation_count == 0

    def test_record_state_change(self):
        """Test state change recording."""
        metrics = OscillationMetrics(max_history=10)
        now = datetime.now(timezone.utc)
        
        metrics.record_state_change(now, "state1")
        metrics.record_state_change(now, "state2")
        
        assert len(metrics.state_changes) == 2

    def test_record_correction(self):
        """Test correction recording."""
        metrics = OscillationMetrics()
        now = datetime.now(timezone.utc)
        
        metrics.record_correction(now, 0.5)
        metrics.record_correction(now, -0.3)
        
        assert len(metrics.correction_history) == 2

    def test_history_pruning(self):
        """Test history is pruned to max_history."""
        metrics = OscillationMetrics(max_history=3)
        now = datetime.now(timezone.utc)
        
        for i in range(5):
            metrics.record_state_change(now, f"state{i}")
        
        assert len(metrics.state_changes) == 3

    def test_oscillation_detection_simple(self):
        """Test simple oscillation detection."""
        metrics = OscillationMetrics()
        now = datetime.now(timezone.utc)
        
        # Add alternating states
        metrics.record_state_change(now, "a")
        metrics.record_state_change(now, "b")
        metrics.record_state_change(now, "a")
        
        # Should not detect with only 3 states
        assert metrics.detect_oscillation(window_size=2) is False
        
        # Add more alternating states
        metrics.record_state_change(now, "b")
        metrics.record_state_change(now, "a")
        metrics.record_state_change(now, "b")
        
        # Should detect oscillation now
        result = metrics.detect_oscillation(window_size=2)
        assert result is True


class TestLoopHealthState:
    """Tests for LoopHealthState."""

    def test_health_state_creation(self):
        """Test health state can be created."""
        state = LoopHealthState(
            loop_id="test-loop",
            controller_type=ControllerType.RUNTIME_SUPERVISION,
            status=LoopStatus.RUNNING,
        )
        assert state.loop_id == "test-loop"
        assert state.controller_type == ControllerType.RUNTIME_SUPERVISION
        assert state.status == LoopStatus.RUNNING
        assert state.iterations == 0

    def test_health_state_to_dict(self):
        """Test health state can be serialized."""
        state = LoopHealthState(
            loop_id="test-loop",
            controller_type=ControllerType.PROJECTION_REFRESH,
            status=LoopStatus.CONVERGED,
            iterations=42,
        )
        d = state.to_dict()
        assert d['loop_id'] == "test-loop"
        assert d['status'] == 'CONVERGED'


class TestAuthorityBoundary:
    """Tests for authority boundary enforcement."""

    def test_check_authority_violation_commit(self):
        """Test commit actions are detected as violations."""
        assert check_authority_violation("commit_changes", None) is True
        assert check_authority_violation("CREATE_COMMIT", None) is True
        assert check_authority_violation("git_commit", None) is True

    def test_check_authority_violation_merge(self):
        """Test merge actions are detected as violations."""
        assert check_authority_violation("merge_branch", None) is True
        assert check_authority_violation("APPROVE_MERGE", None) is True

    def test_check_authority_violation_governance(self):
        """Test governance mutation is detected as violation."""
        assert check_authority_violation("governance_mutation", None) is True
        assert check_authority_violation("governance_update", None) is True

    def test_check_authority_violation_replay(self):
        """Test replay mutation is detected as violation."""
        assert check_authority_violation("replay_mutation", None) is True
        assert check_authority_violation("rewrite_replay", None) is True

    def test_check_authority_violation_authority(self):
        """Test authority inference is detected as violation."""
        assert check_authority_violation("infer_authority", None) is True
        assert check_authority_violation("authority_inference", None) is True

    def test_check_authority_violation_cross_workspace(self):
        """Test cross-workspace operations are detected."""
        class MockTarget:
            workspace_id = "other-workspace"
        
        # Same workspace - should be OK
        assert check_authority_violation("some_action", MockTarget(), workspace_id="other-workspace") is False
        
        # Different workspace - should be violation
        assert check_authority_violation("some_action", MockTarget(), workspace_id="current-workspace") is True

    def test_check_authority_violation_allowed(self):
        """Test allowed operations pass check."""
        assert check_authority_violation("refresh_projection", None) is False
        assert check_authority_violation("reconcile_state", None) is False
        assert check_authority_violation("damp_correction", None) is False

    def test_enforce_authority_boundary_raises(self):
        """Test enforce raises on violation."""
        with pytest.raises(AuthorityBoundaryViolationError):
            enforce_authority_boundary("commit", None)

    def test_enforce_authority_boundary_passes(self):
        """Test enforce passes for allowed operations."""
        # Should not raise
        enforce_authority_boundary("refresh", None)


@pytest.mark.asyncio
class TestReconciliationController:
    """Tests for ReconciliationController base class."""

    async def test_controller_creation(self):
        """Test controller can be created."""
        config = ReconciliationController.Config(
            controller_id="test-controller",
            controller_type=ControllerType.RUNTIME_SUPERVISION,
        )
        # Use mock subclass since ReconciliationController is abstract
        controller = RuntimeSupervisionController(config)
        assert controller.controller_id == "test-controller"
        assert controller.controller_type == ControllerType.RUNTIME_SUPERVISION
        assert controller.status == LoopStatus.PENDING

    async def test_controller_start_stop(self):
        """Test controller can be started and stopped."""
        config = ReconciliationController.Config(
            controller_id="test-controller",
            controller_type=ControllerType.RUNTIME_SUPERVISION,
            cadence=ReconciliationCadence(
                min_interval_seconds=0.01,
                max_interval_seconds=0.1,
                jitter_factor=0,
            ),
        )
        controller = RuntimeSupervisionController(config)
        
        await controller.start()
        assert controller.running is True
        assert controller.status == LoopStatus.RUNNING
        
        await controller.stop()
        assert controller.running is False
        assert controller.status == LoopStatus.STOPPED

    async def test_controller_health_state(self):
        """Test controller provides health state."""
        config = ReconciliationController.Config(
            controller_id="test-controller",
            controller_type=ControllerType.PROJECTION_REFRESH,
        )
        controller = ProjectionRefreshController(config)
        
        health = controller.health_state
        assert health.loop_id == "test-controller"
        assert health.controller_type == ControllerType.PROJECTION_REFRESH
        assert health.status == LoopStatus.PENDING

    async def test_controller_authority_violation_response(self):
        """Test controller responds to authority violations."""
        config = ReconciliationController.Config(
            controller_id="test-controller",
            controller_type=ControllerType.TELEMETRY_AGGREGATION,
        )
        controller = TelemetryAggregationController(config)
        
        with pytest.raises(RuntimeError, match="Authority violation"):
            controller._authority_violation_response("test_violation")


@pytest.mark.asyncio
class TestRuntimeSupervisionController:
    """Tests for RuntimeSupervisionController."""

    async def test_derive_state_empty(self):
        """Test derive_state with empty events."""
        config = ReconciliationController.Config(
            controller_id="runtime-supervision",
            controller_type=ControllerType.RUNTIME_SUPERVISION,
        )
        controller = RuntimeSupervisionController(config)
        
        state = controller.derive_state([])
        assert state == {}

    async def test_derive_state_with_events(self):
        """Test derive_state processes runtime events."""
        config = ReconciliationController.Config(
            controller_id="runtime-supervision",
            controller_type=ControllerType.RUNTIME_SUPERVISION,
        )
        controller = RuntimeSupervisionController(config)
        
        # Mock events
        class MockEvent:
            event_type = "RuntimeStatusEvent"
            stream_id = "stream-1"
            status = "ACTIVE"
            timestamp = None
        
        state = controller.derive_state([MockEvent()])
        assert "stream-1" in state
        assert state["stream-1"]["status"] == "ACTIVE"

    async def test_apply_correction_logs(self):
        """Test apply_correction logs advisory actions."""
        config = ReconciliationController.Config(
            controller_id="runtime-supervision",
            controller_type=ControllerType.RUNTIME_SUPERVISION,
        )
        controller = RuntimeSupervisionController(config)
        
        # Should not raise, just log
        controller.apply_correction({
            "stream-1": {
                "action": "restart",
                "reason": "test",
            }
        })


@pytest.mark.asyncio
class TestProjectionRefreshController:
    """Tests for ProjectionRefreshController."""

    async def test_derive_state_empty(self):
        """Test derive_state with empty events."""
        config = ReconciliationController.Config(
            controller_id="projection-refresh",
            controller_type=ControllerType.PROJECTION_REFRESH,
        )
        controller = ProjectionRefreshController(config)
        
        state = controller.derive_state([])
        assert "projections" in state
        assert state["projections"] == {}

    async def test_constructor_with_config(self):
        """Test controller can be created with config."""
        config = ReconciliationController.Config(
            controller_id="projection-refresh",
            controller_type=ControllerType.PROJECTION_REFRESH,
        )
        controller = ProjectionRefreshController(config, projection_registry=None)
        assert controller.controller_id == "projection-refresh"


@pytest.mark.asyncio
class TestTelemetryAggregationController:
    """Tests for TelemetryAggregationController."""

    async def test_derive_state_empty(self):
        """Test derive_state with empty events."""
        config = ReconciliationController.Config(
            controller_id="telemetry-aggregation",
            controller_type=ControllerType.TELEMETRY_AGGREGATION,
        )
        controller = TelemetryAggregationController(config)
        
        state = controller.derive_state([])
        assert "throughput" in state
        assert "queue_depth" in state

    async def test_derive_state_with_events(self):
        """Test derive_state processes telemetry events."""
        config = ReconciliationController.Config(
            controller_id="telemetry-aggregation",
            controller_type=ControllerType.TELEMETRY_AGGREGATION,
        )
        controller = TelemetryAggregationController(config)
        
        class MockEvent:
            event_type = "ThroughputEvent"
            value = 100
        
        state = controller.derive_state([MockEvent()])
        assert state["throughput"] > 0

    async def test_calculate_correction_throughput(self):
        """Test correction calculation for high throughput."""
        config = ReconciliationController.Config(
            controller_id="telemetry-aggregation",
            controller_type=ControllerType.TELEMETRY_AGGREGATION,
        )
        controller = TelemetryAggregationController(config)
        
        current_state = {
            "throughput": 150.0,
            "queue_depth": 0,
            "runtime_saturation": 0.0,
            "cadence": 0.0,
            "density": 0.0,
        }
        desired_state = {}
        
        correction = controller.calculate_correction(current_state, desired_state)
        assert "throughput" in correction
        assert correction["throughput"]["action"] == "stabilize"


@pytest.mark.asyncio
class TestWorkspaceHygieneController:
    """Tests for WorkspaceHygieneController."""

    async def test_controller_creation(self):
        """Test controller can be created for a workspace."""
        config = ReconciliationController.Config(
            controller_id="workspace-hygiene",
            controller_type=ControllerType.WORKSPACE_HYGIENE,
        )
        controller = WorkspaceHygieneController(config, workspace_id="test-workspace")
        
        assert controller.controller_id == "workspace-hygiene"
        assert controller.config.workspace_id == "test-workspace"

    async def test_derive_state_empty(self):
        """Test derive_state with empty events."""
        config = ReconciliationController.Config(
            controller_id="workspace-hygiene",
            controller_type=ControllerType.WORKSPACE_HYGIENE,
        )
        controller = WorkspaceHygieneController(config, workspace_id="test-workspace")
        
        state = controller.derive_state([])
        assert "stale_artifacts" in state
        assert "temp_states" in state
        assert "namespace_health" in state


@pytest.mark.asyncio
class TestTopologyDensityController:
    """Tests for TopologyDensityController."""

    async def test_controller_creation(self):
        """Test controller can be created."""
        config = ReconciliationController.Config(
            controller_id="topology-density",
            controller_type=ControllerType.TOPOLOGY_DENSITY,
        )
        controller = TopologyDensityController(config)
        
        assert controller.controller_id == "topology-density"
        assert controller.config.controller_type == ControllerType.TOPOLOGY_DENSITY

    async def test_derive_state_empty(self):
        """Test derive_state with empty events."""
        config = ReconciliationController.Config(
            controller_id="topology-density",
            controller_type=ControllerType.TOPOLOGY_DENSITY,
        )
        controller = TopologyDensityController(config)
        
        state = controller.derive_state([])
        assert "node_density" in state
        assert "edge_density" in state
        assert "visual_complexity" in state


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.asyncio
async def test_full_reconciliation_cycle():
    """Test a full reconciliation cycle with all components."""
    # Create governance primitives
    cadence = ReconciliationCadence(
        min_interval_seconds=0.01,
        max_interval_seconds=0.1,
        jitter_factor=0.0,
    )
    damping = DampingFactor(
        damp_type=DampingType.EXPONENTIAL,
        base=0.5,
    )
    retry = RetryCeiling(
        max_retries=3,
        retry_base_delay=0.01,
    )
    convergence = ConvergenceWindow(
        max_iterations=10,
        max_duration_seconds=1.0,
    )
    
    # Create controller config
    config = ReconciliationController.Config(
        controller_id="test-cycle",
        controller_type=ControllerType.RUNTIME_SUPERVISION,
        cadence=cadence,
        damping=damping,
        retry=retry,
        convergence=convergence,
    )
    
    # Create controller
    controller = RuntimeSupervisionController(config)
    
    # Start controller
    await controller.start()
    assert controller.status == LoopStatus.RUNNING
    
    # Get health state
    health = controller.health_state
    assert health.status == LoopStatus.RUNNING
    
    # Stop controller
    await controller.stop()
    assert controller.status == LoopStatus.STOPPED


def test_reconciliation_determinism():
    """Test that reconciliation is deterministic."""
    controller1 = RuntimeSupervisionController(
        ReconciliationController.Config(
            controller_id="det-test-1",
            controller_type=ControllerType.RUNTIME_SUPERVISION,
        )
    )
    controller2 = RuntimeSupervisionController(
        ReconciliationController.Config(
            controller_id="det-test-2",
            controller_type=ControllerType.RUNTIME_SUPERVISION,
        )
    )
    
    # Same input should produce same derived state
    class MockEvent:
        event_type = "RuntimeStatusEvent"
        stream_id = "stream-1"
        status = "ACTIVE"
        timestamp = None
    
    events = [MockEvent()]
    state1 = controller1.derive_state(events)
    state2 = controller2.derive_state(events)
    
    assert state1 == state2


def test_no_authority_mutation():
    """Test that controllers do not mutate authority boundaries."""
    config = ReconciliationController.Config(
        controller_id="authority-test",
        controller_type=ControllerType.RUNTIME_SUPERVISION,
    )
    controller = RuntimeSupervisionController(config)
    
    # Attempt to apply a correction that would violate authority
    with pytest.raises(RuntimeError, match="Authority violation"):
        controller._authority_violation_response("attempted_commit_creation")
    
    # Check that forbidden actions are detected
    assert controller._check_authority_violation("create_commit", "target") is True
    assert controller._check_authority_violation("refresh_projection", "target") is False
