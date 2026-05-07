"""
Storage Backend implementations for rig_tools.

These are the implementation-layer backends that handle actual storage
operations (JSON, SQLite, etc.). They implement the internals while the 
domain layer provides the public interface via protocols.
"""

from rig_tools.backends.storage.base import StorageBackendImpl, StorageBackendError
from rig_tools.backends.storage.json_file import JSONFileBackend
from rig_tools.backends.storage.sqlite import SQLiteBackend

__all__ = [
    "StorageBackendImpl",
    "StorageBackendError",
    "JSONFileBackend",
    "SQLiteBackend",
]
