from __future__ import annotations

import json
import os
import platform
import sys
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1.0.0"

def get_system_stats() -> Dict[str, Any]:
    stats = {
        "platform": platform.system(),
        "machine": platform.machine(),
        "python_version": sys.version.split()[0],
        "cpu_count": os.cpu_count() or 1,
        "total_memory_bytes": 0,
        "available_memory_bytes": 0,
    }
    
    # Try psutil
    try:
        import psutil
        vm = psutil.virtual_memory()
        stats["total_memory_bytes"] = vm.total
        stats["available_memory_bytes"] = vm.available
    except ImportError:
        # Fallback for RAM on macOS
        if stats["platform"] == "Darwin":
            try:
                res = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
                stats["total_memory_bytes"] = int(res)
                # Available memory is harder without psutil, assume 50% for MVP
                stats["available_memory_bytes"] = stats["total_memory_bytes"] // 2
            except: pass
            
    return stats

def check_backend_availability() -> Dict[str, bool]:
    availability = {
        "mlx": False,
        "llama_cpp_python": False,
        "llama_server": False,
        "huggingface_hub": False
    }
    
    try:
        import mlx.core
        availability["mlx"] = True
    except ImportError: pass
    
    try:
        import llama_cpp
        availability["llama_cpp_python"] = True
    except ImportError: pass
    
    try:
        import huggingface_hub
        availability["huggingface_hub"] = True
    except ImportError: pass
    
    # Check if llama-server is in PATH
    try:
        subprocess.check_call(["which", "llama-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        availability["llama_server"] = True
    except: pass
    
    return availability

def recommend_profile(total_mem_bytes: int) -> Dict[str, Any]:
    total_gb = total_mem_bytes / (1024**3)
    
    if total_gb >= 64:
        return {
            "profile_id": "ultra",
            "max_parallel_candidates": 8,
            "default_context_tokens": 32768,
            "patch_context_tokens": 128000,
            "swarm_mode": "parallel"
        }
    elif total_gb >= 32:
        return {
            "profile_id": "high",
            "max_parallel_candidates": 4,
            "default_context_tokens": 16384,
            "patch_context_tokens": 64000,
            "swarm_mode": "parallel"
        }
    elif total_gb >= 16:
        return {
            "profile_id": "medium",
            "max_parallel_candidates": 2,
            "default_context_tokens": 8192,
            "patch_context_tokens": 32000,
            "swarm_mode": "parallel"
        }
    else:
        return {
            "profile_id": "low",
            "max_parallel_candidates": 1,
            "default_context_tokens": 4096,
            "patch_context_tokens": 8192,
            "swarm_mode": "sequential"
        }

def run_benchmark(repo_root: Path, quick: bool = True) -> Dict[str, Any]:
    benchmark_id = f"bench-{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    
    stats = get_system_stats()
    backends = check_backend_availability()
    profile = recommend_profile(stats["total_memory_bytes"])
    
    benchmark = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "created_at": created_at,
        "platform": stats["platform"],
        "machine": stats["machine"],
        "python_version": stats["python_version"],
        "total_memory_bytes": stats["total_memory_bytes"],
        "available_memory_bytes": stats["available_memory_bytes"],
        "cpu_count": stats["cpu_count"],
        "backend_availability": backends,
        "quick_results": {
            "prompt_eval_tokens_per_second": None,
            "generation_tokens_per_second": None,
            "model_id": None
        },
        "recommended_profile": profile,
        "warnings": [],
        "authoritative": True
    }
    
    if stats["total_memory_bytes"] == 0:
        benchmark["warnings"].append("could_not_determine_memory")
        
    return benchmark

def write_benchmark_report(repo_root: Path, benchmark: Dict[str, Any]) -> Path:
    target_dir = repo_root / ".build" / "rig" / "bench"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = target_dir / "latest.json"
    json_path.write_text(json.dumps(benchmark, indent=2), encoding="utf-8")
    
    md_path = target_dir / "latest.md"
    total_gb = benchmark['total_memory_bytes'] / (1024**3)
    md_content = [
        f"# Rig System Benchmark: {benchmark['benchmark_id']}",
        f"- Platform: {benchmark['platform']} ({benchmark['machine']})",
        f"- RAM: {total_gb:.1f} GB",
        f"- CPU: {benchmark['cpu_count']} cores",
        "",
        "## Backends",
    ]
    for b, avail in benchmark["backend_availability"].items():
        status = "✅" if avail else "❌"
        md_content.append(f"- {status} {b}")
        
    md_content.extend([
        "",
        "## Recommended Profile",
        f"- Profile: **{benchmark['recommended_profile']['profile_id']}**",
        f"- Parallel Candidates: {benchmark['recommended_profile']['max_parallel_candidates']}",
        f"- Default Context: {benchmark['recommended_profile']['default_context_tokens']} tokens",
        f"- Swarm Mode: {benchmark['recommended_profile']['swarm_mode']}",
    ])
    
    md_path.write_text("\n".join(md_content), encoding="utf-8")
    return json_path

def get_latest_benchmark(repo_root: Path) -> Optional[Dict[str, Any]]:
    path = repo_root / ".build" / "rig" / "bench" / "latest.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except: pass
    return None
