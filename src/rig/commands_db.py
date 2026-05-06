from __future__ import annotations

import json

from rig_tools import rig_duckdb


def register(subparsers, helpers):
    parser = subparsers.add_parser("db", help="DuckDB analytical index", description="Build and query Rig's rebuildable DuckDB analytical index.")
    db = parser.add_subparsers(dest="db_cmd", required=True)

    init = db.add_parser("init", help="Initialize the DuckDB index")
    init.set_defaults(handler=lambda args: _emit(helpers, rig_duckdb.init_db(helpers.repo_root)))

    ingest = db.add_parser("ingest", help="Ingest artifact rows into DuckDB")
    ingest.set_defaults(handler=lambda args: _emit(helpers, rig_duckdb.ingest(helpers.repo_root)))

    rebuild = db.add_parser("rebuild", help="Rebuild DuckDB from artifacts")
    rebuild.set_defaults(handler=lambda args: _emit(helpers, rig_duckdb.rebuild(helpers.repo_root)))

    health = db.add_parser("health", help="Show DuckDB health")
    health.set_defaults(handler=lambda args: _emit(helpers, rig_duckdb.health(helpers.repo_root)))

    query = db.add_parser("query", help="Query DuckDB")
    query_sub = query.add_subparsers(dest="query_cmd", required=True)

    latest_runs = query_sub.add_parser("latest-runs", help="Latest runs")
    latest_runs.set_defaults(handler=lambda args: _emit(helpers, {"rows": rig_duckdb.query_latest_runs(helpers.repo_root)}))

    task = query_sub.add_parser("task", help="Task query")
    task.add_argument("--task", required=True)
    task.set_defaults(handler=lambda args: _emit(helpers, rig_duckdb.query_task(helpers.repo_root, args.task)))

    diag = query_sub.add_parser("diagnostics", help="Diagnostics by target")
    diag.add_argument("--target", required=True)
    diag.set_defaults(handler=lambda args: _emit(helpers, {"rows": rig_duckdb.query_diagnostics(helpers.repo_root, args.target)}))

    gate = query_sub.add_parser("registry-gate", help="Registry gate rows")
    gate.set_defaults(handler=lambda args: _emit(helpers, {"rows": rig_duckdb.query_registry_gate(helpers.repo_root)}))

    plans = query_sub.add_parser("commit-plans", help="Commit plan rows")
    plans.set_defaults(handler=lambda args: _emit(helpers, {"rows": rig_duckdb.query_commit_plans(helpers.repo_root)}))


def _emit(helpers, payload) -> int:
    if isinstance(payload, dict) and payload.get("status") == "tool_missing":
        print(json.dumps(payload))
        return 0
    if helpers.output_mode == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0

