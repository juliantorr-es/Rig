"""Tests for Reconciliation Governance Primitives (PHASE 4 & 9).

This module validates:
- Deterministic primitives
- Bounded primitives
- Replay-safe primitives
- Observable primitives
- Topology-visible primitives

file: tests/test_reconciliation_governance.py
"""

import pytest
from dataclasses import asdict
from datetime import datetime, timezone

from rig.domain.reconciliation_governance import (
    # Schema
    SCHEMA_VERSION,
    # Enums
    DampingType,
    RetryBackoffType,
    DropPolicy,
    LoopStatus,
    # Primitives
    ReconciliationCadence,
    DampingFactor,
    RetryCeiling,
    ConvergenceWindow,
    CancellationPolicy,
    EventStormConfig,
    # Health and Info
    ConvergenceInfo,
    DampingInfo,
    RetryInfo,
    LoopHealthState,
    ReconciliationContext,
    # Authority
    AuthorityBoundaryViolationError,
    check_authority_violation,
    enforce_authority_boundary,
    # Constants
    DEFAULT_MIN_INTERVAL_SECONDS,
    DEFAULT_MAX_INTERVAL_SECONDS,
    DEFAULT_JITTER_FACTOR,
    DEFAULT_DAMP_BASE,
    DEFAULT_DAMP_RATE,
    DEFAULT_DAMP_THRESHOLD,
    DEFAULT_DAMP_MIN_FACTOR,
    DEFAULT_DAMP_MAX_FACTOR,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_BASE_DELAY,
    DEFAULT_RETRY_MAX_DELAY,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_DURATION_SECONDS,
    DEFAULT_STABILISATION_THRESHOLD,
    DEFAULT_STABILISATION_WINDOW_SECONDS,
    DEFAULT_MAX_EVENTS_PER_SECOND,
    DEFAULT_BURST_THRESHOLD,
    DEFAULT_BURST_WINDOW_SECONDS,
    DEFAULT_QUEUE_MAX_SIZE,
    DEFAULT_CANCELLATION_TIMEOUT,
    DEFAULT_FORCE_SHUTDOWN_AFTER,
)


class TestConstants:
    """Tests for module constants."""

    def test_schema_version(self):
        """Test schema version is defined."""
        assert SCHEMA_VERSION == "rig.reconciliation_governance.v1"

    def test_default_values_are_valid(self):
        """Test all default values are valid."""
        # Cadence
        assert DEFAULT_MIN_INTERVAL_SECONDS == 0.1
        assert DEFAULT_MAX_INTERVAL_SECONDS == 10.0
        assert DEFAULT_JITTER_FACTOR == 0.1

        # Damping
        assert DEFAULT_DAMP_BASE == 0.5
        assert DEFAULT_DAMP_RATE == 0.1
        assert DEFAULT_DAMP_THRESHOLD == 0.01
        assert DEFAULT_DAMP_MIN_FACTOR == 0.01
        assert DEFAULT_DAMP_MAX_FACTOR == 1.0

        # Retry
        assert DEFAULT_MAX_RETRIES == 5
        assert DEFAULT_RETRY_BASE_DELAY == 0.1
        assert DEFAULT_RETRY_MAX_DELAY == 10.0

        # Convergence
        assert DEFAULT_MAX_ITERATIONS == 100
        assert DEFAULT_MAX_DURATION_SECONDS == 60.0
        assert DEFAULT_STABILISATION_THRESHOLD == 0.001
        assert DEFAULT_STABILISATION_WINDOW_SECONDS == 2.0

        # Event storm
        assert DEFAULT_MAX_EVENTS_PER_SECOND == 100
        assert DEFAULT_BURST_THRESHOLD == 50
        assert DEFAULT_BURST_WINDOW_SECONDS == 1.0
        assert DEFAULT_QUEUE_MAX_SIZE == 1000

        # Cancellation
        assert DEFAULT_CANCELLATION_TIMEOUT == 5.0
        assert DEFAULT_FORCE_SHUTDOWN_AFTER == 10.0


class TestReconciliationCadence:
    """Tests for ReconciliationCadence primitive."""

    def test_default_creation(self):
        """Test default cadence can be created."""
        cadence = ReconciliationCadence()
        assert cadence.min_interval_seconds == DEFAULT_MIN_INTERVAL_SECONDS
        assert cadence.max_interval_seconds == DEFAULT_MAX_INTERVAL_SECONDS
        assert cadence.jitter_factor == DEFAULT_JITTER_FACTOR

    def test_custom_creation(self):
        """Test custom cadence can be created."""
        cadence = ReconciliationCadence(
            min_interval_seconds=0.5,
            max_interval_seconds=5.0,
            jitter_factor=0.2,
        )
        assert cadence.min_interval_seconds == 0.5
        assert cadence.max_interval_seconds == 5.0
        assert cadence.jitter_factor == 0.2

    def test_validation_min_interval(self):
        """Test negative min_interval raises ValueError."""
        with pytest.raises(ValueError, match="min_interval_seconds must be >= 0"):
            ReconciliationCadence(min_interval_seconds=-0.1)

    def test_validation_max_less_than_min(self):
        """Test max < min raises ValueError."""
        with pytest.raises(ValueError, match="max_interval_seconds must be >= min_interval_seconds"):
            ReconciliationCadence(min_interval_seconds=5.0, max_interval_seconds=1.0)

    def test_validation_jitter_range(self):
        """Test jitter outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="jitter_factor must be in"):
            ReconciliationCadence(jitter_factor=-0.1)
        with pytest.raises(ValueError, match="jitter_factor must be in"):
            ReconciliationCadence(jitter_factor=1.5)

    def test_calculate_next_interval_in_bounds(self):
        """Test interval calculation respects bounds."""
        cadence = ReconciliationCadence(
            min_interval_seconds=1.0,
            max_interval_seconds=10.0,
            jitter_factor=0.0,
        )
        for _ in range(100):
            interval = cadence.calculate_next_interval()
            assert 1.0 <= interval <= 10.0

    def test_calculate_next_interval_with_jitter_seed(self):
        """Test deterministic interval with seed."""
        cadence = ReconciliationCadence(
            min_interval_seconds=1.0,
            max_interval_seconds=10.0,
            jitter_factor=0.5,
        )
        # Same seed should produce same result
        interval1 = cadence.calculate_next_interval(jitter_seed=42)
        interval2 = cadence.calculate_next_interval(jitter_seed=42)
        assert interval1 == interval2

    def test_to_dict(self):
        """Test serialization to dict."""
        cadence = ReconciliationCadence(
            min_interval_seconds=0.5,
            max_interval_seconds=5.0,
            jitter_factor=0.2,
        )
        d = cadence.to_dict()
        assert d['min_interval_seconds'] == 0.5
        assert d['max_interval_seconds'] == 5.0
        assert d['jitter_factor'] == 0.2


class TestDampingFactor:
    """Tests for DampingFactor primitive."""

    def test_default_creation(self):
        """Test default damping can be created."""
        damping = DampingFactor()
        assert damping.damp_type == DampingType.EXPONENTIAL
        assert damping.base == DEFAULT_DAMP_BASE
        assert damping.rate == DEFAULT_DAMP_RATE
        assert damping.threshold == DEFAULT_DAMP_THRESHOLD
        assert damping.min_factor == DEFAULT_DAMP_MIN_FACTOR
        assert damping.max_factor == DEFAULT_DAMP_MAX_FACTOR

    def test_validation_base(self):
        """Test invalid base raises ValueError."""
        with pytest.raises(ValueError, match="base must be in"):
            DampingFactor(base=0.0)
        with pytest.raises(ValueError, match="base must be in"):
            DampingFactor(base=1.5)

    def test_validation_rate(self):
        """Test invalid rate raises ValueError."""
        with pytest.raises(ValueError, match="rate must be in"):
            DampingFactor(rate=0.0)
        with pytest.raises(ValueError, match="rate must be in"):
            DampingFactor(rate=1.5)

    def test_validation_threshold(self):
        """Test negative threshold raises ValueError."""
        with pytest.raises(ValueError, match="threshold must be >= 0"):
            DampingFactor(threshold=-0.1)

    def test_validation_factor_bounds(self):
        """Test invalid min/max factor raises ValueError."""
        with pytest.raises(ValueError, match="min_factor <= max_factor must be in"):
            DampingFactor(min_factor=0.2, max_factor=0.1)

    def test_exponential_damping(self):
        """Test exponential damping behavior."""
        damping = DampingFactor(
            damp_type=DampingType.EXPONENTIAL,
            base=0.5,
            min_factor=0.01,
            max_factor=1.0,
        )
        # Iteration 0: base^0 = 1.0, but min_factor clamps to 0.01
        # Actually: factor = base^iteration, value = factor * current_value
        # With current_value=1.0, iteration=0: factor = 0.5^0 = 1.0, clamped to [0.01, 1.0] = 1.0
        result0 = damping.apply(0, 1.0)
        # iteration=1: factor = 0.5^1 = 0.5
        result1 = damping.apply(1, 1.0)
        # iteration=2: factor = 0.5^2 = 0.25
        result2 = damping.apply(2, 1.0)
        
        assert result0 == 1.0  # base^0 = 1, clamped = 1
        assert result1 == 0.5  # base^1 * 1 = 0.5
        assert result2 == 0.25  # base^2 * 1 = 0.25

    def test_linear_damping(self):
        """Test linear damping behavior."""
        damping = DampingFactor(
            damp_type=DampingType.LINEAR,
            rate=0.2,
            min_factor=0.0,
            max_factor=1.0,
        )
        # factor = max(0, 1 - rate * iteration)
        assert damping.apply(0, 1.0) == 1.0  # max(0, 1 - 0.2 * 0) = 1.0
        assert damping.apply(1, 1.0) == 0.8  # max(0, 1 - 0.2 * 1) = 0.8
        assert damping.apply(5, 1.0) == 0.01  # max(0, 1 - 0.2 * 5) = 0, clamped to 0.01

    def test_threshold_damping_below(self):
        """Test threshold damping returns 0 for values below threshold."""
        damping = DampingFactor(
            damp_type=DampingType.THRESHOLD,
            threshold=0.5,
        )
        assert damping.apply(0, 0.1) == 0.0  # 0.1 < 0.5
        assert damping.apply(0, 0.4) == 0.0  # 0.4 < 0.5

    def test_threshold_damping_above(self):
        """Test threshold damping returns value for values above threshold."""
        damping = DampingFactor(
            damp_type=DampingType.THRESHOLD,
            threshold=0.5,
        )
        assert damping.apply(0, 0.5) == 0.5
        assert damping.apply(0, 1.0) == 1.0

    def test_hysteresis_damping_positive(self):
        """Test hysteresis damping with positive values."""
        damping = DampingFactor(
            damp_type=DampingType.HYSTERESIS,
            base=0.5,
        )
        result = damping.apply(0, 1.0)
        # For positive current_value: factor = base
        assert result == 0.5

    def test_hysteresis_damping_negative(self):
        """Test hysteresis damping with negative values."""
        damping = DampingFactor(
            damp_type=DampingType.HYSTERESIS,
            base=0.5,
        )
        result = damping.apply(0, -1.0)
        # For negative current_value: factor = 1/base
        assert result == 2.0

    def test_damping_clamping(self):
        """Test damping respects min/max bounds."""
        damping = DampingFactor(
            damp_type=DampingType.EXPONENTIAL,
            base=0.5,
            min_factor=0.1,
            max_factor=0.9,
        )
        result = damping.apply(1000, 1.0)
        assert 0.1 <= result <= 0.9


class TestRetryCeiling:
    """Tests for RetryCeiling primitive."""

    def test_default_creation(self):
        """Test default retry can be created."""
        retry = RetryCeiling()
        assert retry.max_retries == DEFAULT_MAX_RETRIES
        assert retry.retry_base_delay == DEFAULT_RETRY_BASE_DELAY
        assert retry.retry_max_delay == DEFAULT_RETRY_MAX_DELAY
        assert retry.retry_backoff_type == RetryBackoffType.EXPONENTIAL
        assert "timeout" in retry.retryable_errors
        assert "network_error" in retry.retryable_errors

    def test_validation_max_retries(self):
        """Test negative max_retries raises ValueError."""
        with pytest.raises(ValueError, match="max_retries must be >= 0"):
            RetryCeiling(max_retries=-1)

    def test_validation_base_delay(self):
        """Test negative base_delay raises ValueError."""
        with pytest.raises(ValueError, match="retry_base_delay must be >= 0"):
            RetryCeiling(retry_base_delay=-0.1)

    def test_validation_max_delay_less_than_base(self):
        """Test max_delay < base_delay raises ValueError."""
        with pytest.raises(ValueError, match="retry_max_delay must be >= retry_base_delay"):
            RetryCeiling(retry_base_delay=1.0, retry_max_delay=0.5)

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        retry = RetryCeiling(
            max_retries=10,
            retry_base_delay=0.1,
            retry_max_delay=10.0,
            retry_backoff_type=RetryBackoffType.EXPONENTIAL,
        )
        assert retry.calculate_delay(0) == 0.1
        assert retry.calculate_delay(1) == 0.2
        assert retry.calculate_delay(2) == 0.4
        assert retry.calculate_delay(3) == 0.8
        assert retry.calculate_delay(4) == 1.6
        # Capped at max_delay
        assert retry.calculate_delay(10) == 10.0

    def test_linear_backoff(self):
        """Test linear backoff calculation."""
        retry = RetryCeiling(
            max_retries=10,
            retry_base_delay=0.1,
            retry_max_delay=10.0,
            retry_backoff_type=RetryBackoffType.LINEAR,
        )
        assert retry.calculate_delay(0) == 0.1
        assert retry.calculate_delay(1) == 0.2
        assert retry.calculate_delay(2) == 0.3
        assert retry.calculate_delay(9) == 1.0

    def test_constant_backoff(self):
        """Test constant backoff calculation."""
        retry = RetryCeiling(
            max_retries=10,
            retry_base_delay=0.5,
            retry_max_delay=10.0,
            retry_backoff_type=RetryBackoffType.CONSTANT,
        )
        assert retry.calculate_delay(0) == 0.5
        assert retry.calculate_delay(5) == 0.5
        assert retry.calculate_delay(100) == 0.5

    def test_is_retryable_transient_errors(self):
        """Test transient errors are retryable."""
        retry = RetryCeiling()
        assert retry.is_retryable("timeout") is True
        assert retry.is_retryable("network_error") is True
        assert retry.is_retryable("resource_unavailable") is True
        assert retry.is_retryable("rate_limited") is True
        assert retry.is_retryable("model_unavailable") is True

    def test_is_retryable_permanent_errors(self):
        """Test permanent errors are NOT retryable."""
        retry = RetryCeiling()
        assert retry.is_retryable("authority_violation") is False
        assert retry.is_retryable("bounds_violation") is False
        assert retry.is_retryable("replay_conflict") is False
        assert retry.is_retryable("convergence_timeout") is False

    def test_is_retryable_case_insensitive(self):
        """Test retryable check is case insensitive."""
        retry = RetryCeiling()
        assert retry.is_retryable("TIMEOUT") is True
        assert retry.is_retryable("Timeout") is True
        assert retry.is_retryable("timeOut") is True

    def test_to_dict(self):
        """Test serialization to dict."""
        retry = RetryCeiling(
            max_retries=3,
            retry_base_delay=0.5,
            retry_max_delay=5.0,
        )
        d = retry.to_dict()
        assert d['max_retries'] == 3
        assert d['retry_base_delay'] == 0.5
        assert d['retryable_errors'] == list(retry.retryable_errors)


class TestConvergenceWindow:
    """Tests for ConvergenceWindow primitive."""

    def test_default_creation(self):
        """Test default window can be created."""
        window = ConvergenceWindow()
        assert window.max_iterations == DEFAULT_MAX_ITERATIONS
        assert window.max_duration_seconds == DEFAULT_MAX_DURATION_SECONDS
        assert window.stabilisation_threshold == DEFAULT_STABILISATION_THRESHOLD
        assert window.stabilisation_window == DEFAULT_STABILISATION_WINDOW_SECONDS

    def test_validation_max_iterations(self):
        """Test max_iterations < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_iterations must be >= 1"):
            ConvergenceWindow(max_iterations=0)

    def test_validation_duration(self):
        """Test max_duration <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="max_duration_seconds must be > 0"):
            ConvergenceWindow(max_duration_seconds=0)

    def test_validation_stabilisation_threshold(self):
        """Test negative stabilisation_threshold raises ValueError."""
        with pytest.raises(ValueError, match="stabilisation_threshold must be >= 0"):
            ConvergenceWindow(stabilisation_threshold=-0.1)

    def test_validation_stabilisation_window(self):
        """Test stabilisation_window <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="stabilisation_window must be > 0"):
            ConvergenceWindow(stabilisation_window=0)

    def test_is_converged_by_iterations(self):
        """Test convergence by max iterations."""
        window = ConvergenceWindow(max_iterations=10)
        assert window.is_converged(iterations=5, duration=1.0) is False
        assert window.is_converged(iterations=10, duration=1.0) is True
        assert window.is_converged(iterations=11, duration=1.0) is True

    def test_is_converged_by_duration(self):
        """Test convergence by max duration."""
        window = ConvergenceWindow(max_duration_seconds=5.0)
        assert window.is_converged(iterations=1, duration=2.0) is False
        assert window.is_converged(iterations=1, duration=5.0) is True
        assert window.is_converged(iterations=1, duration=6.0) is True

    def test_is_converged_by_stabilisation(self):
        """Test convergence by stabilisation threshold."""
        window = ConvergenceWindow(
            max_iterations=100,
            max_duration_seconds=60.0,
        )
        assert window.is_converged(
            iterations=50,
            duration=10.0,
            stabilisation_threshold_met=True
        ) is True

    def test_is_converged_not_by_timeout_or_iterations(self):
        """Test not converged when neither condition met."""
        window = ConvergenceWindow(
            max_iterations=100,
            max_duration_seconds=60.0,
        )
        assert window.is_converged(
            iterations=50,
            duration=30.0,
            stabilisation_threshold_met=False
        ) is False

    def test_to_dict(self):
        """Test serialization to dict."""
        window = ConvergenceWindow(
            max_iterations=50,
            max_duration_seconds=30.0,
        )
        d = window.to_dict()
        assert d['max_iterations'] == 50
        assert d['max_duration_seconds'] == 30.0


class TestCancellationPolicy:
    """Tests for CancellationPolicy primitive."""

    def test_default_creation(self):
        """Test default policy can be created."""
        policy = CancellationPolicy()
        assert policy.cancellation_timeout == DEFAULT_CANCELLATION_TIMEOUT
        assert policy.force_shutdown_after == DEFAULT_FORCE_SHUTDOWN_AFTER

    def test_validation_cancellation_timeout(self):
        """Test negative cancellation_timeout raises ValueError."""
        with pytest.raises(ValueError, match="cancellation_timeout must be >= 0"):
            CancellationPolicy(cancellation_timeout=-1.0)

    def test_validation_force_shutdown(self):
        """Test force_shutdown < cancellation_timeout raises ValueError."""
        with pytest.raises(ValueError, match="force_shutdown_after must be >= cancellation_timeout"):
            CancellationPolicy(
                cancellation_timeout=10.0,
                force_shutdown_after=5.0
            )

    def test_to_dict(self):
        """Test serialization to dict."""
        policy = CancellationPolicy(
            cancellation_timeout=2.0,
            force_shutdown_after=5.0,
            cleanup_hook_keys=["hook1", "hook2"],
        )
        d = policy.to_dict()
        assert d['cancellation_timeout'] == 2.0
        assert d['force_shutdown_after'] == 5.0


class TestEventStormConfig:
    """Tests for EventStormConfig primitive."""

    def test_default_creation(self):
        """Test default config can be created."""
        config = EventStormConfig()
        assert config.max_events_per_second == DEFAULT_MAX_EVENTS_PER_SECOND
        assert config.burst_threshold == DEFAULT_BURST_THRESHOLD
        assert config.burst_window_seconds == DEFAULT_BURST_WINDOW_SECONDS
        assert config.queue_max_size == DEFAULT_QUEUE_MAX_SIZE
        assert config.drop_policy == DropPolicy.NEWEST

    def test_validation_max_events(self):
        """Test max_events < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_events_per_second must be >= 1"):
            EventStormConfig(max_events_per_second=0)

    def test_validation_burst_threshold(self):
        """Test burst_threshold < 1 raises ValueError."""
        with pytest.raises(ValueError, match="burst_threshold must be >= 1"):
            EventStormConfig(burst_threshold=0)

    def test_validation_burst_window(self):
        """Test burst_window <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="burst_window_seconds must be > 0"):
            EventStormConfig(burst_window_seconds=0)

    def test_validation_queue_size(self):
        """Test queue_max_size < 1 raises ValueError."""
        with pytest.raises(ValueError, match="queue_max_size must be >= 1"):
            EventStormConfig(queue_max_size=0)

    def test_drop_policy_values(self):
        """Test all drop policy values work."""
        for policy in [DropPolicy.NEWEST, DropPolicy.OLDEST, DropPolicy.RANDOM]:
            config = EventStormConfig(drop_policy=policy)
            assert config.drop_policy == policy


class TestLoopHealthState:
    """Tests for LoopHealthState."""

    def test_creation(self):
        """Test health state can be created."""
        state = LoopHealthState(
            loop_id="test-loop",
            controller_type="runtime_supervision",
            status=LoopStatus.RUNNING,
            iterations=10,
            last_iteration_time=datetime.now(timezone.utc),
            last_error="test error",
        )
        assert state.loop_id == "test-loop"
        assert state.controller_type == "runtime_supervision"
        assert state.status == LoopStatus.RUNNING
        assert state.iterations == 10

    def test_to_dict_simple(self):
        """Test simple serialization."""
        state = LoopHealthState(
            loop_id="test",
            controller_type="test_type",
            status=LoopStatus.PENDING,
        )
        d = state.to_dict()
        assert d['loop_id'] == "test"
        assert d['controller_type'] == "test_type"
        assert d['status'] == 'PENDING'

    def test_to_dict_with_nested(self):
        """Test serialization with nested objects."""
        convergence = ConvergenceInfo(
            current_iteration=5,
            total_iterations=10,
            current_duration=1.0,
            max_duration=10.0,
            stabilisation_threshold=0.001,
            converged=True,
        )
        damping = DampingInfo(
            current_factor=0.5,
            damp_type=DampingType.EXPONENTIAL,
            iterations_applied=5,
            oscillation_detected=False,
        )
        retry = RetryInfo(
            retry_count=2,
            total_retries=5,
            last_error="timeout",
            next_delay=0.5,
        )
        
        state = LoopHealthState(
            loop_id="test",
            controller_type="test",
            status=LoopStatus.RUNNING,
            convergence_info=convergence,
            damping_info=damping,
            retry_info=retry,
        )
        
        d = state.to_dict()
        assert 'convergence_info' in d
        assert d['convergence_info']['current_iteration'] == 5
        assert 'damping_info' in d
        assert 'retry_info' in d


class TestReconciliationContext:
    """Tests for ReconciliationContext."""

    def test_default_creation(self):
        """Test default context can be created."""
        context = ReconciliationContext()
        assert context.is_replay is False
        assert context.replay_timestamp is None
        assert context.event_sequence == 0
        assert context.deterministic_ordering is True
        assert context.workspace_id is None

    def test_replay_context(self):
        """Test replay context."""
        now = datetime.now(timezone.utc)
        context = ReconciliationContext(
            is_replay=True,
            replay_timestamp=now,
            event_sequence=42,
            deterministic_ordering=True,
            workspace_id="workspace-1",
        )
        assert context.is_replay is True
        assert context.replay_timestamp == now
        assert context.event_sequence == 42
        assert context.workspace_id == "workspace-1"

    def test_to_dict(self):
        """Test serialization."""
        now = datetime.now(timezone.utc)
        context = ReconciliationContext(
            is_replay=True,
            replay_timestamp=now,
            event_sequence=100,
            workspace_id="ws-1",
        )
        d = asdict(context)
        assert d['is_replay'] is True
        assert d['event_sequence'] == 100
        assert d['workspace_id'] == "ws-1"


class TestAuthorityBoundary:
    """Tests for authority boundary enforcement."""

    def test_check_authority_violation_forbidden_actions(self):
        """Test forbidden actions are detected."""
        forbidden = [
            "commit", "merge", "approve", "publish", "authorize",
            "governance_mutation", "replay_mutation", "authority_inference",
            "schema_migration", "finalize", "snapshot",
        ]
        for action in forbidden:
            assert check_authority_violation(action, None) is True
            assert check_authority_violation(f"test_{action}", None) is True
            assert check_authority_violation(f"{action}_test", None) is True

    def test_check_authority_violation_allowed_actions(self):
        """Test allowed actions pass."""
        allowed = [
            "refresh", "reconcile", "damp", "stabilize", "cool",
            "prune", "simplify", "flatten", "verify", "clean",
        ]
        for action in allowed:
            assert check_authority_violation(action, None) is False

    def test_check_authority_violation_cross_workspace(self):
        """Test cross-workspace violations are detected."""
        class MockTarget:
            workspace_id = "other"
        
        # Same workspace - OK
        assert check_authority_violation("test", MockTarget(), workspace_id="other") is False
        
        # Different workspace - violation
        assert check_authority_violation("test", MockTarget(), workspace_id="current") is True

    def test_check_authority_violation_with_custom_patterns(self):
        """Test custom forbidden patterns."""
        assert check_authority_violation(
            "custom_action",
            None,
            forbidden_patterns={"custom"}
        ) is True
        
        assert check_authority_violation(
            "normal_action",
            None,
            forbidden_patterns={"custom"}
        ) is False

    def test_check_authority_violation_with_allowed_patterns(self):
        """Test allowed patterns override."""
        assert check_authority_violation(
            "commit",
            None,
            allowed_patterns={"commit"},
            forbidden_patterns=set(),  # Empty forbidden
        ) is True  # Not in allowed_patterns
        
        assert check_authority_violation(
            "commit",
            None,
            allowed_patterns={"commit", "other"},
            forbidden_patterns=set(),
        ) is False  # In allowed_patterns

    def test_enforce_authority_boundary_raises(self):
        """Test enforce raises on violation."""
        with pytest.raises(AuthorityBoundaryViolationError):
            enforce_authority_boundary("commit", None)
        
        with pytest.raises(AuthorityBoundaryViolationError):
            enforce_authority_boundary("merge", None, workspace_id="ws1")

    def test_enforce_authority_boundary_passes(self):
        """Test enforce passes for allowed operations."""
        # Should not raise
        enforce_authority_boundary("refresh", None)
        enforce_authority_boundary("reconcile", None, workspace_id="ws1")


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterministicBehavior:
    """Tests to verify deterministic behavior of primitives."""

    def test_cadence_deterministic_with_seed(self):
        """Test cadence with seed is deterministic."""
        cadence = ReconciliationCadence(
            min_interval_seconds=1.0,
            max_interval_seconds=10.0,
            jitter_factor=0.5,
        )
        intervals = [cadence.calculate_next_interval(jitter_seed=42) for _ in range(5)]
        # All should be the same with same seed
        assert all(i == intervals[0] for i in intervals)

    def test_damping_deterministic(self):
        """Test damping is deterministic."""
        damping = DampingFactor(
            damp_type=DampingType.EXPONENTIAL,
            base=0.5,
        )
        results = [damping.apply(i, 1.0) for i in range(10)]
        # Same inputs should produce same outputs
        results2 = [damping.apply(i, 1.0) for i in range(10)]
        assert results == results2

    def test_retry_deterministic(self):
        """Test retry is deterministic."""
        retry = RetryCeiling(
            max_retries=10,
            retry_base_delay=0.1,
            retry_backoff_type=RetryBackoffType.EXPONENTIAL,
        )
        results = [retry.calculate_delay(i) for i in range(10)]
        results2 = [retry.calculate_delay(i) for i in range(10)]
        assert results == results2

    def test_convergence_deterministic(self):
        """Test convergence detection is deterministic."""
        window = ConvergenceWindow(
            max_iterations=100,
            max_duration_seconds=60.0,
        )
        result1 = window.is_converged(iterations=50, duration=30.0)
        result2 = window.is_converged(iterations=50, duration=30.0)
        assert result1 == result2
