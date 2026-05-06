from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"

class DiffReviewer:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.diff_dir = self.repo_root / ".build" / "rig" / "diff"

    def run_review(self, workspace_id: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        review_id = f"rev-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        
        status = "pass"
        warnings = []
        changed_files = []
        counts = {"files_changed": 0, "insertions": 0, "deletions": 0}
        
        # Check if it's a git repo
        is_git = (self.repo_root / ".git").exists()
        if not is_git:
            return {
                "schema_version": SCHEMA_VERSION,
                "diff_review_id": review_id,
                "created_at": created_at,
                "repo_root": str(self.repo_root),
                "workspace_id": workspace_id,
                "status": "skipped",
                "changed_files": [],
                "counts": counts,
                "risky_paths": [],
                "generated_paths": [],
                "proof_paths": [],
                "schema_paths": [],
                "source_paths": [],
                "diff_excerpt_path": None,
                "warnings": ["not_a_git_repository"],
                "authoritative": True
            }

        try:
            # 1. Get changed files
            res = subprocess.check_output(["git", "status", "--porcelain"], cwd=self.repo_root, text=True)
            for line in res.splitlines():
                if line.strip():
                    # Status is first 2 chars
                    f_path = line[3:].strip()
                    changed_files.append(f_path)
            
            # 2. Get stats
            if changed_files:
                res = subprocess.check_output(["git", "diff", "--shortstat"], cwd=self.repo_root, text=True).strip()
                # Example: 2 files changed, 10 insertions(+), 5 deletions(-)
                if res:
                    counts["files_changed"] = len(changed_files)
                    if "insertion" in res:
                        counts["insertions"] = int(res.split("insertion")[0].split(",")[-1].strip())
                    if "deletion" in res:
                        counts["deletions"] = int(res.split("deletion")[0].split(",")[-1].strip())

            # 3. Classify paths
            risky = []
            generated = []
            proofs = []
            schemas = []
            sources = []
            
            for f in changed_files:
                f_lower = f.lower()
                if "scripts/rig_tools/" in f_lower or "scripts/rig.py" in f_lower:
                    sources.append(f)
                elif f_lower.startswith(".build/"):
                    generated.append(f)
                elif f_lower.startswith("docs/proofs/"):
                    proofs.append(f)
                elif f_lower.endswith(".schema.json"):
                    schemas.append(f)
                elif "secret" in f_lower or ".env" in f_lower or f_lower.endswith(".pem"):
                    risky.append(f)
                    status = "fail"
                    
            # 4. Get diff excerpt (capped)
            diff_text = ""
            if changed_files:
                diff_text = subprocess.check_output(["git", "diff", "--unified=3"], cwd=self.repo_root, text=True)
                if len(diff_text) > 10000:
                    diff_text = diff_text[:10000] + "\n... (diff truncated)"
            
            review = {
                "schema_version": SCHEMA_VERSION,
                "diff_review_id": review_id,
                "created_at": created_at,
                "repo_root": str(self.repo_root),
                "workspace_id": workspace_id,
                "status": status,
                "changed_files": changed_files,
                "counts": counts,
                "risky_paths": risky,
                "generated_paths": generated,
                "proof_paths": proofs,
                "schema_paths": schemas,
                "source_paths": sources,
                "diff_excerpt_path": None,
                "warnings": warnings,
                "authoritative": True
            }
            
            if not dry_run:
                rev_dir = self.diff_dir / "reviews"
                rev_dir.mkdir(parents=True, exist_ok=True)
                
                json_path = rev_dir / f"{review_id}.json"
                json_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
                
                patch_path = rev_dir / f"{review_id}.patch.txt"
                patch_path.write_text(diff_text, encoding="utf-8")
                review["diff_excerpt_path"] = str(patch_path)
                
                # Update latest
                (self.diff_dir / "latest.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
                
                # Update markdown
                md_path = self.diff_dir / "latest.md"
                md_content = [
                    f"# Diff Review: {review_id}",
                    f"- Status: {status.upper()}",
                    f"- Files Changed: {counts['files_changed']}",
                    f"- Insertions: {counts['insertions']}",
                    f"- Deletions: {counts['deletions']}",
                    "",
                    "## Risky Paths" if risky else "",
                ]
                for r in risky: md_content.append(f"- ⚠️ {r}")
                md_content.append("\n## Changed Files")
                for f in changed_files[:20]: md_content.append(f"- {f}")
                if len(changed_files) > 20: md_content.append(f"- ... and {len(changed_files)-20} more")
                
                md_path.write_text("\n".join(md_content), encoding="utf-8")

            return review
            
        except Exception as e:
            return {
                "schema_version": SCHEMA_VERSION,
                "diff_review_id": review_id,
                "created_at": created_at,
                "repo_root": str(self.repo_root),
                "workspace_id": workspace_id,
                "status": "fail",
                "changed_files": [],
                "counts": counts,
                "risky_paths": [],
                "generated_paths": [],
                "proof_paths": [],
                "schema_paths": [],
                "source_paths": [],
                "diff_excerpt_path": None,
                "warnings": [str(e)],
                "authoritative": True
            }
