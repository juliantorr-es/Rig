from __future__ import annotations

import sqlite3
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

class StateStore:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.db_dir = self.repo_root / ".build" / "rig" / "state"
        self.db_path = self.db_dir / "rig.sqlite"
        self.schema_version = "rig.state_store.v1"
        
        self.required_tables = [
            "settings", "actions", "command_plans", "action_results", 
            "events", "tasks", "task_edges", "queue_jobs", 
            "loop_runs", "loop_steps", "scheduler_jobs", 
            "artifacts", "prompt_traces", "gc_marks"
        ]

    def connect(self) -> sqlite3.Connection:
        """Connects to the SQLite database. Creates directory if missing."""
        self.db_dir.mkdir(parents=True, exist_ok=True)
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
        # For MVP, we have a single initial migration
        # In a real app, these would be separate .sql files or versioned functions
        
        initial_tables = []
        
        # 1. Schema Migrations
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
        """)
        
        # 2. Settings
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # 3. Actions
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS actions (
                action_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # 4. Command Plans
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS command_plans (
                plan_id TEXT PRIMARY KEY,
                action_id TEXT NOT NULL,
                task TEXT,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # 5. Action Results
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS action_results (
                result_id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                status TEXT NOT NULL,
                exit_code INTEGER,
                data TEXT NOT NULL,
                finished_at TEXT NOT NULL
            )
        """)
        
        # 6. Events
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                event_type TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # 7. Tasks
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                status TEXT NOT NULL,
                data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # 8. Task Edges
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS task_edges (
                from_task TEXT NOT NULL,
                to_task TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                PRIMARY KEY (from_task, to_task)
            )
        """)
        
        # 9. Queue Jobs
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS queue_jobs (
                job_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # 10. Loop Runs
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS loop_runs (
                loop_run_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # 11. Loop Steps
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS loop_steps (
                step_id TEXT PRIMARY KEY,
                loop_run_id TEXT NOT NULL,
                status TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # 12. Scheduler Jobs
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS scheduler_jobs (
                job_name TEXT PRIMARY KEY,
                schedule TEXT NOT NULL,
                last_run TEXT,
                next_run TEXT,
                data TEXT
            )
        """)
        
        # 13. Artifacts
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS artifacts (
                path TEXT PRIMARY KEY,
                artifact_type TEXT NOT NULL,
                hash TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # 14. Prompt Traces
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS prompt_traces (
                trace_id TEXT PRIMARY KEY,
                task TEXT,
                backend TEXT NOT NULL,
                model TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # 15. GC Marks
        initial_tables.append("""
            CREATE TABLE IF NOT EXISTS gc_marks (
                path TEXT PRIMARY KEY,
                class TEXT NOT NULL,
                marked_at TEXT NOT NULL
            )
        """)
        
        return initial_tables

    def migrate(self, dry_run: bool = False) -> List[str]:
        """Applies migrations to the database."""
        plan = self.get_migration_plan()
        applied = []
        
        if dry_run:
            # We just return the plan as "would apply"
            return plan

        with self.connect() as conn:
            # Check if v1 is already applied
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
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
