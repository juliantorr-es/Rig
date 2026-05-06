from __future__ import annotations

import os
import json
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from rig_tools import project_adapters

SCHEMA_VERSION = "1.0.0"
MAX_SCAN_FILES = 10000
MAX_SCAN_BYTES_PER_FILE = 1024 * 64 # 64KB for pattern matching if needed, though MVP is mostly file-based

DEFAULT_IGNORE = {
    ".git", ".build", "node_modules", ".venv", "venv", "dist", "build", 
    "DerivedData", "target", ".DS_Store", "__pycache__"
}

LANG_MAP = {
    ".py": "python",
    ".swift": "swift",
    ".rs": "rust",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".md": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
}

def run_digest(repo_root: Path) -> Dict[str, Any]:
    """Scans the repository and returns a project digest."""
    digest_id = f"dig-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    
    stats: Dict[str, Dict[str, Any]] = {}
    detected_files: List[str] = []
    
    file_count = 0
    total_bytes = 0
    
    # 1. Recursive Scan
    for root, dirs, files in os.walk(repo_root):
        # Respect ignore
        dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORE and not d.startswith(".")]
        
        rel_root = Path(root).relative_to(repo_root)
        
        for f in files:
            if f.startswith("."):
                continue
            
            file_count += 1
            if file_count > MAX_SCAN_FILES:
                break
                
            f_path = Path(root) / f
            try:
                f_size = f_path.stat().st_size
            except OSError:
                continue
                
            total_bytes += f_size
            ext = f_path.suffix.lower()
            lang = LANG_MAP.get(ext, "other")
            
            if lang not in stats:
                stats[lang] = {"file_count": 0, "bytes": 0}
            
            stats[lang]["file_count"] += 1
            stats[lang]["bytes"] += f_size
            detected_files.append(str(rel_root / f))
            
        if file_count > MAX_SCAN_FILES:
            break

    # 2. Language Summaries
    languages = []
    for lang, data in stats.items():
        percentage = (data["bytes"] / total_bytes * 100) if total_bytes > 0 else 0
        languages.append({
            "language": lang,
            "file_count": data["file_count"],
            "bytes": data["bytes"],
            "percentage": round(percentage, 2),
            "confidence": "high" if percentage > 10 else "medium"
        })
    languages.sort(key=lambda x: x["bytes"], reverse=True)

    # 3. Stack Detection
    detected_stacks = []
    adapters = project_adapters.list_adapters()
    
    for adapter in adapters:
        evidence = []
        for detector in adapter.get("detectors", []):
            # Cheap check for file or directory presence
            if detector.endswith("/"):
                if (repo_root / detector).is_dir():
                    evidence.append(detector)
            elif detector.startswith("*."):
                ext = detector[1:]
                if any(f.endswith(ext) for f in detected_files):
                    evidence.append(detector)
            else:
                if (repo_root / detector).exists():
                    evidence.append(detector)
        
        if evidence:
            confidence = "high" if len(evidence) >= 2 else "medium"
            detected_stacks.append({
                "stack_id": adapter["adapter_id"],
                "confidence": confidence,
                "evidence": evidence,
                "recommended_adapter": adapter["adapter_id"]
            })

    # 4. Roots mapping
    source_roots = _detect_roots(repo_root, ["src", "lib", "Sources", "app"])
    test_roots = _detect_roots(repo_root, ["tests", "test", "Tests"])
    docs_roots = _detect_roots(repo_root, ["Docs", "docs", "documentation"])

    # 5. Build systems and package managers
    build_systems = []
    package_managers = []
    if (repo_root / "CMakeLists.txt").exists(): build_systems.append("cmake")
    if (repo_root / "Makefile").exists(): build_systems.append("make")
    if (repo_root / "Package.swift").exists(): build_systems.append("swiftpm")
    if (repo_root / "Cargo.toml").exists(): build_systems.append("cargo")
    if (repo_root / "package.json").exists(): package_managers.append("npm")
    if (repo_root / "pnpm-lock.yaml").exists(): package_managers.append("pnpm")
    if (repo_root / "pyproject.toml").exists(): build_systems.append("pip/build")

    return {
        "schema_version": SCHEMA_VERSION,
        "digest_id": digest_id,
        "created_at": created_at,
        "repo_root": str(repo_root),
        "git_repo_detected": (repo_root / ".git").is_dir(),
        "rig_initialized": (repo_root / ".rig").is_dir(),
        "languages": languages,
        "detected_stacks": detected_stacks,
        "build_systems": build_systems,
        "package_managers": package_managers,
        "source_roots": source_roots,
        "test_roots": test_roots,
        "docs_roots": docs_roots,
        "config_files": [f for f in detected_files if f.endswith((".json", ".toml", ".yaml", ".yml", ".config.js"))][:20],
        "ignored_roots": list(DEFAULT_IGNORE),
        "recommended_adapters": [s["recommended_adapter"] for s in detected_stacks],
        "recommended_validators": sorted(list(set(sum([project_adapters.get_adapter(s["recommended_adapter"]).get("validator_rules", []) for s in detected_stacks], [])))),
        "warnings": ["scan_limit_reached"] if file_count > MAX_SCAN_FILES else [],
        "authoritative": False
    }

def _detect_roots(repo_root: Path, names: List[str]) -> List[str]:
    roots = []
    for name in names:
        if (repo_root / name).is_dir():
            roots.append(name)
    return roots

def write_digest(repo_root: Path, digest: Dict[str, Any]) -> Path:
    target_dir = repo_root / ".build" / "rig" / "project"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = target_dir / "latest-digest.json"
    json_path.write_text(json.dumps(digest, indent=2), encoding="utf-8")
    
    md_path = target_dir / "latest-digest.md"
    md_content = [
        f"# Project Digest: {digest['digest_id']}",
        f"Created: {digest['created_at']}",
        "",
        "## Languages",
        "| Language | Files | Bytes | % |",
        "|---|---|---|---|",
    ]
    for lang in digest["languages"]:
        md_content.append(f"| {lang['language']} | {lang['file_count']} | {lang['bytes']} | {lang['percentage']}% |")
    
    md_content.extend([
        "",
        "## Detected Stacks",
    ])
    for stack in digest["detected_stacks"]:
        md_content.append(f"- **{stack['stack_id']}** (Confidence: {stack['confidence']})")
        md_content.append(f"  - Evidence: {', '.join(stack['evidence'])}")
        
    md_path.write_text("\n".join(md_content), encoding="utf-8")
    return json_path
