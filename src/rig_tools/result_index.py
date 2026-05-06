from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _repo_rel(repo_root: Path, path: str | Path | None) -> str | None:
    if path is None:
        return None
    text = str(path)
    if not text:
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        try:
            return str(candidate.relative_to(repo_root))
        except Exception:
            return text.replace("\\", "/")
    text = text.replace("\\", "/")
    if text.startswith("./"):
        return text[2:]
    return text


def _stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(data), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _normalize_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _count_artifacts(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _latest_pipeline_manifest(repo_root: Path, task: str | None, run_id: str | None) -> str | None:
    runs_root = repo_root / ".build" / "anigma-pipeline" / "runs"
    if not runs_root.exists():
        return None
    candidates = list(runs_root.glob("*/*/manifest.json"))
    if not candidates:
        return None
    best: Path | None = None
    for manifest in candidates:
        if task and task not in manifest.as_posix():
            try:
                data = _load_json(manifest, {})
            except Exception:
                continue
            if data.get("task") != task and data.get("task_id") != task:
                continue
        if run_id and run_id not in manifest.as_posix():
            try:
                data = _load_json(manifest, {})
            except Exception:
                continue
            if data.get("run_id") != run_id:
                continue
        if best is None or manifest.stat().st_mtime > best.stat().st_mtime:
            best = manifest
    return _repo_rel(repo_root, best) if best else None


def _discover_run_results(repo_root: Path) -> list[Path]:
    results_dir = repo_root / ".build" / "rig" / "results"
    if not results_dir.exists():
        return []
    return sorted(
        [p for p in results_dir.glob("*.json") if p.is_file()],
        key=lambda p: (p.stat().st_mtime, p.name),
    )


def _discover_pipeline_manifests(repo_root: Path) -> list[Path]:
    runs_root = repo_root / ".build" / "anigma-pipeline" / "runs"
    if not runs_root.exists():
        return []
    return sorted([p for p in runs_root.glob("*/*/manifest.json") if p.is_file()], key=lambda p: (p.stat().st_mtime, p.as_posix()))


def _discover_step_results(repo_root: Path) -> list[Path]:
    runs_root = repo_root / ".build" / "anigma-pipeline" / "runs"
    if not runs_root.exists():
        return []
    return sorted([p for p in runs_root.glob("*/*/step-results/*.json") if p.is_file()], key=lambda p: (p.stat().st_mtime, p.as_posix()))


def _discover_swift_diagnostics(repo_root: Path) -> list[Path]:
    out_dir = repo_root / ".build" / "rig" / "swift-diagnostics"
    if not out_dir.exists():
        return []
    return sorted([p for p in out_dir.glob("*.json") if p.is_file()], key=lambda p: (p.stat().st_mtime, p.name))


def _discover_affected(repo_root: Path) -> list[Path]:
    out_dir = repo_root / ".build" / "rig" / "affected"
    if not out_dir.exists():
        return []
    return sorted([p for p in out_dir.glob("*.json") if p.is_file()], key=lambda p: p.name)


def _discover_cache_metadata(repo_root: Path) -> list[Path]:
    out_dir = repo_root / ".build" / "rig" / "cache-metadata"
    if not out_dir.exists():
        return []
    return sorted([p for p in out_dir.glob("*.json") if p.is_file()], key=lambda p: p.name)


def _discover_validator_registry_checks(repo_root: Path) -> list[Path]:
    root = repo_root / ".build" / "anigma-diagnostics" / "tasks"
    if not root.exists():
        return []
    return sorted([p for p in root.glob("*/*/*/logs/validator-registry-check.json") if p.is_file()], key=lambda p: (p.stat().st_mtime, p.as_posix()))


def _discover_review_bundle_manifests(repo_root: Path) -> list[Path]:
    out_dir = repo_root / ".build" / "review-bundles"
    if not out_dir.exists():
        return []
    return sorted([p for p in out_dir.glob("*.zip") if p.is_file()], key=lambda p: p.name)


def build_run_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _discover_run_results(repo_root):
        data = _load_json(path, {})
        artifacts = _normalize_list(data.get("artifacts"))
        warnings = _normalize_list(data.get("warnings"))
        errors = _normalize_list(data.get("errors"))
        rows.append({
            "run_id": data.get("run_id") or path.stem,
            "command_group": data.get("command_group"),
            "command": data.get("command"),
            "task": data.get("task"),
            "status": data.get("status"),
            "exit_code": data.get("exit_code"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "duration_seconds": data.get("duration_seconds"),
            "artifact_count": _count_artifacts(artifacts),
            "warning_count": len(warnings),
            "error_count": len(errors),
            "result_path": _repo_rel(repo_root, path),
            "latest_manifest_path": _latest_pipeline_manifest(repo_root, data.get("task"), data.get("run_id")),
        })
    rows.sort(key=lambda row: (str(row.get("finished_at") or ""), str(row.get("run_id") or "")))
    return rows


def build_step_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _discover_step_results(repo_root):
        data = _load_json(path, {})
        rows.append({
            "run_id": data.get("run_id"),
            "task": data.get("task_id") or data.get("task"),
            "profile": data.get("profile"),
            "step_id": data.get("step_id"),
            "command": data.get("command"),
            "status": data.get("status"),
            "exit_code": data.get("exit_code"),
            "duration_seconds": data.get("duration_seconds"),
            "known_blocker_id": data.get("matched_known_blocker"),
            "stdout_log": _repo_rel(repo_root, data.get("stdout_log")),
            "stderr_log": _repo_rel(repo_root, data.get("stderr_log")),
            "result_path": _repo_rel(repo_root, path),
        })
    rows.sort(key=lambda row: (str(row.get("run_id") or ""), str(row.get("profile") or ""), str(row.get("step_id") or "")))
    return rows


def build_swift_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    result_lookup = {}
    for path in _discover_run_results(repo_root):
        data = _load_json(path, {})
        result_lookup.setdefault("latest", data)
    for path in _discover_swift_diagnostics(repo_root):
        data = _load_json(path, {})
        diagnostics = _normalize_list(data.get("diagnostics"))
        categories = sorted({str(item.get("category")) for item in diagnostics if isinstance(item, dict) and item.get("category")})
        run_id = data.get("run_id")
        task = data.get("task")
        rows.append({
            "run_id": run_id,
            "task": task,
            "target": data.get("target"),
            "command": " ".join(data.get("command", [])) if isinstance(data.get("command"), list) else data.get("command"),
            "exit_code": data.get("exit_code"),
            "status": data.get("status"),
            "diagnostic_count": len(diagnostics),
            "error_count": sum(1 for item in diagnostics if isinstance(item, dict) and item.get("severity") == "error"),
            "warning_count": sum(1 for item in diagnostics if isinstance(item, dict) and item.get("severity") == "warning"),
            "categories": ";".join(categories),
            "known_blocker_id": next((item.get("known_blocker_id") for item in diagnostics if isinstance(item, dict) and item.get("known_blocker_id")), None),
            "latest_json": _repo_rel(repo_root, path),
            "latest_md": _repo_rel(repo_root, path.with_suffix(".md")),
        })
    rows.sort(key=lambda row: (str(row.get("task") or ""), str(row.get("target") or ""), str(row.get("latest_json") or "")))
    return rows


def build_affected_rows(repo_root: Path) -> list[dict[str, Any]]:
    grouped: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for path in _discover_affected(repo_root):
        data = _load_json(path, {})
        if not isinstance(data, dict):
            continue
        key = (data.get("task"), data.get("mode"))
        row = grouped.setdefault(key, {
            "task": data.get("task"),
            "mode": data.get("mode"),
            "changed_file_count": None,
            "directly_affected_targets": [],
            "affected_risk_count": None,
            "recommended_profiles": [],
            "files_json": _repo_rel(repo_root, repo_root / ".build" / "rig" / "affected" / "files.json"),
            "targets_json": _repo_rel(repo_root, repo_root / ".build" / "rig" / "affected" / "targets.json"),
            "risks_json": _repo_rel(repo_root, repo_root / ".build" / "rig" / "affected" / "risks.json"),
            "profiles_json": _repo_rel(repo_root, repo_root / ".build" / "rig" / "affected" / "profiles.json"),
            "summary_md": _repo_rel(repo_root, repo_root / ".build" / "rig" / "affected" / "summary.md"),
            "result_paths": [],
        })
        if path.name == "files.json":
            row["changed_file_count"] = data.get("changed_file_count")
        elif path.name == "targets.json":
            row["directly_affected_targets"] = _normalize_list(data.get("directly_affected_targets"))
        elif path.name == "risks.json":
            row["affected_risk_count"] = data.get("affected_risk_count")
        elif path.name == "profiles.json":
            row["recommended_profiles"] = _normalize_list(data.get("recommended_profiles"))
        row["result_paths"].append(_repo_rel(repo_root, path))
    rows = []
    for row in grouped.values():
        rows.append({
            "task": row["task"],
            "mode": row["mode"],
            "changed_file_count": row["changed_file_count"],
            "directly_affected_targets": ";".join(row["directly_affected_targets"]),
            "affected_risk_count": row["affected_risk_count"],
            "recommended_profiles": ";".join(row["recommended_profiles"]),
            "files_json": row["files_json"],
            "targets_json": row["targets_json"],
            "risks_json": row["risks_json"],
            "profiles_json": row["profiles_json"],
            "summary_md": row["summary_md"],
            "result_path": ";".join(sorted(dict.fromkeys(row["result_paths"]))),
        })
    rows.sort(key=lambda row: (str(row.get("task") or ""), str(row.get("mode") or ""), str(row.get("result_path") or "")))
    return rows


def build_cache_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _discover_cache_metadata(repo_root):
        data = _load_json(path, {})
        input_files = _normalize_list(data.get("input_files"))
        output_files = _normalize_list(data.get("output_files"))
        rows.append({
            "artifact_id": data.get("artifact_id") or path.stem,
            "producer": data.get("producer"),
            "command": data.get("command"),
            "cache_key": data.get("cache_key"),
            "status": data.get("status"),
            "input_count": len(input_files),
            "output_count": len(output_files),
            "duration_seconds": data.get("duration_seconds"),
            "metadata_path": _repo_rel(repo_root, path),
        })
    rows.sort(key=lambda row: (str(row.get("producer") or ""), str(row.get("artifact_id") or "")))
    return rows


def build_registry_rows(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _discover_validator_registry_checks(repo_root):
        data = _load_json(path, {})
        if not isinstance(data, dict):
            continue
        parts = path.parts
        phase = "unknown"
        if "validate" in parts:
            phase = "validate"
        elif "review" in parts:
            phase = "review"
        rows.append({
            "task_id": parts[-5] if len(parts) >= 5 else None,
            "phase": phase,
            "status": data.get("status"),
            "exit_code": data.get("exitCode"),
            "failure_count": data.get("failureCount"),
            "warning_count": data.get("warningCount"),
            "strict_warning_count": data.get("strictWarningCount"),
            "report_path": _repo_rel(repo_root, path),
            "log_path": _repo_rel(repo_root, path.with_suffix(".log")) if path.with_suffix(".log").exists() else None,
            "diagnostic_run_path": _repo_rel(repo_root, path.parent.parent.parent.parent),
            "timestamp_or_run_id": path.parent.parent.parent.name,
        })
    rows.sort(key=lambda row: (str(row.get("task_id") or ""), str(row.get("phase") or ""), str(row.get("report_path") or "")))
    return rows


def _read_review_bundle_manifest(repo_root: Path, bundle_path: Path) -> dict[str, Any] | None:
    import zipfile

    if not bundle_path.exists():
        return None
    try:
        with zipfile.ZipFile(bundle_path) as zf:
            with zf.open("bundle-manifest.json") as fh:
                return json.loads(fh.read().decode("utf-8"))
    except Exception:
        return None


def build_indexes(repo_root: Path) -> dict[str, Any]:
    runs = build_run_rows(repo_root)
    steps = build_step_rows(repo_root)
    swift = build_swift_rows(repo_root)
    affected = build_affected_rows(repo_root)
    cache_rows = build_cache_rows(repo_root)
    registry_rows = build_registry_rows(repo_root)
    return {
        "rig-run-index": runs,
        "rig-step-index": steps,
        "rig-swift-diagnostics-index": swift,
        "rig-affected-index": affected,
        "rig-cache-metadata-index": cache_rows,
        "validator-registry-index": registry_rows,
    }


def write_indexes(repo_root: Path) -> dict[str, Path]:
    indexes_dir = repo_root / "Docs" / "indexes"
    indexes_dir.mkdir(parents=True, exist_ok=True)
    indexes = build_indexes(repo_root)
    output_paths: dict[str, Path] = {}
    headers = {
        "rig-run-index": ["run_id", "command_group", "command", "task", "status", "exit_code", "started_at", "finished_at", "duration_seconds", "artifact_count", "warning_count", "error_count", "result_path", "latest_manifest_path"],
        "rig-step-index": ["run_id", "task", "profile", "step_id", "command", "status", "exit_code", "duration_seconds", "known_blocker_id", "stdout_log", "stderr_log", "result_path"],
        "rig-swift-diagnostics-index": ["run_id", "task", "target", "command", "exit_code", "status", "diagnostic_count", "error_count", "warning_count", "categories", "known_blocker_id", "latest_json", "latest_md"],
        "rig-affected-index": ["task", "mode", "changed_file_count", "directly_affected_targets", "affected_risk_count", "recommended_profiles", "files_json", "targets_json", "risks_json", "profiles_json", "summary_md", "result_path"],
        "rig-cache-metadata-index": ["artifact_id", "producer", "command", "cache_key", "status", "input_count", "output_count", "duration_seconds", "metadata_path"],
        "validator-registry-index": ["task_id", "phase", "status", "exit_code", "failure_count", "warning_count", "strict_warning_count", "report_path", "log_path", "diagnostic_run_path", "timestamp_or_run_id"],
    }

    for name, rows in indexes.items():
        json_path = indexes_dir / f"{name}.json"
        csv_path = indexes_dir / f"{name}.csv"
        _write_json(json_path, rows)
        _write_csv(csv_path, rows, headers.get(name, list(rows[0].keys()) if rows else []))
        output_paths[f"{name}.json"] = json_path
        output_paths[f"{name}.csv"] = csv_path
    return output_paths


def build_context_pack(repo_root: Path, *, task: str | None = None, budget: str = "small") -> dict[str, Any]:
    run_rows = build_run_rows(repo_root)
    swift_rows = build_swift_rows(repo_root)
    affected_rows = build_affected_rows(repo_root)
    cache_rows = build_cache_rows(repo_root)
    registry_rows = build_registry_rows(repo_root)

    latest_run = next((row for row in reversed(run_rows) if not task or row.get("task") == task), run_rows[-1] if run_rows else None)
    latest_swift = swift_rows[-1] if swift_rows else None
    latest_affected = next((row for row in reversed(affected_rows) if not task or row.get("task") == task), affected_rows[-1] if affected_rows else None)
    latest_registry = next((row for row in reversed(registry_rows) if not task or row.get("task_id") == task), registry_rows[-1] if registry_rows else None)
    cache_fresh = sum(1 for row in cache_rows if row.get("status") == "fresh")
    cache_total = len(cache_rows)

    lines = [
        "# Rig Context Pack",
        "",
        f"- Task: `{task or 'n/a'}`",
        f"- Budget: `{budget}`",
        f"- Run rows: `{len(run_rows)}`",
        f"- Swift diagnostics rows: `{len(swift_rows)}`",
        f"- Affected rows: `{len(affected_rows)}`",
        f"- Cache metadata rows: `{len(cache_rows)}`",
        f"- Registry gate rows: `{len(registry_rows)}`",
        f"- Cache fresh: `{cache_fresh}/{cache_total}`",
        "",
        "## Latest Run",
    ]
    if latest_run:
        lines.extend([
            f"- Run ID: `{latest_run.get('run_id')}`",
            f"- Command group: `{latest_run.get('command_group')}`",
            f"- Status: `{latest_run.get('status')}`",
            f"- Exit code: `{latest_run.get('exit_code')}`",
            f"- Result path: `{latest_run.get('result_path')}`",
        ])
    else:
        lines.append("- None")
    lines.extend(["", "## Swift Diagnostics"])
    if latest_swift:
        lines.extend([
            f"- Target: `{latest_swift.get('target') or 'n/a'}`",
            f"- Status: `{latest_swift.get('status')}`",
            f"- Exit code: `{latest_swift.get('exit_code')}`",
            f"- Diagnostic count: `{latest_swift.get('diagnostic_count')}`",
            f"- Categories: `{latest_swift.get('categories') or 'n/a'}`",
        ])
    else:
        lines.append("- None")
    lines.extend(["", "## Affected"])
    if latest_affected:
        lines.extend([
            f"- Mode: `{latest_affected.get('mode')}`",
            f"- Changed files: `{latest_affected.get('changed_file_count')}`",
            f"- Directly affected targets: `{latest_affected.get('directly_affected_targets') or 'n/a'}`",
            f"- Affected risks: `{latest_affected.get('affected_risk_count')}`",
            f"- Recommended profiles: `{latest_affected.get('recommended_profiles') or 'n/a'}`",
        ])
    else:
        lines.append("- None")
    lines.extend(["", "## Cache Metadata", f"- Fresh rows: `{cache_fresh}`", f"- Total rows: `{cache_total}`"])
    lines.extend(["", "## Validator Registry"])
    if latest_registry:
        lines.extend([
            f"- Task ID: `{latest_registry.get('task_id') or 'n/a'}`",
            f"- Phase: `{latest_registry.get('phase')}`",
            f"- Status: `{latest_registry.get('status')}`",
            f"- Exit code: `{latest_registry.get('exit_code')}`",
            f"- Report path: `{latest_registry.get('report_path')}`",
        ])
    else:
        lines.append("- None")
    return {
        "task": task,
        "budget": budget,
        "latest_run": latest_run,
        "latest_swift": latest_swift,
        "latest_affected": latest_affected,
        "latest_registry": latest_registry,
        "cache_fresh": cache_fresh,
        "cache_total": cache_total,
        "registry_rows": len(registry_rows),
        "markdown": "\n".join(lines) + "\n",
    }
