"""
Backend contracts for rig_tools implementation layer.

This package provides backend implementations that rig_tools modules use
for interacting with external systems (ML, VCS, UI, Storage).

These are implementation details and should only be used by rig_tools
modules, not by the domain layer or CLI directly.

Modules:
- ml: ML backend implementations (MLX, LlamaCpp, etc.)
- vcs: Version control system backend implementations (Git)
- ui: UI backend implementations (TUI, Web, etc.)
- storage: Storage backend implementations (JSON, SQLite, etc.)
"""

# Re-export key types for convenience
from rig_tools.backends.ml import (
    MLBackendImpl,
    MLXBackend,
    LlamaCppBackend,
)
from rig_tools.backends.vcs import (
    VCSBackend,
    GitBackend,
)
from rig_tools.backends.storage import (
    StorageBackendImpl,
    JSONFileBackend,
    SQLiteBackend,
)

__all__ = [
    # ML
    "MLBackendImpl",
    "MLXBackend",
    "LlamaCppBackend",
    # VCS
    "VCSBackend",
    "GitBackend",
    # Storage
    "StorageBackendImpl",
    "JSONFileBackend",
    "SQLiteBackend",
]
