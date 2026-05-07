from __future__ import annotations

import json
from pathlib import Path

from rig_tools.model_registry import list_models, inspect_model, register_model, verify_model
from rig_tools import system_benchmark


def register(subparsers, helpers):
    parser = subparsers.add_parser("model", help="Model inventory")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("list", help="List models").set_defaults(handler=lambda args: _emit(list_models(helpers.repo_root)))
    insp = sub.add_parser("inspect", help="Inspect model"); insp.add_argument("model_id"); insp.set_defaults(handler=lambda args: _emit(inspect_model(helpers.repo_root, args.model_id)))
    reg = sub.add_parser("register", help="Register model"); reg.add_argument("path_or_name"); reg.set_defaults(handler=lambda args: _emit(register_model(helpers.repo_root, args.path_or_name)))
    ver = sub.add_parser("verify", help="Verify model"); ver.add_argument("model_id"); ver.set_defaults(handler=lambda args: _emit(verify_model(helpers.repo_root, args.model_id)))
    rec = sub.add_parser("recommend", help="Recommend a model class"); rec.add_argument("--dry-run", action="store_true"); rec.set_defaults(handler=lambda args: _emit(_recommend(helpers.repo_root, dry_run=args.dry_run)))


def _emit(payload):
    print(json.dumps(payload, indent=2))
    return 0


def _recommend(repo_root: Path, *, dry_run: bool) -> dict[str, object]:
    benchmark = system_benchmark.run_benchmark(repo_root, quick=True)
    if not dry_run:
        system_benchmark.write_benchmark_report(repo_root, benchmark)
    return {
        "status": "dry_run" if dry_run else "generated",
        "benchmark_id": benchmark["benchmark_id"],
        "recommended_profile": benchmark["recommended_profile"],
        "backend_availability": benchmark["backend_availability"],
        "weights_downloaded": False,
    }
