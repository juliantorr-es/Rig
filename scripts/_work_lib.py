"""_work_lib.py — Shared helpers for Rig ADR work-status scripts.

Not intended as a public API. Import only from sibling work_*.py scripts.
"""
from __future__ import annotations

import fnmatch
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADR_WORK_ROOT = Path(".rig/work/adr")
HEARTBEAT_WARN_SECONDS = 30 * 60    # 30 minutes
HEARTBEAT_STALE_SECONDS = 4 * 3600  # 4 hours


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(ts: str) -> datetime:
    """Parse an ISO 8601 UTC timestamp (with or without fractional seconds)."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S+00:00"):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Fallback: strip trailing Z and parse
    return datetime.fromisoformat(ts.rstrip("Z")).replace(tzinfo=timezone.utc)


def seconds_since(ts: str) -> float:
    try:
        then = parse_iso(ts)
        delta = datetime.now(timezone.utc) - then
        return delta.total_seconds()
    except Exception:
        return float("inf")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def repo_root() -> Path:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True, capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError("Not in a git repository")
    return Path(r.stdout.strip()).resolve()


def adr_workspace(task_id: str) -> Path:
    return repo_root() / ".rig" / "work" / "adr" / task_id


def task_json_path(task_id: str) -> Path:
    return adr_workspace(task_id) / "task.json"


def progress_jsonl_path(task_id: str) -> Path:
    return adr_workspace(task_id) / "progress.jsonl"


def projection_json_path(task_id: str) -> Path:
    return adr_workspace(task_id) / "projection.json"


def findings_md_path(task_id: str) -> Path:
    return adr_workspace(task_id) / "notes" / "out-of-scope-findings.md"


# ---------------------------------------------------------------------------
# Task loading
# ---------------------------------------------------------------------------

def load_task(task_id: str) -> dict[str, Any]:
    path = task_json_path(task_id)
    if not path.exists():
        raise FileNotFoundError(
            f"Task not found: {path}\n"
            f"Hint: Is '{task_id}' a valid ADR task ID?"
        )
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_mission(task: dict, mission_id: str) -> dict[str, Any]:
    for m in task.get("missions", []):
        if m["id"] == mission_id:
            return m
    raise ValueError(
        f"Mission '{mission_id}' not found in task '{task['id']}'.\n"
        f"Known missions: {[m['id'] for m in task.get('missions', [])]}"
    )


# ---------------------------------------------------------------------------
# Progress ledger
# ---------------------------------------------------------------------------

def load_events(task_id: str) -> list[dict[str, Any]]:
    path = progress_jsonl_path(task_id)
    if not path.exists():
        return []
    events: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON on line {lineno} of {path}: {exc}")
    return events


def append_event(task_id: str, event: dict[str, Any]) -> None:
    path = progress_jsonl_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def make_event(
    event_type: str,
    task_id: str,
    worker: str,
    *,
    mission_id: str | None = None,
    note: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    r = subprocess.run(["git", "branch", "--show-current"], text=True, capture_output=True)
    git_branch = r.stdout.strip() if r.returncode == 0 else ""
    r2 = subprocess.run(["git", "rev-parse", "--short", "HEAD"], text=True, capture_output=True)
    git_head = r2.stdout.strip() if r2.returncode == 0 else ""

    ev: dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "ts": now_iso(),
        "worker": worker,
        "type": event_type,
        "task_id": task_id,
        "git_branch": git_branch,
        "git_head": git_head,
    }
    if mission_id is not None:
        ev["mission_id"] = mission_id
    if note is not None:
        ev["note"] = note
    ev.update(extra)
    return ev


# ---------------------------------------------------------------------------
# Path validation helpers
# ---------------------------------------------------------------------------

def path_matches_any(path: str, patterns: list[str]) -> bool:
    """Return True if path matches any glob pattern in the list."""
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        # Also match if path starts with the pattern prefix (for ** globs)
        if pat.endswith("/**"):
            prefix = pat[:-3]
            if path.startswith(prefix + "/") or path == prefix:
                return True
        if pat.endswith("/*"):
            prefix = pat[:-2]
            rest = path[len(prefix) + 1:] if path.startswith(prefix + "/") else ""
            if rest and "/" not in rest:
                return True
    return False


def validate_paths_allowed(paths: list[str], allowed: list[str], protected: list[str]) -> list[str]:
    """Return list of violation messages (empty = all clear)."""
    errors: list[str] = []
    for p in paths:
        if path_matches_any(p, protected):
            errors.append(f"Path is protected: {p}")
        elif not path_matches_any(p, allowed):
            errors.append(f"Path not in allowed_paths: {p}")
    return errors


# ---------------------------------------------------------------------------
# Projection computation
# ---------------------------------------------------------------------------

def compute_projection(task_id: str) -> dict[str, Any]:
    task = load_task(task_id)
    events = load_events(task_id)

    # Active claims: claim_started without a subsequent claim_released or handoff
    active_claims_map: dict[str, dict] = {}  # key: worker+mission_id
    out_of_scope_findings: list[dict] = []
    last_heartbeat_by_worker: dict[str, str] = {}
    conflicts: list[str] = []

    for ev in events:
        etype = ev.get("type", "")
        worker = ev.get("worker", "")
        mission_id = ev.get("mission_id")
        claim_key = f"{worker}:{mission_id or '_task_'}"

        if etype == "claim_started":
            active_claims_map[claim_key] = {
                "mission_id": mission_id,
                "worker": worker,
                "claimed_at": ev.get("ts", ""),
                "paths": ev.get("paths", []),
            }
        elif etype in ("claim_released", "handoff"):
            active_claims_map.pop(claim_key, None)
        elif etype == "heartbeat":
            last_heartbeat_by_worker[worker] = ev.get("ts", "")
        elif etype == "out_of_scope_finding":
            out_of_scope_findings.append({
                "ts": ev.get("ts", ""),
                "worker": worker,
                "task_id": task_id,
                "mission_id": mission_id,
                "finding": ev.get("note", ""),
                "source_event_id": ev.get("event_id", ""),
                "status": "observed",
            })
        elif etype == "handoff":
            for f in ev.get("out_of_scope_findings", []):
                out_of_scope_findings.append({
                    "ts": ev.get("ts", ""),
                    "worker": worker,
                    "task_id": task_id,
                    "mission_id": mission_id,
                    "finding": f,
                    "source_event_id": ev.get("event_id", ""),
                    "status": "observed",
                })

    # Also extract out_of_scope_findings from handoff events
    for ev in events:
        if ev.get("type") == "handoff":
            for f in ev.get("out_of_scope_findings", []):
                entry = {
                    "ts": ev.get("ts", ""),
                    "worker": ev.get("worker", ""),
                    "task_id": task_id,
                    "mission_id": ev.get("mission_id"),
                    "finding": f,
                    "source_event_id": ev.get("event_id", ""),
                    "status": "observed",
                }
                if entry not in out_of_scope_findings:
                    out_of_scope_findings.append(entry)

    active_claims = list(active_claims_map.values())

    # Stale claims
    stale_claims = []
    for claim in active_claims:
        worker = claim["worker"]
        last_hb = last_heartbeat_by_worker.get(worker)
        if last_hb is None:
            age = seconds_since(claim["claimed_at"])
        else:
            age = seconds_since(last_hb)
        if age > HEARTBEAT_STALE_SECONDS:
            stale_claims.append({**claim, "stale_reason": f"No heartbeat for {int(age/3600)}h"})

    # Mission status summary
    mission_statuses = []
    for m in task.get("missions", []):
        mid = m["id"]
        active = next((c for c in active_claims if c.get("mission_id") == mid), None)
        last_hb = None
        if active:
            last_hb = last_heartbeat_by_worker.get(active["worker"])
        mission_statuses.append({
            "id": mid,
            "title": m["title"],
            "status": m["status"],
            "active_claim": active["worker"] if active else None,
            "last_heartbeat": last_hb,
        })

    # Conflict detection: same mission claimed by multiple workers
    mission_claim_counts: dict[str, list[str]] = {}
    for claim in active_claims:
        mid = claim.get("mission_id") or "_task_"
        mission_claim_counts.setdefault(mid, []).append(claim["worker"])
    for mid, workers in mission_claim_counts.items():
        if len(workers) > 1:
            conflicts.append(f"Mission '{mid}' claimed by multiple workers: {', '.join(workers)}")

    # Next safe action
    if conflicts:
        next_action = "Resolve conflicting claims before proceeding."
    elif stale_claims:
        next_action = "Stale claims detected. Run work_handoff.py or work_claim.py --release to clear."
    elif active_claims:
        next_action = "Work in progress. Heartbeat regularly. Run work_handoff.py when complete."
    elif all(m["status"] in ("closed", "ready_for_review") for m in task.get("missions", [])):
        next_action = "All missions complete. Run work_doctor.py then promote."
    else:
        next_action = "Claim an open mission with work_claim.py to begin work."

    return {
        "generated_at": now_iso(),
        "task_id": task_id,
        "adr": task.get("adr", ""),
        "task_status": task.get("status", ""),
        "missions": mission_statuses,
        "active_claims": active_claims,
        "stale_claims": stale_claims,
        "conflicts": conflicts,
        "last_heartbeat_by_worker": last_heartbeat_by_worker,
        "latest_events": events[-10:],
        "out_of_scope_findings_count": len(out_of_scope_findings),
        "next_safe_action": next_action,
        "_out_of_scope_findings": out_of_scope_findings,  # internal, used for notes generation
    }


# ---------------------------------------------------------------------------
# Out-of-scope findings notes generation
# ---------------------------------------------------------------------------

def regenerate_findings_md(task_id: str, projection: dict[str, Any]) -> None:
    findings = projection.get("_out_of_scope_findings", [])
    path = findings_md_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Out-of-Scope Findings — {task_id}",
        "",
        "Generated by `work_status.py`. Do not hand-edit.",
        f"Last updated: {projection['generated_at']}",
        "",
    ]
    if not findings:
        lines += ["_No out-of-scope findings recorded yet._", ""]
    else:
        for f in findings:
            lines += [
                f"## [{f['ts']}] {f['worker']}",
                "",
                f"- **task_id**: {f['task_id']}",
            ]
            if f.get("mission_id"):
                lines.append(f"- **mission_id**: {f['mission_id']}")
            lines += [
                f"- **finding**: {f['finding']}",
                f"- **source_event_id**: {f['source_event_id']}",
                f"- **status**: {f['status']}",
                "",
            ]
    path.write_text("\n".join(lines), encoding="utf-8")
