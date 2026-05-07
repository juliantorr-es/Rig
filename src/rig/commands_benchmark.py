from __future__ import annotations

import json
from pathlib import Path

from rig_tools import system_benchmark


def register(subparsers, helpers):
    parser = subparsers.add_parser("benchmark", help="Local runtime benchmarking")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    run = sub.add_parser("run", help="Run a local benchmark")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(handler=lambda args: _run(helpers.repo_root, dry_run=args.dry_run))


def _run(repo_root: Path, *, dry_run: bool) -> int:
    benchmark = system_benchmark.run_benchmark(repo_root, quick=True)
    if dry_run:
        benchmark = dict(benchmark)
        benchmark["status"] = "dry_run"
    if not dry_run:
        system_benchmark.write_benchmark_report(repo_root, benchmark)
    print(json.dumps(benchmark, indent=2, sort_keys=True))
    return 0
