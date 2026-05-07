"""
Domain modules for Rig.

These modules provide the core domain logic and serve as the deep modules
behind the CLI command adapters. Each domain module exposes a narrow,
well-defined interface that hides implementation complexity.

The interface is the test surface.
"""

from rig.domain.workspace import WorkspaceDomain, WorkspaceRecord, WORKSPACE_STATUSES

__all__ = ["WorkspaceDomain", "WorkspaceRecord", "WORKSPACE_STATUSES"]
