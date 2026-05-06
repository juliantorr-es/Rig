from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from rig_tools.result import RigResult, write_latest_result, write_run_result
from rig_tools.result_index import build_context_pack, write_indexes


def _emit_result(helpers, payload: dict) -> int:
    payload = helpers._apply_notification(payload)  # noqa: SLF001
    write_latest_result(helpers.repo_root, payload)
    run_id = payload.get("run_id")
    if run_id:
        write_run_result(helpers.repo_root, run_id, payload)
    if helpers.output_mode == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
    return int(payload.get("exit_code", 0))


def _emit_events(helpers, run_id: str, command: str, task: str | None, started_at: str, finished_at: str, artifacts: list[dict], status: str, exit_code: int) -> None:
    if helpers.output_mode not in {"jsonl", "agent"}:
        return
    helpers._emit({  # noqa: SLF001
        "schema_version": "rig.event.v1",
        "event_type": "run_started",
        "timestamp_utc": started_at,
        "run_id": run_id,
        "command_group": "docs",
        "command": command,
        "task": task,
        "attributes": {},
    })
    for artifact in artifacts:
        helpers._emit({  # noqa: SLF001
            "schema_version": "rig.event.v1",
            "event_type": "artifact",
            "timestamp_utc": finished_at,
            "run_id": run_id,
            "command_group": "docs",
            "command": command,
            "task": task,
            "attributes": {"path": artifact.get("path"), "artifact_type": artifact.get("type")},
        })
    helpers._emit({  # noqa: SLF001
        "schema_version": "rig.event.v1",
        "event_type": "run_finished",
        "timestamp_utc": finished_at,
        "run_id": run_id,
        "command_group": "docs",
        "command": command,
        "task": task,
        "attributes": {"status": status, "exit_code": exit_code, "result_path": ".build/rig/results/latest.json"},
    })


def _table_path(repo_root: Path, name: str) -> Path | None:
    path = repo_root / "Docs" / "indexes" / f"{name}.csv"
    return path if path.exists() else None


def register(subparsers, helpers):
    parser = subparsers.add_parser("docs", help="Docs index and context commands", description="Ingest Rig result artifacts into compact docs indexes and context packs.")
    docs_sub = parser.add_subparsers(dest="docs_cmd", required=True)

    index = docs_sub.add_parser("index-rig-results", help="Build Rig result indexes")
    index.set_defaults(handler=lambda args: _handle_index(helpers, args))

    table = docs_sub.add_parser("table", help="Show a docs index table path")
    table.add_argument("name")
    table.set_defaults(handler=lambda args: _handle_table(helpers, args))

    context = docs_sub.add_parser("context-pack", help="Build a compact Rig context pack")
    context.add_argument("--task")
    context.add_argument("--budget", default="small")
    context.set_defaults(handler=lambda args: _handle_context_pack(helpers, args))


def _handle_index(helpers, args) -> int:
    started = time.time()
    run_id = uuid.uuid4().hex[:12]
    helpers._begin_stream(run_id)  # noqa: SLF001
    helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_started", "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)), "run_id": run_id, "command_group": "docs", "command": "rig docs index-rig-results", "task": None, "attributes": {}})
    paths = write_indexes(helpers.repo_root)
    payload = RigResult(
        command_group="docs",
        command="rig docs index-rig-results",
        status="passed",
        exit_code=0,
        run_id=run_id,
        task=None,
        summary={
            "index_count": len(paths),
            "indexes": sorted(str(path.relative_to(helpers.repo_root)) for path in paths.values()),
        },
        artifacts=[{"path": str(path.relative_to(helpers.repo_root)), "type": "index"} for path in paths.values()],
    ).to_dict()
    finished = time.time()
    payload["started_at"] = payload.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    payload["finished_at"] = payload.get("finished_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished))
    payload["duration_seconds"] = round(finished - started, 3)
    helpers._emit({"schema_version": "rig.event.v1", "event_type": "artifact", "timestamp_utc": payload["finished_at"], "run_id": run_id, "command_group": "docs", "command": payload["command"], "task": None, "attributes": {"path": ".build/rig/results/latest.json", "artifact_type": "result"}})
    helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_finished", "timestamp_utc": payload["finished_at"], "run_id": run_id, "command_group": "docs", "command": payload["command"], "task": None, "attributes": {"status": payload["status"], "exit_code": payload["exit_code"], "result_path": ".build/rig/results/latest.json"}})
    helpers._finish_stream(run_id)  # noqa: SLF001
    _emit_events(helpers, run_id, payload["command"], None, payload["started_at"], payload["finished_at"], payload["artifacts"], payload["status"], payload["exit_code"])
    return _emit_result(helpers, payload)


def _handle_table(helpers, args) -> int:
    started = time.time()
    run_id = uuid.uuid4().hex[:12]
    helpers._begin_stream(run_id)  # noqa: SLF001
    index_name = args.name
    table_path = _table_path(helpers.repo_root, index_name)
    if table_path is None:
        result = RigResult(
            command_group="docs",
            command=f"rig docs table {index_name}",
            status="failed",
            exit_code=2,
            run_id=run_id,
            task=None,
            errors=[{"message": f"missing table: {index_name}"}],
            summary={"table": index_name},
        ).to_dict()
        finished = time.time()
        result["started_at"] = result.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
        result["finished_at"] = result.get("finished_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished))
        result["duration_seconds"] = round(finished - started, 3)
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_finished", "timestamp_utc": result["finished_at"], "run_id": run_id, "command_group": "docs", "command": result["command"], "task": None, "attributes": {"status": result["status"], "exit_code": result["exit_code"], "result_path": ".build/rig/results/latest.json"}})
        helpers._finish_stream(run_id)  # noqa: SLF001
        _emit_events(helpers, run_id, result["command"], None, result["started_at"], result["finished_at"], [], result["status"], result["exit_code"])
        return _emit_result(helpers, result)
    payload = RigResult(
        command_group="docs",
        command=f"rig docs table {index_name}",
        status="passed",
        exit_code=0,
        run_id=run_id,
        task=None,
        summary={"table": index_name, "path": str(table_path.relative_to(helpers.repo_root))},
        artifacts=[{"path": str(table_path.relative_to(helpers.repo_root)), "type": "csv"}],
    ).to_dict()
    finished = time.time()
    payload["started_at"] = payload.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    payload["finished_at"] = payload.get("finished_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished))
    payload["duration_seconds"] = round(finished - started, 3)
    helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_finished", "timestamp_utc": payload["finished_at"], "run_id": run_id, "command_group": "docs", "command": payload["command"], "task": None, "attributes": {"status": payload["status"], "exit_code": payload["exit_code"], "result_path": ".build/rig/results/latest.json"}})
    helpers._finish_stream(run_id)  # noqa: SLF001
    _emit_events(helpers, run_id, payload["command"], None, payload["started_at"], payload["finished_at"], payload["artifacts"], payload["status"], payload["exit_code"])
    if helpers.output_mode in {"json", "jsonl", "agent"}:
        return _emit_result(helpers, payload)
    print(str(table_path.relative_to(helpers.repo_root)))
    return 0


def _handle_context_pack(helpers, args) -> int:
    started = time.time()
    run_id = uuid.uuid4().hex[:12]
    helpers._begin_stream(run_id)  # noqa: SLF001
    pack = build_context_pack(helpers.repo_root, task=args.task, budget=args.budget)
    out_dir = helpers.repo_root / ".build" / "rig" / "context-packs"
    out_dir.mkdir(parents=True, exist_ok=True)
    task_slug = args.task or "latest"
    path = out_dir / f"{task_slug}-{args.budget}.md"
    path.write_text(pack["markdown"], encoding="utf-8")
    payload = RigResult(
        command_group="docs",
        command=f"rig docs context-pack --task {args.task or ''} --budget {args.budget}".strip(),
        status="passed",
        exit_code=0,
        run_id=run_id,
        task=args.task,
        summary={
            "task": args.task,
            "budget": args.budget,
            "path": str(path.relative_to(helpers.repo_root)),
            "cache_fresh": pack["cache_fresh"],
            "cache_total": pack["cache_total"],
        },
        artifacts=[{"path": str(path.relative_to(helpers.repo_root)), "type": "context_pack"}],
    ).to_dict()
    finished = time.time()
    payload["started_at"] = payload.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started))
    payload["finished_at"] = payload.get("finished_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished))
    payload["duration_seconds"] = round(finished - started, 3)
    helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_finished", "timestamp_utc": payload["finished_at"], "run_id": run_id, "command_group": "docs", "command": payload["command"], "task": args.task, "attributes": {"status": payload["status"], "exit_code": payload["exit_code"], "result_path": ".build/rig/results/latest.json"}})
    helpers._finish_stream(run_id)  # noqa: SLF001
    _emit_events(helpers, run_id, payload["command"], args.task, payload["started_at"], payload["finished_at"], payload["artifacts"], payload["status"], payload["exit_code"])
    if helpers.output_mode in {"json", "jsonl", "agent"}:
        return _emit_result(helpers, payload)
    print(str(path.relative_to(helpers.repo_root)))
    return 0
