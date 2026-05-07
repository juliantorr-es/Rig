"""
VCS Backend implementations for rig_tools.

These are the implementation-layer backends that handle actual VCS
operations (primarily Git). They implement the internals while the 
domain layer provides the public interface via protocols.
"""

from rig_tools.backends.vcs.base import VCSBackend, GitBackend

__all__ = [
    "VCSBackend",
    "GitBackend",
]
