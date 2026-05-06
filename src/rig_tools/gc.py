from __future__ import annotations

import os
import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Literal, Set

from rig_tools.settings_store import SettingsStore
from rig_tools.state_store import StateStore

class GarbageCollector:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.settings = SettingsStore(repo_root).get_effective_settings()
        self.state_store = StateStore(repo_root)
        self.gc_dir = repo_root / ".build" / "rig" / "gc"
        self.gc_plans_dir = self.gc_dir / "plans"
        self.gc_runs_dir = self.gc_dir / "runs"
        
        # Retention defaults if settings missing
        retention = self.settings.get("retention", {})
        self.policy = {
            "ephemeral_days": retention.get("ephemeral_days", 7),
            "cache_days": retention.get("cache_days", 14),
            "projection_days": retention.get("projection_days", 30),
            "receipt_days": retention.get("receipt_days", 90),
            "bundle_days": retention.get("bundle_days", 90)
        }

    def classify_artifact(self, path: Path) -> str:
        """Classifies an artifact into a retention class."""
        rel_path = path.relative_to(self.repo_root)
        parts = rel_path.parts
        
        if parts[0] == "Docs" or parts[0] == "Session-bundles":
            # Check for archive candidates
            if "td" in parts and "archive" not in parts and ("done" in rel_path.name.lower() or "old" in rel_path.name.lower()):
                return "archive_candidate"
            if "Session-bundles" in parts:
                return "archive_candidate"
            if "generated" in rel_path.name.lower() or "tmp" in rel_path.name.lower():
                return "archive_candidate"
            if parts[0] == "Docs":
                return "canonical"
            return "protected_unknown"
            
        canonical_roots = {"Scripts", "scripts", "anigma", "schemas", "proofs", ".git", ".rig"}
        if parts[0] in canonical_roots or rel_path.name in {"Package.swift", "pyproject.toml", "GEMINI.md"}:
            return "canonical"
            
        if parts[0] == ".build":
            if "projections" in parts:
                return "projection"
            if "cache" in parts or "context" in parts:
                return "cache"
            if "loops" in parts or "actions" in parts or "results" in parts or "receipts" in parts:
                return "receipt"
            if "gc" in parts and ("plans" in parts or "runs" in parts):
                return "receipt"
            # Scratch files, temp logs
            if "tmp" in parts or rel_path.suffix in {".log", ".tmp", ".scratch"}:
                return "ephemeral"
            if rel_path.name == "tui-snapshot.json":
                return "ephemeral"
                
        return "protected_unknown"

    def get_retention_days(self, artifact_class: str) -> int:
        mapping = {
            "ephemeral": self.policy["ephemeral_days"],
            "cache": self.policy["cache_days"],
            "projection": self.policy["projection_days"],
            "receipt": self.policy["receipt_days"],
            "canonical": 999999,
            "protected_unknown": 999999
        }
        return mapping.get(artifact_class, 999999)

    def create_plan(self) -> Dict[str, Any]:
        """Scans the .build/rig directory and identifies candidates for deletion."""
        now = datetime.now(timezone.utc)
        plan_id = str(uuid.uuid4())[:8]
        candidates = []
        protected_paths = []
        bytes_reclaimable = 0
        delete_count = 0
        warnings = []

        scan_root = self.repo_root / ".build" / "rig"
        if not scan_root.exists():
            return self._empty_plan(plan_id, now)

        for root, dirs, files in os.walk(scan_root):
            for name in files:
                file_path = Path(root) / name
                try:
                    artifact_class = self.classify_artifact(file_path)
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                    age_days = (now - mtime).days
                    size_bytes = file_path.stat().st_size
                    
                    retention_days = self.get_retention_days(artifact_class)
                    
                    action = "retain"
                    reason = f"Within retention period ({age_days} < {retention_days} days)"
                    
                    if artifact_class in {"canonical", "protected_unknown"}:
                        action = "protect"
                        reason = f"Protected artifact class: {artifact_class}"
                        protected_paths.append(str(file_path.relative_to(self.repo_root)))
                    elif artifact_class == "archive_candidate":
                        action = "retain"
                        reason = "Candidate for Docs Normalization archive, not deletion"
                        protected_paths.append(str(file_path.relative_to(self.repo_root)))
                    elif age_days >= retention_days:
                        action = "delete"
                        reason = f"Exceeds retention period ({age_days} >= {retention_days} days)"
                        bytes_reclaimable += size_bytes
                        delete_count += 1
                        
                    candidates.append({
                        "path": str(file_path.relative_to(self.repo_root)),
                        "artifact_class": artifact_class,
                        "age_days": age_days,
                        "size_bytes": size_bytes,
                        "reason": reason,
                        "action": action,
                        "requires_apply": action == "delete"
                    })
                except Exception as e:
                    warnings.append(f"Failed to scan {file_path}: {str(e)}")

        plan = {
            "schema_version": "rig.gc_plan.v1",
            "plan_id": plan_id,
            "created_at": now.isoformat(),
            "status": "pass" if not warnings else "warn",
            "retention_policy": self.policy,
            "candidates": candidates,
            "protected": protected_paths,
            "warnings": warnings,
            "bytes_reclaimable": bytes_reclaimable,
            "delete_count": delete_count,
            "authoritative": True
        }
        
        self._persist_plan(plan)
        return plan

    def run(self, plan: Dict[str, Any], mode: Literal["dry_run", "apply"] = "dry_run") -> Dict[str, Any]:
        """Executes a GC plan."""
        started_at = datetime.now(timezone.utc)
        run_id = str(uuid.uuid4())[:8]
        deleted_paths = []
        retained_paths = []
        protected_paths = plan["protected"]
        failed_paths = []
        bytes_reclaimed = 0
        warnings = []

        for candidate in plan["candidates"]:
            path = self.repo_root / candidate["path"]
            if candidate["action"] == "delete" and mode == "apply":
                try:
                    size = path.stat().st_size
                    path.unlink()
                    deleted_paths.append(candidate["path"])
                    bytes_reclaimed += size
                except Exception as e:
                    failed_paths.append({"path": candidate["path"], "error": str(e)})
            elif candidate["action"] == "delete":
                # dry_run
                retained_paths.append(candidate["path"])
            else:
                retained_paths.append(candidate["path"])

        finished_at = datetime.now(timezone.utc)
        
        status = "dry_run"
        if mode == "apply":
            status = "passed" if not failed_paths else "partial"
            if not deleted_paths and failed_paths:
                status = "failed"

        run = {
            "schema_version": "rig.gc_run.v1",
            "run_id": run_id,
            "plan_id": plan["plan_id"],
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "mode": mode,
            "deleted_paths": deleted_paths,
            "retained_paths": retained_paths,
            "protected_paths": protected_paths,
            "failed_paths": failed_paths,
            "bytes_reclaimed": bytes_reclaimed,
            "status": status,
            "warnings": warnings,
            "authoritative": True
        }
        
        self._persist_run(run)
        return run

    def explain(self, path_str: str) -> Dict[str, Any]:
        """Explains why a path is classified a certain way."""
        path = self.repo_root / path_str
        if not path.exists():
            return {"error": "Path does not exist"}
            
        artifact_class = self.classify_artifact(path)
        retention_days = self.get_retention_days(artifact_class)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age_days = (datetime.now(timezone.utc) - mtime).days
        
        return {
            "path": path_str,
            "artifact_class": artifact_class,
            "retention_days": retention_days,
            "age_days": age_days,
            "mtime": mtime.isoformat(),
            "eligible_for_deletion": age_days >= retention_days and artifact_class not in {"canonical", "protected_unknown"}
        }

    def _empty_plan(self, plan_id: str, now: datetime) -> Dict[str, Any]:
        return {
            "schema_version": "rig.gc_plan.v1",
            "plan_id": plan_id,
            "created_at": now.isoformat(),
            "status": "pass",
            "retention_policy": self.policy,
            "candidates": [],
            "protected": [],
            "warnings": ["No scan root found at .build/rig"],
            "bytes_reclaimable": 0,
            "delete_count": 0,
            "authoritative": True
        }

    def _persist_plan(self, plan: Dict[str, Any]):
        self.gc_plans_dir.mkdir(parents=True, exist_ok=True)
        path = self.gc_plans_dir / f"{plan['plan_id']}.json"
        path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        
        # Symlink latest
        latest = self.gc_dir / "latest-plan.json"
        if latest.exists(): latest.unlink()
        try:
            latest.symlink_to(f"plans/{plan['plan_id']}.json")
        except Exception:
            # Fallback for Windows or non-symlink environments
            latest.write_text(json.dumps(plan, indent=2), encoding="utf-8")
            
        # Record to State Store
        try:
            with self.state_store.connect() as conn:
                conn.execute("""
                    INSERT INTO event_log (event_type, payload, created_at)
                    VALUES (?, ?, ?)
                """, ("gc_plan_created", json.dumps({"plan_id": plan["plan_id"], "delete_count": plan["delete_count"]}), plan["created_at"]))
                conn.commit()
        except Exception:
            pass

    def _persist_run(self, run: Dict[str, Any]):
        self.gc_runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.gc_runs_dir / f"{run['run_id']}.json"
        path.write_text(json.dumps(run, indent=2), encoding="utf-8")
        
        # Symlink latest
        latest = self.gc_dir / "latest-run.json"
        if latest.exists(): latest.unlink()
        try:
            latest.symlink_to(f"runs/{run['run_id']}.json")
        except Exception:
            latest.write_text(json.dumps(run, indent=2), encoding="utf-8")

        # Record to State Store
        try:
            with self.state_store.connect() as conn:
                conn.execute("""
                    INSERT INTO event_log (event_type, payload, created_at)
                    VALUES (?, ?, ?)
                """, ("gc_run_completed", json.dumps({"run_id": run["run_id"], "status": run["status"], "bytes_reclaimed": run["bytes_reclaimed"]}), run["finished_at"]))
                conn.commit()
        except Exception:
            pass
