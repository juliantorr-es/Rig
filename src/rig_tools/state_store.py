"""
State Store for Rig

Provides durable storage for Rig's state using SQLite.
Manages database connections, schema migrations, and table operations.

Uses rig_tools.backends.storage.sqlite.SQLiteBackend for underlying storage.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sqlite3

from rig_tools.core.filesystem import ensure_dir
from rig_tools.backends.storage.sqlite import SQLiteBackend


# =============================================================================
# State Store Configuration
# =============================================================================

STATE_STORE_SCHEMA_VERSION = "rig.state_store.v1"

# Required tables for Rig state
REQUIRED_TABLES = [
    "settings", "actions", "command_plans", "action_results",
    "events", "tasks", "task_edges", "queue_jobs",
    "loop_runs", "loop_steps", "scheduler_jobs",
    "artifacts", "prompt_traces", "gc_marks"
]

# Schema definitions for each table
SCHEMA_DEFINITIONS = {
    "schema_migrations": """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """,
    "settings": """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "actions": """
        CREATE TABLE IF NOT EXISTS actions (
            action_id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "command_plans": """
        CREATE TABLE IF NOT EXISTS command_plans (
            plan_id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            task TEXT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "action_results": """
        CREATE TABLE IF NOT EXISTS action_results (
            result_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL,
            action_id TEXT NOT NULL,
            status TEXT NOT NULL,
            exit_code INTEGER,
            data TEXT NOT NULL,
            finished_at TEXT NOT NULL
        )
    """,
    "events": """
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            event_type TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "tasks": """
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "task_edges": """
        CREATE TABLE IF NOT EXISTS task_edges (
            from_task TEXT NOT NULL,
            to_task TEXT NOT NULL,
            edge_type TEXT NOT NULL,
            PRIMARY KEY (from_task, to_task)
        )
    """,
    "queue_jobs": """
        CREATE TABLE IF NOT EXISTS queue_jobs (
            job_id TEXT PRIMARY KEY,
            task TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "loop_runs": """
        CREATE TABLE IF NOT EXISTS loop_runs (
            loop_run_id TEXT PRIMARY KEY,
            task TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "loop_steps": """
        CREATE TABLE IF NOT EXISTS loop_steps (
            step_id TEXT PRIMARY KEY,
            loop_run_id TEXT NOT NULL,
            status TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "scheduler_jobs": """
        CREATE TABLE IF NOT EXISTS scheduler_jobs (
            job_name TEXT PRIMARY KEY,
            schedule TEXT NOT NULL,
            last_run TEXT,
            next_run TEXT,
            data TEXT
        )
    """,
    "artifacts": """
        CREATE TABLE IF NOT EXISTS artifacts (
            path TEXT PRIMARY KEY,
            artifact_type TEXT NOT NULL,
            hash TEXT,
            created_at TEXT NOT NULL
        )
    """,
    "prompt_traces": """
        CREATE TABLE IF NOT EXISTS prompt_traces (
            trace_id TEXT PRIMARY KEY,
            task TEXT,
            backend TEXT NOT NULL,
            model TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """,
    "gc_marks": """
        CREATE TABLE IF NOT EXISTS gc_marks (
            path TEXT PRIMARY KEY,
            class TEXT NOT NULL,
            marked_at TEXT NOT NULL
        )
    """,
}


class StateStore:
    """
    SQLite-based state storage for Rig.
    
    Manages database schema, connections, and provides access to state tables.
    Uses SQLiteBackend from rig_tools.backends.storage for underlying operations.
    """
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.db_dir = self.repo_root / ".build" / "rig" / "state"
        self.db_path = self.db_dir / "rig.sqlite"
        self.schema_version = STATE_STORE_SCHEMA_VERSION
        
        # Use SQLiteBackend for key-value style operations on settings table
        self._settings_backend = SQLiteBackend(
            self.db_path,
            table_name="settings"
        )
        
        # Track required tables
        self.required_tables = REQUIRED_TABLES
    
    def connect(self) -> sqlite3.Connection:
        """Connects to the SQLite database. Creates directory if missing."""
        ensure_dir(self.db_dir)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_status(self) -> Dict[str, Any]:
        """Returns the current status of the state store."""
        status = "missing"
        if self.db_path.exists():
            status = "initialized"
            
        tables_info = {}
        migrations = []
        
        if status == "initialized":
            try:
                with self.connect() as conn:
                    # Check tables
                    for table in self.required_tables + ["schema_migrations"]:
                        res = conn.execute(
                            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                            (table,)
                        ).fetchone()
                        exists = res[0] > 0
                        count = 0
                        if exists:
                            try:
                                res = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
                                count = res[0]
                            except sqlite3.OperationalError:
                                # Table might exist but be corrupted or locked
                                pass
                        tables_info[table] = {"exists": exists, "count": count}
                    
                    # Get migrations
                    if tables_info.get("schema_migrations", {}).get("exists"):
                        res = conn.execute("SELECT version, applied_at FROM schema_migrations ORDER BY applied_at ASC")
                        migrations = [{"version": r["version"], "applied_at": r["applied_at"]} for r in res]
            except Exception as e:
                status = "error"
                tables_info["error"] = str(e)
        
        return {
            "schema_version": self.schema_version,
            "db_path": str(self.db_path.relative_to(self.repo_root)) if status != "missing" else str(self.db_path),
            "status": status,
            "tables": tables_info,
            "migrations": migrations,
            "authoritative": True
        }
    
    def get_migration_plan(self) -> List[str]:
        """Returns the SQL statements required to bring the database to current version."""
        # Build migration plan from schema definitions
        plan = []
        
        # First, ensure schema_migrations table exists
        plan.append(SCHEMA_DEFINITIONS["schema_migrations"])
        
        # Then create all other tables
        for table in self.required_tables:
            if table in SCHEMA_DEFINITIONS:
                plan.append(SCHEMA_DEFINITIONS[table])
        
        return plan
    
    def migrate(self, dry_run: bool = False) -> List[str]:
        """Applies migrations to the database."""
        plan = self.get_migration_plan()
        applied = []
        
        if dry_run:
            # We just return the plan as "would apply"
            return plan
        
        with self.connect() as conn:
            # Ensure schema_migrations table exists
            conn.execute(SCHEMA_DEFINITIONS["schema_migrations"])
            
            # Check if v1 is already applied
            res = conn.execute("SELECT count(*) FROM schema_migrations WHERE version = 'v1'").fetchone()
            if res[0] > 0:
                return ["v1 already applied"]
            
            for sql in plan:
                conn.execute(sql)
                applied.append(sql)
            
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                ("v1", datetime.now(timezone.utc).isoformat())
            )
            conn.commit()
            
        return applied
    
    def rebuild_index(self, dry_run: bool = False) -> List[str]:
        """Stub for rebuilding indices from durable artifacts."""
        # This will eventually read JSON/JSONL and populate SQLite
        if dry_run:
            return ["Would scan .build/rig/ results and events to rebuild SQLite state."]
        return ["Index rebuild not fully implemented yet."]
    
    # =========================================================================
    # Convenience methods for common operations
    # =========================================================================
    
    def get_setting(self, key: str) -> Optional[Any]:
        """Get a setting value by key."""
        try:
            result = self._settings_backend.read(key)
            if result:
                return result.get("value")
            return None
        except Exception:
            return None
    
    def set_setting(self, key: str, value: Any, updated_at: Optional[str] = None) -> None:
        """Set a setting value by key."""
        if updated_at is None:
            updated_at = datetime.now(timezone.utc).isoformat()
        
        self._settings_backend.write(key, {
            "value": value,
            "updated_at": updated_at
        })
    
    def delete_setting(self, key: str) -> bool:
        """Delete a setting by key."""
        return self._settings_backend.delete(key)
    
    def list_settings(self) -> List[str]:
        """List all setting keys."""
        return self._settings_backend.list_keys()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        all_data = self._settings_backend.get_all()
        return {k: v.get("value") for k, v in all_data.items()}
