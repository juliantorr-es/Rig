"""
SQLite Storage Backend implementation for rig_tools.

Provides key-value storage using SQLite database.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

from rig_tools.core import get_tracer, trace_context, ensure_dir
from rig_tools.core.filesystem import PathLike
from rig_tools.backends.storage.base import StorageBackendImpl, StorageNotFoundError

logger = logging.getLogger(__name__)


class SQLiteBackend(StorageBackendImpl):
    """
    SQLite-based storage backend.
    
    Stores key-value pairs in a SQLite database table.
    Values are serialized as JSON for flexible storage.
    """
    
    backend_id = "sqlite"
    display_name = "SQLite Storage"
    
    def __init__(self, db_path: PathLike, **config: Any):
        """
        Initialize SQLite backend.
        
        Args:
            db_path: Path to the SQLite database file
            **config: Additional configuration options
        """
        super().__init__(**config)
        self._db_path = Path(db_path)
        self._connection: SQLite3Connection | None = None
        self._table_name = config.get("table_name", "rig_storage")
        
        # Initialize the database
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database and create tables."""
        ensure_dir(self._db_path.parent)
        
        self._connection = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        
        # Create table if not exists
        cursor = self._connection.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._table_name} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster key lookups
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self._table_name}_key 
            ON {self._table_name}(key)
        """)
        
        self._connection.commit()
        cursor.close()
    
    def _get_cursor(self) -> sqlite3.Cursor:
        """Get a database cursor."""
        if self._connection is None:
            raise RuntimeError("Database not initialized")
        return self._connection.cursor()
    
    def read(self, key: str) -> Optional[dict[str, Any]]:
        """Read a value from the database."""
        with trace_context("sqlite.read", category="storage", key=key):
            cursor = self._get_cursor()
            
            cursor.execute(
                f"SELECT value FROM {self._table_name} WHERE key = ?",
                (key,),
            )
            
            row = cursor.fetchone()
            cursor.close()
            
            if row is None:
                return None
            
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize value for {key}: {e}")
                return None
    
    def write(self, key: str, value: dict[str, Any]) -> None:
        """Write a value to the database."""
        with trace_context("sqlite.write", category="storage", key=key):
            cursor = self._get_cursor()
            
            # Serialize value as JSON
            serialized = json.dumps(value, sort_keys=True)
            
            # Upsert: insert or replace
            cursor.execute(f"""
                INSERT INTO {self._table_name} (key, value, updated_at) 
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET 
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
            """, (key, serialized))
            
            self._connection.commit()
            cursor.close()
            
            logger.debug(f"Wrote {key} to SQLite database")
    
    def delete(self, key: str) -> bool:
        """Delete a value from the database."""
        with trace_context("sqlite.delete", category="storage", key=key):
            cursor = self._get_cursor()
            
            cursor.execute(
                f"DELETE FROM {self._table_name} WHERE key = ?",
                (key,),
            )
            
            deleted = cursor.rowcount > 0
            self._connection.commit()
            cursor.close()
            
            if deleted:
                logger.debug(f"Deleted {key} from SQLite database")
            
            return deleted
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in the database."""
        cursor = self._get_cursor()
        
        cursor.execute(
            f"SELECT 1 FROM {self._table_name} WHERE key = ?",
            (key,),
        )
        
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists
    
    def list_keys(self, prefix: str = "") -> list[str]:
        """List all stored keys."""
        cursor = self._get_cursor()
        
        if prefix:
            cursor.execute(
                f"SELECT key FROM {self._table_name} WHERE key LIKE ? ORDER BY key",
                (f"{prefix}%",),
            )
        else:
            cursor.execute(f"SELECT key FROM {self._table_name} ORDER BY key")
        
        keys = [row["key"] for row in cursor.fetchall()]
        cursor.close()
        return keys
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.debug("SQLite database connection closed")
    
    def clear(self) -> None:
        """Clear all stored data."""
        with trace_context("sqlite.clear", category="storage"):
            cursor = self._get_cursor()
            cursor.execute(f"DELETE FROM {self._table_name}")
            self._connection.commit()
            cursor.close()
            logger.debug("Cleared all data from SQLite database")
    
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        cursor = self._get_cursor()
        
        # Get count
        cursor.execute(f"SELECT COUNT(*) as cnt FROM {self._table_name}")
        row = cursor.fetchone()
        count = row["cnt"] if row else 0
        
        # Get total size (sum of all value lengths)
        cursor.execute(f"SELECT SUM(LENGTH(value)) as total_size FROM {self._table_name}")
        row = cursor.fetchone()
        total_size = row["total_size"] if row else 0
        
        cursor.close()
        
        return {
            "backend": self.backend_id,
            "db_path": str(self._db_path),
            "table_name": self._table_name,
            "key_count": count,
            "total_size_bytes": total_size or 0,
            "avg_size_bytes": total_size / count if count > 0 else 0,
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(db={self._db_path!r}, table={self._table_name!r})>"


# Type hint for SQLite3 connection
SQLite3Connection = sqlite3.Connection
