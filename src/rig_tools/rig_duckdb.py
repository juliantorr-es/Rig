from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DB_FILENAME = ".build/rig/rig.duckdb"
LOCK_FILENAME = ".build/rig/rig.duckdb.lock"
MANIFEST_FILENAME = ".build/rig/rig-duckdb-manifest.json"
SCHEMA_VERSION = "rig.duckdb_manifest.v1"


def duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401
    except Exception:
        return False
    return True


def duckdb_version() -> str | None:
    if not duckdb_available():
        return None
    import duckdb

    return duckdb.__version__


def db_path(repo_root: Path) -> Path:
    return repo_root / DB_FILENAME


def lock_path(repo_root: Path) -> Path:
    return repo_root / LOCK_FILENAME


def manifest_path(repo_root: Path) -> Path:
    return repo_root / MANIFEST_FILENAME


def _repo_rel(repo_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def json_root_kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, str):
        return "string"
    return "invalid"


def extract_schema_version(value: Any) -> str | None:
    if isinstance(value, dict):
        schema_version = value.get("schema_version")
        return schema_version if isinstance(schema_version, str) else None
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            schema_version = first.get("schema_version")
            if isinstance(schema_version, str):
                return f"array:{schema_version}"
    return None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str | None:
    try:
        return _sha256_bytes(path.read_bytes())
    except Exception:
        return None


def _connect(repo_root: Path, read_only: bool = False):
    import duckdb

    db = duckdb.connect(str(db_path(repo_root)), read_only=read_only)
    db.execute("PRAGMA threads=1")
    return db


def _lock_is_fresh(repo_root: Path, max_age_seconds: int = 900) -> bool:
    path = lock_path(repo_root)
    if not path.exists():
        return False
    try:
        age = time.time() - path.stat().st_mtime
        return age <= max_age_seconds
    except Exception:
        return False


def _acquire_lock(repo_root: Path) -> tuple[bool, str | None]:
    path = lock_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if _lock_is_fresh(repo_root):
        return False, "writer_lock_active"
    path.write_text(json.dumps({"pid": os.getpid(), "created_at": time.time()}, sort_keys=True) + "\n", encoding="utf-8")
    return True, None


def _release_lock(repo_root: Path) -> None:
    path = lock_path(repo_root)
    try:
        path.unlink()
    except Exception:
        pass


def _run_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    results_dir = repo_root / ".build" / "rig" / "results"
    if not results_dir.exists():
        return rows
    for path in sorted([p for p in results_dir.glob("*.json") if p.is_file()], key=lambda p: (p.stat().st_mtime, p.name)):
        data = _load_json(path, {})
        if not isinstance(data, dict):
            continue
        artifacts = data.get("artifacts")
        warnings = data.get("warnings")
        errors = data.get("errors")
        rows.append({
            "run_id": data.get("run_id") or path.stem,
            "task": data.get("task"),
            "command_group": data.get("command_group"),
            "command": data.get("command"),
            "status": data.get("status"),
            "exit_code": data.get("exit_code"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "duration_seconds": data.get("duration_seconds"),
            "result_path": _repo_rel(repo_root, path),
            "event_path": _repo_rel(repo_root, repo_root / ".build" / "rig" / "events" / f"{(data.get('run_id') or path.stem)}.jsonl"),
            "artifact_count": len(artifacts) if isinstance(artifacts, list) else 0,
            "warning_count": len(warnings) if isinstance(warnings, list) else 0,
            "error_count": len(errors) if isinstance(errors, list) else 0,
        })
    rows.sort(key=lambda row: (str(row.get("finished_at") or ""), str(row.get("run_id") or "")))
    return rows


def _event_rows(repo_root: Path) -> list[dict[str, Any]]:
    from rig_tools import monitor

    rows = []
    for path in sorted((repo_root / ".build" / "rig" / "events").glob("*.jsonl"), key=lambda p: p.name):
        run_id = path.stem
        for idx, event in enumerate(monitor.read_events(repo_root, run_id)):
            rows.append({
                "run_id": event.get("run_id") or run_id,
                "event_index": idx,
                "event_type": event.get("event_type"),
                "timestamp_utc": event.get("timestamp_utc"),
                "command_group": event.get("command_group"),
                "command": event.get("command"),
                "step_id": event.get("attributes", {}).get("step_id"),
                "status": event.get("attributes", {}).get("status"),
                "message": event.get("attributes", {}).get("text") or event.get("attributes", {}).get("message"),
                "raw_json": json.dumps(event, sort_keys=True),
            })
    return rows


def _affected_rows(repo_root: Path) -> list[dict[str, Any]]:
    from rig_tools import result_index

    rows = []
    for row in result_index.build_affected_rows(repo_root):
        rows.append({
            "task": row.get("task"),
            "mode": row.get("mode"),
            "changed_file_count": row.get("changed_file_count"),
            "affected_targets_json": json.dumps((row.get("directly_affected_targets") or "").split(";"), sort_keys=True),
            "affected_risk_count": row.get("affected_risk_count"),
            "recommended_profiles_json": json.dumps((row.get("recommended_profiles") or "").split(";"), sort_keys=True),
            "artifact_path": row.get("summary_md"),
        })
    return rows


def _diagnostic_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((repo_root / ".build" / "rig" / "swift-diagnostics").glob("*.json"), key=lambda p: p.name):
        data = _load_json(path, {})
        for item in data.get("diagnostics", []) if isinstance(data, dict) else []:
            if not isinstance(item, dict):
                continue
            rows.append({
                "run_id": data.get("run_id") or path.stem,
                "task": data.get("task"),
                "diagnostic_type": "swift",
                "target": item.get("target") or data.get("target"),
                "status": data.get("status"),
                "category": item.get("category"),
                "severity": item.get("severity"),
                "file": item.get("file"),
                "line": item.get("line"),
                "message": item.get("message"),
                "known_blocker_id": item.get("known_blocker_id"),
                "artifact_path": _repo_rel(repo_root, path),
            })
    return rows


def _registry_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows = []
    root = repo_root / ".build" / "anigma-diagnostics" / "tasks"
    if not root.exists():
        return rows
    for path in sorted(root.glob("*/*/*/logs/validator-registry-check.json"), key=lambda p: p.as_posix()):
        data = _load_json(path, {})
        rows.append({
            "task": path.parts[-5] if len(path.parts) >= 5 else None,
            "phase": "validate" if "validate" in path.parts else "review" if "review" in path.parts else "unknown",
            "status": data.get("status"),
            "exit_code": data.get("exitCode"),
            "failure_count": data.get("failureCount"),
            "warning_count": data.get("warningCount"),
            "report_path": _repo_rel(repo_root, path),
            "log_path": _repo_rel(repo_root, path.with_suffix(".log")) if path.with_suffix(".log").exists() else None,
        })
    return rows


def _commit_plan_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((repo_root / ".build" / "rig" / "git").glob("commit-plan-*.json"), key=lambda p: p.name):
        data = _load_json(path, {})
        rows.append({
            "task": data.get("task") or path.stem.replace("commit-plan-", ""),
            "status": data.get("status"),
            "scope_status": data.get("scope_status"),
            "registry_gate_status": data.get("registry_gate_status"),
            "schema_status": data.get("schema_status"),
            "production_source_changed": data.get("production_source_changed"),
            "baselines_changed": data.get("baselines_changed"),
            "commit_message": data.get("commit_message"),
            "plan_path": _repo_rel(repo_root, path),
        })
    return rows


def _cache_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((repo_root / ".build" / "rig" / "cache-metadata").glob("*.json"), key=lambda p: p.name):
        data = _load_json(path, {})
        rows.append({
            "artifact_id": data.get("artifact_id") or path.stem,
            "producer": data.get("producer"),
            "command": data.get("command"),
            "cache_key": data.get("cache_key"),
            "status": data.get("status"),
            "input_count": len(data.get("input_files", []) or []),
            "output_count": len(data.get("output_files", []) or []),
            "duration_seconds": data.get("duration_seconds"),
            "metadata_path": _repo_rel(repo_root, path),
        })
    return rows


def _artifact_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows = []
    omitted: list[dict[str, Any]] = []
    roots = [
        repo_root / ".build" / "rig" / "results",
        repo_root / ".build" / "rig" / "events",
        repo_root / ".build" / "rig" / "affected",
        repo_root / ".build" / "rig" / "swift-diagnostics",
        repo_root / ".build" / "rig" / "git",
        repo_root / ".build" / "rig" / "schema-validation",
        repo_root / ".build" / "rig" / "cache-metadata",
        repo_root / ".build" / "anigma-diagnostics" / "tasks",
        repo_root / "Docs" / "indexes",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted([p for p in root.rglob("*") if p.is_file()], key=lambda p: p.as_posix()):
            if path.suffix not in {".json", ".jsonl", ".md", ".csv", ".log"}:
                continue
            schema_version = None
            root_kind = None
            if path.suffix == ".json":
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    value = object()
                root_kind = json_root_kind(value)
                schema_version = extract_schema_version(value)
                if root_kind == "invalid":
                    omitted.append({"path": _repo_rel(repo_root, path), "reason": "invalid_json"})
            elif path.suffix == ".jsonl":
                root_kind = "array"
            rows.append({
                "path": _repo_rel(repo_root, path),
                "artifact_type": path.suffix.lstrip("."),
                "task": None,
                "run_id": None,
                "schema_version": schema_version,
                "json_root_kind": root_kind,
                "sha256": _sha256_path(path),
                "size_bytes": path.stat().st_size,
                "indexed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
    return rows, omitted


def _manifest(repo_root: Path, warnings: list[str], source_counts: dict[str, int], omitted: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "db_path": _repo_rel(repo_root, db_path(repo_root)),
        "db_schema_version": SCHEMA_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duckdb_available": duckdb_available(),
        "duckdb_version": duckdb_version(),
        "table_counts": {},
        "source_artifact_counts": source_counts,
        "omitted_artifacts": omitted,
        "warnings": warnings,
        "canonical_truth_statement": "DuckDB is a derived index; JSON/JSONL/proofs/Git remain canonical.",
    }


def _init_schema(con) -> None:
    con.execute("create table if not exists runs(run_id varchar, task varchar, command_group varchar, command varchar, status varchar, exit_code integer, started_at varchar, finished_at varchar, duration_seconds double, result_path varchar, event_path varchar)")
    con.execute("create table if not exists events(run_id varchar, event_index integer, event_type varchar, timestamp_utc varchar, command_group varchar, command varchar, step_id varchar, status varchar, message varchar, raw_json varchar)")
    con.execute("create table if not exists affected(task varchar, mode varchar, changed_file_count integer, affected_targets_json varchar, affected_risk_count integer, recommended_profiles_json varchar, artifact_path varchar)")
    con.execute("create table if not exists diagnostics(run_id varchar, task varchar, diagnostic_type varchar, target varchar, status varchar, category varchar, severity varchar, file varchar, line integer, message varchar, known_blocker_id varchar, artifact_path varchar)")
    con.execute("create table if not exists registry_gate(task varchar, phase varchar, status varchar, exit_code integer, failure_count integer, warning_count integer, report_path varchar, log_path varchar)")
    con.execute("create table if not exists commit_plans(task varchar, status varchar, scope_status varchar, registry_gate_status varchar, schema_status varchar, production_source_changed boolean, baselines_changed boolean, commit_message varchar, plan_path varchar)")
    con.execute("create table if not exists cache_metadata(artifact_id varchar, producer varchar, command varchar, cache_key varchar, status varchar, input_count integer, output_count integer, duration_seconds double, metadata_path varchar)")
    con.execute("create table if not exists artifacts(path varchar, artifact_type varchar, task varchar, run_id varchar, schema_version varchar, json_root_kind varchar, sha256 varchar, size_bytes bigint, indexed_at varchar)")


def init_db(repo_root: Path) -> dict[str, Any]:
    if not duckdb_available():
        return {"status": "tool_missing", "step": "step_skipped", "tool": "duckdb", "message": "duckdb not installed"}
    db_path(repo_root).parent.mkdir(parents=True, exist_ok=True)
    con = _connect(repo_root, read_only=False)
    try:
        _init_schema(con)
        con.close()
    finally:
        pass
    manifest = _manifest(repo_root, [], {}, [])
    table_counts = query_counts(repo_root)
    manifest["table_counts"] = table_counts
    manifest_path(repo_root).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "passed", "manifest_path": _repo_rel(repo_root, manifest_path(repo_root)), "db_path": _repo_rel(repo_root, db_path(repo_root))}


def _insert_rows(con, table: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        return
    placeholders = ",".join(["?"] * len(columns))
    con.executemany(f"insert into {table} ({','.join(columns)}) values ({placeholders})", [[row.get(col) for col in columns] for row in rows])


def ingest(repo_root: Path) -> dict[str, Any]:
    if not duckdb_available():
        return {"status": "tool_missing", "step": "step_skipped", "tool": "duckdb", "message": "duckdb not installed"}
    acquired, reason = _acquire_lock(repo_root)
    if not acquired:
        return {"status": "failed", "reason": reason}
    omitted: list[dict[str, Any]] = []
    source_counts = {}
    warnings: list[str] = []
    try:
        con = _connect(repo_root)
        _init_schema(con)
        con.execute("delete from runs")
        con.execute("delete from events")
        con.execute("delete from affected")
        con.execute("delete from diagnostics")
        con.execute("delete from registry_gate")
        con.execute("delete from commit_plans")
        con.execute("delete from cache_metadata")
        con.execute("delete from artifacts")
        runs = _run_rows(repo_root)
        events = _event_rows(repo_root)
        affected = _affected_rows(repo_root)
        diagnostics = _diagnostic_rows(repo_root)
        registry = _registry_rows(repo_root)
        plans = _commit_plan_rows(repo_root)
        cache = _cache_rows(repo_root)
        artifacts, artifact_omitted = _artifact_rows(repo_root)
        omitted.extend(artifact_omitted)
        for item in artifact_omitted:
            if item.get("reason") == "invalid_json":
                warnings.append(f"invalid_json:{item.get('path')}")
        source_counts = {
            "runs": len(runs),
            "events": len(events),
            "affected": len(affected),
            "diagnostics": len(diagnostics),
            "registry_gate": len(registry),
            "commit_plans": len(plans),
            "cache_metadata": len(cache),
            "artifacts": len(artifacts),
        }
        _insert_rows(con, "runs", runs, ["run_id","task","command_group","command","status","exit_code","started_at","finished_at","duration_seconds","result_path","event_path"])
        _insert_rows(con, "events", events, ["run_id","event_index","event_type","timestamp_utc","command_group","command","step_id","status","message","raw_json"])
        _insert_rows(con, "affected", affected, ["task","mode","changed_file_count","affected_targets_json","affected_risk_count","recommended_profiles_json","artifact_path"])
        _insert_rows(con, "diagnostics", diagnostics, ["run_id","task","diagnostic_type","target","status","category","severity","file","line","message","known_blocker_id","artifact_path"])
        _insert_rows(con, "registry_gate", registry, ["task","phase","status","exit_code","failure_count","warning_count","report_path","log_path"])
        _insert_rows(con, "commit_plans", plans, ["task","status","scope_status","registry_gate_status","schema_status","production_source_changed","baselines_changed","commit_message","plan_path"])
        _insert_rows(con, "cache_metadata", cache, ["artifact_id","producer","command","cache_key","status","input_count","output_count","duration_seconds","metadata_path"])
        _insert_rows(con, "artifacts", artifacts, ["path","artifact_type","task","run_id","schema_version","json_root_kind","sha256","size_bytes","indexed_at"])
        counts = query_counts(repo_root, con)
        manifest = _manifest(repo_root, warnings, source_counts, omitted)
        manifest["table_counts"] = counts
        manifest_path(repo_root).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        con.close()
        return {"status": "passed", "manifest_path": _repo_rel(repo_root, manifest_path(repo_root)), "db_path": _repo_rel(repo_root, db_path(repo_root)), "table_counts": counts, "source_artifact_counts": source_counts}
    finally:
        _release_lock(repo_root)


def rebuild(repo_root: Path) -> dict[str, Any]:
    if not duckdb_available():
        return {"status": "tool_missing", "step": "step_skipped", "tool": "duckdb", "message": "duckdb not installed"}
    if db_path(repo_root).exists():
        try:
            db_path(repo_root).unlink()
        except Exception:
            pass
    return ingest(repo_root)


def query_counts(repo_root: Path, con=None) -> dict[str, int]:
    if not duckdb_available():
        return {}
    owns = con is None
    if con is None:
        con = _connect(repo_root, read_only=True)
    try:
        counts = {}
        for table in ["runs","events","affected","diagnostics","registry_gate","commit_plans","cache_metadata","artifacts"]:
            try:
                counts[table] = int(con.execute(f"select count(*) from {table}").fetchone()[0])
            except Exception:
                counts[table] = 0
        return counts
    finally:
        if owns:
            con.close()


def health(repo_root: Path) -> dict[str, Any]:
    available = duckdb_available()
    return {
        "duckdb_available": available,
        "duckdb_version": duckdb_version(),
        "db_path": _repo_rel(repo_root, db_path(repo_root)),
        "db_exists": db_path(repo_root).exists(),
        "lock_exists": lock_path(repo_root).exists(),
        "lock_fresh": _lock_is_fresh(repo_root),
        "table_counts": query_counts(repo_root) if available and db_path(repo_root).exists() else {},
        "manifest_path": _repo_rel(repo_root, manifest_path(repo_root)),
    }


def _query_df(repo_root: Path, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    if not duckdb_available() or not db_path(repo_root).exists():
        return []
    con = _connect(repo_root, read_only=True)
    try:
        rel = con.execute(sql, params)
        cols = [c[0] for c in rel.description]
        return [dict(zip(cols, row)) for row in rel.fetchall()]
    finally:
        con.close()


def query_latest_runs(repo_root: Path) -> list[dict[str, Any]]:
    return _query_df(repo_root, "select * from runs order by coalesce(finished_at,''), run_id desc limit 50")


def query_task(repo_root: Path, task: str) -> dict[str, Any]:
    return {
        "task": task,
        "runs": _query_df(repo_root, "select * from runs where task=? order by coalesce(finished_at,''), run_id desc", (task,)),
        "affected": _query_df(repo_root, "select * from affected where task=?", (task,)),
        "diagnostics": _query_df(repo_root, "select * from diagnostics where task=? or run_id in (select run_id from runs where task=?)", (task, task)),
        "registry_gate": _query_df(repo_root, "select * from registry_gate where task=?", (task,)),
        "commit_plans": _query_df(repo_root, "select * from commit_plans where task=?", (task,)),
    }


def query_diagnostics(repo_root: Path, target: str) -> list[dict[str, Any]]:
    return _query_df(repo_root, "select * from diagnostics where target=?", (target,))


def query_registry_gate(repo_root: Path) -> list[dict[str, Any]]:
    return _query_df(repo_root, "select * from registry_gate order by task, phase")


def query_commit_plans(repo_root: Path) -> list[dict[str, Any]]:
    return _query_df(repo_root, "select * from commit_plans order by task")
