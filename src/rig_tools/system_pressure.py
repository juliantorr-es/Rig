from __future__ import annotations

import json
import os
import platform
import socket
import sys
import time
from pathlib import Path
from typing import Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

def sample_system_pressure(repo_root: Path) -> dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data = {
        "schema_version": "rig.system_pressure.v1",
        "created_at": now,
        "hostname": socket.gethostname(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "warnings": [],
        "authoritative": False,
        "status": "available" if HAS_PSUTIL else "unavailable",
    }

    if not HAS_PSUTIL:
        data["warnings"].append("system telemetry unavailable: install psutil")
        return data

    try:
        # RAM
        mem = psutil.virtual_memory()
        data["memory"] = {
            "total_bytes": mem.total,
            "available_bytes": mem.available,
            "used_bytes": mem.used,
            "percent": mem.percent,
        }

        # Swap
        swap = psutil.swap_memory()
        data["swap"] = {
            "total_bytes": swap.total,
            "used_bytes": swap.used,
            "free_bytes": swap.free,
            "percent": swap.percent,
        }

        # CPU
        data["cpu"] = {
            "percent": psutil.cpu_percent(interval=None),
            "count": psutil.cpu_count(),
            "load_average": os.getloadavg() if hasattr(os, "getloadavg") else [0, 0, 0],
        }

        # Disk
        disk = psutil.disk_usage(str(repo_root))
        data["disk"] = {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": disk.percent,
        }

        # Processes
        current_proc = psutil.Process()
        data["rig_process"] = {
            "pid": current_proc.pid,
            "rss_bytes": current_proc.memory_info().rss,
            "cpu_percent": current_proc.cpu_percent(),
            "thread_count": current_proc.num_threads(),
            "open_files": len(current_proc.open_files()),
        }

        # Child processes (e.g. workers)
        children = []
        for child in current_proc.children(recursive=True):
            try:
                children.append({
                    "pid": child.pid,
                    "name": child.name(),
                    "rss_bytes": child.memory_info().rss,
                    "cpu_percent": child.cpu_percent(),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        data["child_processes"] = children

        # Local Model (Best effort from artifacts)
        model_info = _read_model_info(repo_root)
        data["local_model"] = model_info

        # Accelerators
        data["accelerators"] = {
            "metal_backend_detected": _detect_metal(),
            "gpu_utilization_status": "unavailable",
        }

    except Exception as exc:
        data["warnings"].append(f"telemetry sample error: {exc}")

    _write_artifacts(repo_root, data)
    return data

def _read_model_info(repo_root: Path) -> dict[str, Any]:
    info = {
        "latest_backend": "idle",
        "latest_model": "none",
        "context_used_percent_estimate": 0,
    }
    loop_path = repo_root / ".build" / "rig" / "loop" / "latest.json"
    if loop_path.exists():
        try:
            loop_data = json.loads(loop_path.read_text(encoding="utf-8"))
            info["latest_backend"] = loop_data.get("backend", "idle")
            info["latest_model"] = loop_data.get("model", "none")
        except Exception:
            pass
    return info

def _detect_metal() -> bool:
    if sys.platform != "darwin": return False
    # Simple check for Apple Silicon / Metal
    return os.uname().machine == "arm64"

def _write_artifacts(repo_root: Path, data: dict[str, Any]) -> None:
    out_dir = repo_root / ".build" / "rig" / "system-pressure"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON
    (out_dir / "latest.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    
    # Markdown
    md = [
        f"# System Pressure - {data['created_at']}",
        "",
        "## Resource Summary",
    ]
    if data["status"] == "unavailable":
        md.append("- Status: **UNAVAILABLE** (install psutil)")
    else:
        mem = data.get("memory", {})
        cpu = data.get("cpu", {})
        disk = data.get("disk", {})
        md.append(f"- **RAM**: {mem.get('percent')}% used")
        md.append(f"- **CPU**: {cpu.get('percent')}%")
        md.append(f"- **Disk**: {disk.get('free_bytes', 0)//(1024**3)} GB free")
        
        md.append("\n## Rig Process")
        proc = data.get("rig_process", {})
        md.append(f"- **PID**: {proc.get('pid')}")
        md.append(f"- **RSS**: {proc.get('rss_bytes', 0)//(1024**2)} MB")
        md.append(f"- **Threads**: {proc.get('thread_count')}")
        
    (out_dir / "latest.md").write_text("\n".join(md) + "\n", encoding="utf-8")
