from __future__ import annotations

import json
import importlib
import platform
import sys
from pathlib import Path

from rig_tools.doctor import run_doctor
from rig_tools import orchestration
from rig_tools import system_benchmark, llama_cpp_local, mlx_local


def _emit(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def _queue(repo_root: Path) -> dict[str, object]:
    return orchestration.queue_health(repo_root)


def _repair_queue(repo_root: Path, *, migrate_legacy_queue: bool = False) -> dict[str, object]:
    result = orchestration.queue_health(repo_root, repair=True)
    repaired = dict(result)
    repaired["repair"] = {
        "quarantined": result.get("quarantined", []),
        "migrated": None,
    }
    if migrate_legacy_queue:
        repaired["repair"]["migrated"] = orchestration.migrate_legacy_queue(repo_root)
    return repaired


def _deps(repo_root: Path) -> dict[str, object]:
    checks: dict[str, object] = {}
    for name, module_name in [("textual", "textual"), ("pywebview", "webview"), ("mlx", "mlx"), ("llama_cpp", "llama_cpp"), ("psutil", "psutil")]:
        try:
            module = importlib.import_module(module_name)
            checks[name] = {"available": True, "version": getattr(module, "__version__", None)}
        except Exception as exc:
            checks[name] = {"available": False, "error": str(exc)}
    checks["llama_cpp_capability"] = llama_cpp_local.detect_llama_cpp_environment()
    checks["mlx_capability"] = mlx_local.detect_mlx_environment()
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "python_ge_314": sys.version_info >= (3, 14),
        "platform": platform.platform(),
        "deps": checks,
        "benchmark_prerequisites": {
            "psutil": checks["psutil"]["available"],
            "mlx": checks["mlx"]["available"],
            "llama_cpp": checks["llama_cpp"]["available"],
        },
    }


def _safe_run_doctor(repo_root: Path, *, format_type: str) -> int:
    try:
        return run_doctor(repo_root, format_type=format_type)
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc), "message": "Rig doctor encountered an internal error. Re-run with --debug for a traceback."}, indent=2, sort_keys=True), file=sys.stderr)
        return 1


def register(subparsers, helpers):
    parser = subparsers.add_parser("doctor", help="Integrated Rig OS health checks", description="Integrated runtime and subsystem health checks.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    sub = parser.add_subparsers(dest="doctor_command")
    sub.add_parser("queue", help="Inspect queue health").set_defaults(handler=lambda args: _emit(_queue(helpers.repo_root)))
    sub.add_parser("deps", help="Inspect dependency health").set_defaults(handler=lambda args: _emit(_deps(helpers.repo_root)))
    repair = sub.add_parser("repair", help="Repair queue health")
    repair.add_argument("--queue", action="store_true")
    repair.add_argument("--migrate-legacy-queue", action="store_true")
    repair.set_defaults(handler=lambda args: _emit(_repair_queue(helpers.repo_root, migrate_legacy_queue=args.migrate_legacy_queue)) if args.queue or args.migrate_legacy_queue else _emit(_queue(helpers.repo_root)))
    parser.set_defaults(handler=lambda args: _safe_run_doctor(helpers.repo_root, format_type=args.format))
