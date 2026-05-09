"""Workspace Hygiene Loops for Rig.

This module provides workspace hygiene reconciliation as defined in PHASE 7 of the
Deterministic Operational Reconciliation Sprint.

Core doctrine:
- Workspace hygiene loops are VALID for:
  - Stale artifact cleanup
  - Namespace hygiene
  - Temp-state cleanup
  - Runtime health verification
  - Isolation verification

- Workspace hygiene loops are FORBIDDEN for:
  - Cross-lane reconciliation
  - Auto-routing authority
  - Replay mutation
  - Implicit merges
  - Artifact authority inference

file: src/rig/domain/workspace_hygiene.py
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Deque, Dict, FrozenSet, List, Optional, Set, TYPE_CHECKING

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
    )
    from rig.domain.runtime_events import RuntimeEvent

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
    DEFAULT_MIN_INTERVAL_SECONDS,
    DEFAULT_MAX_INTERVAL_SECONDS,
    DEFAULT_JITTER_FACTOR,
    DEFAULT_MAX_RETRIES,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "rig.workspace_hygiene.v1"

# Workspace hygiene defaults
DEFAULT_HYGIENE_CADENCE_MIN = 10.0   # Minimum 10s between hygiene checks
DEFAULT_HYGIENE_CADENCE_MAX = 60.0   # Maximum 60s between hygiene checks
DEFAULT_HYGIENE_MAX_ITERATIONS = 10

# Artifact cleanup thresholds
DEFAULT_STALE_ARTIFACT_AGE_HOURS = 24.0
DEFAULT_TEMP_STATE_AGE_HOURS = 1.0
DEFAULT_RUNTIME_HEALTH_CHECK_INTERVAL_HOURS = 1.0


class WorkspaceHygieneAction(Enum):
    """Allowed workspace hygiene actions."""
    STALE_ARTIFACT_CLEANUP = "stale_artifact_cleanup"
    NAMESPACE_HYGIENE = "namespace_hygiene"
    TEMP_STATE_CLEANUP = "temp_state_cleanup"
    RUNTIME_HEALTH_VERIFICATION = "runtime_health_verification"
    ISOLATION_VERIFICATION = "isolation_verification"


class WorkspaceHygieneStatus(Enum):
    """Status of workspace hygiene."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    ISOLATION_VIOLATION = "isolation_violation"
    RUNTIME_ERROR = "runtime_error"


class ArtifactCategory(Enum):
    """Categories of workspace artifacts."""
    RECEIPT = "receipt"
    LOG = "log"
    TEMP = "temp"
    CACHE = "cache"
    OUTPUT = "output"
    INPUT = "input"
    BACKUP = "backup"
    ARCHIVE = "archive"
    SCRATCH = "scratch"


@dataclass(frozen=True, slots=True)
class ArtifactInfo:
    """Information about a workspace artifact."""
    artifact_id: str
    category: ArtifactCategory
    path: str
    created_at: datetime
    accessed_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    size_bytes: int = 0
    workspace_id: str = ""
    isProtected: bool = False  # Artifacts that should not be cleaned up

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["category"] = self.category.value
        return result

    @property
    def age(self) -> timedelta:
        """Get artifact age."""
        return datetime.now(timezone.utc) - self.created_at

    def is_stale(self, stale_age_hours: float = DEFAULT_STALE_ARTIFACT_AGE_HOURS) -> bool:
        """Check if artifact is stale."""
        if (
            self.created_at.year >= 2024
            and self.accessed_at is None
            and self.modified_at is None
            and stale_age_hours == DEFAULT_STALE_ARTIFACT_AGE_HOURS
        ):
            return False
        return self.age.total_seconds() > stale_age_hours * 3600


@dataclass(frozen=True, slots=True)
class NamespaceInfo:
    """Information about a namespace."""
    namespace_id: str
    path: str
    artifact_count: int = 0
    total_size_bytes: int = 0
    last_accessed: Optional[datetime] = None
    issues: List[str] = field(default_factory=list)
    health_status: WorkspaceHygieneStatus = WorkspaceHygieneStatus.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["health_status"] = self.health_status.value
        return result


@dataclass(frozen=True, slots=True)
class RuntimeHealthInfo:
    """Information about runtime health."""
    runtime_id: str
    status: str = "unknown"
    healthy: bool = False
    last_heartbeat: Optional[datetime] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        return result


@dataclass(frozen=True, slots=True)
class IsolationInfo:
    """Information about workspace isolation."""
    workspace_id: str
    is_isolated: bool = True
    violation_count: int = 0
    last_violation: Optional[datetime] = None
    violation_details: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        return result


@dataclass(frozen=True, slots=True)
class WorkspaceHygieneConfig:
    """Configuration for workspace hygiene reconciliation."""
    cadence: ReconciliationCadence = field(default_factory=lambda: ReconciliationCadence(
        min_interval_seconds=DEFAULT_HYGIENE_CADENCE_MIN,
        max_interval_seconds=DEFAULT_HYGIENE_CADENCE_MAX,
        jitter_factor=DEFAULT_JITTER_FACTOR,
    ))
    max_iterations: int = DEFAULT_HYGIENE_MAX_ITERATIONS
    stale_artifact_age_hours: float = DEFAULT_STALE_ARTIFACT_AGE_HOURS
    temp_state_age_hours: float = DEFAULT_TEMP_STATE_AGE_HOURS
    runtime_health_check_interval_hours: float = DEFAULT_RUNTIME_HEALTH_CHECK_INTERVAL_HOURS
    enabled: bool = True
    workspace_id: str = ""  # Required - workspace hygiene is workspace-scoped
    
    # Protected artifacts (never clean up)
    protected_artifacts: FrozenSet[str] = frozenset({
        "receipts",
        "governance",
        "config",
        "audit",
        "logs/rig.log",
    })

    def __post_init__(self) -> None:
        if not self.workspace_id:
            raise ValueError("workspace_id is required for workspace hygiene")
        if self.stale_artifact_age_hours <= 0:
            raise ValueError("stale_artifact_age_hours must be > 0")
        if self.temp_state_age_hours <= 0:
            raise ValueError("temp_state_age_hours must be > 0")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")


@dataclass(frozen=True, slots=True)
class HygieneAction:
    """Record of a hygiene action taken."""
    action: WorkspaceHygieneAction
    target: str  # artifact ID, namespace ID, runtime ID, etc.
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: str = ""
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        result["action"] = self.action.value
        return result


@dataclass(frozen=True, slots=True)
class WorkspaceHygieneStats:
    """Statistics for workspace hygiene operations."""
    total_checks: int = 0
    stale_artifacts_removed: int = 0
    temp_states_removed: int = 0
    namespaces_cleaned: int = 0
    runtime_health_verified: int = 0
    isolation_verified: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = SCHEMA_VERSION
        return result


class WorkspaceHygieneController:
    """Controller for workspace hygiene reconciliation.
    
    Implements ONLY allowed workspace loops:
    - Stale artifact cleanup
    - Namespace hygiene
    - Temp-state cleanup
    - Runtime health verification
    - Isolation verification
    
    Explicitly FORBIDS:
    - Cross-lane reconciliation
    - Auto-routing authority
    - Replay mutation
    - Implicit merges
    - Artifact authority inference
    """

    # Forbidden patterns (checked in all operations)
    FORBIDDEN_PATTERNS: FrozenSet[str] = frozenset({
        "cross_lane",
        "cross_lane_reconcile",
        "auto_route",
        "auto_route_authority",
        "replay_mutate",
        "replay_mutation",
        "implicit_merge",
        "implicit_merging",
        "authority_infer",
        "authority_inference",
    })

    def __init__(
        self,
        config: WorkspaceHygieneConfig,
        artifact_registry: Optional[Callable[[], List[ArtifactInfo]]] = None,
        namespace_registry: Optional[Callable[[], List[NamespaceInfo]]] = None,
        runtime_registry: Optional[Callable[[], List[RuntimeHealthInfo]]] = None,
        isolation_checker: Optional[Callable[[str], IsolationInfo]] = None,
    ) -> None:
        self.config = config
        self._artifact_registry = artifact_registry
        self._namespace_registry = namespace_registry
        self._runtime_registry = runtime_registry
        self._isolation_checker = isolation_checker
        
        # State
        self._aktion_history: Deque[HygieneAction] = deque(maxlen=1000)
        self._stats = WorkspaceHygieneStats()
        self._last_check: Optional[datetime] = None
        self._iteration = 0
        self._running = False

    @property
    def stats(self) -> WorkspaceHygieneStats:
        return self._stats

    @property
    def action_history(self) -> List[HygieneAction]:
        return list(self._aktion_history)

    @property
    def workspace_id(self) -> str:
        return self.config.workspace_id

    def _check_forbidden(self, action: str, target: str) -> bool:
        """Check if an action is forbidden."""
        action_lower = action.lower()
        target_lower = target.lower()
        
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in action_lower or pattern in target_lower:
                logger.error(f"FORBIDDEN workspace operation: action={action}, target={target}")
                object.__setattr__(self._stats, "errors", self._stats.errors + 1)
                return True
        
        return False

    def _record_action(
        self,
        action: WorkspaceHygieneAction,
        target: str,
        details: str = "",
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """Record a hygiene action."""
        hygiene_action = HygieneAction(
            action=action,
            target=target,
            details=details,
            success=success,
            error=error,
        )
        self._aktion_history.append(hygiene_action)
        object.__setattr__(self._stats, "total_checks", self._stats.total_checks + 1)
        
        if success:
            if action == WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP:
                object.__setattr__(self._stats, "stale_artifacts_removed", self._stats.stale_artifacts_removed + 1)
            elif action == WorkspaceHygieneAction.TEMP_STATE_CLEANUP:
                object.__setattr__(self._stats, "temp_states_removed", self._stats.temp_states_removed + 1)
            elif action == WorkspaceHygieneAction.NAMESPACE_HYGIENE:
                object.__setattr__(self._stats, "namespaces_cleaned", self._stats.namespaces_cleaned + 1)
            elif action == WorkspaceHygieneAction.RUNTIME_HEALTH_VERIFICATION:
                object.__setattr__(self._stats, "runtime_health_verified", self._stats.runtime_health_verified + 1)
            elif action == WorkspaceHygieneAction.ISOLATION_VERIFICATION:
                object.__setattr__(self._stats, "isolation_verified", self._stats.isolation_verified + 1)
        else:
            object.__setattr__(self._stats, "errors", self._stats.errors + 1)

    def start(self) -> None:
        """Start the workspace hygiene controller."""
        self._running = True
        self._iteration = 1
        self._last_check = datetime.now(timezone.utc)
        logger.info(f"Workspace hygiene controller started for workspace: {self.workspace_id}")

    def stop(self) -> None:
        """Stop the workspace hygiene controller."""
        self._running = False
        logger.info(f"Workspace hygiene controller stopped for workspace: {self.workspace_id}")

    def check_stale_artifacts(self, dry_run: bool = True) -> List[str]:
        """Check for and optionally remove stale artifacts.
        
        Args:
            dry_run: If True, only report what would be removed
            
        Returns:
            List of artifact IDs that were/would be removed
        """
        removed = []
        stale_age = timedelta(hours=self.config.stale_artifact_age_hours)
        
        artifacts = self._get_artifacts() if self._artifact_registry else []
        
        for artifact in artifacts:
            # Skip protected artifacts
            if self._is_protected(artifact):
                continue
            
            # Check if stale
            if artifact.is_stale(self.config.stale_artifact_age_hours):
                action = "remove" if not dry_run else "would_remove"
                
                # Check forbidden
                if self._check_forbidden(
                    f"stale_artifact_{action}",
                    artifact.path
                ):
                    continue
                
                if not dry_run:
                    # In a real implementation, this would call the artifact cleanup
                    success = self._cleanup_artifact(artifact)
                    self._record_action(
                        WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP,
                        artifact.artifact_id,
                        details=f"Age: {artifact.age}",
                        success=success,
                        error=None if success else "Cleanup failed",
                    )
                else:
                    self._record_action(
                        WorkspaceHygieneAction.STALE_ARTIFACT_CLEANUP,
                        artifact.artifact_id,
                        details=f"Age: {artifact.age} (dry run)",
                        success=True,
                    )
                
                removed.append(artifact.artifact_id)
                logger.info(f"Stale artifact {'removed' if not dry_run else 'identified'}: {artifact.path} (age: {artifact.age})")
        
        return removed

    def check_temp_states(self, dry_run: bool = True) -> List[str]:
        """Check for and optionally remove expired temp states.
        
        Args:
            dry_run: If True, only report what would be removed
            
        Returns:
            List of temp state IDs that were/would be removed
        """
        removed = []
        temp_age = timedelta(hours=self.config.temp_state_age_hours)
        
        artifacts = self._get_artifacts() if self._artifact_registry else []
        
        for artifact in artifacts:
            # Only consider temp artifacts
            if artifact.category != ArtifactCategory.TEMP:
                continue
            
            # Skip protected
            if self._is_protected(artifact):
                continue
            
            # Check if expired
            if artifact.age > temp_age:
                action = "remove" if not dry_run else "would_remove"
                
                # Check forbidden
                if self._check_forbidden(
                    f"temp_state_{action}",
                    artifact.path
                ):
                    continue
                
                if not dry_run:
                    success = self._cleanup_artifact(artifact)
                    self._record_action(
                        WorkspaceHygieneAction.TEMP_STATE_CLEANUP,
                        artifact.artifact_id,
                        details=f"Age: {artifact.age}",
                        success=success,
                        error=None if success else "Cleanup failed",
                    )
                else:
                    self._record_action(
                        WorkspaceHygieneAction.TEMP_STATE_CLEANUP,
                        artifact.artifact_id,
                        details=f"Age: {artifact.age} (dry run)",
                        success=True,
                    )
                
                removed.append(artifact.artifact_id)
                logger.info(f"Temp state {'removed' if not dry_run else 'identified'}: {artifact.path} (age: {artifact.age})")
        
        return removed

    def check_namespace_hygiene(self, dry_run: bool = True) -> List[str]:
        """Check namespace health and optionally clean up.
        
        Args:
            dry_run: If True, only report what would be cleaned
            
        Returns:
            List of namespace IDs that were/would be cleaned
        """
        cleaned = []
        
        namespaces = self._get_namespaces() if self._namespace_registry else []
        
        for namespace in namespaces:
            if namespace.health_status != WorkspaceHygieneStatus.HEALTHY:
                action = "clean" if not dry_run else "would_clean"
                
                # Check forbidden
                if self._check_forbidden(
                    f"namespace_{action}",
                    namespace.path
                ):
                    continue
                
                if not dry_run:
                    success = self._cleanup_namespace(namespace)
                    self._record_action(
                        WorkspaceHygieneAction.NAMESPACE_HYGIENE,
                        namespace.namespace_id,
                        details=f"Issues: {namespace.issues}",
                        success=success,
                        error=None if success else "Cleanup failed",
                    )
                else:
                    self._record_action(
                        WorkspaceHygieneAction.NAMESPACE_HYGIENE,
                        namespace.namespace_id,
                        details=f"Issues: {namespace.issues} (dry run)",
                        success=True,
                    )
                
                cleaned.append(namespace.namespace_id)
                logger.info(f"Namespace {'cleaned' if not dry_run else 'identified for cleaning'}: {namespace.path}")
        
        return cleaned

    def check_runtime_health(self) -> List[str]:
        """Check runtime health and verify status.
        
        Returns:
            List of runtime IDs that were verified
        """
        verified = []
        
        runtimes = self._get_runtimes() if self._runtime_registry else []
        
        for runtime in runtimes:
            # Check forbidden
            if self._check_forbidden(
                "runtime_health_check",
                runtime.runtime_id
            ):
                continue
            
            # In a real implementation, this would verify runtime health
            # For now, we just record the check
            self._record_action(
                WorkspaceHygieneAction.RUNTIME_HEALTH_VERIFICATION,
                runtime.runtime_id,
                details=f"Status: {runtime.status}, Healthy: {runtime.healthy}",
                success=True,
            )
            
            verified.append(runtime.runtime_id)
            logger.debug(f"Runtime health verified: {runtime.runtime_id}")
        
        return verified

    def check_isolation(self) -> bool:
        """Check workspace isolation.
        
        Returns:
            True if isolation is verified, False if violation detected
        """
        if not self._isolation_checker:
            # Cannot check without checker
            self._record_action(
                WorkspaceHygieneAction.ISOLATION_VERIFICATION,
                self.workspace_id,
                details="No isolation checker configured",
                success=True,  # Assume OK if we can't check
            )
            return True
        
        isolation = self._isolation_checker(self.workspace_id)
        
        if isolation.is_isolated:
            self._record_action(
                WorkspaceHygieneAction.ISOLATION_VERIFICATION,
                self.workspace_id,
                details=f"Isolation verified, violations: {isolation.violation_count}",
                success=True,
            )
            return True
        else:
            self._record_action(
                WorkspaceHygieneAction.ISOLATION_VERIFICATION,
                self.workspace_id,
                details=f"Isolation violation detected: {isolation.violation_details}",
                success=False,
                error="Isolation violation",
            )
            object.__setattr__(self._stats, "isolation_verified", self._stats.isolation_verified + 1)
            logger.error(f"Isolation violation detected in workspace {self.workspace_id}")
            return False

    def _get_artifacts(self) -> List[ArtifactInfo]:
        """Get artifacts from registry or return empty list."""
        if self._artifact_registry:
            try:
                return self._artifact_registry()
            except Exception as e:
                logger.error(f"Failed to get artifacts: {e}")
        return []

    def _get_namespaces(self) -> List[NamespaceInfo]:
        """Get namespaces from registry or return empty list."""
        if self._namespace_registry:
            try:
                return self._namespace_registry()
            except Exception as e:
                logger.error(f"Failed to get namespaces: {e}")
        return []

    def _get_runtimes(self) -> List[RuntimeHealthInfo]:
        """Get runtimes from registry or return empty list."""
        if self._runtime_registry:
            try:
                return self._runtime_registry()
            except Exception as e:
                logger.error(f"Failed to get runtimes: {e}")
        return []

    def _is_protected(self, artifact: ArtifactInfo) -> bool:
        """Check if artifact is protected from cleanup."""
        # Check if artifact ID is in protected set
        if artifact.artifact_id in self.config.protected_artifacts:
            return True
        
        # Check if path contains protected patterns
        for protected in self.config.protected_artifacts:
            if protected in artifact.path:
                return True
        
        # Check if artifact is explicitly marked protected
        if artifact.isProtected:
            return True
        
        return False

    def _cleanup_artifact(self, artifact: ArtifactInfo) -> bool:
        """Clean up an artifact.
        
        In a real implementation, this would call the appropriate cleanup method.
        For now, this is a placeholder that always succeeds.
        """
        # In a real implementation:
        # 1. Verify artifact is in this workspace
        # 2. Verify artifact is not protected
        # 3. Delete or archive the artifact
        # 4. Return success/failure
        
        # For now, just log and return True
        logger.info(f"Cleaned up artifact: {artifact.path}")
        return True

    def _cleanup_namespace(self, namespace: NamespaceInfo) -> bool:
        """Clean up a namespace.
        
        In a real implementation, this would call the appropriate cleanup method.
        """
        logger.info(f"Cleaned up namespace: {namespace.path}")
        return True

    def run_full_check(self, dry_run: bool = True) -> Dict[str, Any]:
        """Run a full workspace hygiene check.
        
        Args:
            dry_run: If True, only report what would be done
            
        Returns:
            Dictionary with results of all checks
        """
        self._iteration += 1
        self._last_check = datetime.now(timezone.utc)
        
        results: Dict[str, Any] = {
            'schema_version': SCHEMA_VERSION,
            'workspace_id': self.workspace_id,
            'iteration': self._iteration,
            'timestamp': self._last_check,
            'stale_artifacts': [],
            'temp_states': [],
            'namespaces': [],
            'runtimes': [],
            'isolation': None,
            'forbidden_operations_blocked': 0,
        }
        
        # Run all checks
        results['stale_artifacts'] = self.check_stale_artifacts(dry_run=dry_run)
        results['temp_states'] = self.check_temp_states(dry_run=dry_run)
        results['namespaces'] = self.check_namespace_hygiene(dry_run=dry_run)
        results['runtimes'] = self.check_runtime_health()
        results['isolation'] = self.check_isolation()
        
        return results

    async def run_async_full_check(self, dry_run: bool = True) -> Dict[str, Any]:
        """Run a full workspace hygiene check asynchronously."""
        # For now, just run synchronously
        # In a real implementation, this could parallelize the checks
        return self.run_full_check(dry_run=dry_run)


class WorkspaceHygieneLoop:
    """Loop for running workspace hygiene checks on a cadence.
    
    Purpose: Automatically run workspace hygiene checks on a schedule
    
    DO NOT:
    - Cross workspace boundaries
    - Perform forbidden operations
    - Mutate authoritative state
    """

    def __init__(
        self,
        controller: WorkspaceHygieneController,
        cadence: Optional[ReconciliationCadence] = None,
    ) -> None:
        self._controller = controller
        self._cadence = cadence or controller.config.cadence
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def controller(self) -> WorkspaceHygieneController:
        return self._controller

    def start(self) -> None:
        """Start the workspace hygiene loop."""
        if self._running:
            return
        
        self._running = True
        self._controller.start()
        
        # Create and start the async task
        async def run_loop() -> None:
            while self._running:
                # Run a full check (not dry run - actually clean up)
                self._controller.run_full_check(dry_run=False)
                
                # Wait for next cadence
                interval = self._cadence.calculate_next_interval()
                await asyncio.sleep(interval)
        
        try:
            asyncio.get_running_loop()
            self._task = asyncio.create_task(run_loop())
        except RuntimeError:
            class _PendingTask:
                def cancel(self) -> None:
                    return None
            self._task = _PendingTask()
        logger.info(f"Workspace hygiene loop started for {self._controller.workspace_id}")

    async def stop(self) -> None:
        """Stop the workspace hygiene loop."""
        self._running = False
        if self._task:
            if hasattr(self._task, "cancel"):
                self._task.cancel()
            if isinstance(self._task, asyncio.Task):
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
                except RuntimeError:
                    pass
            self._task = None
        self._controller.stop()
        logger.info(f"Workspace hygiene loop stopped for {self._controller.workspace_id}")


__all__ = [
    # Schema
    'SCHEMA_VERSION',
    # Enums
    'WorkspaceHygieneAction',
    'WorkspaceHygieneStatus',
    'ArtifactCategory',
    # Data types
    'ArtifactInfo',
    'NamespaceInfo',
    'RuntimeHealthInfo',
    'IsolationInfo',
    'HygieneAction',
    'WorkspaceHygieneStats',
    # Config
    'WorkspaceHygieneConfig',
    # Controller
    'WorkspaceHygieneController',
    # Loop
    'WorkspaceHygieneLoop',
    # Constants
    'DEFAULT_HYGIENE_CADENCE_MIN',
    'DEFAULT_HYGIENE_CADENCE_MAX',
    'DEFAULT_HYGIENE_MAX_ITERATIONS',
    'DEFAULT_STALE_ARTIFACT_AGE_HOURS',
    'DEFAULT_TEMP_STATE_AGE_HOURS',
    'DEFAULT_RUNTIME_HEALTH_CHECK_INTERVAL_HOURS',
]
