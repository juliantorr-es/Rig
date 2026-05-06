from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rig_tools import prompt_telemetry, rig_duckdb, system_pressure, model_manager, kanban_board, task_graph

SCHEMA_VERSION = "rig.monitor_state.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _repo_rel(repo_root: Path, value: str | Path| Optional) -> str| Optional:
    if value is None:
        return None
    path = Path(str(value))
    if path.is_absolute():
        try:
            return str(path.relative_to(repo_root))
        except Exception:
            return str(path).replace("\\", "/")
    return str(path).replace("\\", "/")


def _list_paths(root: Path, pattern: str) -> list[Path]:
    if not root.exists():
        return []
    return sorted([p for p in root.glob(pattern) if p.is_file()], key=lambda p: (p.stat().st_mtime, p.name))


def _latest_path(paths: list[Path]) -> Path| Optional:
    return paths[-1] if paths else None


def _artifact_list(payload: dict) -> list[str]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return []
    out = []
    for item in artifacts:
        if isinstance(item, dict) and item.get("path"):
            out.append(str(item["path"]))
    return out


def _summarize_result(path: Path, repo_root: Path) -> dict[str, Any]:
    data = _load_json(path, {})
    return {
        "run_id": data.get("run_id") or path.stem,
        "task": data.get("task"),
        "command_group": data.get("command_group"),
        "command": data.get("command"),
        "status": data.get("status"),
        "exit_code": data.get("exit_code"),
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "duration_seconds": data.get("duration_seconds"),
        "artifacts": _artifact_list(data),
        "event_path": _repo_rel(repo_root, repo_root / ".build" / "rig" / "events" / f"{path.stem}.jsonl"),
        "result_path": _repo_rel(repo_root, path),
    }


def _parse_event_line(line: str) -> dict[str, Any]| Optional:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except Exception:
        return {"schema_version": "rig.event.v1", "event_type": "parse_error", "raw": stripped}


def read_events(repo_root: Path, run_id: str| Optional = None) -> list[dict[str, Any]]:
    events_dir = repo_root / ".build" / "rig" / "events"
    if run_id == "latest":
        latest = events_dir / "latest.jsonl"
        if latest.exists():
            run_id = latest.stem
        else:
            latest_file = _latest_path(_list_paths(events_dir, "*.jsonl"))
            if latest_file:
                run_id = latest_file.stem
    path = events_dir / f"{run_id}.jsonl" if run_id else _latest_path(_list_paths(events_dir, "*.jsonl"))
    if path is None or not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        event = _parse_event_line(line)
        if event:
            events.append(event)
    return events


def build_runs(repo_root: Path) -> list[dict[str, Any]]:
    runs_dir = repo_root / ".build" / "rig" / "results"
    rows = []
    for path in _list_paths(runs_dir, "*.json"):
        if path.name == "latest.json":
            continue
        rows.append(_summarize_result(path, repo_root))
    rows.sort(key=lambda row: (str(row.get("finished_at") or ""), str(row.get("run_id") or "")))
    return rows


def build_agent_runs(repo_root: Path) -> list[dict[str, Any]]:
    runs_dir = repo_root / ".build" / "rig" / "agents" / "runs"
    if not runs_dir.exists():
        return []
    rows = []
    for path in sorted(runs_dir.glob("*/agent-run.json"), key=lambda p: p.parent.name):
        data = _load_json(path, {})
        if isinstance(data, dict):
            data = dict(data)
            data["run_dir"] = _repo_rel(repo_root, path.parent)
            rows.append(data)
    rows.sort(key=lambda row: (str(row.get("finished_at") or ""), str(row.get("run_id") or "")))
    return rows


def build_loop_runs(repo_root: Path) -> list[dict[str, Any]]:
    runs_dir = repo_root / ".build" / "rig" / "loop" / "runs"
    if not runs_dir.exists():
        return []
    rows = []
    for path in sorted(runs_dir.glob("*/loop-run.json"), key=lambda p: p.parent.name):
        data = _load_json(path, {})
        if isinstance(data, dict):
            rows.append({**data, "run_dir": _repo_rel(repo_root, path.parent)})
    rows.sort(key=lambda row: (str(row.get("finished_at") or ""), str(row.get("run_id") or "")))
    return rows


def build_tasks(repo_root: Path) -> list[dict[str, Any]]:
    runs = build_runs(repo_root)
    affected = _load_json(repo_root / ".build" / "rig" / "affected" / "targets.json", {})
    profiles = _load_json(repo_root / ".build" / "rig" / "affected" / "profiles.json", {})
    swift = _load_json(repo_root / ".build" / "rig" / "swift-diagnostics" / "latest.json", {})
    schema = _load_json(repo_root / ".build" / "rig" / "schema-validation" / "latest.json", {})
    registry = _load_json(repo_root / ".build" / "anigma-diagnostics" / "tasks", {})
    commit_plan = _load_json(repo_root / ".build" / "rig" / "git" / "commit-plan-rig-git-management-bootstrap.json", {})

    latest_by_task: dict[str, dict[str, Any]] = {}
    for run in runs:
        task = str(run.get("task") or "n/a")
        latest_by_task[task] = run

    rows = []
    for task, run in latest_by_task.items():
        rows.append({
            "task_id": task,
            "latest_run_status": run.get("status"),
            "latest_pipeline_status": run.get("status"),
            "affected_targets": ";".join(affected.get("directly_affected_targets", [])) if isinstance(affected, dict) else "",
            "recommended_profiles": ";".join(profiles.get("recommended_profiles", [])) if isinstance(profiles, dict) else "",
            "swift_status": swift.get("status") if isinstance(swift, dict) else None,
            "schema_status": schema.get("status") if isinstance(schema, dict) else None,
            "registry_gate_status": None if not isinstance(registry, dict) else registry.get("status"),
            "review_status": None,
            "commit_plan_status": commit_plan.get("status") if isinstance(commit_plan, dict) else None,
            "blockers": [],
        })
    rows.sort(key=lambda row: str(row.get("task_id") or ""))
    return rows


def build_latest_events(repo_root: Path, limit: int = 20) -> list[dict[str, Any]]:
    events = []
    for path in _list_paths(repo_root / ".build" / "rig" / "events", "*.jsonl"):
        if path.name == "latest.jsonl":
            continue
        for event in read_events(repo_root, path.stem):
            event["_event_path"] = _repo_rel(repo_root, path)
            events.append(event)
    events.sort(key=lambda e: str(e.get("timestamp_utc") or ""))
    return events[-limit:]


def _summary_from_json(path: Path, repo_root: Path, keys: list[str]) -> dict[str, Any]:
    data = _load_json(path, {})
    if not isinstance(data, dict):
        return {"path": _repo_rel(repo_root, path), "status": "missing"}
    return {"path": _repo_rel(repo_root, path), **{k: data.get(k) for k in keys}}


def _context_pack_summary(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ".build" / "rig" / "context" / "latest.json"
    data = _load_json(path, {})
    if not isinstance(data, dict):
        return {"path": None, "char_count": None, "warnings": []}
    return {
        "path": _repo_rel(repo_root, path),
        "char_count": data.get("char_count"),
        "compression_ratio": data.get("compression_ratio"),
        "warnings": data.get("warnings") or [],
        "task": data.get("task"),
        "purpose": data.get("purpose"),
    }


def _queue_summary(repo_root: Path) -> dict[str, Any]:
    queue_path = repo_root / ".build" / "rig" / "queue" / "queue.json"
    queue = _load_json(queue_path, {})
    jobs = queue.get("jobs") if isinstance(queue, dict) else []
    if not isinstance(jobs, list):
        jobs = []
    counts: dict[str, int] = {}
    for job in jobs:
        if isinstance(job, dict):
            counts[str(job.get("status") or "unknown")] = counts.get(str(job.get("status") or "unknown"), 0) + 1
    latest_checkpoint = None
    cps = _list_paths(repo_root / ".build" / "rig" / "queue" / "checkpoints", "*.json")
    if cps:
        latest_checkpoint = _load_json(cps[-1], {})
    return {
        "path": _repo_rel(repo_root, queue_path),
        "jobs_total": len(jobs),
        "status_counts": counts,
        "latest_checkpoint": latest_checkpoint,
    }


def _patch_summary(repo_root: Path) -> dict[str, Any]:
    root = repo_root / ".build" / "rig" / "patches"
    if not root.exists():
        return {"path": _repo_rel(repo_root, root), "patch_count": 0, "latest_patch": None}
    patches = _list_paths(root, "*/patch.json")
    latest = _load_json(patches[-1], {}) if patches else None
    return {
        "path": _repo_rel(repo_root, root),
        "patch_count": len(patches),
        "latest_patch": latest,
    }


def _tui_summary(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ".build" / "rig" / "tui" / "latest-state.json"
    data = _load_json(path, {})
    if not isinstance(data, dict) or not data:
        return {"path": _repo_rel(repo_root, path), "status": "missing"}
    return {
        "path": _repo_rel(repo_root, path),
        "python": data.get("python"),
        "queue_status": (data.get("queue") or {}).get("status"),
        "loop_status": (data.get("loop") or {}).get("status"),
        "prompt_quarantine_count": (data.get("prompt_summary") or {}).get("quarantine_count"),
        "warnings": data.get("warnings") or [],
    }


def _prompt_summary(repo_root: Path) -> dict[str, Any]:
    root = repo_root / ".build" / "rig" / "prompts"
    latest = _load_json(root / "latest.json", {}) if root.exists() else {}
    traces_root = root / "traces"
    quarantine_root = root / "quarantine"
    regression_root = root / "regression"
    experiments_root = root / "experiments"
    latest_quarantine = None
    quarantine_paths = _list_paths(quarantine_root, "*/trace.json") if quarantine_root.exists() else []
    if quarantine_paths:
        latest_quarantine = _load_json(quarantine_paths[-1], {})
    latest_experiment = None
    experiment_paths = _list_paths(experiments_root, "*/latest.json") if experiments_root.exists() else []
    if experiment_paths:
        latest_experiment = _load_json(experiment_paths[-1], {})
    return {
        "path": _repo_rel(repo_root, root),
        "trace_count": len(_list_paths(traces_root, "*/trace.json")) if traces_root.exists() else 0,
        "quarantine_count": len(quarantine_paths),
        "top_failure_types": prompt_telemetry.top_failure_types(repo_root, limit=5) if hasattr(prompt_telemetry, "top_failure_types") else [],
        "latest_experiment": latest_experiment,
        "latest_quarantined_trace": latest_quarantine,
        "regression_case_count": len(_list_paths(regression_root, "**/cases/*.json")) if regression_root.exists() else 0,
        "latest_trace": latest,
    }


def _action_summary(repo_root: Path) -> dict[str, Any]:
    root = repo_root / ".build" / "rig" / "actions"
    latest = _load_json(root / "latest.json", {}) if root.exists() else {}
    return {
        "path": _repo_rel(repo_root, root),
        "count": len(_list_paths(root, "*.json")) if root.exists() else 0,
        "latest_action": latest,
    }


def _policy_summary(repo_root: Path) -> dict[str, Any]:
    root = repo_root / ".build" / "rig" / "policy"
    latest = _load_json(root / "latest.json", {}) if root.exists() else {}
    return {
        "path": _repo_rel(repo_root, root),
        "count": len(_list_paths(root, "*.json")) if root.exists() else 0,
        "latest_decision": latest,
    }


def _doctor_summary(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ".build" / "rig" / "doctor" / "latest.json"
    data = _load_json(path, {})
    if not isinstance(data, dict):
        return {"path": None, "status": None, "warnings": []}
    return {
        "path": _repo_rel(repo_root, path),
        "status": data.get("status"),
        "failures": data.get("failures", []),
        "warnings": data.get("warnings", []),
    }


def _contract_audit_summary(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ".build" / "rig" / "audit" / "contracts" / "latest.json"
    data = _load_json(path, {})
    if not isinstance(data, dict):
        return {"path": None, "status": None, "issues": []}
    return {
        "path": _repo_rel(repo_root, path),
        "status": data.get("status"),
        "issues": data.get("issues", []),
        "surfaces": data.get("surfaces", []),
    }


def _db_state(repo_root: Path) -> dict[str, Any]:
    if not rig_duckdb.duckdb_available() or not rig_duckdb.db_path(repo_root).exists():
        return {}
    try:
        from rig_tools import result_index

        return {
            "runs": rig_duckdb.query_latest_runs(repo_root),
            "agent_runs": build_agent_runs(repo_root),
            "loop_runs": build_loop_runs(repo_root),
            "tasks": result_index.build_tasks(repo_root),
            "latest_events": result_index.build_latest_events(repo_root),
            "affected_summary": result_index.build_affected_rows(repo_root)[-1] if result_index.build_affected_rows(repo_root) else {},
            "swift_diagnostics_summary": result_index.build_swift_rows(repo_root)[-1] if result_index.build_swift_rows(repo_root) else {},
            "schema_validation_summary": rig_duckdb.health(repo_root),
            "cache_metadata_summary": rig_duckdb.health(repo_root),
            "review_bundle_summary": {},
            "git_status_summary": {},
            "commit_plan_summary": rig_duckdb.query_commit_plans(repo_root)[-1] if rig_duckdb.query_commit_plans(repo_root) else {},
            "registry_gate_summary": rig_duckdb.query_registry_gate(repo_root)[-1] if rig_duckdb.query_registry_gate(repo_root) else {},
            "context_pack_summary": _context_pack_summary(repo_root),
            "queue_summary": _queue_summary(repo_root),
            "patch_summary": _patch_summary(repo_root),
            "tui_summary": _tui_summary(repo_root),
            "action_summary": _action_summary(repo_root),
            "policy_summary": _policy_summary(repo_root),
            "doctor_summary": _doctor_summary(repo_root),
            "contract_audit_summary": _contract_audit_summary(repo_root),
            "prompt_summary": _prompt_summary(repo_root),
            "warnings": [],
        }
    except Exception as exc:
        return {"warnings": [f"duckdb_read_failed:{exc}"]}


def build_state(repo_root: Path, *, from_db: bool = False) -> dict[str, Any]:
    if from_db:
        db_state = _db_state(repo_root)
        if db_state and not db_state.get("warnings"):
            db_state["schema_version"] = SCHEMA_VERSION
            db_state["generated_at"] = utc_now()
            return db_state
            
    board = kanban_board.build_kanban_board(repo_root)
    graph = task_graph.build_task_graph(repo_root, board.get("cards", []))
    
    runs = build_runs(repo_root)
    agent_runs = build_agent_runs(repo_root)
    loop_runs = build_loop_runs(repo_root)
    tasks = build_tasks(repo_root)
    latest_events = build_latest_events(repo_root)
    affected_summary = _summary_from_json(repo_root / ".build" / "rig" / "affected" / "targets.json", repo_root, ["task", "mode", "directly_affected_targets"])
    swift_diagnostics_summary = _summary_from_json(repo_root / ".build" / "rig" / "swift-diagnostics" / "latest.json", repo_root, ["status", "exit_code", "diagnostics", "tool_missing"])
    schema_validation_summary = _summary_from_json(repo_root / ".build" / "rig" / "schema-validation" / "latest.json", repo_root, ["status", "exit_code", "artifact"])
    cache_metadata_summary = {
        "path": _repo_rel(repo_root, repo_root / ".build" / "rig" / "cache-metadata"),
        "count": len(_list_paths(repo_root / ".build" / "rig" / "cache-metadata", "*.json")),
    }
    review_bundle_summary = {
        "path": _repo_rel(repo_root, repo_root / ".build" / "review-bundles"),
        "count": len(_list_paths(repo_root / ".build" / "review-bundles", "*.zip")),
    }
    context_pack_summary = _context_pack_summary(repo_root)
    queue_summary = _queue_summary(repo_root)
    patch_summary = _patch_summary(repo_root)
    tui_summary = _tui_summary(repo_root)
    action_summary = _action_summary(repo_root)
    policy_summary = _policy_summary(repo_root)
    doctor_summary = _doctor_summary(repo_root)
    contract_audit_summary = _contract_audit_summary(repo_root)
    prompt_summary = _prompt_summary(repo_root)
    
    model_summary = {
        "catalog_count": len(model_manager.load_catalog(repo_root)),
        "local_count": len(model_manager.list_local_models(repo_root)),
        "active_model": _load_json(repo_root / ".build" / "rig" / "models" / "active-llama-cpp-model.json", {}).get("model_id"),
    }
    
    board_summary = {
        "column_counts": {col: len([c for c in board["cards"] if c["column_id"] == col]) for col in kanban_board.COLUMNS},
        "card_count": len(board["cards"]),
    }
    
    graph_summary = {
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "runnable_count": len(graph["runnable_tasks"]),
        "blocked_count": len(graph["blocked_tasks"]),
        "top_runnable": graph["runnable_tasks"][:5],
    }

    agent_discovery_summary = _summary_from_json(repo_root / ".build" / "rig" / "agents" / "discovery" / "latest.json", repo_root, ["created_at", "agents"])
    git_status_summary = _summary_from_json(repo_root / ".build" / "rig" / "git" / "commit-plan-rig-git-management-bootstrap.json", repo_root, ["status", "registry_gate_status"])
    commit_plan_summary = _summary_from_json(repo_root / ".build" / "rig" / "git" / "commit-plan-rig-git-management-bootstrap.json", repo_root, ["status", "commit_message", "files", "registry_gate_status"])
    registry_gate_summary = _summary_from_json(repo_root / ".build" / "anigma-diagnostics" / "tasks" / "rig-monitor-tui-bootstrap", repo_root, ["status", "exitCode", "failureCount"])
    system_pressure_summary = system_pressure.sample_system_pressure(repo_root)
    warnings = []
    if not runs:
        warnings.append("no_runs_found")
    if not latest_events:
        warnings.append("no_events_found")
    if not agent_runs:
        warnings.append("no_agent_runs_found")
    if not loop_runs:
        warnings.append("no_loop_runs_found")
    
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "repo_name": repo_root.name,
        "runs": runs,
        "agent_runs": agent_runs,
        "loop_runs": loop_runs,
        "tasks": tasks,
        "latest_events": latest_events,
        "affected_summary": affected_summary,
        "swift_diagnostics_summary": swift_diagnostics_summary,
        "schema_validation_summary": schema_validation_summary,
        "cache_metadata_summary": cache_metadata_summary,
        "review_bundle_summary": review_bundle_summary,
        "context_pack_summary": context_pack_summary,
        "queue_summary": queue_summary,
        "registry_gate_summary": registry_gate_summary,
        "patch_summary": patch_summary,
        "tui_summary": tui_summary,
        "action_summary": action_summary,
        "policy_summary": policy_summary,
        "doctor_summary": doctor_summary,
        "contract_audit_summary": contract_audit_summary,
        "prompt_summary": prompt_summary,
        "model_summary": model_summary,
        "board_summary": board_summary,
        "graph_summary": graph_summary,
        "agent_discovery_summary": agent_discovery_summary,
        "system_pressure": system_pressure_summary,
        "warnings": warnings,
    }


def write_state(repo_root: Path, *, from_db: bool = False) -> Path:
    out_dir = repo_root / ".build" / "rig" / "monitor"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "state.json"
    path.write_text(json.dumps(build_state(repo_root, from_db=from_db), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def render_html(state: dict[str, Any]) -> str:
    def table(rows: list[dict[str, Any]], headers: list[str]) -> str:
        if not rows:
            return "<p>Missing.</p>"
        head = "".join(f"<th>{h}</th>" for h in headers)
        body_rows = []
        for row in rows:
            cells = "".join(f"<td>{row.get(h, '')}</td>" for h in headers)
            body_rows.append(f"<tr>{cells}</tr>")
        return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"

    def kv(items: dict[str, Any]) -> str:
        rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in items.items())
        return f"<table>{rows}</table>"

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rig Monitor</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f6f7fb; color: #111; }}
section {{ margin: 0 0 24px; padding: 16px; background: white; border-radius: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #e6e6e6; text-align: left; padding: 6px 8px; vertical-align: top; }}
h2 {{ margin-top: 0; }}
</style>
</head>
<body>
<h1>Rig Monitor</h1>
<section><h2>Overview</h2>{kv({"generated_at": state.get("generated_at"), "warnings": ", ".join(state.get("warnings", [])) or "none"})}</section>
<section><h2>Kanban</h2>{kv(state.get("board_summary", {}).get("column_counts", {}))}</section>
<section><h2>Graph</h2>{kv(state.get("graph_summary", {}))}</section>
<section><h2>Tasks</h2>{table(state.get("tasks", []), ["task_id", "latest_run_status", "latest_pipeline_status", "affected_targets", "commit_plan_status"])}</section>
<section><h2>Runs</h2>{table(state.get("runs", []), ["run_id", "task", "command_group", "status", "exit_code", "duration_seconds"])}</section>
<section><h2>Agent Runs</h2>{table(state.get("agent_runs", []), ["run_id", "plan_id", "task", "agent_id", "status", "exit_code", "duration_seconds"])}</section>
<section><h2>Loop Runs</h2>{table(state.get("loop_runs", []), ["run_id", "task", "mode", "status", "stop_reason", "duration_seconds"])}</section>
<section><h2>Latest Events</h2>{table(state.get("latest_events", []), ["timestamp_utc", "event_type", "run_id", "command_group"])}</section>
<section><h2>Affected</h2>{kv(state.get("affected_summary", {}))}</section>
<section><h2>Swift Diagnostics</h2>{kv(state.get("swift_diagnostics_summary", {}))}</section>
<section><h2>Schema Validation</h2>{kv(state.get("schema_validation_summary", {}))}</section>
<section><h2>Git / Commit Plan</h2>{kv(state.get("commit_plan_summary", {}))}</section>
<section><h2>Registry Gate</h2>{kv(state.get("registry_gate_summary", {}))}</section>
<section><h2>Cache Metadata</h2>{kv(state.get("cache_metadata_summary", {}))}</section>
<section><h2>Review Bundles</h2>{kv(state.get("review_bundle_summary", {}))}</section>
<section><h2>Context Pack</h2>{kv(state.get("context_pack_summary", {}))}</section>
<section><h2>Queue</h2>{kv(state.get("queue_summary", {}))}</section>
<section><h2>Patch</h2>{kv(state.get("patch_summary", {}))}</section>
<section><h2>Action</h2>{kv(state.get("action_summary", {}))}</section>
<section><h2>Policy</h2>{kv(state.get("policy_summary", {}))}</section>
<section><h2>Doctor</h2>{kv(state.get("doctor_summary", {}))}</section>
<section><h2>Contract Audit</h2>{kv(state.get("contract_audit_summary", {}))}</section>
<section><h2>Prompt Telemetry</h2>{kv(state.get("prompt_summary", {}))}</section>
<section><h2>System Pressure</h2>{kv(state.get("system_pressure", {}).get("memory", {}))}</section>
</body>
</html>
"""


def write_html(repo_root: Path, state: dict[str, Any]) -> Path:
    out_dir = repo_root / ".build" / "rig" / "monitor"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render_html(state), encoding="utf-8")
    return path


def write_snapshot(repo_root: Path, *, from_db: bool = False) -> dict[str, Path]:
    state = build_state(repo_root, from_db=from_db)
    state_path = write_state(repo_root, from_db=from_db)
    html_path = write_html(repo_root, state)
    return {"state": state_path, "html": html_path}
