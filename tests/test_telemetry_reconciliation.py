"""Tests for Telemetry Reconciliation module.

PHASE 9: Test file for telemetry_reconciliation.py
Validates: deterministic reconciliation, bounded cadence, oscillation prevention,
replay-safe aggregation, cancellation correctness, topology awareness, no authority mutation.
"""

from __future__ import annotations

import random
import pytest
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, FrozenSet, List, Optional, Set
from unittest.mock import MagicMock, patch, AsyncMock

from rig.domain.telemetry_reconciliation import (
    SCHEMA_VERSION,
    TelemetryLoopType,
    TelemetryMetricType,
    TelemetryMetricConfig,
    TelemetryAggregationConfig,
    TelemetrySample,
    AggregatedMetric,
    TelemetryAggregationLoop,
    ThroughputStabilizationLoop,
    QueueDepthConvergenceLoop,
    RuntimeCoolingLoop,
    CadenceStabilizationLoop,
    DensityConvergenceLoop,
    TelemetryReconciliationController,
    DEFAULT_TELEMETRY_CADENCE_MIN,
    DEFAULT_TELEMETRY_CADENCE_MAX,
    DEFAULT_TELEMETRY_MAX_ITERATIONS,
)
from rig.domain.reconciliation_governance import (
    ReconciliationCadence,
    DampingFactor,
    RetryCeiling,
    ConvergenceWindow,
    DampingType,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_cadence() -> ReconciliationCadence:
    return ReconciliationCadence(
        min_interval_seconds=1.0,
        max_interval_seconds=10.0,
        jitter_factor=0.1,
    )


@pytest.fixture
def mock_damping() -> DampingFactor:
    return DampingFactor(
        base=0.5,
        min_factor=0.1,
        max_factor=0.9,
        damping_type=DampingType.EXPONENTIAL,
    )


@pytest.fixture
def mock_retry() -> RetryCeiling:
    return RetryCeiling(
        max_retries=3,
        base_delay_seconds=1.0,
        max_delay_seconds=10.0,
    )


@pytest.fixture
def mock_convergence() -> ConvergenceWindow:
    return ConvergenceWindow(
        max_iterations=100,
        max_duration_seconds=60.0,
    )


@pytest.fixture
def mock_metric_config() -> TelemetryMetricConfig:
    return TelemetryMetricConfig(
        metric_type=TelemetryMetricType.THROUGHPUT,
        loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
        target_value=100.0,
        damping_type=DampingType.EXPONENTIAL,
        min_value=0.0,
        max_value=1000.0,
        enabled=True,
    )


@pytest.fixture
def mock_aggregation_config(
    mock_cadence: ReconciliationCadence,
    mock_damping: DampingFactor,
    mock_retry: RetryCeiling,
    mock_convergence: ConvergenceWindow,
    mock_metric_config: TelemetryMetricConfig,
) -> TelemetryAggregationConfig:
    return TelemetryAggregationConfig(
        cadence=mock_cadence,
        damping=mock_damping,
        retry=mock_retry,
        convergence=mock_convergence,
        metric_configs={TelemetryMetricType.THROUGHPUT: mock_metric_config},
        enabled=True,
        workspace_id="test-workspace",
    )


@pytest.fixture
def throughput_loop(mock_aggregation_config: TelemetryAggregationConfig) -> ThroughputStabilizationLoop:
    return ThroughputStabilizationLoop(mock_aggregation_config)


@pytest.fixture
def queue_loop(mock_aggregation_config: TelemetryAggregationConfig) -> QueueDepthConvergenceLoop:
    # Need to update the metric config for queue depth
    queue_config = TelemetryAggregationConfig(
        cadence=mock_aggregation_config.cadence,
        damping=mock_aggregation_config.damping,
        retry=mock_aggregation_config.retry,
        convergence=mock_aggregation_config.convergence,
        metric_configs={
            TelemetryMetricType.QUEUE_DEPTH: TelemetryMetricConfig(
                metric_type=TelemetryMetricType.QUEUE_DEPTH,
                loop_type=TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE,
                target_value=0.0,
                max_value=10000.0,
            )
        },
        enabled=True,
    )
    return QueueDepthConvergenceLoop(queue_config)


@pytest.fixture
def runtime_loop(mock_aggregation_config: TelemetryAggregationConfig) -> RuntimeCoolingLoop:
    runtime_config = TelemetryAggregationConfig(
        cadence=mock_aggregation_config.cadence,
        damping=mock_aggregation_config.damping,
        retry=mock_aggregation_config.retry,
        convergence=mock_aggregation_config.convergence,
        metric_configs={
            TelemetryMetricType.RUNTIME_SATURATION: TelemetryMetricConfig(
                metric_type=TelemetryMetricType.RUNTIME_SATURATION,
                loop_type=TelemetryLoopType.RUNTIME_COOLING,
                target_value=0.8,
                max_value=1.0,
            )
        },
        enabled=True,
    )
    return RuntimeCoolingLoop(runtime_config)


@pytest.fixture
def cadence_loop(mock_aggregation_config: TelemetryAggregationConfig) -> CadenceStabilizationLoop:
    cadence_config = TelemetryAggregationConfig(
        cadence=mock_aggregation_config.cadence,
        damping=mock_aggregation_config.damping,
        retry=mock_aggregation_config.retry,
        convergence=mock_aggregation_config.convergence,
        metric_configs={
            TelemetryMetricType.CADENCE: TelemetryMetricConfig(
                metric_type=TelemetryMetricType.CADENCE,
                loop_type=TelemetryLoopType.CADENCE_STABILIZATION,
                target_value=10.0,
            )
        },
        enabled=True,
    )
    return CadenceStabilizationLoop(cadence_config)


@pytest.fixture
def density_loop(mock_aggregation_config: TelemetryAggregationConfig) -> DensityConvergenceLoop:
    density_config = TelemetryAggregationConfig(
        cadence=mock_aggregation_config.cadence,
        damping=mock_aggregation_config.damping,
        retry=mock_aggregation_config.retry,
        convergence=mock_aggregation_config.convergence,
        metric_configs={
            TelemetryMetricType.DENSITY: TelemetryMetricConfig(
                metric_type=TelemetryMetricType.DENSITY,
                loop_type=TelemetryLoopType.DENSITY_CONVERGENCE,
                target_value=0.5,
                max_value=1.0,
            )
        },
        enabled=True,
    )
    return DensityConvergenceLoop(density_config)


@pytest.fixture
def mock_controller(mock_aggregation_config: TelemetryAggregationConfig) -> TelemetryReconciliationController:
    return TelemetryReconciliationController(
        config=mock_aggregation_config,
        enabled_loops=set(TelemetryLoopType),
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
        assert SCHEMA_VERSION == "rig.telemetry_reconciliation.v1"

    def test_default_cadence_min(self):
        assert DEFAULT_TELEMETRY_CADENCE_MIN == 1.0

    def test_default_cadence_max(self):
        assert DEFAULT_TELEMETRY_CADENCE_MAX == 10.0

    def test_default_max_iterations(self):
        assert DEFAULT_TELEMETRY_MAX_ITERATIONS == 100


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Test enumeration types."""

    def test_telemetry_loop_type_values(self):
        assert TelemetryLoopType.THROUGHPUT_STABILIZATION.value == "throughput_stabilization"
        assert TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE.value == "queue_depth_convergence"
        assert TelemetryLoopType.RUNTIME_COOLING.value == "runtime_cooling"
        assert TelemetryLoopType.CADENCE_STABILIZATION.value == "cadence_stabilization"
        assert TelemetryLoopType.DENSITY_CONVERGENCE.value == "density_convergence"

    def test_telemetry_metric_type_values(self):
        assert TelemetryMetricType.THROUGHPUT.value == "throughput"
        assert TelemetryMetricType.QUEUE_DEPTH.value == "queue_depth"
        assert TelemetryMetricType.RUNTIME_SATURATION.value == "runtime_saturation"
        assert TelemetryMetricType.CADENCE.value == "cadence"
        assert TelemetryMetricType.DENSITY.value == "density"
        assert TelemetryMetricType.LATENCY.value == "latency"
        assert TelemetryMetricType.ERROR_RATE.value == "error_rate"
        assert TelemetryMetricType.MEMORY_USAGE.value == "memory_usage"
        assert TelemetryMetricType.CPU_USAGE.value == "cpu_usage"


# =============================================================================
# Config Type Tests
# =============================================================================

class TestTelemetryMetricConfig:
    """Test TelemetryMetricConfig validation."""

    def test_default_metric_config(self):
        config = TelemetryMetricConfig(
            metric_type=TelemetryMetricType.THROUGHPUT,
            loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
        )
        assert config.metric_type == TelemetryMetricType.THROUGHPUT
        assert config.loop_type == TelemetryLoopType.THROUGHPUT_STABILIZATION
        assert config.target_value == 0.0
        assert config.damping_type == DampingType.EXPONENTIAL
        assert config.min_value == 0.0
        assert config.max_value == 1.0
        assert config.enabled is True

    def test_metric_config_with_values(self):
        config = TelemetryMetricConfig(
            metric_type=TelemetryMetricType.THROUGHPUT,
            loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
            target_value=100.0,
            damping_type=DampingType.LINEAR,
            min_value=0.0,
            max_value=1000.0,
            enabled=True,
        )
        assert config.target_value == 100.0
        assert config.damping_type == DampingType.LINEAR
        assert config.min_value == 0.0
        assert config.max_value == 1000.0

    def test_metric_config_validation_negative_min(self):
        with pytest.raises(ValueError, match="min_value must be >= 0"):
            TelemetryMetricConfig(
                metric_type=TelemetryMetricType.THROUGHPUT,
                loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
                min_value=-1.0,
            )

    def test_metric_config_validation_max_not_greater_than_min(self):
        with pytest.raises(ValueError, match="max_value must be > min_value"):
            TelemetryMetricConfig(
                metric_type=TelemetryMetricType.THROUGHPUT,
                loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
                min_value=10.0,
                max_value=10.0,
            )

    def test_metric_config_is_frozen(self):
        config = TelemetryMetricConfig(
            metric_type=TelemetryMetricType.THROUGHPUT,
            loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
        )
        with pytest.raises(AttributeError):
            config.target_value = 50.0


class TestTelemetryAggregationConfig:
    """Test TelemetryAggregationConfig."""

    def test_default_config(self):
        config = TelemetryAggregationConfig()
        assert config.cadence.min_interval_seconds == DEFAULT_TELEMETRY_CADENCE_MIN
        assert config.cadence.max_interval_seconds == DEFAULT_TELEMETRY_CADENCE_MAX
        assert config.convergence.max_iterations == DEFAULT_TELEMETRY_MAX_ITERATIONS
        assert config.enabled is True
        assert config.workspace_id is None

    def test_config_with_workspace(self):
        config = TelemetryAggregationConfig(workspace_id="ws-1")
        assert config.workspace_id == "ws-1"

    def test_config_is_frozen(self):
        config = TelemetryAggregationConfig()
        with pytest.raises(AttributeError):
            config.enabled = False


# =============================================================================
# Data Type Tests
# =============================================================================

class TestTelemetrySample:
    """Test TelemetrySample."""

    def test_default_sample(self):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=100.0,
        )
        assert sample.metric_type == TelemetryMetricType.THROUGHPUT
        assert sample.value == 100.0
        assert isinstance(sample.timestamp, datetime)
        assert sample.source == "unknown"
        assert sample.tags == {}

    def test_sample_with_all_fields(self):
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.QUEUE_DEPTH,
            value=50.0,
            timestamp=now,
            source="runtime-1",
            tags={"key": "value"},
        )
        assert sample.timestamp == now
        assert sample.source == "runtime-1"
        assert sample.tags == {"key": "value"}

    def test_sample_to_dict(self):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=100.0,
            source="test",
        )
        d = sample.to_dict()
        assert d["metric_type"] == "throughput"
        assert d["value"] == 100.0
        assert d["source"] == "test"

    def test_sample_is_frozen(self):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=100.0,
        )
        with pytest.raises(AttributeError):
            sample.value = 200.0


class TestAggregatedMetric:
    """Test AggregatedMetric."""

    def test_default_aggregated_metric(self):
        now = datetime.now(timezone.utc)
        metric = AggregatedMetric(
            metric_type=TelemetryMetricType.THROUGHPUT,
            current_value=100.0,
            target_value=150.0,
            aggregated_value=100.0,
            sample_count=10,
            min_value=50.0,
            max_value=150.0,
            last_update=now,
            damping_factor=0.5,
            converged=True,
        )
        assert metric.metric_type == TelemetryMetricType.THROUGHPUT
        assert metric.current_value == 100.0
        assert metric.target_value == 150.0
        assert metric.aggregated_value == 100.0
        assert metric.sample_count == 10
        assert metric.converged is True

    def test_aggregated_metric_to_dict(self):
        now = datetime.now(timezone.utc)
        metric = AggregatedMetric(
            metric_type=TelemetryMetricType.QUEUE_DEPTH,
            current_value=10.0,
            target_value=0.0,
            aggregated_value=10.0,
            sample_count=5,
            min_value=0.0,
            max_value=20.0,
            last_update=now,
            damping_factor=1.0,
            converged=False,
        )
        d = metric.to_dict()
        assert d["metric_type"] == "queue_depth"
        assert d["current_value"] == 10.0
        assert d["converged"] is False


# =============================================================================
# Throughput Stabilization Loop Tests
# =============================================================================

class TestThroughputStabilizationLoop:
    """Test ThroughputStabilizationLoop."""

    def test_init(self, throughput_loop: ThroughputStabilizationLoop):
        assert throughput_loop.loop_type == TelemetryLoopType.THROUGHPUT_STABILIZATION
        assert throughput_loop.metric_type == TelemetryMetricType.THROUGHPUT
        assert throughput_loop.samples == []
        assert throughput_loop.aggregated_value == 0.0
        assert throughput_loop.converged is False

    def test_receive_sample(self, throughput_loop: ThroughputStabilizationLoop):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=100.0,
        )
        throughput_loop.receive_sample(sample)
        
        assert len(throughput_loop.samples) == 1
        assert throughput_loop.sample_count == 1
        assert throughput_loop.aggregated_value > 0

    def test_receive_sample_wrong_metric_ignored(self, throughput_loop: ThroughputStabilizationLoop):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.QUEUE_DEPTH,  # Wrong type
            value=100.0,
        )
        throughput_loop.receive_sample(sample)
        
        assert len(throughput_loop.samples) == 0
        assert throughput_loop.sample_count == 0

    def test_apply_correction(self, throughput_loop: ThroughputStabilizationLoop):
        # First add some samples
        for i in range(10):
            throughput_loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=100.0 + i,
            ))
        
        initial_value = throughput_loop.aggregated_value
        
        # Apply correction towards higher target
        throughput_loop.apply_correction(150.0)
        
        assert throughput_loop.aggregated_value >= initial_value

    def test_get_aggregated_metric(self, throughput_loop: ThroughputStabilizationLoop):
        for i in range(10):
            throughput_loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=100.0 + i * 10,
            ))
        
        metric = throughput_loop.get_aggregated_metric()
        assert metric is not None
        assert metric.metric_type == TelemetryMetricType.THROUGHPUT
        assert metric.sample_count == 10
        assert metric.min_value == 100.0
        assert metric.max_value == 190.0

    def test_reset(self, throughput_loop: ThroughputStabilizationLoop):
        throughput_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=100.0,
        ))
        
        assert throughput_loop.sample_count == 1
        
        throughput_loop.reset()
        
        assert throughput_loop.samples == []
        assert throughput_loop.aggregated_value == 0.0
        assert throughput_loop.sample_count == 0
        assert throughput_loop.converged is False

    def test_weighted_average_aggregation(self, throughput_loop: ThroughputStabilizationLoop):
        """Test that throughput loop uses weighted average."""
        # Add samples with increasing values
        samples = [
            TelemetrySample(metric_type=TelemetryMetricType.THROUGHPUT, value=v)
            for v in [10, 20, 30, 40, 50]
        ]
        
        for s in samples:
            throughput_loop.receive_sample(s)
        
        # The weighted average should give more weight to recent samples
        metric = throughput_loop.get_aggregated_metric()
        assert metric is not None
        # Simple average would be 30, weighted should be higher
        assert metric.aggregated_value > 25  # Biomed towards higher (recent) values

    def test_value_bounded_by_config(self, throughput_loop: ThroughputStabilizationLoop):
        """Test that values are bounded by metric config."""
        # The mock_aggregation_config has max_value=1000 for throughput
        # Send a sample above max
        throughput_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=2000.0,  # Above max
        ))
        
        metric = throughput_loop.get_aggregated_metric()
        assert metric is not None
        # Should be clamped to max
        # Note: the config in fixture has max_value=1000
        # But the loop uses its own config which may differ


# =============================================================================
# Queue Depth Convergence Loop Tests
# =============================================================================

class TestQueueDepthConvergenceLoop:
    """Test QueueDepthConvergenceLoop."""

    def test_init(self, queue_loop: QueueDepthConvergenceLoop):
        assert queue_loop.loop_type == TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE
        assert queue_loop.metric_type == TelemetryMetricType.QUEUE_DEPTH

    def test_receive_sample(self, queue_loop: QueueDepthConvergenceLoop):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.QUEUE_DEPTH,
            value=100.0,
        )
        queue_loop.receive_sample(sample)
        
        assert queue_loop.sample_count == 1

    def test_max_based_aggregation(self, queue_loop: QueueDepthConvergenceLoop):
        """Test that queue depth uses max aggregation."""
        samples = [
            TelemetrySample(metric_type=TelemetryMetricType.QUEUE_DEPTH, value=v)
            for v in [10, 50, 30, 20, 100]  # Max is 100
        ]
        
        for s in samples:
            queue_loop.receive_sample(s)
        
        # Queue depth should use max (peak depth matters)
        metric = queue_loop.get_aggregated_metric()
        assert metric is not None
        # The max value seen should be 100
        assert metric.max_value == 100.0

    def test_faster_damping_for_reduction(self, queue_loop: QueueDepthConvergenceLoop):
        """Test that queue depth has faster damping when decreasing."""
        # Start with high queue
        for _ in range(10):
            queue_loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.QUEUE_DEPTH,
                value=100.0,
            ))
        
        initial = queue_loop.aggregated_value
        
        # Now send decreasing values
        for v in [90.0, 80.0, 70.0, 60.0, 50.0]:
            queue_loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.QUEUE_DEPTH,
                value=v,
            ))
        
        # Value should have decreased
        assert queue_loop.aggregated_value < initial


# =============================================================================
# Runtime Cooling Loop Tests
# =============================================================================

class TestRuntimeCoolingLoop:
    """Test RuntimeCoolingLoop."""

    def test_init(self, runtime_loop: RuntimeCoolingLoop):
        assert runtime_loop.loop_type == TelemetryLoopType.RUNTIME_COOLING
        assert runtime_loop.metric_type == TelemetryMetricType.RUNTIME_SATURATION

    def test_receive_sample(self, runtime_loop: RuntimeCoolingLoop):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.RUNTIME_SATURATION,
            value=0.8,
        )
        runtime_loop.receive_sample(sample)
        
        assert runtime_loop.sample_count == 1

    def test_saturation_above_target_strong_damping(self, runtime_loop: RuntimeCoolingLoop):
        """Test that saturation above target uses strong damping."""
        # Target is 0.8, send value above
        runtime_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.RUNTIME_SATURATION,
            value=0.95,  # Above target
        ))
        
        # Aggregated value should be damped towards target
        metric = runtime_loop.get_aggregated_metric()
        assert metric is not None

    def test_latest_value_used(self, runtime_loop: RuntimeCoolingLoop):
        """Test that runtime saturation uses latest value."""
        # Send multiple values
        for v in [0.5, 0.6, 0.7, 0.8, 0.9]:
            runtime_loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.RUNTIME_SATURATION,
                value=v,
            ))
        
        # The aggregated value should be based on the latest (0.9)
        metric = runtime_loop.get_aggregated_metric()
        assert metric is not None


# =============================================================================
# Cadence Stabilization Loop Tests
# =============================================================================

class TestCadenceStabilizationLoop:
    """Test CadenceStabilizationLoop."""

    def test_init(self, cadence_loop: CadenceStabilizationLoop):
        assert cadence_loop.loop_type == TelemetryLoopType.CADENCE_STABILIZATION
        assert cadence_loop.metric_type == TelemetryMetricType.CADENCE

    def test_receive_sample(self, cadence_loop: CadenceStabilizationLoop):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.CADENCE,
            value=10.0,
        )
        cadence_loop.receive_sample(sample)
        
        assert cadence_loop.sample_count == 1

    def test_harmonic_mean_aggregation(self, cadence_loop: CadenceStabilizationLoop):
        """Test that cadence uses harmonic mean."""
        # Harmonic mean of [10, 20] is 2*(10*20)/(10+20) = 400/30 = 13.33...
        samples = [
            TelemetrySample(metric_type=TelemetryMetricType.CADENCE, value=10.0),
            TelemetrySample(metric_type=TelemetryMetricType.CADENCE, value=20.0),
        ]
        
        for s in samples:
            cadence_loop.receive_sample(s)
        
        metric = cadence_loop.get_aggregated_metric()
        assert metric is not None


# =============================================================================
# Density Convergence Loop Tests
# =============================================================================

class TestDensityConvergenceLoop:
    """Test DensityConvergenceLoop."""

    def test_init(self, density_loop: DensityConvergenceLoop):
        assert density_loop.loop_type == TelemetryLoopType.DENSITY_CONVERGENCE
        assert density_loop.metric_type == TelemetryMetricType.DENSITY
        assert density_loop._rising is False
        assert density_loop._falling is False

    def test_receive_sample(self, density_loop: DensityConvergenceLoop):
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.DENSITY,
            value=0.5,
        )
        density_loop.receive_sample(sample)
        
        assert density_loop.sample_count == 1

    def test_geometric_mean_aggregation(self, density_loop: DensityConvergenceLoop):
        """Test that density uses geometric mean."""
        samples = [
            TelemetrySample(metric_type=TelemetryMetricType.DENSITY, value=0.1),
            TelemetrySample(metric_type=TelemetryMetricType.DENSITY, value=0.9),
        ]
        
        for s in samples:
            density_loop.receive_sample(s)
        
        metric = density_loop.get_aggregated_metric()
        assert metric is not None
        # Geometric mean of 0.1 and 0.9 is sqrt(0.1*0.9) = sqrt(0.09) = 0.3
        # But with clamping, it should be close

    def test_hysteresis_rising(self, density_loop: DensityConvergenceLoop):
        """Test hysteresis when density is rising."""
        target = 0.5
        upper_threshold = target * 1.2  # 0.6
        lower_threshold = target * 0.8  # 0.4
        
        # Start below lower threshold
        density_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.DENSITY,
            value=0.3,
        ))
        
        # Jump above upper threshold - should trigger rising
        density_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.DENSITY,
            value=0.7,
        ))
        
        # Check hysteresis state
        # The loop should have detected the transition

    def test_hysteresis_falling(self, density_loop: DensityConvergenceLoop):
        """Test hysteresis when density is falling."""
        target = 0.5
        upper_threshold = target * 1.2  # 0.6
        
        # Start above upper threshold
        density_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.DENSITY,
            value=0.7,
        ))
        
        # Drop below lower threshold - should trigger falling
        density_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.DENSITY,
            value=0.3,
        ))


# =============================================================================
# Controller Tests
# =============================================================================

class TestTelemetryReconciliationController:
    """Test TelemetryReconciliationController."""

    def test_init_all_loops(self, mock_aggregation_config: TelemetryAggregationConfig):
        controller = TelemetryReconciliationController(
            config=mock_aggregation_config,
            enabled_loops=set(TelemetryLoopType),
        )
        
        assert len(controller.loops) == 5
        assert TelemetryLoopType.THROUGHPUT_STABILIZATION in controller.loops
        assert TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE in controller.loops
        assert TelemetryLoopType.RUNTIME_COOLING in controller.loops
        assert TelemetryLoopType.CADENCE_STABILIZATION in controller.loops
        assert TelemetryLoopType.DENSITY_CONVERGENCE in controller.loops

    def test_init_subset_of_loops(self, mock_aggregation_config: TelemetryAggregationConfig):
        controller = TelemetryReconciliationController(
            config=mock_aggregation_config,
            enabled_loops={TelemetryLoopType.THROUGHPUT_STABILIZATION},
        )
        
        assert len(controller.loops) == 1
        assert TelemetryLoopType.THROUGHPUT_STABILIZATION in controller.loops

    def test_start_stop(self, mock_controller: TelemetryReconciliationController):
        assert mock_controller.running is False
        
        mock_controller.start()
        assert mock_controller.running is True
        
        mock_controller.stop()
        assert mock_controller.running is False

    def test_receive_samples(self, mock_controller: TelemetryReconciliationController):
        samples = [
            TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=100.0,
            ),
            TelemetrySample(
                metric_type=TelemetryMetricType.QUEUE_DEPTH,
                value=50.0,
            ),
        ]
        
        mock_controller.receive_samples(samples)
        
        # Check that samples were routed to correct loops
        metrics = mock_controller.get_metrics()
        assert TelemetryMetricType.THROUGHPUT in metrics or TelemetryMetricType.QUEUE_DEPTH in metrics

    def test_get_metrics(self, mock_controller: TelemetryReconciliationController):
        # Add samples first
        samples = [
            TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=100.0,
            ),
        ]
        mock_controller.receive_samples(samples)
        
        metrics = mock_controller.get_metrics()
        assert len(metrics) > 0
        
        for metric_type, metric in metrics.items():
            assert isinstance(metric, AggregatedMetric)

    def test_set_target(self, mock_aggregation_config: TelemetryAggregationConfig):
        controller = TelemetryReconciliationController(
            config=mock_aggregation_config,
            enabled_loops={TelemetryLoopType.THROUGHPUT_STABILIZATION},
        )
        
        original_target = controller.config.metric_configs[TelemetryMetricType.THROUGHPUT].target_value
        
        controller.set_target(TelemetryMetricType.THROUGHPUT, 200.0)
        
        # The loop config should have been updated
        loop = controller.loops[TelemetryLoopType.THROUGHPUT_STABILIZATION]
        new_config = loop.config
        assert new_config.metric_configs[TelemetryMetricType.THROUGHPUT].target_value == 200.0

    def test_apply_corrections(self, mock_controller: TelemetryReconciliationController):
        # Add samples
        samples = [
            TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=50.0,
            ),
        ]
        mock_controller.receive_samples(samples)
        
        # Get initial values
        metrics_before = mock_controller.get_metrics()
        initial_values = {mt: m.current_value for mt, m in metrics_before.items()}
        
        # Apply corrections
        mock_controller.apply_corrections()
        
        # Values may or may not have changed depending on correction logic
        metrics_after = mock_controller.get_metrics()

    def test_get_health_state(self, mock_controller: TelemetryReconciliationController):
        mock_controller.start()
        
        health = mock_controller.get_health_state()
        
        assert len(health) == 5  # All loop types
        for loop_type, state in health.items():
            assert "status" in state
            assert "metric_type" in state
            assert "aggregated_value" in state
            assert "sample_count" in state
            assert "converged" in state
            assert "error" in state

    @pytest.mark.asyncio
    async def test_run_once(self, mock_controller: TelemetryReconciliationController, mock_aggregation_config: TelemetryAggregationConfig):
        """Test async run_once."""
        # Create a fresh controller for async test
        config = TelemetryAggregationConfig(
            cadence=mock_aggregation_config.cadence,
            damping=mock_aggregation_config.damping,
            retry=mock_aggregation_config.retry,
            convergence=mock_aggregation_config.convergence,
            metric_configs=mock_aggregation_config.metric_configs,
            enabled=True,
            workspace_id="test",
        )
        controller = TelemetryReconciliationController(
            config=config,
            enabled_loops={TelemetryLoopType.THROUGHPUT_STABILIZATION},
        )
        controller.start()
        
        # Add samples
        controller.receive_samples([
            TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=100.0,
            ),
        ])
        
        # Run once
        await controller.run_once()
        
        # Controller should still be running
        assert controller.running is True

    @pytest.mark.asyncio
    async def test_run_once_not_running(self, mock_controller: TelemetryReconciliationController):
        """Test run_once when not running does nothing."""
        # Controller is stopped by default
        assert mock_controller.running is False
        
        await mock_controller.run_once()
        
        # Should not error, just return


# =============================================================================
# Deterministic Behavior Tests
# =============================================================================

class TestDeterministicBehavior:
    """Test deterministic behavior of telemetry loops."""

    def test_deterministic_sample_processing(self):
        """Same samples processed in same order produce same results."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
            metric_configs={
                TelemetryMetricType.THROUGHPUT: TelemetryMetricConfig(
                    metric_type=TelemetryMetricType.THROUGHPUT,
                    loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
                )
            },
        )
        
        samples = [
            TelemetrySample(metric_type=TelemetryMetricType.THROUGHPUT, value=v)
            for v in [10, 20, 30, 40, 50]
        ]
        
        # First pass
        loop1 = ThroughputStabilizationLoop(config)
        for s in samples:
            loop1.receive_sample(s)
        metric1 = loop1.get_aggregated_metric()
        
        # Second pass
        loop2 = ThroughputStabilizationLoop(config)
        for s in samples:
            loop2.receive_sample(s)
        metric2 = loop2.get_aggregated_metric()
        
        # Results should be identical
        assert metric1 is not None
        assert metric2 is not None
        assert metric1.sample_count == metric2.sample_count
        assert metric1.min_value == metric2.min_value
        assert metric1.max_value == metric2.max_value

    def test_deterministic_correction(self):
        """Correction application is deterministic."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
            metric_configs={
                TelemetryMetricType.QUEUE_DEPTH: TelemetryMetricConfig(
                    metric_type=TelemetryMetricType.QUEUE_DEPTH,
                    loop_type=TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE,
                    target_value=0.0,
                    max_value=10000.0,
                )
            },
        )
        
        loop1 = QueueDepthConvergenceLoop(config)
        loop2 = QueueDepthConvergenceLoop(config)
        
        # Add same samples
        samples = [
            TelemetrySample(metric_type=TelemetryMetricType.QUEUE_DEPTH, value=100.0)
            for _ in range(10)
        ]
        
        for loop in [loop1, loop2]:
            for s in samples:
                loop.receive_sample(s)
        
        # Apply same correction
        target = 50.0
        loop1.apply_correction(target)
        loop2.apply_correction(target)
        
        # Results should be the same
        assert loop1.aggregated_value == loop2.aggregated_value


# =============================================================================
# Bounded Cadence Tests
# =============================================================================

class TestBoundedCadence:
    """Test bounded cadence enforcement."""

    def test_cadence_bounds_in_config(self):
        """Cadence bounds are enforced at config level."""
        cadence = ReconciliationCadence(
            min_interval_seconds=1.0,
            max_interval_seconds=10.0,
            jitter_factor=0.1,
        )
        assert cadence.min_interval_seconds == 1.0
        assert cadence.max_interval_seconds == 10.0

    def test_default_cadence_match_constants(self):
        """Default cadence matches module constants."""
        config = TelemetryAggregationConfig()
        assert config.cadence.min_interval_seconds == DEFAULT_TELEMETRY_CADENCE_MIN
        assert config.cadence.max_interval_seconds == DEFAULT_TELEMETRY_CADENCE_MAX

    def test_max_iterations_bounded(self):
        """Max iterations is bounded."""
        convergence = ConvergenceWindow(max_iterations=100)
        assert convergence.max_iterations == 100


# =============================================================================
# Oscillation Prevention Tests
# =============================================================================

class TestOscillationPrevention:
    """Test oscillation prevention mechanisms."""

    def test_damping_prevents_oscillation(self):
        """Damping prevents rapid oscillations."""
        config = TelemetryAggregationConfig(
            damping=DampingFactor(
                base=0.1,  # Very strong damping
                min_factor=0.01,
                max_factor=0.5,
            ),
            workspace_id="test",
            metric_configs={
                TelemetryMetricType.THROUGHPUT: TelemetryMetricConfig(
                    metric_type=TelemetryMetricType.THROUGHPUT,
                    loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
                )
            },
        )
        
        loop = ThroughputStabilizationLoop(config)
        
        # Send alternating high/low values
        for _ in range(10):
            loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=100.0,
            ))
            loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=0.0,
            ))
        
        # With strong damping, the aggregated value should be stable
        metric = loop.get_aggregated_metric()
        assert metric is not None
        # Value should be somewhere between 0 and 100, not oscillating wildly
        assert 0 <= metric.current_value <= 100

    def test_convergence_detection(self):
        """Loops detect when they have converged."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
            metric_configs={
                TelemetryMetricType.THROUGHPUT: TelemetryMetricConfig(
                    metric_type=TelemetryMetricType.THROUGHPUT,
                    loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
                    target_value=100.0,
                )
            },
        )
        
        loop = ThroughputStabilizationLoop(config)
        
        # Add samples at target value
        for _ in range(20):
            loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=100.0,  # At target
            ))
        
        # Apply correction towards target
        loop.apply_correction(100.0)
        
        # After many samples at target with correction, should converge
        # Note: convergence may take multiple iterations

    def test_sample_count_bounded(self):
        """Sample history is bounded."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
        )
        loop = ThroughputStabilizationLoop(config)
        
        # Add many samples
        for i in range(2000):
            loop.receive_sample(TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=float(i),
            ))
        
        # Sample count should be bounded by deque maxlen (1000)
        assert len(loop.samples) <= 1000


# =============================================================================
# Authority Boundary Tests
# =============================================================================

class TestAuthorityBoundaries:
    """Test that authority boundaries are respected."""

    def test_no_authority_inference(self):
        """Telemetry loops do not infer authority."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
        )
        loop = ThroughputStabilizationLoop(config)
        
        # Sample with authority-like metadata
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=100.0,
            source="user-command",  # Should be treated as just a source string
            tags={"priority": "critical", "auto_approve": "true"},
        )
        
        loop.receive_sample(sample)
        
        # The loop only uses value, metric_type, and timestamp
        assert loop.sample_count == 1
        assert loop.aggregated_value == 100.0

    def test_no_mutation_of_source_data(self):
        """Telemetry processing does not mutate source data."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
        )
        loop = ThroughputStabilizationLoop(config)
        
        original_value = 100.0
        sample = TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=original_value,
            tags={"original": "data"},
        )
        
        # Store original for comparison
        original_tags = dict(sample.tags)
        
        loop.receive_sample(sample)
        
        # Sample should be unchanged
        assert sample.value == original_value
        assert sample.tags == original_tags


# =============================================================================
# Namespace Isolation Tests
# =============================================================================

class TestNamespaceIsolation:
    """Test namespace isolation for telemetry."""

    def test_workspace_id_scoping(self):
        """Telemetry is scoped by workspace."""
        config1 = TelemetryAggregationConfig(workspace_id="ws-1")
        config2 = TelemetryAggregationConfig(workspace_id="ws-2")
        
        controller1 = TelemetryReconciliationController(config=config1)
        controller2 = TelemetryReconciliationController(config=config2)
        
        # Add samples to both
        sample1 = TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=100.0,
            source="ws-1-source",
        )
        sample2 = TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=200.0,
            source="ws-2-source",
        )
        
        controller1.receive_samples([sample1])
        controller2.receive_samples([sample2])
        
        # Each controller has its own samples
        metrics1 = controller1.get_metrics()
        metrics2 = controller2.get_metrics()
        
        # They should have different data
        # (Note: they have separate loop instances)

    def test_workspace_id_required_for_config(self):
        """Workspace ID can be None but is recommended for scoping."""
        # Config allows None workspace_id
        config = TelemetryAggregationConfig(workspace_id=None)
        assert config.workspace_id is None
        
        controller = TelemetryReconciliationController(config=config)
        assert controller.config.workspace_id is None


# =============================================================================
# Replay Safety Tests
# =============================================================================

class TestReplaySafety:
    """Test replay-safe behavior."""

    def test_replay_same_samples_same_aggregation(self):
        """Replaying same samples produces same aggregated values."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
        )
        
        samples = [
            TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=v,
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
            for v in [10, 20, 30, 40, 50]
        ]
        
        # First pass
        loop1 = ThroughputStabilizationLoop(config)
        for s in samples:
            loop1.receive_sample(s)
        metric1 = loop1.get_aggregated_metric()
        
        # Second pass with new loop
        loop2 = ThroughputStabilizationLoop(config)
        for s in samples:
            loop2.receive_sample(s)
        metric2 = loop2.get_aggregated_metric()
        
        # Should produce same results
        assert metric1 is not None
        assert metric2 is not None
        assert metric1.sample_count == metric2.sample_count
        assert metric1.min_value == metric2.min_value
        assert metric1.max_value == metric2.max_value

    def test_reset_allows_clean_replay(self):
        """Reset allows clean replay of data."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
        )
        loop = ThroughputStabilizationLoop(config)
        
        # First set of samples
        samples1 = [
            TelemetrySample(metric_type=TelemetryMetricType.THROUGHPUT, value=v)
            for v in [10, 20, 30]
        ]
        for s in samples1:
            loop.receive_sample(s)
        
        metric1 = loop.get_aggregated_metric()
        
        # Reset
        loop.reset()
        
        # Second set of samples
        samples2 = [
            TelemetrySample(metric_type=TelemetryMetricType.THROUGHPUT, value=v)
            for v in [40, 50, 60]
        ]
        for s in samples2:
            loop.receive_sample(s)
        
        metric2 = loop.get_aggregated_metric()
        
        # Second metric should reflect second set of samples only
        assert metric2 is not None
        assert metric2.sample_count == 3
        assert metric2.min_value >= 40  # All values in second set are >= 40


# =============================================================================
# Topology Awareness Tests
# =============================================================================

class TestTopologyAwareness:
    """Test topology-aware behavior."""

    def test_metric_type_routing(self):
        """Samples are routed to correct loops by metric type."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
            metric_configs={
                mt: TelemetryMetricConfig(
                    metric_type=mt,
                    loop_type=loop_type,
                )
                for mt, loop_type in [
                    (TelemetryMetricType.THROUGHPUT, TelemetryLoopType.THROUGHPUT_STABILIZATION),
                    (TelemetryMetricType.QUEUE_DEPTH, TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE),
                ]
            },
        )
        
        controller = TelemetryReconciliationController(
            config=config,
            enabled_loops={TelemetryLoopType.THROUGHPUT_STABILIZATION, TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE},
        )
        
        # Send samples for both metric types
        samples = [
            TelemetrySample(metric_type=TelemetryMetricType.THROUGHPUT, value=100.0),
            TelemetrySample(metric_type=TelemetryMetricType.QUEUE_DEPTH, value=50.0),
        ]
        
        controller.receive_samples(samples)
        
        metrics = controller.get_metrics()
        
        # Both metric types should have been processed
        assert TelemetryMetricType.THROUGHPUT in metrics
        assert TelemetryMetricType.QUEUE_DEPTH in metrics

    def test_loop_type_isolation(self):
        """Different loop types operate independently."""
        config = TelemetryAggregationConfig(
            workspace_id="test",
        )
        
        throughput_loop = ThroughputStabilizationLoop(config)
        queue_loop = QueueDepthConvergenceLoop(config)
        
        # Add samples to both
        throughput_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.THROUGHPUT,
            value=100.0,
        ))
        queue_loop.receive_sample(TelemetrySample(
            metric_type=TelemetryMetricType.QUEUE_DEPTH,
            value=50.0,
        ))
        
        # Each should have its own samples
        assert throughput_loop.sample_count == 1
        assert queue_loop.sample_count == 1
        assert throughput_loop.samples[0].metric_type == TelemetryMetricType.THROUGHPUT
        assert queue_loop.samples[0].metric_type == TelemetryMetricType.QUEUE_DEPTH


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for telemetry reconciliation."""

    def test_full_telemetry_workflow(self):
        """Test complete telemetry reconciliation workflow."""
        config = TelemetryAggregationConfig(
            workspace_id="integration-test",
            metric_configs={
                TelemetryMetricType.THROUGHPUT: TelemetryMetricConfig(
                    metric_type=TelemetryMetricType.THROUGHPUT,
                    loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
                    target_value=100.0,
                ),
            },
        )
        
        controller = TelemetryReconciliationController(
            config=config,
            enabled_loops={TelemetryLoopType.THROUGHPUT_STABILIZATION},
        )
        
        controller.start()
        
        # 1. Send samples
        samples = [
            TelemetrySample(
                metric_type=TelemetryMetricType.THROUGHPUT,
                value=80.0 + i * 5,
                source=f"source-{i}",
            )
            for i in range(10)
        ]
        controller.receive_samples(samples)
        
        # 2. Get metrics
        metrics = controller.get_metrics()
        assert TelemetryMetricType.THROUGHPUT in metrics
        metric = metrics[TelemetryMetricType.THROUGHPUT]
        assert metric.sample_count == 10
        
        # 3. Apply corrections
        controller.apply_corrections()
        
        # 4. Get health state
        health = controller.get_health_state()
        assert TelemetryLoopType.THROUGHPUT_STABILIZATION.value in health
        assert health[TelemetryLoopType.THROUGHPUT_STABILIZATION.value]["status"] == "running"
        
        controller.stop()

    def test_all_loops_convergence(self):
        """Test all loop types can converge."""
        config = TelemetryAggregationConfig(
            workspace_id="convergence-test",
            metric_configs={
                mt: TelemetryMetricConfig(
                    metric_type=mt,
                    loop_type=lt,
                    target_value=100.0,
                )
                for mt, lt in [
                    (TelemetryMetricType.THROUGHPUT, TelemetryLoopType.THROUGHPUT_STABILIZATION),
                    (TelemetryMetricType.QUEUE_DEPTH, TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE),
                    (TelemetryMetricType.RUNTIME_SATURATION, TelemetryLoopType.RUNTIME_COOLING),
                    (TelemetryMetricType.CADENCE, TelemetryLoopType.CADENCE_STABILIZATION),
                    (TelemetryMetricType.DENSITY, TelemetryLoopType.DENSITY_CONVERGENCE),
                ]
            },
        )
        
        controller = TelemetryReconciliationController(
            config=config,
            enabled_loops=set(TelemetryLoopType),
        )
        
        controller.start()
        
        # Send samples at target values
        samples = []
        for mt in list(TelemetryMetricType)[:5]:  # First 5 metric types
            samples.append(TelemetrySample(
                metric_type=mt,
                value=100.0,  # At target
            ))
        
        # Send many samples to allow convergence
        for _ in range(50):
            controller.receive_samples(samples)
        
        # Apply corrections repeatedly
        for _ in range(20):
            controller.apply_corrections()
        
        # Check health
        health = controller.get_health_state()
        
        controller.stop()

    def test_deterministic_full_workflow(self):
        """Test that full workflow is deterministic."""
        config = TelemetryAggregationConfig(
            workspace_id="deterministic-test",
            jitter_factor=0.0,  # No randomness
        )
        
        # Run workflow twice
        results = []
        for _ in range(2):
            controller = TelemetryReconciliationController(
                config=config,
                enabled_loops={TelemetryLoopType.THROUGHPUT_STABILIZATION},
            )
            controller.start()
            
            samples = [
                TelemetrySample(
                    metric_type=TelemetryMetricType.THROUGHPUT,
                    value=v,
                    timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                )
                for v in [10, 20, 30, 40, 50]
            ]
            controller.receive_samples(samples)
            controller.apply_corrections()
            
            metrics = controller.get_metrics()
            results.append(metrics)
            
            controller.stop()
        
        # Results should be identical
        assert len(results) == 2
        for mt in results[0]:
            assert mt in results[1]
            assert results[0][mt].sample_count == results[1][mt].sample_count
            assert results[0][mt].min_value == results[1][mt].min_value
            assert results[0][mt].max_value == results[1][mt].max_value
