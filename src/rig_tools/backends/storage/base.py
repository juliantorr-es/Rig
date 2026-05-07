"""
Base Storage Backend implementation for rig_tools.

This is the implementation-layer abstract base that concrete storage backends
inherits from. It provides common functionality and enforces the interface
that all storage backends must implement.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from rig_tools.core import get_tracer, trace_context
from rig_tools.core.errors import RigError, RigNotFoundError

logger = logging.getLogger(__name__)


class StorageBackendError(RigError):
    """Base error for storage backend operations."""
    pass


class StorageNotFoundError(RigNotFoundError):
    """Raised when a storage key is not found."""
    def __init__(self, key: str):
        super().__init__(
            f"Storage key '{key}' not found",
            code="STORAGE_NOT_FOUND",
            resource_type="storage key",
            resource_id=key,
        )


class StorageKeyError(RigError):
    """Raised when there's an issue with a storage key."""
    pass


class StorageBackendImpl(ABC):
    """
    Abstract base class for storage backend implementations.
    
    All concrete storage backends (JSON, SQLite, etc.) must inherit from
    this class and implement the required methods.
    
    This is the implementation-layer contract, while StorageBackend (Protocol)
    in the domain layer is the public interface.
    """
    
    backend_id: str = ""  # e.g., "json", "sqlite"
    display_name: str = ""  # Human-readable name
    
    def __init__(self, **config: Any):
        """
        Initialize the storage backend.
        
        Args:
            **config: Backend-specific configuration options
        """
        self.config = config
        self._tracer = get_tracer("storage_backend")
    
    @property
    def is_available(self) -> bool:
        """Check if the backend is available."""
        return True
    
    # =========================================================================
    # Core Key-Value Operations
    # =========================================================================
    
    @abstractmethod
    def read(self, key: str) -> Optional[dict[str, Any]]:
        """
        Read a value by key.
        
        Args:
            key: The key to read
            
        Returns:
            The value as dictionary, or None if not found
        """
        pass
    
    @abstractmethod
    def write(self, key: str, value: dict[str, Any]) -> None:
        """
        Write a value by key.
        
        Args:
            key: The key to write to
            value: The value to write (must be serializable dictionary)
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete a value by key.
        
        Args:
            key: The key to delete
            
        Returns:
            True if the key existed and was deleted, False otherwise
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if a key exists.
        
        Args:
            key: The key to check
            
        Returns:
            True if the key exists
        """
        pass
    
    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]:
        """
        List all keys with optional prefix filter.
        
        Args:
            prefix: Optional prefix to filter keys
            
        Returns:
            List of matching keys
        """
        pass
    
    # =========================================================================
    # Batch Operations
    # =========================================================================
    
    def read_batch(self, keys: list[str]) -> dict[str, Optional[dict[str, Any]]]:
        """
        Read multiple keys in a batch.
        
        Args:
            keys: List of keys to read
            
        Returns:
            Dictionary mapping keys to their values (or None if not found)
        """
        result = {}
        for key in keys:
            result[key] = self.read(key)
        return result
    
    def write_batch(self, items: dict[str, dict[str, Any]]) -> None:
        """
        Write multiple key-value pairs in a batch.
        
        Args:
            items: Dictionary of key-value pairs to write
        """
        for key, value in items.items():
            self.write(key, value)
    
    def delete_batch(self, keys: list[str]) -> dict[str, bool]:
        """
        Delete multiple keys in a batch.
        
        Args:
            keys: List of keys to delete
            
        Returns:
            Dictionary mapping keys to whether they were deleted
        """
        result = {}
        for key in keys:
            result[key] = self.delete(key)
        return result
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_all(self) -> dict[str, dict[str, Any]]:
        """Get all key-value pairs."""
        keys = self.list_keys()
        return {k: self.read(k) for k in keys if self.read(k) is not None}
    
    def clear(self) -> None:
        """Clear all data from the backend."""
        for key in self.list_keys():
            self.delete(key)
    
    def count(self) -> int:
        """Count the number of keys."""
        return len(self.list_keys())
    
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        import time
        
        keys = self.list_keys()
        total_size = 0
        
        for key in keys:
            value = self.read(key)
            if value:
                import json
                total_size += len(json.dumps(value))
        
        return {
            "backend": self.backend_id,
            "key_count": len(keys),
            "total_size_bytes": total_size,
            "avg_size_bytes": total_size / len(keys) if keys else 0,
        }
    
    # =========================================================================
    # Resource Management
    # =========================================================================
    
    @abstractmethod
    def close(self) -> None:
        """Close any resources used by the backend."""
        pass
    
    def __enter__(self) -> StorageBackendImpl:
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(backend={self.backend_id!r}, keys={self.count()})>"
