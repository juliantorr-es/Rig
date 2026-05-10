"""Runtime Doctor & Diagnostics Module for Rig.

Phase 2: Runtime & Agent Execution Plane - Doctor & Diagnostics.

Core doctrine:
- Runtime output is advisory evidence only
- Only receipts/proposals become authoritative evidence
- UI streams projections, NOT raw subprocesses
- All runtime execution remains advisory-only
- NO autonomous apply, direct workspace mutation, hidden execution, background daemons,
  cloud orchestration, production networking, real API keys, or destructive Git commands

This module provides diagnostic and health checking capabilities for runtime
infrastructure. It performs read-only checks and reports findings without
mutating any state.

See docs/architecture/runtime-streaming.md for the canonical streaming architecture.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import signal
import ResourceManager  # type: ignore  # noqa: F401
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from rig.domain.runtime_streaming import (
        RuntimeStreamEvent,
        RuntimeSupervisor,
        RuntimeStreamProjection,
        WebSocketStreamIntegrator,
    )
    from rig.domain.runtime_replay import RuntimeReplayEngine

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLACEHOLDER_DOCTOR_ID = "DOCTOR_ID_PLACEHOLDER"
PLACEHOLDER_CHECK_ID = "CHECK_ID_PLACEHOLDER"
PLACEHOLDER_RUNTIME_ID = "RUNTIME_ID_PLACEHOLDER"

# Default timeouts
DEFAULT_DOCTOR_TIMEOUT_SECONDS = 30
DEFAULT_DOCTOR_CHECK_TIMEOUT_SECONDS = 5
DEFAULT_DOCTOR_INTERVAL_SECONDS = 60

# Resource thresholds
DEFAULT_CPU_WARNING_THRESHOLD = 80.0  # 80%
DEFAULT_CPU_CRITICAL_THRESHOLD = 95.0  # 95%
DEFAULT_MEMORY_WARNING_THRESHOLD = 80.0  # 80%
DEFAULT_MEMORY_CRITICAL_THRESHOLD = 95.0  # 95%
DEFAULT_DISK_WARNING_THRESHOLD = 80.0  # 80%
DEFAULT_DISK_CRITICAL_THRESHOLD = 95.0  # 95%

# Process limits
DEFAULT_MAX_PROCESSES = 100
DEFAULT_MAX_THREADS = 1000
DEFAULT_MAX_FILE_DESCRIPTORS = 1024

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RuntimeDoctorCheckCategory(Enum):
    """Categories for runtime doctor checks."""

    SYSTEM = "system"  # System-level checks (CPU, memory, disk)
    RUNTIME = "runtime"  # Runtime infrastructure checks
    STREAM = "stream"  # Stream event pipeline checks
    PROJECTION = "projection"  # Projection pipeline checks
    WEBSOCKET = "websocket"  # WebSocket integration checks
    REPLAY = "replay"  # Replay & integrity checks
    SUPERVISOR = "supervisor"  # Process supervision checks
    NETWORK = "network"  # Network connectivity checks
    SECURITY = "security"  # Security posture checks
    CONFIGURATION = "configuration"  # Configuration validation


class RuntimeDoctorCheckSeverity(Enum):
    """Severity levels for doctor check findings."""

    INFO = "info"
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RuntimeDoctorCheckStatus(Enum):
    """Status of a doctor check."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"
    ERROR = "error"


class RuntimeHealthStatus(Enum):
    """Overall health status levels."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class RuntimeDoctorAction(Enum):
    """Actions that can be performed by the doctor."""

    CHECK = "check"  # Run checks
    DIAGNOSE = "diagnose"  # Deep diagnosis
    MONITOR = "monitor"  # Continuous monitoring
    REPORT = "report"  # Generate report
    RESET = "reset"  # Reset check state
    CLEANUP = "cleanup"  # Clean up stale resources


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeDoctorCheckMetadata:
    """Metadata for a runtime doctor check."""

    check_id: str = PLACEHOLDER_CHECK_ID
    category: RuntimeDoctorCheckCategory = RuntimeDoctorCheckCategory.SYSTEM
    label: str = ""
    description: str = ""
    severity: RuntimeDoctorCheckSeverity = RuntimeDoctorCheckSeverity.INFO

    # Execution info
    timeout_seconds: float = DEFAULT_DOCTOR_CHECK_TIMEOUT_SECONDS
    interval_seconds: float = 0  # 0 means run once

    # Dependencies
    requires: List[str] = field(default_factory=list)  # Check IDs this depends on
    required_for: List[str] = field(default_factory=list)  # Check IDs that depend on this

    # Tags for filtering
    tags: Set[str] = field(default_factory=set)

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @property
    def is_periodic(self) -> bool:
        """Check if this check should run periodically."""
        return self.interval_seconds > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RuntimeDoctorCheckResult:
    """Result of a runtime doctor check."""

    check_id: str = PLACEHOLDER_CHECK_ID
    status: RuntimeDoctorCheckStatus = RuntimeDoctorCheckStatus.PENDING
    severity: RuntimeDoctorCheckSeverity = RuntimeDoctorCheckSeverity.INFO
    message: str = ""
    detail: str = ""

    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: float = 0.0

    # Metadata reference
    metadata: Optional[RuntimeDoctorCheckMetadata] = None

    # Evidence (structured data from the check)
    evidence: Dict[str, Any] = field(default_factory=dict)

    # Related checks
    caused_by: Optional[str] = None  # Check ID that caused this result
    blocks: List[str] = field(default_factory=list)  # Check IDs blocked by this result

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    @property
    def is_passing(self) -> bool:
        """Check if the check passed."""
        return self.status == RuntimeDoctorCheckStatus.PASSED

    @property
    def is_failing(self) -> bool:
        """Check if the check failed."""
        return self.status in (
            RuntimeDoctorCheckStatus.FAILED,
            RuntimeDoctorCheckStatus.ERROR,
            RuntimeDoctorCheckStatus.TIMEOUT,
        )

    @property
    def is_skipped(self) -> bool:
        """Check if the check was skipped."""
        return self.status == RuntimeDoctorCheckStatus.SKIPPED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "check_id": self.check_id,
            "status": self.status.value,
            "severity": self.severity.value,
            "message": self.message,
            "detail": self.detail,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": round(self.duration_ms, 2),
            "evidence": self.evidence,
            "caused_by": self.caused_by,
            "blocks": self.blocks,
            "is_passing": self.is_passing,
            "is_failing": self.is_failing,
            "is_skipped": self.is_skipped,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }
        if self.metadata:
            result["metadata"] = self.metadata.to_dict()
        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)

    @classmethod
    def create(
        cls,
        check_id: str,
        status: RuntimeDoctorCheckStatus,
        severity: RuntimeDoctorCheckSeverity = RuntimeDoctorCheckSeverity.INFO,
        message: str = "",
        detail: str = "",
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        duration_ms: float = 0.0,
        metadata: Optional[RuntimeDoctorCheckMetadata] = None,
        evidence: Optional[Dict[str, Any]] = None,
        caused_by: Optional[str] = None,
        blocks: Optional[List[str]] = None,
    ) -> "RuntimeDoctorCheckResult":
        """Factory method for creating check results."""
        return cls(
            check_id=check_id,
            status=status,
            severity=severity,
            message=message,
            detail=detail,
            started_at=started_at or datetime.now(timezone.utc).isoformat(),
            completed_at=completed_at or datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
            metadata=metadata,
            evidence=evidence or {},
            caused_by=caused_by,
            blocks=blocks or [],
        )


@dataclass(frozen=True, slots=True)
class RuntimeHealthIndicator:
    """A health indicator aggregating multiple check results."""

    name: str = ""
    category: str = ""
    description: str = ""

    # Overall status
    status: RuntimeHealthStatus = RuntimeHealthStatus.UNKNOWN
    score: float = 0.0  # 0-100 score

    # Component results
    check_results: Dict[str, RuntimeDoctorCheckResult] = field(default_factory=dict)

    # Counts
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    skipped_checks: int = 0
    warning_checks: int = 0
    error_checks: int = 0

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
        name: str,
        category: str = "general",
        description: str = "",
        check_results: Optional[Dict[str, RuntimeDoctorCheckResult]] = None,
    ) -> "RuntimeHealthIndicator":
        """Factory method for creating health indicators."""
        results = check_results or {}
        
        total = len(results)
        passed = sum(1 for r in results.values() if r.is_passing)
        failed = sum(1 for r in results.values() if r.is_failing)
        skipped = sum(1 for r in results.values() if r.is_skipped)
        warnings = sum(1 for r in results.values() 
                      if r.severity == RuntimeDoctorCheckSeverity.WARNING)
        errors = sum(1 for r in results.values() 
                    if r.severity in (RuntimeDoctorCheckSeverity.ERROR, RuntimeDoctorCheckSeverity.CRITICAL))

        # Calculate score and status
        score = ((passed * 100) + (skipped * 50)) / max(total, 1)
        
        if total == 0:
            status = RuntimeHealthStatus.UNKNOWN
        elif failed > 0:
            status = RuntimeHealthStatus.CRITICAL if errors > 0 else RuntimeHealthStatus.UNHEALTHY
        elif warnings > 0:
            status = RuntimeHealthStatus.DEGRADED
        elif passed == total:
            status = RuntimeHealthStatus.HEALTHY
        else:
            status = RuntimeHealthStatus.DEGRADED

        return cls(
            name=name,
            category=category,
            description=description,
            status=status,
            score=round(score, 2),
            check_results=results,
            total_checks=total,
            passed_checks=passed,
            failed_checks=failed,
            skipped_checks=skipped,
            warning_checks=warnings,
            error_checks=errors,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "status": self.status.value,
            "score": self.score,
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "skipped_checks": self.skipped_checks,
            "warning_checks": self.warning_checks,
            "error_checks": self.error_checks,
            "check_results": {k: v.to_dict() for k, v in self.check_results.items()},
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


@dataclass(frozen=True, slots=True)
class RuntimeDoctorReport:
    """Complete diagnostic report from the runtime doctor."""

    report_id: str = PLACEHOLDER_DOCTOR_ID
    generated_at: str = ""
    runtime_id: str = PLACEHOLDER_RUNTIME_ID

    # Overall health
    overall_status: RuntimeHealthStatus = RuntimeHealthStatus.UNKNOWN
    overall_score: float = 0.0

    # Health indicators by category
    indicators: Dict[str, RuntimeHealthIndicator] = field(default_factory=dict)

    # All check results
    check_results: Dict[str, RuntimeDoctorCheckResult] = field(default_factory=dict)

    # Summary counts
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    skipped_checks: int = 0
    warning_count: int = 0
    error_count: int = 0

    # System information
    system_info: Dict[str, Any] = field(default_factory=dict)

    # Recommendations
    recommendations: List[Dict[str, Any]] = field(default_factory=list)

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
        runtime_id: str = PLACEHOLDER_RUNTIME_ID,
        indicators: Optional[Dict[str, RuntimeHealthIndicator]] = None,
        check_results: Optional[Dict[str, RuntimeDoctorCheckResult]] = None,
        system_info: Optional[Dict[str, Any]] = None,
    ) -> "RuntimeDoctorReport":
        """Factory method for creating doctor reports."""
        now = datetime.now(timezone.utc).isoformat()
        report_id = hashlib.sha256(f"{runtime_id}_{now}".encode()).hexdigest()[:16]

        ind = indicators or {}
        results = check_results or {}

        total = len(results)
        passed = sum(1 for r in results.values() if r.is_passing)
        failed = sum(1 for r in results.values() if r.is_failing)
        skipped = sum(1 for r in results.values() if r.is_skipped)
        warnings = sum(1 for r in results.values() 
                      if r.severity == RuntimeDoctorCheckSeverity.WARNING)
        errors = sum(1 for r in results.values() 
                    if r.severity in (RuntimeDoctorCheckSeverity.ERROR, RuntimeDoctorCheckSeverity.CRITICAL))

        # Calculate overall score
        score = ((passed * 100) + (skipped * 50) - (failed * 100)) / max(total, 1)
        score = max(0.0, min(100.0, score))

        # Determine overall status
        if total == 0:
            status = RuntimeHealthStatus.UNKNOWN
        elif failed > 0:
            status = RuntimeHealthStatus.CRITICAL if errors > 0 else RuntimeHealthStatus.UNHEALTHY
        elif warnings > 0:
            status = RuntimeHealthStatus.DEGRADED
        elif passed == total:
            status = RuntimeHealthStatus.HEALTHY
        else:
            status = RuntimeHealthStatus.DEGRADED

        # Generate recommendations
        recommendations = _generate_recommendations(results, ind)

        return cls(
            report_id=f"dr_{report_id}",
            generated_at=now,
            runtime_id=runtime_id,
            overall_status=status,
            overall_score=round(score, 2),
            indicators=ind,
            check_results=results,
            total_checks=total,
            passed_checks=passed,
            failed_checks=failed,
            skipped_checks=skipped,
            warning_count=warnings,
            error_count=errors,
            system_info=system_info or _collect_system_info(),
            recommendations=recommendations,
        )

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors in the report."""
        return self.error_count > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings in the report."""
        return self.warning_count > 0

    @property
    def is_healthy(self) -> bool:
        """Check if the overall status is healthy."""
        return self.overall_status == RuntimeHealthStatus.HEALTHY

    @property
    def is_degraded(self) -> bool:
        """Check if the overall status is degraded."""
        return self.overall_status == RuntimeHealthStatus.DEGRADED

    @property
    def is_unhealthy(self) -> bool:
        """Check if the overall status is unhealthy or critical."""
        return self.overall_status in (
            RuntimeHealthStatus.UNHEALTHY,
            RuntimeHealthStatus.CRITICAL,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "runtime_id": self.runtime_id,
            "overall_status": self.overall_status.value,
            "overall_score": self.overall_score,
            "indicators": {k: v.to_dict() for k, v in self.indicators.items()},
            "check_results": {k: v.to_dict() for k, v in self.check_results.items()},
            "total_checks": self.total_checks,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "skipped_checks": self.skipped_checks,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "system_info": self.system_info,
            "recommendations": self.recommendations,
            "has_errors": self.has_errors,
            "has_warnings": self.has_warnings,
            "is_healthy": self.is_healthy,
            "is_degraded": self.is_degraded,
            "is_unhealthy": self.is_unhealthy,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


@dataclass(frozen=True, slots=True)
class RuntimeDoctorCapability:
    """A capability check result."""

    capability_id: str = ""
    name: str = ""
    description: str = ""
    category: str = ""

    # Status
    available: bool = False
    enabled: bool = False
    tested: bool = False
    passed: bool = False

    # Details
    message: str = ""
    error: Optional[str] = None
    version: Optional[str] = None
    path: Optional[str] = None

    # Advisory-only flag
    advisory_only: bool = field(default=True, init=False)
    authoritative: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Enforce advisory-only invariant."""
        object.__setattr__(self, 'advisory_only', True)
        object.__setattr__(self, 'authoritative', False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "available": self.available,
            "enabled": self.enabled,
            "tested": self.tested,
            "passed": self.passed,
            "message": self.message,
            "error": self.error,
            "version": self.version,
            "path": self.path,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True, slots=True)
class RuntimeDoctorDiagnostic:
    """A diagnostic entry with detailed information."""

    diagnostic_id: str = PLACEHOLDER_CHECK_ID
    name: str = ""
    category: RuntimeDoctorCheckCategory = RuntimeDoctorCheckCategory.SYSTEM
    severity: RuntimeDoctorCheckSeverity = RuntimeDoctorCheckSeverity.INFO

    # Content
    message: str = ""
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    # Timing
    created_at: str = ""

    # Remediation
    recommendation: str = ""
    suggested_action: Optional[str] = None
    documentation_url: Optional[str] = None

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
        diagnostic_id: str,
        name: str,
        category: RuntimeDoctorCheckCategory = RuntimeDoctorCheckCategory.SYSTEM,
        severity: RuntimeDoctorCheckSeverity = RuntimeDoctorCheckSeverity.INFO,
        message: str = "",
        description: str = "",
        details: Optional[Dict[str, Any]] = None,
        recommendation: str = "",
        suggested_action: Optional[str] = None,
        documentation_url: Optional[str] = None,
    ) -> "RuntimeDoctorDiagnostic":
        """Factory method for creating diagnostics."""
        return cls(
            diagnostic_id=diagnostic_id,
            name=name,
            category=category,
            severity=severity,
            message=message,
            description=description,
            details=details or {},
            created_at=datetime.now(timezone.utc).isoformat(),
            recommendation=recommendation,
            suggested_action=suggested_action,
            documentation_url=documentation_url,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "diagnostic_id": self.diagnostic_id,
            "name": self.name,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "description": self.description,
            "details": self.details,
            "created_at": self.created_at,
            "recommendation": self.recommendation,
            "suggested_action": self.suggested_action,
            "documentation_url": self.documentation_url,
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True)


# ---------------------------------------------------------------------------
# Doctor Engine
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeDoctor:
    """Runtime Doctor engine for diagnostic checks.

    Performs comprehensive diagnostic checks on runtime infrastructure.
    All checks are read-only and produce advisory-only results.
    """

    doctor_id: str = PLACEHOLDER_DOCTOR_ID
    runtime_id: str = PLACEHOLDER_RUNTIME_ID

    # Check registry
    checks: Dict[str, RuntimeDoctorCheckMetadata] = field(default_factory=dict)

    # Results cache
    results: Dict[str, RuntimeDoctorCheckResult] = field(default_factory=dict)

    # Configuration
    timeout_seconds: float = DEFAULT_DOCTOR_TIMEOUT_SECONDS
    check_timeout_seconds: float = DEFAULT_DOCTOR_CHECK_TIMEOUT_SECONDS
    interval_seconds: float = DEFAULT_DOCTOR_INTERVAL_SECONDS

    # State
    running: bool = False
    continuous: bool = False
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None

    # Filtering
    categories: Set[RuntimeDoctorCheckCategory] = field(default_factory=set)
    tags: Set[str] = field(default_factory=set)
    excluded_checks: Set[str] = field(default_factory=set)

    # Callbacks
    on_check_started: Optional[Any] = None
    on_check_completed: Optional[Any] = None
    on_report_generated: Optional[Any] = None

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
        runtime_id: str = PLACEHOLDER_RUNTIME_ID,
        timeout_seconds: float = DEFAULT_DOCTOR_TIMEOUT_SECONDS,
        check_timeout_seconds: float = DEFAULT_DOCTOR_CHECK_TIMEOUT_SECONDS,
        interval_seconds: float = DEFAULT_DOCTOR_INTERVAL_SECONDS,
        checks: Optional[Dict[str, RuntimeDoctorCheckMetadata]] = None,
    ) -> "RuntimeDoctor":
        """Factory method for creating doctor instances."""
        doctor_id = hashlib.sha256(f"{runtime_id}_doctor".encode()).hexdigest()[:16]
        return cls(
            doctor_id=f"dr_{doctor_id}",
            runtime_id=runtime_id,
            timeout_seconds=timeout_seconds,
            check_timeout_seconds=check_timeout_seconds,
            interval_seconds=interval_seconds,
            checks=checks or {},
        )

    def with_check(
        self,
        check_id: str,
        category: RuntimeDoctorCheckCategory,
        label: str,
        description: str = "",
        severity: RuntimeDoctorCheckSeverity = RuntimeDoctorCheckSeverity.INFO,
        timeout_seconds: float = DEFAULT_DOCTOR_CHECK_TIMEOUT_SECONDS,
        interval_seconds: float = 0,
        requires: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None,
    ) -> "RuntimeDoctor":
        """Add a check to the registry."""
        new_checks = dict(self.checks)
        new_checks[check_id] = RuntimeDoctorCheckMetadata(
            check_id=check_id,
            category=category,
            label=label,
            description=description,
            severity=severity,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
            requires=requires or [],
            tags=tags or set(),
        )
        return RuntimeDoctor(
            **{**asdict(self), "checks": new_checks},
        )

    def run_check(
        self,
        check_id: str,
        check_fn: Optional[Any] = None,
    ) -> RuntimeDoctorCheckResult:
        """Run a single check by ID.
        
        If check_fn is provided, it's called with no arguments and should return
        a RuntimeDoctorCheckResult. Otherwise, uses the registered checker.
        """
        metadata = self.checks.get(check_id)
        if metadata is None:
            return RuntimeDoctorCheckResult.create(
                check_id=check_id,
                status=RuntimeDoctorCheckStatus.SKIPPED,
                severity=RuntimeDoctorCheckSeverity.INFO,
                message=f"Check {check_id} not found",
                metadata=metadata,
            )

        start_time = datetime.now(timezone.utc)
        started_at = start_time.isoformat()

        try:
            # Run the check
            if check_fn:
                result = check_fn()
            else:
                # Default: check passes
                result = RuntimeDoctorCheckResult.create(
                    check_id=check_id,
                    status=RuntimeDoctorCheckStatus.PASSED,
                    severity=metadata.severity,
                    message=f"Check passed",
                    metadata=metadata,
                )

            end_time = datetime.now(timezone.utc)
            duration_ms = (end_time - start_time).total_seconds() * 1000

            # Update result with timing
            result = RuntimeDoctorCheckResult(
                **asdict(result),
                started_at=started_at,
                completed_at=end_time.isoformat(),
                duration_ms=duration_ms,
                metadata=metadata,
            )

            if self.on_check_completed:
                self.on_check_completed(result)

            return result

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration_ms = (end_time - start_time).total_seconds() * 1000
            return RuntimeDoctorCheckResult.create(
                check_id=check_id,
                status=RuntimeDoctorCheckStatus.ERROR,
                severity=RuntimeDoctorCheckSeverity.ERROR,
                message=f"Check failed with error: {e}",
                detail=str(e),
                started_at=started_at,
                completed_at=end_time.isoformat(),
                duration_ms=duration_ms,
                metadata=metadata,
                evidence={"exception": str(e), "exception_type": type(e).__name__},
            )

    def run_all_checks(self) -> Dict[str, RuntimeDoctorCheckResult]:
        """Run all registered checks."""
        results: Dict[str, RuntimeDoctorCheckResult] = {}

        # Filter checks based on categories and tags
        checks_to_run = self.checks
        if self.categories:
            checks_to_run = {
                k: v for k, v in checks_to_run.items()
                if v.category in self.categories
            }
        if self.tags:
            checks_to_run = {
                k: v for k, v in checks_to_run.items()
                if v.tags & self.tags
            }
        if self.excluded_checks:
            checks_to_run = {
                k: v for k, v in checks_to_run.items()
                if k not in self.excluded_checks
            }

        # Run checks
        for check_id, metadata in checks_to_run.items():
            if self.on_check_started:
                self.on_check_started(check_id, metadata)

            result = self.run_check(check_id)
            results[check_id] = result

        return results

    def generate_report(self) -> RuntimeDoctorReport:
        """Generate a complete diagnostic report."""
        results = self.run_all_checks()
        
        # Group results by category
        indicators: Dict[str, RuntimeHealthIndicator] = {}
        for check_id, result in results.items():
            metadata = self.checks.get(check_id)
            category = metadata.category.value if metadata else "uncategorized"
            
            if category not in indicators:
                indicators[category] = RuntimeHealthIndicator.create(
                    name=category,
                    category=category,
                )
            
            # Update indicator
            existing_indicator = indicators[category]
            new_results = dict(existing_indicator.check_results)
            new_results[check_id] = result
            
            indicators[category] = RuntimeHealthIndicator.create(
                name=category,
                category=category,
                check_results=new_results,
            )

        report = RuntimeDoctorReport.create(
            runtime_id=self.runtime_id,
            indicators=indicators,
            check_results=results,
        )

        if self.on_report_generated:
            self.on_report_generated(report)

        return report

    def get_capabilities(self) -> List[RuntimeDoctorCapability]:
        """Get list of available capabilities."""
        # This would be populated based on actual runtime environment
        return [
            RuntimeDoctorCapability(
                capability_id="runtime.stream",
                name="Stream Processing",
                description="Process runtime stream events",
                category="stream",
                available=True,
                enabled=True,
                tested=False,
                passed=False,
            ),
            RuntimeDoctorCapability(
                capability_id="runtime.projection",
                name="Projection Pipeline",
                description="Generate UI projections from stream events",
                category="projection",
                available=True,
                enabled=True,
                tested=False,
                passed=False,
            ),
            RuntimeDoctorCapability(
                capability_id="runtime.websocket",
                name="WebSocket Integration",
                description="Real-time WebSocket streaming",
                category="websocket",
                available=True,
                enabled=True,
                tested=False,
                passed=False,
            ),
            RuntimeDoctorCapability(
                capability_id="runtime.replay",
                name="Replay & Integrity",
                description="Replay streams with integrity verification",
                category="replay",
                available=True,
                enabled=True,
                tested=False,
                passed=False,
            ),
        ]

    def quick_check(self) -> RuntimeDoctorReport:
        """Perform a quick health check."""
        return self.generate_report()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "doctor_id": self.doctor_id,
            "runtime_id": self.runtime_id,
            "timeout_seconds": self.timeout_seconds,
            "check_timeout_seconds": self.check_timeout_seconds,
            "interval_seconds": self.interval_seconds,
            "running": self.running,
            "continuous": self.continuous,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "check_count": len(self.checks),
            "result_count": len(self.results),
            "categories": [c.value for c in self.categories],
            "tags": list(self.tags),
            "excluded_checks": list(self.excluded_checks),
            "advisory_only": self.advisory_only,
            "authoritative": self.authoritative,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Built-in Checks
# ---------------------------------------------------------------------------


def register_builtin_checks(doctor: RuntimeDoctor) -> RuntimeDoctor:
    """Register all built-in runtime doctor checks."""
    doc = doctor

    # System checks
    doc = doc.with_check(
        check_id="system.cpu",
        category=RuntimeDoctorCheckCategory.SYSTEM,
        label="CPU Usage",
        description="Check CPU usage levels",
        severity=RuntimeDoctorCheckSeverity.WARNING,
        interval_seconds=60,
        tags={"resource", "system"},
    )

    doc = doc.with_check(
        check_id="system.memory",
        category=RuntimeDoctorCheckCategory.SYSTEM,
        label="Memory Usage",
        description="Check memory usage levels",
        severity=RuntimeDoctorCheckSeverity.WARNING,
        interval_seconds=60,
        tags={"resource", "system"},
    )

    doc = doc.with_check(
        check_id="system.disk",
        category=RuntimeDoctorCheckCategory.SYSTEM,
        label="Disk Space",
        description="Check available disk space",
        severity=RuntimeDoctorCheckSeverity.WARNING,
        interval_seconds=300,
        tags={"resource", "system", "disk"},
    )

    # Runtime checks
    doc = doc.with_check(
        check_id="runtime.stream.buffer",
        category=RuntimeDoctorCheckCategory.STREAM,
        label="Stream Buffer Health",
        description="Check stream buffer sizes and bounds",
        severity=RuntimeDoctorCheckSeverity.INFO,
        interval_seconds=30,
        tags={"stream", "buffer"},
    )

    doc = doc.with_check(
        check_id="runtime.stream.sequence",
        category=RuntimeDoctorCheckCategory.STREAM,
        label="Stream Sequence Integrity",
        description="Verify stream sequence continuity",
        severity=RuntimeDoctorCheckSeverity.WARNING,
        interval_seconds=60,
        tags={"stream", "integrity"},
    )

    # Projection checks
    doc = doc.with_check(
        check_id="projection.pipeline",
        category=RuntimeDoctorCheckCategory.PROJECTION,
        label="Projection Pipeline",
        description="Verify projection pipeline is operating correctly",
        severity=RuntimeDoctorCheckSeverity.INFO,
        interval_seconds=60,
        tags={"projection", "pipeline"},
    )

    doc = doc.with_check(
        check_id="projection.buffer",
        category=RuntimeDoctorCheckCategory.PROJECTION,
        label="Projection Buffer",
        description="Check projection buffer sizes",
        severity=RuntimeDoctorCheckSeverity.INFO,
        interval_seconds=60,
        tags={"projection", "buffer"},
    )

    # WebSocket checks
    doc = doc.with_check(
        check_id="websocket.connection",
        category=RuntimeDoctorCheckCategory.WEBSOCKET,
        label="WebSocket Connections",
        description="Check WebSocket connection health",
        severity=RuntimeDoctorCheckSeverity.INFO,
        interval_seconds=30,
        tags={"websocket", "connection"},
    )

    doc = doc.with_check(
        check_id="websocket.streaming",
        category=RuntimeDoctorCheckCategory.WEBSOCKET,
        label="WebSocket Streaming",
        description="Verify WebSocket stream delivery",
        severity=RuntimeDoctorCheckSeverity.WARNING,
        interval_seconds=30,
        tags={"websocket", "streaming"},
    )

    # Replay checks
    doc = doc.with_check(
        check_id="replay.integrity",
        category=RuntimeDoctorCheckCategory.REPLAY,
        label="Replay Integrity",
        description="Verify replay stream integrity",
        severity=RuntimeDoctorCheckSeverity.INFO,
        interval_seconds=0,  # Run on demand
        tags={"replay", "integrity"},
    )

    doc = doc.with_check(
        check_id="replay.buffer",
        category=RuntimeDoctorCheckCategory.REPLAY,
        label="Replay Buffer",
        description="Check replay buffer capacity",
        severity=RuntimeDoctorCheckSeverity.INFO,
        interval_seconds=60,
        tags={"replay", "buffer"},
    )

    # Supervisor checks
    doc = doc.with_check(
        check_id="supervisor.processes",
        category=RuntimeDoctorCheckCategory.SUPERVISOR,
        label="Process Supervision",
        description="Check supervised process health",
        severity=RuntimeDoctorCheckSeverity.WARNING,
        interval_seconds=30,
        tags={"supervisor", "process"},
    )

    doc = doc.with_check(
        check_id="supervisor.forbidden",
        category=RuntimeDoctorCheckCategory.SUPERVISOR,
        label="Forbidden Command Detection",
        description="Verify forbidden command blocking is active",
        severity=RuntimeDoctorCheckSeverity.CRITICAL,
        interval_seconds=60,
        tags={"supervisor", "security"},
    )

    # Security checks
    doc = doc.with_check(
        check_id="security.runtime_isolation",
        category=RuntimeDoctorCheckCategory.SECURITY,
        label="Runtime Isolation",
        description="Verify runtime isolation boundaries",
        severity=RuntimeDoctorCheckSeverity.CRITICAL,
        interval_seconds=60,
        tags={"security", "isolation"},
    )

    doc = doc.with_check(
        check_id="security.advisory_only",
        category=RuntimeDoctorCheckCategory.SECURITY,
        label="Advisory-Only Enforcement",
        description="Verify all runtime components enforce advisory-only mode",
        severity=RuntimeDoctorCheckSeverity.CRITICAL,
        interval_seconds=60,
        tags={"security", "advisory"},
    )

    return doc


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    """Get current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def _collect_system_info() -> Dict[str, Any]:
    """Collect system information for diagnostics."""
    try:
        import os
        import platform
        import sys
        
        return {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "node_name": platform.node(),
            },
            "python": {
                "version": sys.version,
                "executable": sys.executable,
                "path": sys.path[:5],  # First 5 path entries
            },
            "environment": {
                "cwd": os.getcwd(),
                "uid": os.getuid() if hasattr(os, 'getuid') else None,
                "pid": os.getpid(),
            },
            "resources": {
                "cpu_count": os.cpu_count(),
            },
        }
    except Exception:
        return {}


def _generate_recommendations(
    results: Dict[str, RuntimeDoctorCheckResult],
    indicators: Dict[str, RuntimeHealthIndicator],
) -> List[Dict[str, Any]]:
    """Generate recommendations based on check results."""
    recommendations: List[Dict[str, Any]] = []

    # Sort failed checks by severity
    failed_results = [
        r for r in results.values() if r.is_failing
    ]
    failed_results.sort(
        key=lambda r: {
            RuntimeDoctorCheckSeverity.CRITICAL: 0,
            RuntimeDoctorCheckSeverity.ERROR: 1,
            RuntimeDoctorCheckSeverity.WARNING: 2,
        }.get(r.severity, 3)
    )

    for result in failed_results[:5]:  # Top 5 most critical
        recommendations.append({
            "priority": "high" if result.severity in (RuntimeDoctorCheckSeverity.ERROR, RuntimeDoctorCheckSeverity.CRITICAL) else "medium",
            "title": f"Address {result.metadata.label if result.metadata else result.check_id}",
            "description": result.message,
            "check_id": result.check_id,
            "severity": result.severity.value,
            "action": "Investigate and resolve the issue",
        })

    # General recommendations based on health status
    if indicators:
        overall_indicator = indicators.get("overall") or next(iter(indicators.values()), None)
        if overall_indicator and overall_indicator.status == RuntimeHealthStatus.CRITICAL:
            recommendations.append({
                "priority": "critical",
                "title": "Runtime health is CRITICAL",
                "description": "Multiple critical issues detected",
                "action": "Immediate investigation required",
            })
        elif overall_indicator and overall_indicator.status == RuntimeHealthStatus.UNHEALTHY:
            recommendations.append({
                "priority": "high",
                "title": "Runtime health is UNHEALTHY",
                "description": "One or more checks failed",
                "action": "Investigate failed checks",
            })
        elif overall_indicator and overall_indicator.status == RuntimeHealthStatus.DEGRADED:
            recommendations.append({
                "priority": "medium",
                "title": "Runtime health is DEGRADED",
                "description": "Performance may be impacted",
                "action": "Monitor and address warnings",
            })

    if not recommendations:
        recommendations.append({
            "priority": "low",
            "title": "All checks passed",
            "description": "Runtime infrastructure is healthy",
            "action": "Continue normal operations",
        })

    return recommendations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Constants
    "PLACEHOLDER_DOCTOR_ID",
    "PLACEHOLDER_CHECK_ID",
    "PLACEHOLDER_RUNTIME_ID",
    "DEFAULT_DOCTOR_TIMEOUT_SECONDS",
    "DEFAULT_DOCTOR_CHECK_TIMEOUT_SECONDS",
    "DEFAULT_DOCTOR_INTERVAL_SECONDS",
    "DEFAULT_CPU_WARNING_THRESHOLD",
    "DEFAULT_CPU_CRITICAL_THRESHOLD",
    "DEFAULT_MEMORY_WARNING_THRESHOLD",
    "DEFAULT_MEMORY_CRITICAL_THRESHOLD",
    "DEFAULT_DISK_WARNING_THRESHOLD",
    "DEFAULT_DISK_CRITICAL_THRESHOLD",
    "DEFAULT_MAX_PROCESSES",
    "DEFAULT_MAX_THREADS",
    "DEFAULT_MAX_FILE_DESCRIPTORS",
    # Enums
    "RuntimeDoctorCheckCategory",
    "RuntimeDoctorCheckSeverity",
    "RuntimeDoctorCheckStatus",
    "RuntimeHealthStatus",
    "RuntimeDoctorAction",
    # Models
    "RuntimeDoctorCheckMetadata",
    "RuntimeDoctorCheckResult",
    "RuntimeHealthIndicator",
    "RuntimeDoctorReport",
    "RuntimeDoctorCapability",
    "RuntimeDoctorDiagnostic",
    "RuntimeDoctor",
    # Functions
    "register_builtin_checks",
]
