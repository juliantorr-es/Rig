from __future__ import annotations

import ast
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from rig_tools import structural_rules

SCHEMA_VERSION = "1.0.0"

DEFAULT_IGNORE = {
    ".git", ".build", "node_modules", ".venv", "venv", "dist", "build", 
    "DerivedData", "target"
}

def run_scan(repo_root: Path, languages: Optional[List[str]] = None) -> Dict[str, Any]:
    report_id = f"struct-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    
    findings: List[Dict[str, Any]] = []
    engines: Set[str] = set()
    detected_langs: Set[str] = set()
    warnings: List[str] = []

    # 1. Identify files
    # For MVP, we use os.walk or similar, respecting ignore
    import os
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORE and not d.startswith(".")]
        
        rel_root = Path(root).relative_to(repo_root)
        
        for f in files:
            if f.startswith("."):
                continue
            
            f_path = Path(root) / f
            ext = f_path.suffix.lower()
            
            lang = _map_ext_to_lang(ext)
            if not lang:
                continue
                
            if languages and lang not in languages:
                continue
            
            detected_langs.add(lang)
            
            try:
                # Cap file size for MVP
                if f_path.stat().st_size > 1024 * 512: # 512KB
                    warnings.append(f"Skipped large file: {f_path.relative_to(repo_root)}")
                    continue
                    
                content = f_path.read_text(encoding="utf-8")
                
                # 2. Apply rules based on language
                if lang == "python":
                    engines.add("python_ast")
                    try:
                        tree = ast.parse(content)
                        visitor = structural_rules.PythonShellTrueRule(f_path.relative_to(repo_root))
                        visitor.visit(tree)
                        findings.extend(visitor.findings)
                        
                        visitor = structural_rules.PythonEvalExecRule(f_path.relative_to(repo_root))
                        visitor.visit(tree)
                        findings.extend(visitor.findings)
                        
                        visitor = structural_rules.PythonBroadExceptPassRule(f_path.relative_to(repo_root))
                        visitor.visit(tree)
                        findings.extend(visitor.findings)
                    except SyntaxError:
                        warnings.append(f"Syntax error in {f_path.relative_to(repo_root)}")
                
                elif lang == "swift":
                    engines.add("textual_import_scan")
                    scanner = structural_rules.SwiftImportScanner(f_path.relative_to(repo_root))
                    scanner.scan(content)
                    findings.extend(scanner.findings)
                
                elif lang == "rust":
                    engines.add("textual_inventory_scan")
                    scanner = structural_rules.RustInventoryScanner(f_path.relative_to(repo_root))
                    scanner.scan(content)
                    findings.extend(scanner.findings)
                    
            except Exception as e:
                warnings.append(f"Error scanning {f_path.relative_to(repo_root)}: {str(e)}")

    # 3. Summarize
    counts = {"info": 0, "warning": 0, "error": 0, "critical": 0}
    for f in findings:
        counts[f["severity"]] += 1
        
    status = "pass"
    if counts["critical"] > 0 or counts["error"] > 0:
        status = "fail"
    elif counts["warning"] > 0:
        status = "warn"

    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": report_id,
        "created_at": created_at,
        "status": status,
        "engines": sorted(list(engines)),
        "languages": sorted(list(detected_langs)),
        "findings": findings,
        "counts_by_severity": counts,
        "warnings": warnings,
        "authoritative": True
    }

def _map_ext_to_lang(ext: str) -> Optional[str]:
    mapping = {
        ".py": "python",
        ".swift": "swift",
        ".rs": "rust",
        ".js": "javascript",
        ".ts": "typescript"
    }
    return mapping.get(ext)

def write_report(repo_root: Path, report: Dict[str, Any]) -> Path:
    target_dir = repo_root / ".build" / "rig" / "structural"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    latest_path = target_dir / "latest.json"
    latest_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    
    reports_dir = target_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"{report['report_id']}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    
    md_path = target_dir / "latest.md"
    md_content = [
        f"# Structural Scan Report: {report['report_id']}",
        f"Status: {report['status'].upper()}",
        f"Created: {report['created_at']}",
        "",
        "## Severity Summary",
        f"- Critical: {report['counts_by_severity']['critical']}",
        f"- Error: {report['counts_by_severity']['error']}",
        f"- Warning: {report['counts_by_severity']['warning']}",
        f"- Info: {report['counts_by_severity']['info']}",
        "",
        "## Findings",
        "| Severity | Language | Rule | Path | Message |",
        "|---|---|---|---|---|",
    ]
    for f in report["findings"][:100]: # Cap for MD
        md_content.append(f"| {f['severity']} | {f['language']} | {f['rule_id']} | {f['path']} | {f['message']} |")
        
    if len(report["findings"]) > 100:
        md_content.append(f"\n... and {len(report['findings']) - 100} more findings.")
        
    md_path.write_text("\n".join(md_content), encoding="utf-8")
    return latest_path
