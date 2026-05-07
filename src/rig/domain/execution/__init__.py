"""Execution domain models for governed process execution.

This module provides the domain models for governed execution:
- ExecutionRequest: What to execute
- ExecutionLease: Authorization to execute
- ExecutionResult: Outcome of execution
- ExecutionFailure: Failure details
- ExecutionStreamEvent: Streaming output events

The WorktreeExecutor uses these models to provide governed, leased execution
with proper evidence capture and receipt creation.
"""

from rig.domain.execution.models import (
    ExecutionRequest,
    ExecutionLease,
    ExecutionResult,
    ExecutionFailure,
    ExecutionStreamEvent,
)
from rig.domain.execution.executor import WorktreeExecutor

__all__ = [
    "ExecutionRequest",
    "ExecutionLease", 
    "ExecutionResult",
    "ExecutionFailure",
    "ExecutionStreamEvent",
    "WorktreeExecutor",
]
