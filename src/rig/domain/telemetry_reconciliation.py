"""Telemetry Reconciliation for Rig.

This module provides telemetry reconciliation as defined in PHASE 6 of the
Deterministic Operational Reconciliation Sprint.

Core doctrine:
- Backend-agnostic telemetry processing
- Normalized telemetry outputs
- Replay-safe aggregation
- Bounded oscillation
- Topology-aware

file: src/rig/domain/telemetry_reconciliation.py
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, FrozenSet, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.reconciliation_governance import (
        ReconciliationCadence,
        DampingFactor,
        RetryCeiling,
        ConvergenceWindow,
        CancellationPolicy,
        EventStormConfig,
        ReconciliationContext,
        LoopHealthState,
        LoopStatus,
        DampingType,
    )

from rig.domain.reconciliation_governance import (
    ReconciliationCadence,
    DampingFactor,
    RetryCeiling,
    ConvergenceWindow,
    CancellationPolicy,
    EventStormConfig,
    ReconciliationContext,
    LoopHealthState,
    LoopStatus,
    DampingType,
    DEFAULT_MIN_INTERVAL_SECONDS,
    DEFAULT_MAX_INTERVAL_SECONDS,
    DEFAULT_JITTER_FACTOR,
    DEFAULT_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "rig.telemetry_reconciliation.v1"

# Telemetry-specific defaults
DEFAULT_TELEMETRY_CADENCE_MIN = 1.0   # Minimum 1s between telemetry aggregations
DEFAULT_TELEMETRY_CADENCE_MAX = 10.0  # Maximum 10s between telemetry aggregations
DEFAULT_TELEMETRY_MAX_ITERATIONS = 100


class TelemetryLoopType(Enum):
    """Types of telemetry reconciliation loops."""
    THROUGHPUT_STABILIZATION = "throughput_stabilization"
    QUEUE_DEPTH_CONVERGENCE = "queue_depth_convergence"
    RUNTIME_COOLING = "runtime_cooling"
    CADENCE_STABILIZATION = "cadence_stabilization"
    DENSITY_CONVERGENCE = "density_convergence"


class TelemetryMetricType(Enum):
    """Types of telemetry metrics."""
    THROUGHPUT = "throughput"
    QUEUE_DEPTH = "queue_depth"
    RUNTIME_SATURATION = "runtime_saturation"
    CADENCE = "cadence"
    DENSITY = "density"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"


@dataclass(frozen=True, slots=True)
class TelemetryMetricConfig:
    """Configuration for a telemetry metric."""
    metric_type: TelemetryMetricType
    loop_type: TelemetryLoopType
    target_value: float = 0.0
    damping_type: DampingType = DampingType.EXPONENTIAL
    min_value: float = 0.0
    max_value: float = 1.0
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.min_value < 0:
            raise ValueError("min_value must be >= 0")
        if self.max_value <= self.min_value:
            raise ValueError("max_value must be > min_value")

    @property
    def damping(self) -> DampingFactor:
        return DampingFactor(damp_type=self.damping_type)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["metric_type"] = self.metric_type.value
        result["loop_type"] = self.loop_type.value
        result["damping_type"] = self.damping_type.name
        return result


@dataclass(frozen=True, slots=True)
class TelemetryAggregationConfig:
    """Configuration for telemetry aggregation."""
    cadence: ReconciliationCadence = field(default_factory=lambda: ReconciliationCadence(
        min_interval_seconds=DEFAULT_TELEMETRY_CADENCE_MIN,
        max_interval_seconds=DEFAULT_TELEMETRY_CADENCE_MAX,
        jitter_factor=DEFAULT_JITTER_FACTOR,
    ))
    damping: DampingFactor = field(default_factory=DampingFactor)
    retry: RetryCeiling = field(default_factory=RetryCeiling)
    convergence: ConvergenceWindow = field(default_factory=lambda: ConvergenceWindow(
        max_iterations=DEFAULT_TELEMETRY_MAX_ITERATIONS,
    ))
    metric_configs: Dict[TelemetryMetricType, TelemetryMetricConfig] = field(default_factory=dict)
    enabled: bool = True
    workspace_id: Optional[str] = None
    jitter_factor: float = DEFAULT_JITTER_FACTOR

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["metric_configs"] = {
            metric_type.value if hasattr(metric_type, "value") else str(metric_type): config.to_dict()
            for metric_type, config in self.metric_configs.items()
        }
        result["cadence"] = self.cadence.to_dict()
        result["damping"] = self.damping.to_dict()
        result["retry"] = self.retry.to_dict()
        result["convergence"] = self.convergence.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    """A single telemetry sample."""
    metric_type: TelemetryMetricType
    value: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "unknown"
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["metric_type"] = self.metric_type.value
        if hasattr(self.timestamp, "isoformat"):
            result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass(frozen=True, slots=True)
class AggregatedMetric:
    """Aggregated metric value."""
    metric_type: TelemetryMetricType
    current_value: float
    target_value: float
    aggregated_value: float
    sample_count: int
    min_value: float
    max_value: float
    last_update: datetime
    damping_factor: float
    converged: bool

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["metric_type"] = self.metric_type.value
        if hasattr(self.last_update, "isoformat"):
            result["last_update"] = self.last_update.isoformat()
        return result


class TelemetryAggregationLoop:
    """Base class for telemetry aggregation loops.
    
    Purpose: Base implementation for telemetry reconciliation loops
    
    Requirements:
    - Backend-agnostic
    - Normalized telemetry
    - Replay-safe
    - Bounded oscillation
    - Topology-aware
    """

    def __init__(
        self,
        loop_type: TelemetryLoopType,
        metric_type: TelemetryMetricType,
        config: TelemetryAggregationConfig,
    ) -> None:
        self.loop_type = loop_type
        self.metric_type = metric_type
        self.config = config
        
        # State
        self._samples: Deque[TelemetrySample] = deque(maxlen=1000)
        self._aggregated_value: float = 0.0
        self._sample_count: int = 0
        self._last_update: Optional[datetime] = None
        self._damping_factor: float = 1.0
        self._converged: bool = False
        self._error: Optional[str] = None

    @property
    def samples(self) -> List[TelemetrySample]:
        return list(self._samples)

    @property
    def aggregated_value(self) -> float:
        return self._aggregated_value

    @property
    def sample_count(self) -> int:
        return self._sample_count

    @property
    def last_update(self) -> Optional[datetime]:
        return self._last_update

    @property
    def converged(self) -> bool:
        return self._converged

    @property
    def error(self) -> Optional[str]:
        return self._error

    def receive_sample(self, sample: TelemetrySample) -> None:
        """Receive a telemetry sample."""
        if sample.metric_type != self.metric_type:
            return
        
        self._samples.append(sample)
        self._sample_count += 1
        self._last_update = datetime.now(timezone.utc)
        
        # Aggregate
        self._aggregate_samples()
        
        logger.debug(f"Received {self.metric_type.value} sample: value={sample.value}")

    def _aggregate_samples(self) -> None:
        """Aggregate samples into current value."""
        if not self._samples:
            return
        
        # Get metric config
        metric_config = self.config.metric_configs.get(self.metric_type, TelemetryMetricConfig(
            metric_type=self.metric_type,
            loop_type=self.loop_type,
            max_value=1000.0,
        ))
        
        # Simple average aggregation (can be overridden)
        values = [s.value for s in self._samples]
        new_value = sum(values) / len(values)
        
        # Clamp to bounds
        new_value = max(metric_config.min_value, min(metric_config.max_value, new_value))
        
        # Apply damping
        if self._aggregated_value != 0.0:
            diff = new_value - self._aggregated_value
            metric_config.damping.apply(self._sample_count, diff)
            damped_diff = diff * self._damping_factor
            self._aggregated_value += damped_diff
        else:
            self._aggregated_value = new_value
        
        # Clamp again after damping
        self._aggregated_value = max(metric_config.min_value, min(metric_config.max_value, self._aggregated_value))

    def apply_correction(self, target: float) -> None:
        """Apply correction towards target value."""
        metric_config = self.config.metric_configs.get(self.metric_type, TelemetryMetricConfig(
            metric_type=self.metric_type,
            loop_type=self.loop_type,
            max_value=1000.0,
        ))
        
        # Calculate difference
        diff = target - self._aggregated_value
        
        # Determine damping based on loop type
        damping = metric_config.damping
        
        # Apply damping to the correction
        damped_correction = damping.apply(self._sample_count, diff)
        
        self._aggregated_value += damped_correction
        
        # Clamp to bounds
        self._aggregated_value = max(metric_config.min_value, min(metric_config.max_value, self._aggregated_value))
        
        # Check convergence
        self._converged = abs(self._aggregated_value - target) < 0.001
        
        logger.info(f"{self.loop_type.value}: corrected from {self._aggregated_value - damped_correction:.4f} to {self._aggregated_value:.4f}, target={target}")

    def get_aggregated_metric(self) -> Optional[AggregatedMetric]:
        """Get the current aggregated metric."""
        if not self._samples:
            return None
        
        metric_config = self.config.metric_configs.get(self.metric_type, TelemetryMetricConfig(
            metric_type=self.metric_type,
            loop_type=self.loop_type,
        ))
        
        values = [s.value for s in self._samples]
        
        return AggregatedMetric(
            metric_type=self.metric_type,
            current_value=self._aggregated_value,
            target_value=metric_config.target_value,
            aggregated_value=sum(values) / len(values) if values else 0.0,
            sample_count=len(values),
            min_value=min(values) if values else 0.0,
            max_value=max(values) if values else 0.0,
            last_update=self._last_update or datetime.now(timezone.utc),
            damping_factor=self._damping_factor,
            converged=self._converged,
        )

    def reset(self) -> None:
        """Reset the aggregation loop."""
        self._samples.clear()
        self._aggregated_value = 0.0
        self._sample_count = 0
        self._last_update = None
        self._damping_factor = 1.0
        self._converged = False
        self._error = None


class ThroughputStabilizationLoop(TelemetryAggregationLoop):
    """Telemetry loop for throughput stabilization.
    
    Purpose: Bounded operational synthesis for throughput metrics
    
    Requirements:
    - Stabilize throughput to target value
    - Apply exponential damping
    - Bounded oscillation prevention
    """

    def __init__(self, config: TelemetryAggregationConfig) -> None:
        super().__init__(
            loop_type=TelemetryLoopType.THROUGHPUT_STABILIZATION,
            metric_type=TelemetryMetricType.THROUGHPUT,
            config=config,
        )

    def _aggregate_samples(self) -> None:
        """Aggregate throughput samples with specialized logic."""
        if not self._samples:
            return
        
        metric_config = self.config.metric_configs.get(self.metric_type, TelemetryMetricConfig(
            metric_type=self.metric_type,
            loop_type=self.loop_type,
            target_value=100.0,  # Default target throughput
            max_value=1000.0,
        ))
        
        # Calculate weighted average (more recent samples have more weight)
        values = [s.value for s in self._samples]
        weights = [0.1 ** (len(self._samples) - i - 1) for i in range(len(self._samples))]
        weighted_sum = sum(v * w for v, w in zip(values, weights))
        total_weight = sum(weights)
        new_value = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Clamp
        new_value = max(metric_config.min_value, min(metric_config.max_value, new_value))
        
        # Apply damping
        if self._aggregated_value != 0.0:
            diff = new_value - self._aggregated_value
            self._damping_factor = metric_config.damping.apply(self._sample_count, diff)
            self._aggregated_value += diff * self._damping_factor
        else:
            self._aggregated_value = new_value
        
        # Final clamp
        self._aggregated_value = max(metric_config.min_value, min(metric_config.max_value, self._aggregated_value))


class QueueDepthConvergenceLoop(TelemetryAggregationLoop):
    """Telemetry loop for queue depth convergence.
    
    Purpose: Backlog control via bounded convergence
    
    Requirements:
    - Reduce queue depth to target
    - Linear damping for predictable behavior
    - Bounded retries
    """

    def __init__(self, config: TelemetryAggregationConfig) -> None:
        super().__init__(
            loop_type=TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE,
            metric_type=TelemetryMetricType.QUEUE_DEPTH,
            config=config,
        )

    def _aggregate_samples(self) -> None:
        """Aggregate queue depth samples."""
        if not self._samples:
            return
        
        metric_config = self.config.metric_configs.get(self.metric_type, TelemetryMetricConfig(
            metric_type=self.metric_type,
            loop_type=self.loop_type,
            target_value=0.0,  # Target is empty queue
            max_value=10000.0,
        ))
        
        # Use the latest queue state, but keep peak information in the metric payload.
        new_value = self._samples[-1].value
        
        # Clamp
        new_value = max(metric_config.min_value, min(metric_config.max_value, new_value))
        
        # Apply damping
        if self._aggregated_value != 0.0:
            diff = new_value - self._aggregated_value
            # For queue depth, we want faster reduction than increase
            if diff < 0:
                self._damping_factor = metric_config.damping.min_factor
            else:
                self._damping_factor = metric_config.damping.max_factor
            self._aggregated_value += diff * self._damping_factor
        else:
            self._aggregated_value = new_value
        
        # Final clamp
        self._aggregated_value = max(metric_config.min_value, min(metric_config.max_value, self._aggregated_value))


class RuntimeCoolingLoop(TelemetryAggregationLoop):
    """Telemetry loop for runtime saturation stabilization.
    
    Purpose: Saturation stabilization via bounded cooling
    
    Requirements:
    - Cool runtime when saturation is high
    - Exponential backoff-like damping
    - Replay-safe aggregation
    """

    def __init__(self, config: TelemetryAggregationConfig) -> None:
        super().__init__(
            loop_type=TelemetryLoopType.RUNTIME_COOLING,
            metric_type=TelemetryMetricType.RUNTIME_SATURATION,
            config=config,
        )

    def _aggregate_samples(self) -> None:
        """Aggregate runtime saturation samples."""
        if not self._samples:
            return
        
        metric_config = self.config.metric_configs.get(self.metric_type, TelemetryMetricConfig(
            metric_type=self.metric_type,
            loop_type=self.loop_type,
            target_value=0.8,  # Target 80% saturation
            max_value=1.0,
        ))
        
        # Use latest value (saturation is current state)
        new_value = self._samples[-1].value
        
        # Clamp
        new_value = max(metric_config.min_value, min(metric_config.max_value, new_value))
        
        # For saturation, use stronger damping when above target
        target = metric_config.target_value
        if new_value > target:
            # Above target - strong damping
            diff = new_value - target
            damping = metric_config.damping.base ** (self._sample_count * 2)
            self._aggregated_value = target + diff * damping
        else:
            # Below or at target - normal tracking
            self._aggregated_value = new_value
        
        # Final clamp
        self._aggregated_value = max(metric_config.min_value, min(metric_config.max_value, self._aggregated_value))


class CadenceStabilizationLoop(TelemetryAggregationLoop):
    """Telemetry loop for cadence stabilization.
    
    Purpose: Operational smoothness via cadence smoothing
    
    Requirements:
    - Smooth out cadence spikes
    - Threshold-based damping
    - Topology-aware
    """

    def __init__(self, config: TelemetryAggregationConfig) -> None:
        super().__init__(
            loop_type=TelemetryLoopType.CADENCE_STABILIZATION,
            metric_type=TelemetryMetricType.CADENCE,
            config=config,
        )

    def _aggregate_samples(self) -> None:
        """Aggregate cadence samples."""
        if not self._samples:
            return
        
        metric_config = self.config.metric_configs.get(self.metric_type, TelemetryMetricConfig(
            metric_type=self.metric_type,
            loop_type=self.loop_type,
            target_value=10.0,  # Target cadence
            max_value=100.0,
        ))
        
        # Use harmonic mean for cadence (smooth out bursts)
        values = [s.value for s in self._samples if s.value > 0]
        if not values:
            return
        
        harmonic_mean = len(values) / sum(1.0 / v for v in values)
        
        # Clamp
        new_value = max(metric_config.min_value, min(metric_config.max_value, harmonic_mean))
        
        # Apply threshold damping
        diff = new_value - self._aggregated_value
        if abs(diff) < metric_config.damping.threshold:
            # Below threshold - no change
            pass
        else:
            # Above threshold - apply damping
            if self._aggregated_value != 0.0:
                self._aggregated_value += diff * metric_config.damping.base
            else:
                self._aggregated_value = new_value
        
        # Final clamp
        self._aggregated_value = max(metric_config.min_value, min(metric_config.max_value, self._aggregated_value))


class DensityConvergenceLoop(TelemetryAggregationLoop):
    """Telemetry loop for topology density convergence.
    
    Purpose: topology calmness via density convergence
    
    Requirements:
    - Reduce topology density when too high
    - Hysteresis damping
    - Replay-safe
    """

    def __init__(self, config: TelemetryAggregationConfig) -> None:
        super().__init__(
            loop_type=TelemetryLoopType.DENSITY_CONVERGENCE,
            metric_type=TelemetryMetricType.DENSITY,
            config=config,
        )
        # Hysteresis state
        self._rising: bool = False
        self._falling: bool = False

    def _aggregate_samples(self) -> None:
        """Aggregate density samples with hysteresis."""
        if not self._samples:
            return
        
        metric_config = self.config.metric_configs.get(self.metric_type, TelemetryMetricConfig(
            metric_type=self.metric_type,
            loop_type=self.loop_type,
            target_value=0.5,  # Target density
            max_value=1.0,
        ))
        
        # Use geometric mean for density
        values = [max(0.001, s.value) for s in self._samples]
        product = 1.0
        for v in values:
            product *= v
        geometric_mean = product ** (1.0 / len(values))
        
        new_value = max(metric_config.min_value, min(metric_config.max_value, geometric_mean))
        
        # Hysteresis: different thresholds for rising vs falling
        target = metric_config.target_value
        upper_threshold = target * 1.2  # Allow 20% above before acting
        lower_threshold = target * 0.8  # Allow 20% below before acting
        
        if self._aggregated_value < upper_threshold and new_value >= upper_threshold:
            self._rising = False
            self._falling = True
        elif self._aggregated_value > lower_threshold and new_value <= lower_threshold:
            self._rising = True
            self._falling = False
        
        # Apply different damping based on direction
        if self._rising:
            # Rising density - apply stronger damping
            damping_factor = metric_config.damping.base ** 2
        elif self._falling:
            # Falling density - apply weaker damping
            damping_factor = metric_config.damping.base ** 0.5
        else:
            # Stable - normal damping
            damping_factor = metric_config.damping.base
        
        if self._aggregated_value != 0.0:
            self._aggregated_value += (new_value - self._aggregated_value) * damping_factor
        else:
            self._aggregated_value = new_value
        
        # Final clamp
        self._aggregated_value = max(metric_config.min_value, min(metric_config.max_value, self._aggregated_value))


class TelemetryReconciliationController:
    """Main controller for telemetry reconciliation.
    
    Orchestrates:
    - Throughput stabilization loop
    - Queue depth convergence loop
    - Runtime cooling loop
    - Cadence stabilization loop
    - Density convergence loop
    
    Requirements:
    - Backend-agnostic
    - Normalized telemetry
    - Replay-safe
    - Bounded oscillation
    - Topology-aware
    """

    def __init__(
        self,
        config: TelemetryAggregationConfig,
        enabled_loops: Optional[Set[TelemetryLoopType]] = None,
    ) -> None:
        self.config = config
        self._enabled_loops = enabled_loops or set(TelemetryLoopType)
        
        # Initialize loops
        self._loops: Dict[TelemetryLoopType, TelemetryAggregationLoop] = {}
        
        if TelemetryLoopType.THROUGHPUT_STABILIZATION in self._enabled_loops:
            self._loops[TelemetryLoopType.THROUGHPUT_STABILIZATION] = ThroughputStabilizationLoop(config)
        
        if TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE in self._enabled_loops:
            self._loops[TelemetryLoopType.QUEUE_DEPTH_CONVERGENCE] = QueueDepthConvergenceLoop(config)
        
        if TelemetryLoopType.RUNTIME_COOLING in self._enabled_loops:
            self._loops[TelemetryLoopType.RUNTIME_COOLING] = RuntimeCoolingLoop(config)
        
        if TelemetryLoopType.CADENCE_STABILIZATION in self._enabled_loops:
            self._loops[TelemetryLoopType.CADENCE_STABILIZATION] = CadenceStabilizationLoop(config)
        
        if TelemetryLoopType.DENSITY_CONVERGENCE in self._enabled_loops:
            self._loops[TelemetryLoopType.DENSITY_CONVERGENCE] = DensityConvergenceLoop(config)
        
        self._running = False
        self._sequence = 0

    @property
    def running(self) -> bool:
        return self._running

    @property
    def loops(self) -> Dict[TelemetryLoopType, TelemetryAggregationLoop]:
        return dict(self._loops)

    def start(self) -> None:
        """Start all telemetry loops."""
        self._running = True
        for loop in self._loops.values():
            loop.reset()
        logger.info("Telemetry reconciliation controller started")

    def stop(self) -> None:
        """Stop all telemetry loops."""
        self._running = False
        for loop in self._loops.values():
            loop.reset()
        logger.info("Telemetry reconciliation controller stopped")

    def receive_samples(self, samples: List[TelemetrySample]) -> None:
        """Receive telemetry samples for processing."""
        for sample in samples:
            for loop in self._loops.values():
                if loop.metric_type == sample.metric_type:
                    loop.receive_sample(sample)

    def get_metrics(self) -> Dict[TelemetryMetricType, Optional[AggregatedMetric]]:
        """Get all aggregated metrics."""
        result = {}
        for loop in self._loops.values():
            metric = loop.get_aggregated_metric()
            if metric:
                result[metric.metric_type] = metric
        return result

    def set_target(self, metric_type: TelemetryMetricType, target: float) -> None:
        """Set target value for a metric."""
        # Update metric config
        loop = next((l for l in self._loops.values() if l.metric_type == metric_type), None)
        if loop:
            # Create updated config
            old_config = loop.config
            updated_config = TelemetryAggregationConfig(
                cadence=old_config.cadence,
                damping=old_config.damping,
                retry=old_config.retry,
                convergence=old_config.convergence,
                metric_configs={**old_config.metric_configs,
                    metric_type: TelemetryMetricConfig(
                        metric_type=metric_type,
                        loop_type=loop.loop_type,
                        target_value=target,
                        damping_type=old_config.metric_configs.get(metric_type, TelemetryMetricConfig(
                            metric_type=metric_type,
                            loop_type=loop.loop_type,
                        )).damping_type,
                        min_value=0.0,
                        max_value=1000.0,
                        enabled=True,
                    )},
                enabled=old_config.enabled,
                workspace_id=old_config.workspace_id,
            )
            loop.config = updated_config
            logger.info(f"Set target for {metric_type.value}: {target}")

    def apply_corrections(self) -> None:
        """Apply corrections for all loops."""
        for loop in self._loops.values():
            metric_config = self.config.metric_configs.get(loop.metric_type, TelemetryMetricConfig(
                metric_type=loop.metric_type,
                loop_type=loop.loop_type,
                max_value=1000.0,
            ))
            loop.apply_correction(metric_config.target_value)

    def get_health_state(self) -> Dict[str, Any]:
        """Get health state for all loops."""
        health = {}
        for loop_type, loop in self._loops.items():
            health[loop_type.value] = {
                'schema_version': SCHEMA_VERSION,
                'status': 'running' if self._running else 'stopped',
                'metric_type': loop.metric_type.value,
                'aggregated_value': loop.aggregated_value,
                'sample_count': loop.sample_count,
                'converged': loop.converged,
                'error': loop.error,
            }
        return health

    async def run_once(self) -> None:
        """Run one iteration of all telemetry loops."""
        if not self._running:
            return
        
        self._sequence += 1
        
        # Apply corrections
        self.apply_corrections()
        
        # Check for convergence
        all_converged = all(loop.converged for loop in self._loops.values())
        if all_converged and self._sequence > 10:  # Only check after initial samples
            logger.info("All telemetry loops converged")


__all__ = [
    # Schema
    'SCHEMA_VERSION',
    # Enums
    'TelemetryLoopType',
    'TelemetryMetricType',
    # Config types
    'TelemetryMetricConfig',
    'TelemetryAggregationConfig',
    # Data types
    'TelemetrySample',
    'AggregatedMetric',
    # Loop implementations
    'TelemetryAggregationLoop',
    'ThroughputStabilizationLoop',
    'QueueDepthConvergenceLoop',
    'RuntimeCoolingLoop',
    'CadenceStabilizationLoop',
    'DensityConvergenceLoop',
    # Controller
    'TelemetryReconciliationController',
    # Constants
    'DEFAULT_TELEMETRY_CADENCE_MIN',
    'DEFAULT_TELEMETRY_CADENCE_MAX',
    'DEFAULT_TELEMETRY_MAX_ITERATIONS',
]
