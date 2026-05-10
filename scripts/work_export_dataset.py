#!/usr/bin/env python3
"""work_export_dataset.py — Generate dataset exports from ADR-local ledgers.

Exports are rebuildable analysis artifacts derived from task.json, progress.jsonl,
patch batch metadata, validation events, and out-of-scope findings.

Usage:
    python3 scripts/work_export_dataset.py <task_id> [--output-dir <path>] [--force]

Required export path:
  .rig/work/adr/<adr-id>/exports/

Generated files:
  - events.csv
  - events.parquet (if pyarrow/pandas/polars installed)
  - missions.csv
  - patch_batches.csv
  - validations.csv
  - findings.csv
  - dataset_card.md
  - schema.json

Rules:
- progress.jsonl remains canonical.
- CSV/Parquet exports are generated and must not be hand-edited.
- Large stdout/stderr must not be stored inline; store hashes and artifact paths.
- Do not store secrets.
- Do not store private chain-of-thought.
- Export should be deterministic for the same ledger state.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    adr_workspace,
    load_task,
    load_events,
    repo_root,
)

SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Parquet support detection
# ---------------------------------------------------------------------------

def has_parquet_support() -> bool:
    """Check if pyarrow, pandas, or polars is installed."""
    for module in ("pyarrow", "pandas", "polars"):
        try:
            __import__(module)
            return True
        except ImportError:
            continue
    return False


def write_parquet_file(path: Path, data: list[dict], columns: list[str]) -> bool:
    """Write data to parquet file if supported. Returns True if written."""
    if not has_parquet_support():
        return False
    try:
        import pyarrow as pa  # type: ignore[import-untyped]
        import pyarrow.parquet as pq  # type: ignore[import-untyped]
        table = pa.table({col: [row.get(col, "") for row in data] for col in columns})
        pq.write_table(table, path)
        return True
    except Exception:
        try:
            import pandas as pd  # type: ignore[import-untyped]
            pd.DataFrame(data, columns=columns).to_parquet(path)  # type: ignore[arg-type]
            return True
        except Exception:
            pass
    return False


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def export_dir(task_id: str, output_dir: str | None = None) -> Path:
    """Get or create the export directory for a task."""
    if output_dir:
        base = Path(output_dir)
    else:
        base = adr_workspace(task_id) / "exports"
    base.mkdir(parents=True, exist_ok=True)
    return base


def normalize_path(p: str | None) -> str:
    """Normalize a path for storage (relative, no secrets)."""
    if not p:
        return ""
    # Remove any potential secrets or sensitive paths
    return str(p).replace("\n", " ").replace("\r", " ")


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def hash_text(text: str) -> str:
    """Generate SHA256 hash of text content."""
    if not text or len(text) > 1000000:
        # For very large text, hash a prefix
        text = text[:100000] if text else ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

def extract_events_data(task: dict, events: list[dict]) -> list[dict]:
    """Extract normalized event data for CSV export."""
    rows = []
    for ev in events:
        row = {
            "event_id": ev.get("event_id", ""),
            "ts": ev.get("ts", ""),
            "worker": ev.get("worker", ""),
            "type": ev.get("type", ""),
            "task_id": ev.get("task_id", task.get("id", "")),
            "mission_id": ev.get("mission_id", ""),
            "sprint_id": ev.get("sprint_id", ""),
            "note": normalize_path(ev.get("note", "")),
            "status": ev.get("status", ""),
            "tests": ev.get("tests", ""),
            "completion_summary": normalize_path(ev.get("completion_summary", "")),
            "git_branch": ev.get("git_branch", ""),
            "git_head": ev.get("git_head", ""),
            "patch_batch_id": ev.get("patch_batch_id", ""),
            "precheck_passed": str(ev.get("precheck_passed", "")),
            "validation_passed": str(ev.get("validation_passed", "")),
            "out_of_scope_findings_count": str(len(ev.get("out_of_scope_findings", []))),
            "patch_batches_applied_count": str(len(ev.get("patch_batches_applied", []))),
        }
        rows.append(row)
    return rows


def extract_missions_data(task: dict) -> list[dict]:
    """Extract mission data from task."""
    rows = []
    
    # Handle both sprint-based and flat mission structures
    sprints = task.get("sprints", [])
    flat_missions = task.get("missions", [])
    
    # Process flat missions
    for m in flat_missions:
        rows.append({
            "mission_id": m.get("id", ""),
            "title": m.get("title", ""),
            "status": m.get("status", ""),
            "description": normalize_path(m.get("description", "")),
            "sprint_id": "",
            "allowed_paths": ";".join(m.get("allowed_paths", [])),
            "protected_paths": ";".join(m.get("protected_paths", [])),
            "priority": m.get("priority", ""),
        })
    
    # Process sprint missions
    for s in sprints:
        sprint_id = s.get("id", "")
        for m in s.get("missions", []):
            rows.append({
                "mission_id": m.get("id", ""),
                "title": m.get("title", ""),
                "status": m.get("status", ""),
                "description": normalize_path(m.get("description", "")),
                "sprint_id": sprint_id,
                "allowed_paths": ";".join(m.get("allowed_paths", [])),
                "protected_paths": ";".join(m.get("protected_paths", [])),
                "priority": m.get("priority", ""),
            })
    
    return rows


def extract_patch_batches_data(events: list[dict]) -> list[dict]:
    """Extract patch batch data from events."""
    rows = []
    batch_map: dict[str, dict] = {}
    
    for ev in events:
        batch_id = ev.get("patch_batch_id", "")
        if not batch_id:
            continue
        
        etype = ev.get("type", "")
        if etype not in [
            "patch_batch_planned", "patch_batch_prechecked", 
            "patch_batch_applied", "patch_batch_validated", 
            "patch_batch_blocked", "patch_batch_merge_friendly_checked"
        ]:
            continue
        
        if batch_id not in batch_map:
            batch_map[batch_id] = {
                "patch_batch_id": batch_id,
                "task_id": ev.get("task_id", ""),
                "mission_id": ev.get("mission_id", ""),
                "sprint_id": ev.get("sprint_id", ""),
                "worker": ev.get("worker", ""),
                "planned_at": "",
                "prechecked_at": "",
                "applied_at": "",
                "validated_at": "",
                "blocked_at": "",
                "merge_friendly_checked_at": "",
                "status": "",
                "planned_files": ";".join(ev.get("planned_files", [])),
                "actual_files": ";".join(ev.get("actual_files", [])),
                "precheck_passed": "",
                "precheck_failed_reason": normalize_path(ev.get("precheck_failed_reason", "")),
                "protected_paths_touched": ";".join(ev.get("protected_paths_touched", [])),
                "validation_results_summary": normalize_path(str(ev.get("validation_results", {}))),
                "merge_friendly_result": "",
                "merge_friendly_safe": "",
            }
        
        batch = batch_map[batch_id]
        ts = ev.get("ts", "")
        
        if etype == "patch_batch_planned":
            batch["planned_at"] = ts
            batch["status"] = "planned"
        elif etype == "patch_batch_prechecked":
            batch["prechecked_at"] = ts
            batch["precheck_passed"] = str(ev.get("precheck_passed", ""))
            if batch["status"] == "":
                batch["status"] = "prechecked"
        elif etype == "patch_batch_applied":
            batch["applied_at"] = ts
            batch["actual_files"] = ";".join(ev.get("actual_files", []))
            batch["status"] = "applied"
        elif etype == "patch_batch_validated":
            batch["validated_at"] = ts
            batch["validation_results_summary"] = normalize_path(str(ev.get("validation_results", {})))
            batch["status"] = "validated"
        elif etype == "patch_batch_blocked":
            batch["blocked_at"] = ts
            batch["precheck_failed_reason"] = normalize_path(ev.get("precheck_failed_reason", ""))
            batch["status"] = "blocked"
        elif etype == "patch_batch_merge_friendly_checked":
            batch["merge_friendly_checked_at"] = ts
            batch["merge_friendly_result"] = ev.get("result", "")
            batch["merge_friendly_safe"] = str(ev.get("safe_to_apply", ""))
    
    return list(batch_map.values())


def extract_validations_data(events: list[dict]) -> list[dict]:
    """Extract validation data from events."""
    rows = []
    for ev in events:
        if ev.get("type") != "patch_batch_validated":
            continue
        row = {
            "validation_id": ev.get("event_id", ""),
            "ts": ev.get("ts", ""),
            "task_id": ev.get("task_id", ""),
            "mission_id": ev.get("mission_id", ""),
            "sprint_id": ev.get("sprint_id", ""),
            "patch_batch_id": ev.get("patch_batch_id", ""),
            "worker": ev.get("worker", ""),
            "result": normalize_path(str(ev.get("validation_results", {}))),
            "passed": str(ev.get("validation_passed", True)),
        }
        rows.append(row)
    return rows


def extract_findings_data(events: list[dict], task: dict) -> list[dict]:
    """Extract out-of-scope findings from events."""
    rows = []
    for ev in events:
        findings = ev.get("out_of_scope_findings", [])
        for f in findings:
            row = {
                "finding_id": ev.get("event_id", "") + ":" + hash_text(f),
                "ts": ev.get("ts", ""),
                "worker": ev.get("worker", ""),
                "task_id": ev.get("task_id", task.get("id", "")),
                "mission_id": ev.get("mission_id", ""),
                "sprint_id": ev.get("sprint_id", ""),
                "finding": normalize_path(f),
                "source_event_type": ev.get("type", ""),
                "status": "observed",
            }
            rows.append(row)
        
        # Also check note field for findings
        if ev.get("type") == "out_of_scope_finding":
            row = {
                "finding_id": ev.get("event_id", ""),
                "ts": ev.get("ts", ""),
                "worker": ev.get("worker", ""),
                "task_id": ev.get("task_id", task.get("id", "")),
                "mission_id": ev.get("mission_id", ""),
                "sprint_id": ev.get("sprint_id", ""),
                "finding": normalize_path(ev.get("note", "")),
                "source_event_type": ev.get("type", ""),
                "status": "observed",
            }
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# CSV writing
# ---------------------------------------------------------------------------

def write_csv(path: Path, data: list[dict], columns: list[str] | None = None) -> None:
    """Write data to CSV file."""
    if not data:
        # Write empty CSV with headers
        if columns:
            with path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
        return
    
    if columns is None:
        columns = list(data[0].keys())
    
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------

def generate_schema() -> dict:
    """Generate the schema description for the dataset."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": "Rig ADR work ledger dataset exports. Derived from task.json and progress.jsonl.",
        "tables": {
            "events": {
                "description": "All work events from progress.jsonl",
                "columns": [
                    {"name": "event_id", "type": "string", "description": "Unique event identifier"},
                    {"name": "ts", "type": "datetime", "description": "ISO 8601 UTC timestamp"},
                    {"name": "worker", "type": "string", "description": "Agent or user name"},
                    {"name": "type", "type": "string", "description": "Event type"},
                    {"name": "task_id", "type": "string", "description": "ADR task ID"},
                    {"name": "mission_id", "type": "string", "description": "Mission ID if applicable"},
                    {"name": "sprint_id", "type": "string", "description": "Sprint ID if applicable"},
                    {"name": "note", "type": "string", "description": "Event annotation"},
                    {"name": "status", "type": "string", "description": "Status field"},
                    {"name": "tests", "type": "string", "description": "Test summary"},
                    {"name": "completion_summary", "type": "string", "description": "Completion summary"},
                    {"name": "git_branch", "type": "string", "description": "Git branch at event time"},
                    {"name": "git_head", "type": "string", "description": "Git HEAD commit at event time"},
                ],
            },
            "missions": {
                "description": "Mission definitions from task.json",
                "columns": [
                    {"name": "mission_id", "type": "string", "description": "Unique mission identifier"},
                    {"name": "title", "type": "string", "description": "Mission title"},
                    {"name": "status", "type": "string", "description": "Mission status"},
                    {"name": "description", "type": "string", "description": "Mission description"},
                    {"name": "sprint_id", "type": "string", "description": "Containing sprint ID"},
                    {"name": "allowed_paths", "type": "string", "description": "Semicolon-separated allowed paths"},
                    {"name": "protected_paths", "type": "string", "description": "Semicolon-separated protected paths"},
                    {"name": "priority", "type": "string", "description": "Mission priority"},
                ],
            },
            "patch_batches": {
                "description": "Patch batch tracking from events",
                "columns": [
                    {"name": "patch_batch_id", "type": "string", "description": "Unique batch identifier"},
                    {"name": "task_id", "type": "string", "description": "ADR task ID"},
                    {"name": "mission_id", "type": "string", "description": "Mission ID"},
                    {"name": "sprint_id", "type": "string", "description": "Sprint ID"},
                    {"name": "worker", "type": "string", "description": "Worker who created/managed batch"},
                    {"name": "status", "type": "string", "description": "Current batch status"},
                    {"name": "planned_at", "type": "datetime", "description": "When batch was planned"},
                    {"name": "prechecked_at", "type": "datetime", "description": "When precheck passed"},
                    {"name": "applied_at", "type": "datetime", "description": "When batch was applied"},
                    {"name": "validated_at", "type": "datetime", "description": "When batch was validated"},
                ],
            },
            "validations": {
                "description": "Validation results",
                "columns": [
                    {"name": "validation_id", "type": "string", "description": "Validation event ID"},
                    {"name": "ts", "type": "datetime", "description": "Validation timestamp"},
                    {"name": "patch_batch_id", "type": "string", "description": "Validated patch batch ID"},
                    {"name": "result", "type": "string", "description": "Validation result summary"},
                    {"name": "passed", "type": "string", "description": "Whether validation passed"},
                ],
            },
            "findings": {
                "description": "Out-of-scope findings",
                "columns": [
                    {"name": "finding_id", "type": "string", "description": "Unique finding identifier"},
                    {"name": "ts", "type": "datetime", "description": "Finding timestamp"},
                    {"name": "worker", "type": "string", "description": "Worker who recorded finding"},
                    {"name": "task_id", "type": "string", "description": "ADR task ID"},
                    {"name": "mission_id", "type": "string", "description": "Mission ID if applicable"},
                    {"name": "sprint_id", "type": "string", "description": "Sprint ID if applicable"},
                    {"name": "finding", "type": "string", "description": "Finding text"},
                    {"name": "source_event_type", "type": "string", "description": "Event type that recorded finding"},
                    {"name": "status", "type": "string", "description": "Finding status"},
                ],
            },
        },
        "privacy_notes": [
            "No secrets are stored in exports.",
            "Large stdout/stderr are hashed, not stored inline.",
            "Private chain-of-thought is not stored.",
            "Exports are rebuildable from canonical progress.jsonl.",
        ],
        "intended_use": [
            "Analysis and auditing of ADR implementation progress.",
            "Review and promotion decision support.",
            "Historical tracking of work patterns.",
        ],
        "limitations": [
            "Exports are derived artifacts, not canonical authority.",
            "progress.jsonl remains the source of truth.",
            "Exports should be regenerated after ledger changes.",
        ],
    }


# ---------------------------------------------------------------------------
# Dataset card generation
# ---------------------------------------------------------------------------

def generate_dataset_card(task: dict, export_dir: Path, parquet_written: bool) -> None:
    """Generate dataset_card.md for the exports."""
    card_path = export_dir / "dataset_card.md"
    
    lines = [
        "# Dataset Card: Rig ADR Work Ledger Exports",
        "",
        f"- **Task ID**: {task.get('id', 'unknown')}",
        f"- **ADR**: {task.get('adr', 'unknown')}",
        f"- **Export Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- **Schema Version**: {SCHEMA_VERSION}",
        "",
        "## Source",
        "- **Canonical Source**: `progress.jsonl` and `task.json` in ADR workspace",
        "- **Derived From**: Work events, missions, patch batches, validations, findings",
        "- **Rebuild Command**: `python3 scripts/work_export_dataset.py <task_id>`",
        "",
        "## Generated Files",
        "- `events.csv` - All work events",
        "- `missions.csv` - Mission definitions",
        "- `patch_batches.csv` - Patch batch tracking",
        "- `validations.csv` - Validation results",
        "- `findings.csv` - Out-of-scope findings",
        "- `schema.json` - Table schemas and metadata",
        f"- `events.parquet` - Parquet format (written: {'yes' if parquet_written else 'no, dependency not installed'})",
        "",
        "## Privacy Notes",
        "- No secrets are stored in exports.",
        "- Large stdout/stderr are hashed, not stored inline.",
        "- Private chain-of-thought is not stored.",
        "- Exports are rebuildable from canonical progress.jsonl.",
        "",
        "## Intended Use",
        "- Analysis and auditing of ADR implementation progress",
        "- Review and promotion decision support",
        "- Historical tracking of work patterns",
        "",
        "## Limitations",
        "- Exports are derived artifacts, not canonical authority.",
        "- progress.jsonl remains the source of truth.",
        "- Exports should be regenerated after ledger changes.",
        "- Exports are deterministic for the same ledger state.",
        "",
    ]
    
    card_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="work_export_dataset.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("task_id", metavar="TASK_ID", help="ADR task ID")
    p.add_argument("--output-dir", metavar="PATH", help="Output directory (default: .rig/work/adr/<task_id>/exports/)")
    p.add_argument("--force", action="store_true", help="Overwrite existing exports")
    args = p.parse_args(argv or sys.argv[1:])
    
    try:
        task = load_task(args.task_id)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    
    events = load_events(args.task_id)
    export_dir_path = export_dir(args.task_id, args.output_dir)
    
    # Check if exports already exist and force is not set
    if not args.force and (export_dir_path / "events.csv").exists():
        print(f"ERROR: Exports already exist in {export_dir_path}. Use --force to overwrite.")
        return 1
    
    # Extract data
    print(f"Exporting dataset for task={args.task_id}...")
    
    events_data = extract_events_data(task, events)
    missions_data = extract_missions_data(task)
    patch_batches_data = extract_patch_batches_data(events)
    validations_data = extract_validations_data(events)
    findings_data = extract_findings_data(events, task)
    
    # Define columns for each table
    events_columns = [
        "event_id", "ts", "worker", "type", "task_id", "mission_id", "sprint_id",
        "note", "status", "tests", "completion_summary", "git_branch", "git_head",
        "patch_batch_id", "precheck_passed", "validation_passed",
        "out_of_scope_findings_count", "patch_batches_applied_count",
    ]
    missions_columns = [
        "mission_id", "title", "status", "description", "sprint_id",
        "allowed_paths", "protected_paths", "priority",
    ]
    patch_batches_columns = [
        "patch_batch_id", "task_id", "mission_id", "sprint_id", "worker",
        "status", "planned_at", "prechecked_at", "applied_at", "validated_at",
        "blocked_at", "merge_friendly_checked_at", "planned_files", "actual_files",
        "precheck_passed", "precheck_failed_reason", "protected_paths_touched",
        "validation_results_summary", "merge_friendly_result", "merge_friendly_safe",
    ]
    validations_columns = [
        "validation_id", "ts", "task_id", "mission_id", "sprint_id",
        "patch_batch_id", "worker", "result", "passed",
    ]
    findings_columns = [
        "finding_id", "ts", "worker", "task_id", "mission_id", "sprint_id",
        "finding", "source_event_type", "status",
    ]
    
    # Write CSV files
    write_csv(export_dir_path / "events.csv", events_data, events_columns)
    write_csv(export_dir_path / "missions.csv", missions_data, missions_columns)
    write_csv(export_dir_path / "patch_batches.csv", patch_batches_data, patch_batches_columns)
    write_csv(export_dir_path / "validations.csv", validations_data, validations_columns)
    write_csv(export_dir_path / "findings.csv", findings_data, findings_columns)
    
    # Write Parquet files if supported
    parquet_written = False
    if has_parquet_support():
        write_parquet_file(export_dir_path / "events.parquet", events_data, events_columns)
        parquet_written = True
    
    # Write schema
    schema = generate_schema()
    with (export_dir_path / "schema.json").open("w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    
    # Write dataset card
    generate_dataset_card(task, export_dir_path, parquet_written)
    
    print(f"Dataset exports written to: {export_dir_path}")
    print(f"  - events.csv: {len(events_data)} rows")
    print(f"  - missions.csv: {len(missions_data)} rows")
    print(f"  - patch_batches.csv: {len(patch_batches_data)} rows")
    print(f"  - validations.csv: {len(validations_data)} rows")
    print(f"  - findings.csv: {len(findings_data)} rows")
    print(f"  - schema.json: written")
    print(f"  - dataset_card.md: written")
    print(f"  - events.parquet: {'written' if parquet_written else 'skipped (dependency not installed)'}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
