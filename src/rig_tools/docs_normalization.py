from __future__ import annotations

import os
import json
import uuid
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from rig_tools.state_store import StateStore

class DocsNormalizationPlanner:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.state_store = StateStore(repo_root)
        self.archive_root = repo_root / "Docs" / "archive"
        self.gc_dir = repo_root / ".build" / "rig" / "gc"
        self.manifest_path = self.archive_root / "archive-manifest.json"

    def is_git_tracked(self, path: Path) -> bool:
        """Checks if a file is tracked by git using a safe argv subprocess."""
        try:
            rel_path = str(path.relative_to(self.repo_root))
            res = subprocess.run(
                ["git", "ls-files", "--error-unmatch", rel_path],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=2
            )
            return res.returncode == 0
        except Exception:
            return False

    def _hash_file(self, path: Path) -> str:
        """Returns SHA-256 hash of file content."""
        hasher = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_plan(self) -> Dict[str, Any]:
        """Scans docs and bundles to propose normalization/archive actions."""
        now = datetime.now(timezone.utc)
        plan_id = str(uuid.uuid4())[:8]
        candidates = []
        duplicate_groups = {}
        warnings = []
        
        # Directories to scan
        scan_dirs = [
            self.repo_root / "Docs",
            self.repo_root / "Session-bundles"
        ]

        # Explicitly protected canonical paths (never candidates)
        protected_prefixes = [
            self.repo_root / "Docs" / "governance",
            self.repo_root / "Docs" / "schemas",
            self.repo_root / "Docs" / "proofs",
            self.repo_root / "Docs" / "archive"
        ]

        content_hashes = {}

        for scan_dir in scan_dirs:
            if not scan_dir.exists(): continue
            for root, _, files in os.walk(scan_dir):
                for name in files:
                    # Skip hidden files
                    if name.startswith("."): continue
                    
                    file_path = Path(root) / name
                    
                    # Skip protected
                    if any(file_path.is_relative_to(p) for p in protected_prefixes if p.exists()):
                        continue

                    rel_path = file_path.relative_to(self.repo_root)
                    
                    # Hash for duplicates
                    try:
                        fhash = self._hash_file(file_path)
                        if fhash in content_hashes:
                            content_hashes[fhash].append(str(rel_path))
                        else:
                            content_hashes[fhash] = [str(rel_path)]
                    except Exception as e:
                        warnings.append(f"Failed to hash {rel_path}: {e}")
                        continue
                        
                    # Heuristics for obsolete/superseded
                    is_candidate = False
                    reason = ""
                    artifact_class = "archive_candidate"
                    
                    if "td" in root.lower() and "archive" not in root.lower() and ("done" in name.lower() or "old" in name.lower()):
                        is_candidate = True
                        reason = "Obsolete TD task"
                    elif "Session-bundles" in root:
                        is_candidate = True
                        reason = "Legacy session bundle"
                    elif "generated" in name.lower() or "tmp" in name.lower():
                        is_candidate = True
                        reason = "Temporary or generated artifact"
                        
                    if is_candidate:
                        candidates.append({
                            "original_path": str(rel_path),
                            "proposed_archive_path": f"Docs/archive/{now.year}/{now.month:02d}/misc/{name}",
                            "reason": reason,
                            "artifact_class": artifact_class,
                            "action": "move",
                            "requires_apply": True,
                            "git_tracked": self.is_git_tracked(file_path)
                        })

        # Process duplicates
        groups_list = []
        for fhash, paths in content_hashes.items():
            if len(paths) > 1:
                groups_list.append({"hash": fhash, "paths": paths})
                # Add to candidates (propose archiving the duplicates, keeping the first)
                for dup_path in paths[1:]:
                    candidates.append({
                        "original_path": dup_path,
                        "proposed_archive_path": f"Docs/archive/{now.year}/{now.month:02d}/misc/dup_{Path(dup_path).name}",
                        "reason": f"Exact content duplicate of {paths[0]}",
                        "artifact_class": "duplicate",
                        "action": "move",
                        "requires_apply": True,
                        "git_tracked": self.is_git_tracked(self.repo_root / dup_path)
                    })

        plan = {
            "schema_version": "rig.docs_normalization_plan.v1",
            "plan_id": plan_id,
            "created_at": now.isoformat(),
            "candidates": candidates,
            "duplicate_groups": groups_list,
            "status": "pass" if not warnings else "warn",
            "warnings": warnings,
            "authoritative": True
        }
        
        self._persist_plan(plan)
        return plan

    def _persist_plan(self, plan: Dict[str, Any]):
        self.gc_dir.mkdir(parents=True, exist_ok=True)
        path = self.gc_dir / "latest-docs-plan.json"
        path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        
        try:
            with self.state_store.connect() as conn:
                conn.execute("""
                    INSERT INTO event_log (event_type, payload, created_at)
                    VALUES (?, ?, ?)
                """, ("docs_plan_created", json.dumps({"plan_id": plan["plan_id"], "candidate_count": len(plan["candidates"])}), plan["created_at"]))
                conn.commit()
        except Exception:
            pass

    def run_archive(self, plan: Dict[str, Any], apply: bool = False, allow_git_tracked: bool = False) -> Dict[str, Any]:
        """Executes the docs normalization plan, moving files to the archive."""
        now = datetime.now(timezone.utc)
        entries = []
        warnings = []
        
        for candidate in plan["candidates"]:
            if candidate["action"] != "move": continue
            
            orig_path = self.repo_root / candidate["original_path"]
            arch_path = self.repo_root / candidate["proposed_archive_path"]
            
            is_tracked = candidate.get("git_tracked", False)
            if is_tracked and not allow_git_tracked:
                warnings.append(f"Refusing to archive git-tracked file without --allow-git-tracked-archive: {candidate['original_path']}")
                entries.append({
                    "original_path": candidate["original_path"],
                    "archive_path": candidate["proposed_archive_path"],
                    "artifact_class": candidate["artifact_class"],
                    "reason": "Git-tracked, requires explicit allow flag",
                    "action": "protect",
                    "applied": False
                })
                continue
                
            if apply:
                try:
                    if orig_path.exists():
                        arch_path.parent.mkdir(parents=True, exist_ok=True)
                        orig_path.rename(arch_path)
                        entries.append({
                            "original_path": candidate["original_path"],
                            "archive_path": candidate["proposed_archive_path"],
                            "artifact_class": candidate["artifact_class"],
                            "reason": candidate["reason"],
                            "action": "move",
                            "applied": True
                        })
                except Exception as e:
                    warnings.append(f"Failed to move {orig_path}: {e}")
            else:
                # Dry run
                entries.append({
                    "original_path": candidate["original_path"],
                    "archive_path": candidate["proposed_archive_path"],
                    "artifact_class": candidate["artifact_class"],
                    "reason": candidate["reason"],
                    "action": "move",
                    "applied": False
                })

        manifest = {
            "schema_version": "rig.archive_manifest.v1",
            "created_at": now.isoformat(),
            "archive_root": str(self.archive_root.relative_to(self.repo_root)),
            "entries": entries,
            "warnings": warnings,
            "authoritative": True
        }
        
        if apply:
            self._update_manifest(manifest)
            
        return manifest

    def _update_manifest(self, new_manifest: Dict[str, Any]):
        self.archive_root.mkdir(parents=True, exist_ok=True)
        
        if self.manifest_path.exists():
            try:
                existing = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                existing["entries"].extend(new_manifest["entries"])
                existing["created_at"] = new_manifest["created_at"]
                if new_manifest["warnings"]:
                    existing.setdefault("warnings", []).extend(new_manifest["warnings"])
                new_manifest = existing
            except Exception:
                pass
                
        self.manifest_path.write_text(json.dumps(new_manifest, indent=2), encoding="utf-8")
        
        try:
            with self.state_store.connect() as conn:
                conn.execute("""
                    INSERT INTO event_log (event_type, payload, created_at)
                    VALUES (?, ?, ?)
                """, ("docs_archived", json.dumps({"entries": len(new_manifest["entries"])}), new_manifest["created_at"]))
                conn.commit()
        except Exception:
            pass
