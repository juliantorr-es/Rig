"""
Domain modules for Rig.

These modules provide the core domain logic and serve as the deep modules
behind the CLI command adapters. Each domain module exposes a narrow,
well-defined interface that hides implementation complexity.

The interface is the test surface.
"""

from rig.domain.workspace import WorkspaceDomain, WorkspaceRecord, WORKSPACE_STATUSES
from rig.domain.runtime_events import (
    RuntimeEvent,
    RuntimeLifecycleEvent,
    RuntimeTelemetryEvent,
    ReplayEvent,
    TopologyDeltaEvent,
    GovernanceStateEvent,
    ExecutionRoutingEvent,
    WorkspaceLifecycleEvent,
    IntegrationStatusEvent,
)
from rig.domain.runtime_event_router import RuntimeEventRouter
from rig.domain.runtime_event_transport import RuntimeEventEnvelope, envelope_from_event, event_from_envelope
from rig.domain.workspace_runtime import WorkspaceRuntime
from rig.domain.execution_telemetry import ExecutionTelemetrySample, normalize_telemetry
from rig.domain.replay_event_bridge import ReplayTimelineEntry, ReplayEventBridgeResult, build_replay_timeline

__all__ = [
    "WorkspaceDomain",
    "WorkspaceRecord",
    "WORKSPACE_STATUSES",
    "RuntimeEvent",
    "RuntimeLifecycleEvent",
    "RuntimeTelemetryEvent",
    "ReplayEvent",
    "TopologyDeltaEvent",
    "GovernanceStateEvent",
    "ExecutionRoutingEvent",
    "WorkspaceLifecycleEvent",
    "IntegrationStatusEvent",
    "RuntimeEventRouter",
    "RuntimeEventEnvelope",
    "envelope_from_event",
    "event_from_envelope",
    "WorkspaceRuntime",
    "ExecutionTelemetrySample",
    "normalize_telemetry",
    "ReplayTimelineEntry",
    "ReplayEventBridgeResult",
    "build_replay_timeline",
]
