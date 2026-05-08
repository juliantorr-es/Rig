"""Runtime Benchmarking & Telemetry Module for Rig.

Phase 2: Runtime & Agent Execution Plane - Benchmarking & Telemetry.

Core doctrine:
- Runtime output is advisory evidence only
- Only receipts/proposals become authoritative evidence
- UI streams projections, NOT raw subprocesses
- All runtime execution remains advisory-only
- NO autonomous apply, direct workspace mutation, hidden execution, background daemons,
  cloud orchestration, production networking, real API keys, or destructive Git commands

This module provides benchmarking, telemetry, and performance tracking for runtime
infrastructure. All metrics are collected in a read-only, advisory-only manner.

See docs/architecture/runtime-streaming.md for the canonical streaming architecture.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime_stream import RuntimeStreamEvent
    from rig.domain.runtime_supervisor import RuntimeSupervisor
    from rig.domain.runtime_projection import RuntimeStreamProjection
    from rig.domain.runtime_websocket import WebSocketStreamMessage
    from rig.domain.runtime_replay import RuntimeReplayEngine

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLACEHOLDER_BENCHMARK_ID = "BENCHMARK_ID_PLACEHOLDER"
PLACEHOLDER_METRIC_ID = "METRIC_ID_PLACEHOLDER"
PLACEHOLDER_SESSION_ID = "SESSION_ID_PLACEHOLDER"
PLACEHOLDER_TRACE_ID = "TRACE_ID_PLACEHOLDER"
PLACEHOLDER_SPAN_ID = "SPAN_ID_PLACEHOLDER"

# Default metrics settings
DEFAULT_METRICS_WINDOW_SECONDS = 60
DEFAULT_METRICS_RETENTION_SECONDS = 3600
DEFAULT_METRICS_CARDINALITY_LIMIT = 1000
DEFAULT_METRICS_FLUSH_INTERVAL_SECONDS = 10
DEFAULT_METRICS_BATCH_SIZE = 100

# Benchmark defaults
DEFAULT_BENCHMARK_ITERATIONS = 100
DEFAULT_BENCHMARK_WARMUP_ITERATIONS = 10
DEFAULT_BENCHMARK_TIMEOUT_SECONDS = 60
DEFAULT_BENCHMARK_SAMPLE_SIZE = 1000

# Thresholds
DEFAULT_LATENCY_WARNING_MS = 100.0
DEFAULT_LATENCY_ERROR_MS = 1000.0
DEFAULT_THROUGHPUT_WARNING_PER_SEC = 10.0
DEFAULT_THROUGHPUT_ERROR_PER_SEC = 1.0

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RuntimeMetricKind(Enum):
    """Kinds of runtime metrics."""

    # Counter: monotonically increasing values
    COUNTER = "counter"

    # Gauge: point-in-time values
    GAUGE = "gauge"

    # Histogram: distribution of values
    HISTOGRAM = "histogram"

    # Summary: statistics over observations
    SUMMARY = "summary"

    # Timing: latency measurements
    TIMING = "timing"

    # Rate: events per time unit
    RATE = "rate"

    # Resource: resource usage (CPU, memory, etc.)
    RESOURCE = "resource"


class RuntimeMetricCategory(Enum):
    """Categories for runtime metrics."""

    STREAM = "stream"  # Stream event metrics
    PROJECTION = "projection"  # Projection pipeline metrics
    WEBSOCKET = "websocket"  # WebSocket metrics
    REPLAY = "replay"  # Replay metrics
    SUPERVISOR = "supervisor"  # Process supervision metrics
    SYSTEM = "system"  # System metrics
    BENCHMARK = "benchmark"  # Benchmark metrics
    CUSTOM = "custom"  # Custom metrics


class RuntimeMetricSeverity(Enum):
    """Severity levels for metric alerts."""

    INFO = "info"
    DEBUG = "debug"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RuntimeBenchmarkKind(Enum):
    """Kinds of benchmarks."""

    THROUGHPUT = "throughput"  # Events/second processing
    LATENCY = "latency"  # End-to-end latency
    MEMORY = "memory"  # Memory usage
    CPU = "cpu"  # CPU usage
    STARTUP = "startup"  # Startup time
    SHUTDOWN = "shutdown"  # Shutdown time
    SERIALIZATION = "serialization"  # Serialization performance
    PROJECTION = "projection"  # Projection generation performance
    REPLAY = "replay"  # Replay performance
    WEBSOCKET = "websocket"  # WebSocket performance


class RuntimeBenchmarkStatus(Enum):
    """Status of a benchmark run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class RuntimeTelemetryLevel(Enum):
    """Levels of telemetry collection."""

    NONE = "none"  # No telemetry
    MINIMAL = "minimal"  # Basic metrics only
    STANDARD = "standard"  # Standard metrics
    DETAILED = "detailed"  # All metrics with detailed breakdowns
    DEBUG = "debug"  # Full debug-level telemetry


class RuntimeSamplingStrategy(Enum):
    """Sampling strategies for metrics."""

    ALL = "all"  # Sample all events
    HEAD = "head"  # Sample first N
    TAIL = "tail"  # Sample last N
    RANDOM = "random"  # Random sampling
    THROTTLED = "throttled"  # Throttled sampling
    PERCENTAGE = "percentage"  # Percentage-based sampling


# ---------------------------------------------------------------------------
# Metric Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeMetricDimension:
    """A dimension for metric categorization.

    Dimensions allow metrics to be categorized by various attributes
    (e.g., by provider, by model, by event type, by channel).
    """

    name: str = ""
    value: str = ""

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(cls, name: str, value: str) -> "RuntimeMetricDimension":
        """Factory method."""
        return cls(name=name, value=value)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True, slots=True)
class RuntimeMetricMetadata:
    """Metadata for a runtime metric."""

    metric_id: str = PLACEHOLDER_METRIC_ID
    name: str = ""
    description: str = ""
    kind: RuntimeMetricKind = RuntimeMetricKind.COUNTER
    category: RuntimeMetricCategory = RuntimeMetricCategory.CUSTOM
    unit: str = ""
    base_unit: str = ""
    rate_unit: str = ""

    # Collection settings
    enabled: bool = True
    interval_seconds: float = 0  # 0 means collect on every event
    timeout_seconds: float = DEFAULT_METRICS_WINDOW_SECONDS
    retention_seconds: float = DEFAULT_METRICS_RETENTION_SECONDS

    # Sampling
    sampling_strategy: RuntimeSamplingStrategy = RuntimeSamplingStrategy.ALL
    sampling_rate: float = 1.0
    sampling_size: int = 0

    # Alerting
    warning_threshold: Optional[float] = None
    error_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None

    # Tags
    tags: Set[str] = field(default_factory=set)

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        metric_id: str,
        name: str,
        description: str = "",
        kind: RuntimeMetricKind = RuntimeMetricKind.COUNTER,
        category: RuntimeMetricCategory = RuntimeMetricCategory.CUSTOM,
        unit: str = "",
        base_unit: str = "",
        rate_unit: str = "",
        enabled: bool = True,
        interval_seconds: float = 0,
        timeout_seconds: float = DEFAULT_METRICS_WINDOW_SECONDS,
        retention_seconds: float = DEFAULT_METRICS_RETENTION_SECONDS,
        sampling_strategy: RuntimeSamplingStrategy = RuntimeSamplingStrategy.ALL,
        sampling_rate: float = 1.0,
        sampling_size: int = 0,
        warning_threshold: Optional[float] = None,
        error_threshold: Optional[float] = None,
        critical_threshold: Optional[float] = None,
        tags: Optional[Set[str]] = None,
    ) -> "RuntimeMetricMetadata":
        """Factory method."""
        return cls(
            metric_id=metric_id,
            name=name,
            description=description,
            kind=kind,
            category=category,
            unit=unit,
            base_unit=base_unit,
            rate_unit=rate_unit,
            enabled=enabled,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            retention_seconds=retention_seconds,
            sampling_strategy=sampling_strategy,
            sampling_rate=sampling_rate,
            sampling_size=sampling_size,
            warning_threshold=warning_threshold,
            error_threshold=error_threshold,
            critical_threshold=critical_threshold,
            tags=tags or set(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind.value,
            "category": self.category.value,
            "unit": self.unit,
            "base_unit": self.base_unit,
            "rate_unit": self.rate_unit,
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "retention_seconds": self.retention_seconds,
            "sampling_strategy": self.sampling_strategy.value,
            "sampling_rate": self.sampling_rate,
            "sampling_size": self.sampling_size,
            "warning_threshold": self.warning_threshold,
            "error_threshold": self.error_threshold,
            "critical_threshold": self.critical_threshold,
            "tags": list(self.tags),
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True, slots=True)
class RuntimeMetricDataPoint:
    """A single data point for a metric."""

    metric_id: str = PLACEHOLDER_METRIC_ID
    timestamp: str = ""
    value: float = 0.0

    # Dimensions
    dimensions: Tuple[RuntimeMetricDimension, ...] = field(default=())

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        metric_id: str,
        timestamp: Optional[str] = None,
        value: float = 0.0,
        dimensions: Optional[List[RuntimeMetricDimension]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeMetricDataPoint":
        """Factory method."""
        return cls(
            metric_id=metric_id,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            value=value,
            dimensions=tuple(dimensions or []),
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_id": self.metric_id,
            "timestamp": self.timestamp,
            "value": self.value,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "metadata": self.metadata,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True, slots=True)
class RuntimeHistogramData:
    """Histogram data for a metric."""

    metric_id: str = PLACEHOLDER_METRIC_ID
    timestamp: str = ""

    # Counts at each bucket boundary
    counts: Dict[float, int] = field(default_factory=dict)
    sum: float = 0.0
    count: int = 0

    # Buckets
    bucket_boundaries: Tuple[float, ...] = field(default=())

    # Statistics
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None

    # Percentiles
    percentiles: Dict[float, float] = field(default_factory=dict)

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        metric_id: str,
        timestamp: Optional[str] = None,
        counts: Optional[Dict[float, int]] = None,
        sum_value: float = 0.0,
        count: int = 0,
        bucket_boundaries: Optional[List[float]] = None,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        mean_value: Optional[float] = None,
        percentiles: Optional[Dict[float, float]] = None,
    ) -> "RuntimeHistogramData":
        """Factory method."""
        return cls(
            metric_id=metric_id,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            counts=counts or {},
            sum=sum_value,
            count=count,
            bucket_boundaries=tuple(bucket_boundaries or []),
            min=min_value,
            max=max_value,
            mean=mean_value,
            percentiles=percentiles or {},
        )

    @property
    def total_count(self) -> int:
        """Total count of observations."""
        return self.count

    @property
    def total_sum(self) -> float:
        """Total sum of observations."""
        return self.sum

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_id": self.metric_id,
            "timestamp": self.timestamp,
            "counts": self.counts,
            "sum": self.sum,
            "count": self.count,
            "bucket_boundaries": list(self.bucket_boundaries),
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "percentiles": self.percentiles,
            "total_count": self.total_count,
            "total_sum": self.total_sum,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True, slots=True)
class RuntimeSummaryData:
    """Summary data for a metric."""

    metric_id: str = PLACEHOLDER_METRIC_ID
    timestamp: str = ""

    # Statistics
    count: int = 0
    sum: float = 0.0
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None

    # Quantiles
    quantiles: Dict[float, float] = field(default_factory=dict)

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        metric_id: str,
        timestamp: Optional[str] = None,
        count: int = 0,
        sum_value: float = 0.0,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        mean_value: Optional[float] = None,
        quantiles: Optional[Dict[float, float]] = None,
    ) -> "RuntimeSummaryData":
        """Factory method."""
        return cls(
            metric_id=metric_id,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            count=count,
            sum=sum_value,
            min=min_value,
            max=max_value,
            mean=mean_value,
            quantiles=quantiles or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_id": self.metric_id,
            "timestamp": self.timestamp,
            "count": self.count,
            "sum": self.sum,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "quantiles": self.quantiles,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True, slots=True)
class RuntimeMetricAlert:
    """An alert triggered by a metric threshold."""

    alert_id: str = PLACEHOLDER_METRIC_ID
    metric_id: str = PLACEHOLDER_METRIC_ID
    timestamp: str = ""

    # Status
    severity: RuntimeMetricSeverity = RuntimeMetricSeverity.INFO
    status: str = "firing"  # firing, resolved, acknowledged
    resolved_at: Optional[str] = None

    # Values
    current_value: float = 0.0
    threshold_value: float = 0.0
    threshold_type: str = "warning"  # warning, error, critical

    # Metadata
    message: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        metric_id: str,
        severity: RuntimeMetricSeverity,
        current_value: float,
        threshold_value: float,
        threshold_type: str = "warning",
        message: str = "",
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeMetricAlert":
        """Factory method."""
        alert_id = hashlib.sha256(f"{metric_id}_{severity.value}_{current_value}".encode()).hexdigest()[:16]
        return cls(
            alert_id=f"alert_{alert_id}",
            metric_id=metric_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            severity=severity,
            current_value=current_value,
            threshold_value=threshold_value,
            threshold_type=threshold_type,
            message=message,
            description=description,
            metadata=metadata or {},
        )

    def resolve(self) -> "RuntimeMetricAlert":
        """Mark the alert as resolved."""
        return RuntimeMetricAlert(
            **asdict(self),
            status="resolved",
            resolved_at=datetime.now(timezone.utc).isoformat(),
        )

    def ack(self) -> "RuntimeMetricAlert":
        """Mark the alert as acknowledged."""
        return RuntimeMetricAlert(
            **asdict(self),
            status="acknowledged",
        )

    @property
    def is_firing(self) -> bool:
        """Check if alert is firing."""
        return self.status == "firing"

    @property
    def is_resolved(self) -> bool:
        """Check if alert is resolved."""
        return self.status == "resolved"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "metric_id": self.metric_id,
            "timestamp": self.timestamp,
            "severity": self.severity.value,
            "status": self.status,
            "resolved_at": self.resolved_at,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "threshold_type": self.threshold_type,
            "message": self.message,
            "description": self.description,
            "metadata": self.metadata,
            "is_firing": self.is_firing,
            "is_resolved": self.is_resolved,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


# ---------------------------------------------------------------------------
# Benchmark Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeBenchmarkConfiguration:
    """Configuration for a benchmark run."""

    benchmark_id: str = PLACEHOLDER_BENCHMARK_ID
    name: str = ""
    description: str = ""
    kind: RuntimeBenchmarkKind = RuntimeBenchmarkKind.THROUGHPUT

    # Execution settings
    iterations: int = DEFAULT_BENCHMARK_ITERATIONS
    warmup_iterations: int = DEFAULT_BENCHMARK_WARMUP_ITERATIONS
    timeout_seconds: float = DEFAULT_BENCHMARK_TIMEOUT_SECONDS
    sample_size: int = DEFAULT_BENCHMARK_SAMPLE_SIZE

    # Parameters
    parameters: Dict[str, Any] = field(default_factory=dict)

    # Tags
    tags: Set[str] = field(default_factory=set)

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        benchmark_id: str,
        name: str,
        description: str = "",
        kind: RuntimeBenchmarkKind = RuntimeBenchmarkKind.THROUGHPUT,
        iterations: int = DEFAULT_BENCHMARK_ITERATIONS,
        warmup_iterations: int = DEFAULT_BENCHMARK_WARMUP_ITERATIONS,
        timeout_seconds: float = DEFAULT_BENCHMARK_TIMEOUT_SECONDS,
        sample_size: int = DEFAULT_BENCHMARK_SAMPLE_SIZE,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[Set[str]] = None,
    ) -> "RuntimeBenchmarkConfiguration":
        """Factory method."""
        return cls(
            benchmark_id=benchmark_id,
            name=name,
            description=description,
            kind=kind,
            iterations=iterations,
            warmup_iterations=warmup_iterations,
            timeout_seconds=timeout_seconds,
            sample_size=sample_size,
            parameters=parameters or {},
            tags=tags or set(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "benchmark_id": self.benchmark_id,
            "name": self.name,
            "description": self.description,
            "kind": self.kind.value,
            "iterations": self.iterations,
            "warmup_iterations": self.warmup_iterations,
            "timeout_seconds": self.timeout_seconds,
            "sample_size": self.sample_size,
            "parameters": self.parameters,
            "tags": list(self.tags),
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


@dataclass(slots=True)
class RuntimeBenchmarkResult:
    """Result of a benchmark run."""

    benchmark_id: str = PLACEHOLDER_BENCHMARK_ID
    session_id: str = PLACEHOLDER_SESSION_ID
    run_id: str = PLACEHOLDER_BENCHMARK_ID

    # Status
    status: RuntimeBenchmarkStatus = RuntimeBenchmarkStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # Configuration
    configuration: Optional[RuntimeBenchmarkConfiguration] = None

    # measurements
    measurements: List[float] = field(default_factory=list)
    warmup_measurements: List[float] = field(default_factory=list)

    # Statistics
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std_dev: Optional[float] = None

    # Percentiles
    percentiles: Dict[float, float] = field(default_factory=dict)

    # Derived metrics
    throughput_per_sec: Optional[float] = None
    latency_ms: Optional[float] = None
    memory_bytes: Optional[int] = None
    cpu_percent: Optional[float] = None

    # Error info
    error_message: Optional[str] = None
    error_count: int = 0

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        benchmark_id: str,
        session_id: str = PLACEHOLDER_SESSION_ID,
        configuration: Optional[RuntimeBenchmarkConfiguration] = None,
        measurements: Optional[List[float]] = None,
        warmup_measurements: Optional[List[float]] = None,
    ) -> "RuntimeBenchmarkResult":
        """Factory method."""
        now = datetime.now(timezone.utc).isoformat()
        run_id = hashlib.sha256(f"{benchmark_id}_{now}".encode()).hexdigest()[:16]
        return cls(
            benchmark_id=benchmark_id,
            session_id=session_id,
            run_id=f"run_{run_id}",
            configuration=configuration,
            measurements=measurements or [],
            warmup_measurements=warmup_measurements or [],
            started_at=now,
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration in seconds."""
        if self.started_at and self.completed_at:
            start = datetime.fromisoformat(self.started_at.replace('Z', '+00:00'))
            end = datetime.fromisoformat(self.completed_at.replace('Z', '+00:00'))
            return (end - start).total_seconds()
        return None

    @property
    def sample_count(self) -> int:
        """Number of samples collected (excluding warmup)."""
        return len(self.measurements)

    @property
    def total_count(self) -> int:
        """Total number of measurements (including warmup)."""
        return len(self.measurements) + len(self.warmup_measurements)

    @property
    def is_complete(self) -> bool:
        """Check if benchmark is complete."""
        return self.status == RuntimeBenchmarkStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if benchmark failed."""
        return self.status in (
            RuntimeBenchmarkStatus.FAILED,
            RuntimeBenchmarkStatus.TIMEOUT,
            RuntimeBenchmarkStatus.CANCELLED,
        )

    def compute_statistics(self) -> "RuntimeBenchmarkResult":
        """Compute statistics from measurements."""
        if not self.measurements:
            return self

        sorted_measurements = sorted(self.measurements)
        
        new_min = min(sorted_measurements)
        new_max = max(sorted_measurements)
        new_mean = sum(sorted_measurements) / len(sorted_measurements)
        
        # Median
        n = len(sorted_measurements)
        if n % 2 == 0:
            new_median = (sorted_measurements[n // 2 - 1] + sorted_measurements[n // 2]) / 2
        else:
            new_median = sorted_measurements[n // 2]

        # Std dev
        if len(sorted_measurements) > 1:
            variance = sum((x - new_mean) ** 2 for x in sorted_measurements) / (len(sorted_measurements) - 1)
            new_std_dev = variance ** 0.5
        else:
            new_std_dev = 0.0

        # Percentiles
        new_percentiles: Dict[float, float] = {}
        for p in [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 0.999]:
            idx = int(p * len(sorted_measurements))
            idx = min(idx, len(sorted_measurements) - 1)
            new_percentiles[p] = sorted_measurements[idx]

        now = datetime.now(timezone.utc).isoformat()
        return RuntimeBenchmarkResult(
            **asdict(self),
            min=new_min,
            max=new_max,
            mean=new_mean,
            median=new_median,
            std_dev=new_std_dev,
            percentiles=new_percentiles,
            completed_at=now,
            status=RuntimeBenchmarkStatus.COMPLETED,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result: Dict[str, Any] = {
            "benchmark_id": self.benchmark_id,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "measurements": self.measurements,
            "warmup_measurements": self.warmup_measurements,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "median": self.median,
            "std_dev": self.std_dev,
            "percentiles": self.percentiles,
            "throughput_per_sec": self.throughput_per_sec,
            "latency_ms": self.latency_ms,
            "memory_bytes": self.memory_bytes,
            "cpu_percent": self.cpu_percent,
            "error_message": self.error_message,
            "error_count": self.error_count,
            "sample_count": self.sample_count,
            "total_count": self.total_count,
            "duration_seconds": self.duration_seconds,
            "is_complete": self.is_complete,
            "is_failed": self.is_failed,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }
        if self.configuration:
            result["configuration"] = self.configuration.to_dict()
        return result


@dataclass(frozen=True, slots=True)
class RuntimeBenchmarkComparison:
    """Comparison between multiple benchmark runs."""

    comparison_id: str = PLACEHOLDER_BENCHMARK_ID
    benchmark_id: str = PLACEHOLDER_BENCHMARK_ID
    run_ids: List[str] = field(default_factory=list)

    # Comparison data
    runs: Dict[str, RuntimeBenchmarkResult] = field(default_factory=dict)

    # Aggregated metrics
    baseline_mean: Optional[float] = None
    baseline_std_dev: Optional[float] = None
    comparison_mean: Optional[float] = None
    comparison_std_dev: Optional[float] = None

    # Difference
    difference: Optional[float] = None
    difference_percent: Optional[float] = None

    # Timing
    generated_at: str = ""

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        benchmark_id: str,
        run_ids: List[str],
        runs: Dict[str, RuntimeBenchmarkResult],
    ) -> "RuntimeBenchmarkComparison":
        """Factory method."""
        now = datetime.now(timezone.utc).isoformat()
        comparison_id = hashlib.sha256(f"{benchmark_id}_{'_'.join(run_ids)}".encode()).hexdigest()[:16]

        # Calculate aggregated metrics
        baseline_runs = {k: v for k, v in runs.items() if k in run_ids[:1]}
        comparison_runs = {k: v for k, v in runs.items() if k in run_ids[1:]}

        baseline_means = [r.mean for r in baseline_runs.values() if r.mean is not None]
        comparison_means = [r.mean for r in comparison_runs.values() if r.mean is not None]

        baseline_mean = statistics.mean(baseline_means) if baseline_means else None
        comparison_mean = statistics.mean(comparison_means) if comparison_means else None

        if baseline_mean is not None and comparison_mean is not None:
            difference = comparison_mean - baseline_mean
            difference_percent = (difference / baseline_mean * 100) if baseline_mean != 0 else None
        else:
            difference = None
            difference_percent = None

        return cls(
            comparison_id=f"comp_{comparison_id}",
            benchmark_id=benchmark_id,
            run_ids=run_ids,
            runs=runs,
            baseline_mean=baseline_mean,
            comparison_mean=comparison_mean,
            difference=difference,
            difference_percent=difference_percent,
            generated_at=now,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "comparison_id": self.comparison_id,
            "benchmark_id": self.benchmark_id,
            "run_ids": self.run_ids,
            "runs": {k: v.to_dict() for k, v in self.runs.items()},
            "baseline_mean": self.baseline_mean,
            "comparison_mean": self.comparison_mean,
            "difference": self.difference,
            "difference_percent": self.difference_percent,
            "generated_at": self.generated_at,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True, slots=True)
class RuntimeTelemetryConfiguration:
    """Configuration for telemetry collection."""

    level: RuntimeTelemetryLevel = RuntimeTelemetryLevel.STANDARD
    enabled: bool = True
    flush_interval_seconds: float = DEFAULT_METRICS_FLUSH_INTERVAL_SECONDS
    batch_size: int = DEFAULT_METRICS_BATCH_SIZE

    # Cardinality limits
    max_metrics: int = DEFAULT_METRICS_CARDINALITY_LIMIT
    max_dimensions_per_metric: int = 10
    max_tags: int = 100

    # What to collect
    collect_stream_metrics: bool = True
    collect_projection_metrics: bool = True
    collect_websocket_metrics: bool = True
    collect_replay_metrics: bool = True
    collect_supervisor_metrics: bool = True
    collect_system_metrics: bool = True
    collect_benchmark_metrics: bool = True

    # Sampling
    sampling_strategy: RuntimeSamplingStrategy = RuntimeSamplingStrategy.ALL
    sampling_rate: float = 1.0

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        level: RuntimeTelemetryLevel = RuntimeTelemetryLevel.STANDARD,
        enabled: bool = True,
        flush_interval_seconds: float = DEFAULT_METRICS_FLUSH_INTERVAL_SECONDS,
        batch_size: int = DEFAULT_METRICS_BATCH_SIZE,
        max_metrics: int = DEFAULT_METRICS_CARDINALITY_LIMIT,
        **kwargs: Any,
    ) -> "RuntimeTelemetryConfiguration":
        """Factory method."""
        return cls(
            level=level,
            enabled=enabled,
            flush_interval_seconds=flush_interval_seconds,
            batch_size=batch_size,
            max_metrics=max_metrics,
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "enabled": self.enabled,
            "flush_interval_seconds": self.flush_interval_seconds,
            "batch_size": self.batch_size,
            "max_metrics": self.max_metrics,
            "max_dimensions_per_metric": self.max_dimensions_per_metric,
            "max_tags": self.max_tags,
            "collect_stream_metrics": self.collect_stream_metrics,
            "collect_projection_metrics": self.collect_projection_metrics,
            "collect_websocket_metrics": self.collect_websocket_metrics,
            "collect_replay_metrics": self.collect_replay_metrics,
            "collect_supervisor_metrics": self.collect_supervisor_metrics,
            "collect_system_metrics": self.collect_system_metrics,
            "collect_benchmark_metrics": self.collect_benchmark_metrics,
            "sampling_strategy": self.sampling_strategy.value,
            "sampling_rate": self.sampling_rate,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


# ---------------------------------------------------------------------------
# Telemetry Collector
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeMetricsCollector:
    """Collector for runtime metrics.

    Collects, stores, and aggregates metrics from runtime components.
    All metrics are advisory-only and read-only.
    """

    session_id: str = PLACEHOLDER_SESSION_ID
    started_at: str = ""

    # Configuration
    config: RuntimeTelemetryConfiguration = field(default_factory=RuntimeTelemetryConfiguration)

    # Registered metrics
    metrics: Dict[str, RuntimeMetricMetadata] = field(default_factory=dict)

    # Collected data (by metric_id -> list of timestamps -> values/dimensions)
    counter_values: Dict[str, Dict[str, float]] = field(default_factory=dict)
    gauge_values: Dict[str, Dict[str, float]] = field(default_factory=dict)
    histogram_data: Dict[str, List[RuntimeHistogramData]] = field(default_factory=dict)
    summary_data: Dict[str, List[RuntimeSummaryData]] = field(default_factory=dict)
    timing_values: Dict[str, List[float]] = field(default_factory=dict)

    # Alerts
    alerts: Dict[str, RuntimeMetricAlert] = field(default_factory=dict)
    alert_history: List[RuntimeMetricAlert] = field(default_factory=list)

    # Statistics
    metrics_collected: int = 0
    metrics_dropped: int = 0
    last_flush_at: Optional[str] = None

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        session_id: str = PLACEHOLDER_SESSION_ID,
        config: Optional[RuntimeTelemetryConfiguration] = None,
    ) -> "RuntimeMetricsCollector":
        """Factory method."""
        return cls(
            session_id=session_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            config=config or RuntimeTelemetryConfiguration(),
        )

    def with_metric(
        self,
        metric_id: str,
        name: str,
        description: str = "",
        kind: RuntimeMetricKind = RuntimeMetricKind.COUNTER,
        category: RuntimeMetricCategory = RuntimeMetricCategory.CUSTOM,
        **kwargs: Any,
    ) -> "RuntimeMetricsCollector":
        """Add a metric to the collector."""
        new_metrics = dict(self.metrics)
        new_metrics[metric_id] = RuntimeMetricMetadata.create(
            metric_id=metric_id,
            name=name,
            description=description,
            kind=kind,
            category=category,
            **kwargs,
        )
        return RuntimeMetricsCollector(
            **{**asdict(self), "metrics": new_metrics},
        )

    def record_counter(
        self,
        metric_id: str,
        value: float = 1.0,
        timestamp: Optional[str] = None,
        dimensions: Optional[List[RuntimeMetricDimension]] = None,
    ) -> "RuntimeMetricsCollector":
        """Record a counter value."""
        if not self.config.enabled:
            return self

        ts = timestamp or datetime.now(timezone.utc).isoformat()
        new_counters = dict(self.counter_values)
        
        if metric_id not in new_counters:
            new_counters[metric_id] = {}
        
        timestamp_variables = new_counters[metric_id]
        # For counters, we add the value
        timestamp_variables[ts] = timestamp_variables.get(ts, 0.0) + value

        return RuntimeMetricsCollector(
            **{**asdict(self), "counter_values": new_counters},
            metrics_collected=self.metrics_collected + 1,
        )

    def record_gauge(
        self,
        metric_id: str,
        value: float,
        timestamp: Optional[str] = None,
    ) -> "RuntimeMetricsCollector":
        """Record a gauge value."""
        if not self.config.enabled:
            return self

        ts = timestamp or datetime.now(timezone.utc).isoformat()
        new_gauges = dict(self.gauge_values)
        
        if metric_id not in new_gauges:
            new_gauges[metric_id] = {}
        
        new_gauges[metric_id][ts] = value

        return RuntimeMetricsCollector(
            **{**asdict(self), "gauge_values": new_gauges},
            metrics_collected=self.metrics_collected + 1,
        )

    def record_timing(
        self,
        metric_id: str,
        duration_ms: float,
        timestamp: Optional[str] = None,
    ) -> "RuntimeMetricsCollector":
        """Record a timing measurement."""
        if not self.config.enabled:
            return self

        ts = timestamp or datetime.now(timezone.utc).isoformat()
        new_timings = dict(self.timing_values)
        
        if metric_id not in new_timings:
            new_timings[metric_id] = []
        
        new_timings[metric_id].append(duration_ms)

        return RuntimeMetricsCollector(
            **{**asdict(self), "timing_values": new_timings},
            metrics_collected=self.metrics_collected + 1,
        )

    def record_histogram(
        self,
        metric_id: str,
        value: float,
        timestamp: Optional[str] = None,
        bucket_boundaries: Optional[List[float]] = None,
    ) -> "RuntimeMetricsCollector":
        """Record a histogram data point."""
        if not self.config.enabled:
            return self

        # For now, store as timing for simplicity
        # A full histogram implementation would bucket values
        return self.record_timing(metric_id, value, timestamp)

    def get_metric_statistics(
        self,
        metric_id: str,
        window_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Get statistics for a metric."""
        result: Dict[str, Any] = {}

        # Get counter values
        if metric_id in self.counter_values:
            values = list(self.counter_values[metric_id].values())
            if values:
                result["counter"] = {
                    "count": len(values),
                    "sum": sum(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                }

        # Get gauge values
        if metric_id in self.gauge_values:
            values = list(self.gauge_values[metric_id].values())
            if values:
                result["gauge"] = {
                    "count": len(values),
                    "current": values[-1] if values else None,
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                }

        # Get timing values
        if metric_id in self.timing_values:
            values = self.timing_values[metric_id]
            if values:
                result["timing"] = {
                    "count": len(values),
                    "min_ms": min(values),
                    "max_ms": max(values),
                    "mean_ms": sum(values) / len(values),
                    "median_ms": sorted(values)[len(values) // 2],
                }

        return result

    def get_alerts(self) -> List[RuntimeMetricAlert]:
        """Get all active alerts."""
        return [a for a in self.alerts.values() if a.is_firing]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "config": self.config.to_dict(),
            "metrics": {k: v.to_dict() for k, v in self.metrics.items()},
            "metrics_collected": self.metrics_collected,
            "metrics_dropped": self.metrics_dropped,
            "last_flush_at": self.last_flush_at,
            "counters": len(self.counter_values),
            "gauges": len(self.gauge_values),
            "timings": len(self.timing_values),
            "histograms": len(self.histogram_data),
            "alerts_active": len(self.get_alerts()),
            "alerts_total": len(self.alert_history),
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


# ---------------------------------------------------------------------------
# Benchmark Runner
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class RuntimeBenchmarkRunner:
    """Runner for executing benchmarks.

    Executes benchmark configurations and collects results.
    All benchmarks are advisory-only and read-only.
    """

    runner_id: str = PLACEHOLDER_BENCHMARK_ID
    session_id: str = PLACEHOLDER_SESSION_ID
    started_at: str = ""

    # Configuration
    config: RuntimeBenchmarkConfiguration = field(default_factory=RuntimeBenchmarkConfiguration)

    # State
    status: RuntimeBenchmarkStatus = RuntimeBenchmarkStatus.PENDING
    current_benchmark_id: Optional[str] = None
    current_iteration: int = 0
    current_warmup_iteration: int = 0

    # Results
    results: Dict[str, RuntimeBenchmarkResult] = field(default_factory=dict)
    current_result: Optional[RuntimeBenchmarkResult] = None

    # Statistics
    benchmarks_completed: int = 0
    benchmarks_failed: int = 0
    total_iterations: int = 0

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        session_id: str = PLACEHOLDER_SESSION_ID,
    ) -> "RuntimeBenchmarkRunner":
        """Factory method."""
        runner_id = hashlib.sha256(f"{session_id}_runner".encode()).hexdigest()[:16]
        return cls(
            runner_id=f"br_{runner_id}",
            session_id=session_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

    def run_benchmark(
        self,
        benchmark_config: RuntimeBenchmarkConfiguration,
        benchmark_fn: Any,
    ) -> RuntimeBenchmarkResult:
        """Run a benchmark.
        
        The benchmark_fn is called repeatedly and should return a measurement value.
        """
        result = RuntimeBenchmarkResult.create(
            benchmark_id=benchmark_config.benchmark_id,
            session_id=self.session_id,
            configuration=benchmark_config,
        )

        start_time = time.time()

        try:
            # Warmup iterations
            for i in range(benchmark_config.warmup_iterations):
                try:
                    measurement = benchmark_fn()
                    result.warmup_measurements.append(float(measurement))
                except Exception:
                    pass

            # Main iterations
            for i in range(benchmark_config.iterations):
                try:
                    measurement = benchmark_fn()
                    result.measurements.append(float(measurement))
                    self.total_iterations += 1
                except Exception as e:
                    result.error_count += 1
                    result.error_message = str(e)

            # Compute statistics
            result = result.compute_statistics()
            self.benchmarks_completed += 1

        except Exception as e:
            result = RuntimeBenchmarkResult(
                **asdict(result),
                status=RuntimeBenchmarkStatus.FAILED,
                error_message=str(e),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            self.benchmarks_failed += 1

        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "runner_id": self.runner_id,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "status": self.status.value,
            "current_benchmark_id": self.current_benchmark_id,
            "current_iteration": self.current_iteration,
            "current_warmup_iteration": self.current_warmup_iteration,
            "benchmarks_completed": self.benchmarks_completed,
            "benchmarks_failed": self.benchmarks_failed,
            "total_iterations": self.total_iterations,
            "results_count": len(self.results),
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


# ---------------------------------------------------------------------------
# Telemetry Engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeTelemetryEngine:
    """Engine for managing runtime telemetry and benchmarking.

    Provides a unified interface for collecting metrics, running benchmarks,
    and generating telemetry reports.
    """

    engine_id: str = PLACEHOLDER_BENCHMARK_ID
    session_id: str = PLACEHOLDER_SESSION_ID
    started_at: str = ""

    # Components
    collector: RuntimeMetricsCollector = field(default_factory=RuntimeMetricsCollector)
    runner: RuntimeBenchmarkRunner = field(default_factory=RuntimeBenchmarkRunner)
    config: RuntimeTelemetryConfiguration = field(default_factory=RuntimeTelemetryConfiguration)

    # State
    enabled: bool = True
    running: bool = False

    # Callbacks
    on_metric_recorded: Optional[Any] = None
    on_benchmark_completed: Optional[Any] = None
    on_alert_triggered: Optional[Any] = None

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @classmethod
    def create(
        cls,
        session_id: str = PLACEHOLDER_SESSION_ID,
        config: Optional[RuntimeTelemetryConfiguration] = None,
    ) -> "RuntimeTelemetryEngine":
        """Factory method."""
        engine_id = hashlib.sha256(f"{session_id}_engine".encode()).hexdigest()[:16]
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            engine_id=f"te_{engine_id}",
            session_id=session_id,
            started_at=now,
            collector=RuntimeMetricsCollector.create(session_id),
            runner=RuntimeBenchmarkRunner.create(session_id),
            config=config or RuntimeTelemetryConfiguration(),
        )

    def record_metric(
        self,
        metric_id: str,
        value: float,
        kind: RuntimeMetricKind = RuntimeMetricKind.GAUGE,
        dimensions: Optional[List[RuntimeMetricDimension]] = None,
    ) -> "RuntimeTelemetryEngine":
        """Record a metric value."""
        if not self.enabled:
            return self

        new_collector = self.collector
        
        if kind == RuntimeMetricKind.COUNTER:
            new_collector = new_collector.record_counter(metric_id, value)
        elif kind == RuntimeMetricKind.GAUGE:
            new_collector = new_collector.record_gauge(metric_id, value)
        elif kind == RuntimeMetricKind.TIMING:
            new_collector = new_collector.record_timing(metric_id, value)
        elif kind == RuntimeMetricKind.HISTOGRAM:
            new_collector = new_collector.record_histogram(metric_id, value)

        if self.on_metric_recorded:
            self.on_metric_recorded(metric_id, value, kind)

        return RuntimeTelemetryEngine(
            **{**asdict(self), "collector": new_collector},
        )

    def run_benchmark_config(
        self,
        benchmark_config: RuntimeBenchmarkConfiguration,
        benchmark_fn: Any,
    ) -> RuntimeBenchmarkResult:
        """Run a benchmark configuration."""
        result = self.runner.run_benchmark(benchmark_config, benchmark_fn)
        
        if self.on_benchmark_completed:
            self.on_benchmark_completed(result)

        return result

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive telemetry report."""
        return {
            "engine_id": self.engine_id,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "config": self.config.to_dict(),
            "collector": self.collector.to_dict(),
            "runner": self.runner.to_dict(),
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_id": self.engine_id,
            "session_id": self.session_id,
            "started_at": self.started_at,
            "enabled": self.enabled,
            "running": self.running,
            "collector": self.collector.to_dict(),
            "runner": self.runner.to_dict(),
            "config": self.config.to_dict(),
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Get current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_metric_id(name: str, category: str, labels: Optional[Dict[str, str]] = None) -> str:
    """Generate a metric ID from name and category."""
    parts = [name, category]
    if labels:
        for k, v in sorted(labels.items()):
            parts.append(f"{k}={v}")
    return ".".join(parts).replace(" ", "_")


def _clamp_value(value: float, min_val: float = 0.0, max_val: float = float('inf')) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def _calculate_percentile(sorted_values: List[float], percentile: float) -> float:
    """Calculate a percentile from sorted values."""
    if not sorted_values:
        return 0.0
    idx = int(percentile * len(sorted_values))
    idx = min(idx, len(sorted_values) - 1)
    return sorted_values[idx]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Constants
    "PLACEHOLDER_BENCHMARK_ID",
    "PLACEHOLDER_METRIC_ID",
    "PLACEHOLDER_SESSION_ID",
    "PLACEHOLDER_TRACE_ID",
    "PLACEHOLDER_SPAN_ID",
    "DEFAULT_METRICS_WINDOW_SECONDS",
    "DEFAULT_METRICS_RETENTION_SECONDS",
    "DEFAULT_METRICS_CARDINALITY_LIMIT",
    "DEFAULT_METRICS_FLUSH_INTERVAL_SECONDS",
    "DEFAULT_METRICS_BATCH_SIZE",
    "DEFAULT_BENCHMARK_ITERATIONS",
    "DEFAULT_BENCHMARK_WARMUP_ITERATIONS",
    "DEFAULT_BENCHMARK_TIMEOUT_SECONDS",
    "DEFAULT_BENCHMARK_SAMPLE_SIZE",
    "DEFAULT_LATENCY_WARNING_MS",
    "DEFAULT_LATENCY_ERROR_MS",
    "DEFAULT_THROUGHPUT_WARNING_PER_SEC",
    "DEFAULT_THROUGHPUT_ERROR_PER_SEC",
    # Enums
    "RuntimeMetricKind",
    "RuntimeMetricCategory",
    "RuntimeMetricSeverity",
    "RuntimeBenchmarkKind",
    "RuntimeBenchmarkStatus",
    "RuntimeTelemetryLevel",
    "RuntimeSamplingStrategy",
    # Models - Metrics
    "RuntimeMetricDimension",
    "RuntimeMetricMetadata",
    "RuntimeMetricDataPoint",
    "RuntimeHistogramData",
    "RuntimeSummaryData",
    "RuntimeMetricAlert",
    # Models - Benchmarks
    "RuntimeBenchmarkConfiguration",
    "RuntimeBenchmarkResult",
    "RuntimeBenchmarkComparison",
    # Models - Telemetry
    "RuntimeTelemetryConfiguration",
    # Models - Collectors
    "RuntimeMetricsCollector",
    "RuntimeBenchmarkRunner",
    "RuntimeTelemetryEngine",
]
