from __future__ import annotations

import json
import os
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"

def get_default_cache_path(repo_root: Path) -> Path:
    return repo_root / ".build" / "rig" / "models" / "cache"

def load_catalog(repo_root: Path) -> Dict[str, Any]:
    catalog_path = repo_root / "Docs" / "dev" / "rig" / "model-catalog.json"
    if not catalog_path.exists():
        return {"schema_version": "1.0.0", "models": [], "authoritative": True}
    try:
        return json.loads(catalog_path.read_text(encoding="utf-8"))
    except:
        return {"schema_version": "1.0.0", "models": [], "authoritative": True}

def list_registered_models(repo_root: Path) -> List[Dict[str, Any]]:
    reg_dir = repo_root / ".build" / "rig" / "models" / "registry"
    if not reg_dir.exists():
        return []
    
    models = []
    for f in reg_dir.glob("*.json"):
        try:
            models.append(json.loads(f.read_text(encoding="utf-8")))
        except: pass
    return models

def list_local_models(repo_root: Path) -> List[Dict[str, Any]]:
    return list_registered_models(repo_root)

def recommend_models(repo_root: Path) -> List[Dict[str, Any]]:
    from rig_tools import system_benchmark
    bench = system_benchmark.get_latest_benchmark(repo_root)
    if not bench:
        # Conservative recommendations if no benchmark
        total_ram_gb = 8.0
    else:
        total_ram_gb = bench["total_memory_bytes"] / (1024**3)
        
    catalog = load_catalog(repo_root)
    recommended = []
    for m in catalog.get("models", []):
        if m["min_ram_gb"] <= total_ram_gb:
            recommended.append(m)
            
    return recommended

def get_model_download_plan(repo_root: Path, model_id: str) -> Dict[str, Any]:
    catalog = load_catalog(repo_root)
    model = next((m for m in catalog.get("models", []) if m["model_id"] == model_id), None)
    if not model:
        raise ValueError(f"Model {model_id} not found in catalog")
        
    download_id = f"dl-{uuid.uuid4().hex[:8]}"
    cache_path = get_default_cache_path(repo_root)
    
    # Estimate local path
    if model["format"] == "mlx":
        local_path = cache_path / model["repo_id"].replace("/", "--")
    else:
        local_path = cache_path / (model["filename"] or f"{model['model_id']}.gguf")
        
    return {
        "schema_version": SCHEMA_VERSION,
        "download_id": download_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "repo_id": model["repo_id"],
        "filename": model["filename"],
        "revision": model.get("revision", "main"),
        "backend": model["backend"],
        "format": model["format"],
        "status": "planned",
        "local_path": str(local_path),
        "cache_path": str(cache_path),
        "size_bytes": model.get("size_bytes"),
        "license_status": model["license_status"],
        "dry_run": True,
        "warnings": [],
        "authoritative": True
    }

def run_download(repo_root: Path, plan: Dict[str, Any], dry_run: bool = True) -> Dict[str, Any]:
    if dry_run:
        plan["status"] = "dry_run"
        return plan
        
    plan["status"] = "downloading"
    
    try:
        import huggingface_hub
    except ImportError:
        plan["status"] = "failed"
        plan["warnings"].append("huggingface_hub_missing")
        return plan
        
    cache_dir = Path(plan["cache_path"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        if plan["format"] == "mlx":
            # For MLX, we usually download the whole snapshot
            local_path = huggingface_hub.snapshot_download(
                repo_id=plan["repo_id"],
                revision=plan["revision"],
                cache_dir=cache_dir,
                local_dir=Path(plan["local_path"]),
                local_dir_use_symlinks=False
            )
        else:
            # For GGUF, we download a single file
            local_path = huggingface_hub.hf_hub_download(
                repo_id=plan["repo_id"],
                filename=plan["filename"],
                revision=plan["revision"],
                cache_dir=cache_dir
            )
            
        plan["status"] = "downloaded"
        plan["local_path"] = str(local_path)
        
        # Register the model
        _register_model(repo_root, plan)
        
    except Exception as e:
        plan["status"] = "failed"
        plan["warnings"].append(str(e))
        
    return plan

def _register_model(repo_root: Path, plan: Dict[str, Any]) -> None:
    reg_dir = repo_root / ".build" / "rig" / "models" / "registry"
    reg_dir.mkdir(parents=True, exist_ok=True)
    
    reg_file = reg_dir / f"{plan['model_id']}.json"
    reg_file.write_text(json.dumps(plan, indent=2), encoding="utf-8")

def verify_model(repo_root: Path, model_id: str) -> Dict[str, Any]:
    models = list_registered_models(repo_root)
    m = next((m for m in models if m["model_id"] == model_id), None)
    if not m:
        return {"status": "not_registered", "model_id": model_id}
        
    local_path = Path(m["local_path"])
    if not local_path.exists():
        return {"status": "missing_file", "model_id": model_id, "path": str(local_path)}
        
    return {"status": "verified", "model_id": model_id, "path": str(local_path), "size": local_path.stat().st_size if local_path.is_file() else None}
