"""
JSON File Storage Backend implementation for rig_tools.

Provides key-value storage using JSON files on disk.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from rig_tools.core import get_tracer, trace_context, atomic_write, ensure_dir
from rig_tools.core.filesystem import PathLike
from rig_tools.backends.storage.base import StorageBackendImpl, StorageNotFoundError

logger = logging.getLogger(__name__)


class JSONFileBackend(StorageBackendImpl):
    """
    JSON file-based storage backend.
    
    Stores each key-value pair as a separate JSON file in a directory.
    This provides simple, portable storage that works anywhere.
    """
    
    backend_id = "json_file"
    display_name = "JSON File Storage"
    
    def __init__(self, root: PathLike, **config: Any):
        """
        Initialize JSON file backend.
        
        Args:
            root: Root directory for JSON files
            **config: Additional configuration options
        """
        super().__init__(**config)
        self._root = ensure_dir(root)
        self._lock_path = self._root / ".lock"
    
    @property
    def root(self) -> Path:
        """Get the storage root directory."""
        return self._root
    
    def _get_path(self, key: str) -> Path:
        """Get the file path for a key."""
        # Sanitize key to be a valid filename
        safe_key = key.replace("/", "_").replace("\\", "_")
        if not safe_key.endswith(".json"):
            safe_key += ".json"
        return self._root / safe_key
    
    def read(self, key: str) -> Optional[dict[str, Any]]:
        """Read a value from JSON file."""
        with trace_context("json_file.read", category="storage", key=key):
            path = self._get_path(key)
            
            if not path.exists():
                return None
            
            try:
                content = path.read_text(encoding="utf-8")
                return json.loads(content)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read {key}: {e}")
                return None
    
    def write(self, key: str, value: dict[str, Any]) -> None:
        """Write a value to JSON file."""
        with trace_context("json_file.write", category="storage", key=key):
            path = self._get_path(key)
            ensure_dir(path.parent)
            
            # Write atomically
            content = json.dumps(value, indent=2, sort_keys=True)
            atomic_write(path, content)
            
            logger.debug(f"Wrote {key} to {path}")
    
    def delete(self, key: str) -> bool:
        """Delete a value."""
        with trace_context("json_file.delete", category="storage", key=key):
            path = self._get_path(key)
            
            if not path.exists():
                return False
            
            path.unlink()
            logger.debug(f"Deleted {key} from {path}")
            return True
    
    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        path = self._get_path(key)
        return path.exists()
    
    def list_keys(self, prefix: str = "") -> list[str]:
        """List all stored keys."""
        if not self._root.exists():
            return []
        
        # Remove .json suffix and unsanitize
        all_keys = []
        for json_file in self._root.glob("*.json"):
            if json_file.name.startswith("."):
                continue
            key = json_file.stem
            # Convert underscores back (simple unsanitization)
            all_keys.append(key)
        
        # Filter by prefix if provided
        if prefix:
            return [k for k in all_keys if k.startswith(prefix)]
        
        return sorted(all_keys)
    
    def close(self) -> None:
        """Close the backend (no-op for JSON)."""
        pass
    
    def clear(self) -> None:
        """Clear all stored data."""
        import shutil
        for json_file in self._root.glob("*.json"):
            if not json_file.name.startswith("."):
                json_file.unlink()
    
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics with file sizes."""
        keys = self.list_keys()
        total_size = 0
        
        for key in keys:
            path = self._get_path(key)
            if path.exists():
                total_size += path.stat().st_size
        
        return {
            "backend": self.backend_id,
            "root": str(self._root),
            "key_count": len(keys),
            "total_size_bytes": total_size,
            "avg_size_bytes": total_size / len(keys) if keys else 0,
        }
