from __future__ import annotations

import json
from pathlib import Path

def register(subparsers, helpers):
    parser = subparsers.add_parser("bench", help="System benchmark and profiling", description="Profile local machine capabilities and recommend Rig execution profiles.")
    bench = parser.add_subparsers(dest="bench_cmd", required=True)

    # 1. Status
    status = bench.add_parser("status", help="Show latest benchmark status")
    status.set_defaults(handler=lambda args: _run_status(helpers, args))

    # 2. Run
    run = bench.add_parser("run", help="Run system benchmark")
    run.add_argument("--dry-run", action="store_true", help="Print checks without writing report")
    run.add_argument("--quick", action="store_true", default=True, help="Run quick profiling (default)")
    run.set_defaults(handler=lambda args: _run_bench(helpers, args))

    # 3. Report
    report = bench.add_parser("report", help="Show latest benchmark report")
    report.set_defaults(handler=lambda args: _run_report(helpers, args))

def _run_status(helpers, args) -> int:
    from rig_tools import system_benchmark
    latest = system_benchmark.get_latest_benchmark(helpers.repo_root)
    if latest:
        print(json.dumps({
            "status": "profiled",
            "benchmark_id": latest["benchmark_id"],
            "created_at": latest["created_at"],
            "profile": latest["recommended_profile"]["profile_id"]
        }, indent=2))
    else:
        print(json.dumps({"status": "not_profiled", "recommendation": "Run 'rig bench run --quick'"}, indent=2))
    return 0

def _run_bench(helpers, args) -> int:
    from rig_tools import system_benchmark
    if args.dry_run:
        print("Dry run: would profile system RAM, CPU, and backend availability.")
        return 0
        
    bench = system_benchmark.run_benchmark(helpers.repo_root, quick=args.quick)
    path = system_benchmark.write_benchmark_report(helpers.repo_root, bench)
    
    if helpers.output_mode == "human":
        print(f"Benchmark complete: {bench['benchmark_id']}")
        print(f"Profile: {bench['recommended_profile']['profile_id']}")
        print(f"Report written to {path}")
    else:
        print(json.dumps(bench, indent=2))
    return 0

def _run_report(helpers, args) -> int:
    path = helpers.repo_root / ".build" / "rig" / "bench" / "latest.md"
    if path.exists():
        print(path.read_text(encoding="utf-8"))
    else:
        print("No benchmark report found.")
        return 1
    return 0
