from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"

class ProductizationChecker:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self.product_dir = self.repo_root / ".build" / "rig" / "product"

    def run_check(self, dry_run: bool = False) -> Dict[str, Any]:
        report_id = f"prod-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()
        
        checks = []
        warnings = []
        failures = []
        recommendations = []
        
        # 1. Package/install
        pp_path = self.repo_root / "pyproject.toml"
        if pp_path.exists():
            checks.append({"check_id": "pyproject_exists", "subsystem": "packaging", "status": "pass", "detail": "pyproject.toml found"})
            # Simple content check
            content = pp_path.read_text(encoding="utf-8")
            if 'name = "rig-control"' in content:
                checks.append({"check_id": "project_name_correct", "subsystem": "packaging", "status": "pass", "detail": "name is rig-control"})
            else:
                checks.append({"check_id": "project_name_correct", "subsystem": "packaging", "status": "fail", "detail": "name is not rig-control"})
                failures.append("packaging:project_name_mismatch")
        else:
            checks.append({"check_id": "pyproject_exists", "subsystem": "packaging", "status": "fail", "detail": "pyproject.toml missing"})
            failures.append("packaging:pyproject_missing")

        # 2. UI readiness
        try:
            from rig_tools import tui_app
            checks.append({"check_id": "tui_imports", "subsystem": "ui", "status": "pass", "detail": "TUI classes loadable"})
        except ImportError as e:
            checks.append({"check_id": "tui_imports", "subsystem": "ui", "status": "warn", "detail": f"TUI imports failed: {e}"})
            warnings.append("ui:textual_missing")
        
        # 3. Project onboarding
        from rig_tools import project_digest
        digest_path = self.repo_root / ".build" / "rig" / "project" / "latest.json"
        if digest_path.exists():
            checks.append({"check_id": "project_digested", "subsystem": "onboarding", "status": "pass", "detail": "Latest digest found"})
        else:
            checks.append({"check_id": "project_digested", "subsystem": "onboarding", "status": "warn", "detail": "No project digest found"})
            warnings.append("onboarding:not_digested")
            recommendations.append("Run 'rig project digest' to initialize")

        # 4. Workspace/Review
        ws_dir = self.repo_root / ".build" / "rig" / "workspaces"
        if ws_dir.is_dir():
            checks.append({"check_id": "workspace_dir_exists", "subsystem": "workspaces", "status": "pass", "detail": "Workspaces directory found"})
        else:
            checks.append({"check_id": "workspace_dir_exists", "subsystem": "workspaces", "status": "warn", "detail": "No workspaces created yet"})

        # 5. Safety (Doctor/Audit/Sentinel)
        doc_latest_path = self.repo_root / ".build" / "rig" / "doctor" / "latest.json"
        if doc_latest_path.exists():
            try:
                doc_report = json.loads(doc_latest_path.read_text(encoding="utf-8"))
                if doc_report["status"] == "fail":
                    checks.append({"check_id": "doctor_pass", "subsystem": "safety", "status": "fail", "detail": f"Latest doctor failed with {len(doc_report.get('failures', []))} failures"})
                    failures.append("safety:doctor_fail")
                else:
                    checks.append({"check_id": "doctor_pass", "subsystem": "safety", "status": "pass", "detail": "Latest doctor passed or warned"})
            except:
                checks.append({"check_id": "doctor_pass", "subsystem": "safety", "status": "warn", "detail": "Failed to parse latest doctor report"})
        else:
            checks.append({"check_id": "doctor_pass", "subsystem": "safety", "status": "warn", "detail": "No doctor report found"})
            recommendations.append("Run 'rig doctor' to verify safety")

        status = "pass"
        if failures:
            status = "fail"
        elif warnings:
            status = "warn"
            
        report = {
            "schema_version": SCHEMA_VERSION,
            "report_id": report_id,
            "created_at": created_at,
            "status": status,
            "checks": checks,
            "warnings": warnings,
            "failures": failures,
            "recommendations": recommendations,
            "artifact_paths": [],
            "authoritative": True
        }
        
        if not dry_run:
            self.product_dir.mkdir(parents=True, exist_ok=True)
            (self.product_dir / "reports").mkdir(parents=True, exist_ok=True)
            
            json_path = self.product_dir / "reports" / f"{report_id}.json"
            json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            report["artifact_paths"].append(str(json_path))
            
            # Update latest
            (self.product_dir / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            
            # Update markdown
            md_path = self.product_dir / "latest.md"
            md_content = [
                f"# Rig Productization Report: {report_id}",
                f"- Status: {status.upper()}",
                f"- Created: {created_at}",
                "",
                "## Checks",
            ]
            for c in checks:
                icon = "✅" if c["status"] == "pass" else "⚠️" if c["status"] == "warn" else "❌"
                md_content.append(f"- {icon} **{c['check_id']}**: {c['detail']}")
                
            if recommendations:
                md_content.append("\n## Recommendations")
                for r in recommendations: md_content.append(f"- {r}")
                
            md_path.write_text("\n".join(md_content), encoding="utf-8")
            report["artifact_paths"].append(str(md_path))

        return report
