#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from rig_tools import rig_duckdb, schema_validation

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rig.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def _temp_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="rig-duckdb-test-"))
    for rel in [
        ".build/rig/results",
        ".build/rig/events",
        ".build/rig/affected",
        ".build/rig/swift-diagnostics",
        ".build/rig/git",
        ".build/rig/schema-validation",
        ".build/rig/cache-metadata",
        "Docs/indexes",
    ]:
        (repo / rel).mkdir(parents=True, exist_ok=True)
    return repo


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_json_root_helpers() -> None:
    assert rig_duckdb.json_root_kind({"schema_version": "x"}) == "object"
    assert rig_duckdb.json_root_kind([1, 2]) == "array"
    assert rig_duckdb.json_root_kind("x") == "string"
    assert rig_duckdb.json_root_kind(3) == "number"
    assert rig_duckdb.json_root_kind(True) == "boolean"
    assert rig_duckdb.json_root_kind(None) == "null"
    assert rig_duckdb.extract_schema_version({"schema_version": "rig.result.v1"}) == "rig.result.v1"
    assert rig_duckdb.extract_schema_version([{"schema_version": "rig.event.v1"}]) == "array:rig.event.v1"
    assert rig_duckdb.extract_schema_version([]) is None
    assert rig_duckdb.extract_schema_version("x") is None


def test_artifact_rows_handle_mixed_json_shapes() -> None:
    repo = _temp_repo()
    _write(repo / ".build/rig/results/object.json", {"schema_version": "rig.result.v1", "run_id": "r1"})
    _write(repo / ".build/rig/results/array.json", [{"schema_version": "rig.event.v1"}, {"event_type": "run_started"}])
    _write(repo / ".build/rig/results/invalid.json", "{")
    _write(repo / ".build/rig/results/plain.json", {"hello": "world"})
    rows, omitted = rig_duckdb._artifact_rows(repo)
    by_name = {Path(row["path"]).name: row for row in rows}
    assert by_name["object.json"]["schema_version"] == "rig.result.v1"
    assert by_name["object.json"]["json_root_kind"] == "object"
    assert by_name["array.json"]["schema_version"] == "array:rig.event.v1"
    assert by_name["array.json"]["json_root_kind"] == "array"
    assert by_name["invalid.json"]["schema_version"] is None
    assert by_name["invalid.json"]["json_root_kind"] == "invalid"
    assert any(item["path"].endswith("invalid.json") for item in omitted)


def test_ingest_handles_top_level_arrays_and_invalid_json() -> None:
    repo = _temp_repo()
    _write(repo / ".build/rig/results/latest.json", {"schema_version": "rig.result.v1", "run_id": "r1", "command_group": "pipeline", "command": "rig pipeline run", "status": "passed", "exit_code": 0, "artifacts": [], "warnings": [], "errors": [], "summary": {}})
    _write(repo / ".build/rig/results/array.json", [{"schema_version": "rig.event.v1"}])
    _write(repo / ".build/rig/results/invalid.json", "{")
    _write(repo / ".build/rig/events/r1.jsonl", json.dumps({"schema_version": "rig.event.v1", "event_type": "run_started", "timestamp_utc": "2026-05-05T00:00:00Z", "run_id": "r1", "command_group": "pipeline", "command": "rig pipeline run", "attributes": {}}) + "\n")
    _write(repo / ".build/rig/affected/files.json", {"schema_version": "rig.affected.v1", "mode": "git", "changed_files": []})
    _write(repo / ".build/rig/swift-diagnostics/latest.json", {"schema_version": "rig.swift_diagnostics.v1", "run_label": "x", "command": [], "exit_code": 0, "status": "passed", "summary": {}, "diagnostics": []})
    _write(repo / ".build/rig/cache-metadata/meta.json", {"schema_version": "rig.cache_metadata.v1", "artifact_id": "a", "producer": "p", "command": "c", "cache_key": "k", "status": "fresh", "input_files": [], "output_files": []})
    _write(repo / ".build/rig/git/commit-plan-td.json", {"schema_version": "rig.git_commit_plan.v1", "task": "td", "status": "ready_to_commit", "scope_status": "passed", "registry_gate_status": "passed", "schema_status": "passed", "production_source_changed": False, "baselines_changed": False, "commit_message": "msg"})
    _write(repo / ".build/rig/schema-validation/latest.json", {"schema_version": "rig.result.v1", "run_id": "v1", "command_group": "schema", "command": "rig schema validate", "status": "passed", "exit_code": 0, "artifacts": [], "warnings": [], "errors": [], "summary": {}})
    res = rig_duckdb.ingest(repo)
    assert res["status"] == "passed"
    assert res["source_artifact_counts"]["artifacts"] >= 3
    manifest = json.loads((repo / ".build" / "rig" / "rig-duckdb-manifest.json").read_text(encoding="utf-8"))
    assert any("invalid_json" in warning for warning in manifest["warnings"])
    assert manifest["table_counts"]["artifacts"] >= 3
    assert manifest["table_counts"]["runs"] >= 0


def test_latest_runs_query_and_health_after_ingest() -> None:
    repo = _temp_repo()
    _write(repo / ".build/rig/results/latest.json", {"schema_version": "rig.result.v1", "run_id": "r1", "command_group": "pipeline", "command": "rig pipeline run", "status": "passed", "exit_code": 0, "artifacts": [], "warnings": [], "errors": [], "summary": {}})
    _write(repo / ".build/rig/results/array.json", [{"schema_version": "rig.event.v1"}])
    _write(repo / ".build/rig/events/r1.jsonl", json.dumps({"schema_version": "rig.event.v1", "event_type": "run_started", "timestamp_utc": "2026-05-05T00:00:00Z", "run_id": "r1", "command_group": "pipeline", "command": "rig pipeline run", "attributes": {}}) + "\n")
    _write(repo / ".build/rig/affected/files.json", {"schema_version": "rig.affected.v1", "mode": "git", "changed_files": []})
    _write(repo / ".build/rig/swift-diagnostics/latest.json", {"schema_version": "rig.swift_diagnostics.v1", "run_label": "x", "command": [], "exit_code": 0, "status": "passed", "summary": {}, "diagnostics": []})
    _write(repo / ".build/rig/cache-metadata/meta.json", {"schema_version": "rig.cache_metadata.v1", "artifact_id": "a", "producer": "p", "command": "c", "cache_key": "k", "status": "fresh", "input_files": [], "output_files": []})
    _write(repo / ".build/rig/git/commit-plan-td.json", {"schema_version": "rig.git_commit_plan.v1", "task": "td", "status": "ready_to_commit", "scope_status": "passed", "registry_gate_status": "passed", "schema_status": "passed", "production_source_changed": False, "baselines_changed": False, "commit_message": "msg"})
    _write(repo / ".build/rig/schema-validation/latest.json", {"schema_version": "rig.result.v1", "run_id": "v1", "command_group": "schema", "command": "rig schema validate", "status": "passed", "exit_code": 0, "artifacts": [], "warnings": [], "errors": [], "summary": {}})
    init = rig_duckdb.init_db(repo)
    assert init["status"] == "passed"
    ingest = rig_duckdb.ingest(repo)
    assert ingest["status"] == "passed"
    health_payload = rig_duckdb.health(repo)
    assert health_payload["duckdb_available"] is True
    assert health_payload["table_counts"]["artifacts"] > 0
    latest_runs = rig_duckdb.query_latest_runs(repo)
    assert latest_runs, latest_runs
    assert any(row["run_id"] == "r1" for row in latest_runs)


def test_schema_validation_sees_duckdb_manifest() -> None:
    repo = REPO_ROOT
    manifest = rig_duckdb.health(repo)["manifest_path"]
    result = schema_validation.validate_artifacts(repo, artifact_path=manifest)
    assert result.status in {"passed", "failed", "skipped"}


def main() -> int:
    test_json_root_helpers()
    test_artifact_rows_handle_mixed_json_shapes()
    test_ingest_handles_top_level_arrays_and_invalid_json()
    test_latest_runs_query_and_health_after_ingest()
    test_schema_validation_sees_duckdb_manifest()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
