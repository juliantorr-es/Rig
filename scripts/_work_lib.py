"""_work_lib.py — Shared helpers for Rig ADR work-status scripts.

Not intended as a public API. Import only from sibling work_*.py scripts.
"""
from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
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

# Reserved worktree names that must not be used for ADR implementation
RESERVED_WORKTREE_NAMES = {"preproduction", "main"}

# Canonical worktree base directory
WORKTREES_ROOT = Path(".rig/worktrees")


# ---------------------------------------------------------------------------
# Worktree naming helpers
# ---------------------------------------------------------------------------

def canonical_slug(text: str) -> str:
    """Derive canonical slug from text for use in worktree and branch names.
    
    Rules:
    - Lowercase
    - Trim leading/trailing whitespace
    - Replace non-alphanumeric runs with single hyphen
    - Remove leading/trailing hyphens
    - Preserve adrNNNN prefix format (e.g., adr0009)
    - Deterministic: same input always produces same output
    
    Examples:
    - "Agentic Workflow Refinement" -> "agentic-workflow-refinement"
    - "ADR 0009: Agentic Workflow Refinement" -> "adr-0009-agentic-workflow-refinement"
    - "adr0009-agentic-workflow-refinement" -> "adr0009-agentic-workflow-refinement"
    - "Workspace Domain Authority" -> "workspace-domain-authority"
    - "Receipt/Evidence Unification" -> "receipt-evidence-unification"
    """
    if not text:
        return ""
    # Step 1: Lowercase
    text = text.lower()
    # Step 2: Trim
    text = text.strip()
    # Step 3: Replace non-alphanumeric runs with hyphen
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Step 4: Remove leading/trailing hyphens
    text = text.strip('-')
    return text


def extract_adr_id_from_path(adr_path: str | Path) -> str:
    """Extract ADR ID from an ADR file path.
    
    Examples:
    - "docs/adr/0009-agentic-workflow-refinement.md" -> "adr0009"
    - "docs/adr/0007-workspace-domain-authority.md" -> "adr0007"
    - "adr/0008-something.md" -> "adr0008"
    - "0009-foo.md" -> "adr0009"
    """
    adr_path = str(adr_path)
    # Extract filename and remove extension
    filename = Path(adr_path).name
    if filename.endswith('.md'):
        filename = filename[:-3]
    # Extract leading number
    match = re.match(r'^(\d{4})', filename)
    if match:
        return f"adr{match.group(1)}"
    return ""


def extract_adr_title_from_path(adr_path: str | Path) -> str:
    """Extract ADR title from an ADR file path.
    
    Examples:
    - "docs/adr/0009-agentic-workflow-refinement.md" -> "agentic-workflow-refinement"
    - "docs/adr/0007-workspace-domain-authority.md" -> "workspace-domain-authority"
    """
    adr_path = str(adr_path)
    filename = Path(adr_path).name
    if filename.endswith('.md'):
        filename = filename[:-3]
    # Remove leading ADR number and separator
    # Pattern: NNNN-title-slug or adrNNNN-title-slug
    match = re.match(r'^(?:adr)?(\d{4})[-_](.*)', filename)
    if match:
        return match.group(2)
    # If no ADR number, just strip any leading number
    match = re.match(r'^(\d{4})[-_](.*)', filename)
    if match:
        return match.group(2)
    return filename


def derive_adr_directory_slug(adr_path: str | Path | None = None, 
                              adr_id: str | None = None,
                              adr_title: str | None = None) -> str:
    """Derive ADR directory slug from ADR path, ID, or title.
    
    Priority: adr_path > (adr_id + adr_title) > raise error
    
    The slug format is: <adr_id>-<title_slug>
    
    Examples:
    - adr_path="docs/adr/0009-agentic-workflow-refinement.md" -> "adr0009-agentic-workflow-refinement"
    - adr_id="adr0009", adr_title="Agentic Workflow Refinement" -> "adr0009-agentic-workflow-refinement"
    - adr_id="adr0009", adr_title=" ADR 0009: Agentic Workflow Refinement " -> "adr0009-agentic-workflow-refinement"
    """
    if adr_path:
        path_adr_id = extract_adr_id_from_path(adr_path)
        path_title = extract_adr_title_from_path(adr_path)
        if path_adr_id and path_title:
            return f"{path_adr_id}-{path_title}"
        elif path_adr_id:
            return path_adr_id
    
    if adr_id and adr_title:
        title_slug = canonical_slug(adr_title)
        return f"{adr_id}-{title_slug}"
    
    if adr_path:
        # Fallback: use filename as-is
        filename = Path(str(adr_path)).name
        if filename.endswith('.md'):
            filename = filename[:-3]
        return filename
    
    raise ValueError("Cannot derive ADR directory slug: need adr_path or both adr_id and adr_title")


# Derived name getters for worktrees and branches

def get_adr_worktree_path(adr_path: str | Path | None = None,
                          adr_id: str | None = None,
                          adr_title: str | None = None) -> Path:
    """Get the canonical ADR implementation worktree path.
    
    Returns: .rig/worktrees/<adr-id>-<adr-title-slug>/
    
    Examples:
    - adr_id="adr0009", adr_title="Agentic Workflow Refinement" 
      -> Path(".rig/worktrees/adr0009-agentic-workflow-refinement")
    """
    slug = derive_adr_directory_slug(adr_path=adr_path, adr_id=adr_id, adr_title=adr_title)
    return WORKTREES_ROOT / slug


def get_mission_worktree_path(adr_path: str | Path | None = None,
                               adr_id: str | None = None,
                               adr_title: str | None = None,
                               mission_slug: str | None = None) -> Path:
    """Get the canonical mission-specific worktree path.
    
    Returns: .rig/worktrees/<adr-id>-<adr-title-slug>--<mission-slug>/
    
    Examples:
    - adr_id="adr0009", adr_title="Agentic Workflow Refinement", mission_slug="worktree-naming"
      -> Path(".rig/worktrees/adr0009-agentic-workflow-refinement--worktree-naming")
    """
    if not mission_slug:
        raise ValueError("mission_slug is required for mission worktree path")
    base_slug = derive_adr_directory_slug(adr_path=adr_path, adr_id=adr_id, adr_title=adr_title)
    mission_slug_clean = canonical_slug(mission_slug)
    return WORKTREES_ROOT / f"{base_slug}--{mission_slug_clean}"


def get_sprint_branch_name(adr_path: str | Path | None = None,
                           adr_id: str | None = None,
                           adr_title: str | None = None) -> str:
    """Get the canonical sprint branch name.
    
    Returns: sprint/<adr-id>-<adr-title-slug>
    
    Examples:
    - adr_id="adr0009", adr_title="Agentic Workflow Refinement"
      -> "sprint/adr0009-agentic-workflow-refinement"
    """
    slug = derive_adr_directory_slug(adr_path=adr_path, adr_id=adr_id, adr_title=adr_title)
    return f"sprint/{slug}"


def get_mission_branch_name(adr_id: str, mission_slug: str) -> str:
    """Get the canonical mission (agent) branch name.
    
    Returns: agent/<adr-id>-<mission-slug>
    
    Examples:
    - adr_id="adr0009", mission_slug="worktree-naming"
      -> "agent/adr0009-worktree-naming"
    """
    adr_id_clean = canonical_slug(adr_id) if not adr_id.startswith('adr') else adr_id.lower()
    mission_slug_clean = canonical_slug(mission_slug)
    return f"agent/{adr_id_clean}-{mission_slug_clean}"


def get_promotion_branch_name(adr_path: str | Path | None = None,
                              adr_id: str | None = None,
                              adr_title: str | None = None) -> str:
    """Get the canonical promotion branch name.
    
    Returns: promotion/<adr-id>-<adr-title-slug>
    
    Examples:
    - adr_id="adr0009", adr_title="Agentic Workflow Refinement"
      -> "promotion/adr0009-agentic-workflow-refinement"
    """
    slug = derive_adr_directory_slug(adr_path=adr_path, adr_id=adr_id, adr_title=adr_title)
    return f"promotion/{slug}"


def is_reserved_worktree_name(name: str) -> bool:
    """Check if a worktree name is reserved."""
    return canonical_slug(name) in RESERVED_WORKTREE_NAMES


def validate_worktree_name(name: str) -> tuple[bool, str]:
    """Validate a worktree name against canonical naming policy.
    
    Returns: (is_valid, reason_or_empty)
    """
    slug = canonical_slug(name)
    if not slug:
        return False, "Name produces empty slug"
    if is_reserved_worktree_name(name):
        return False, f"'{name}' is a reserved worktree name"
    if '..' in name or name.startswith('.') or name.startswith('/'):
        return False, f"'{name}' contains invalid path characters"
    return True, ""


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def branch_exists_locally(branch: str) -> bool:
    """Check if a branch exists locally."""
    import subprocess
    r = subprocess.run(
        ["git", "branch", "--list", branch],
        text=True, capture_output=True,
    )
    return r.returncode == 0 and branch in r.stdout


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


def sprint_workspace(task_id: str, sprint_id: str) -> Path:
    """Return the workspace path for a sprint's research artifacts."""
    return adr_workspace(task_id) / "sprints" / sprint_id


def get_sprint(task: dict, sprint_id: str) -> dict[str, Any]:
    """Get sprint by ID from task."""
    for s in task.get("sprints", []):
        if s.get("id") == sprint_id:
            return s
    raise ValueError(
        f"Sprint '{sprint_id}' not found in task '{task['id']}'.\n"
        f"Known sprints: {[s.get('id') for s in task.get('sprints', [])]}"
    )


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
    sprint_id: str | None = None,
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
    if sprint_id is not None:
        ev["sprint_id"] = sprint_id
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
    
    # Track patch batch status
    patch_batch_events: list[dict] = []
    sprint_research_status: dict[str, str] = {}  # sprint_id -> status
    
    # Track promotion events
    promotion_events: list[dict] = []
    last_promotion_attempt: dict | None = None
    last_promotion_success: bool = False
    
    # Track handoff forge evidence for current mission/sprint
    latest_handoff_forge_evidence: dict | None = None
    handoff_forge_gates_checked: bool = False
    
    for ev in events:
        etype = ev.get("type", "")
        worker = ev.get("worker", "")
        mission_id = ev.get("mission_id")
        sprint_id = ev.get("sprint_id")
        claim_key = f"{worker}:{mission_id or '_task_'}"

        # Track sprint research status
        if etype == "sprint_research_started":
            sprint_research_status[sprint_id or ""] = "in_progress"
        elif etype == "sprint_research_completed":
            sprint_research_status[sprint_id or ""] = "completed"
        elif etype == "sprint_research_blocked":
            sprint_research_status[sprint_id or ""] = "blocked"
        
        # Track patch batch events
        if etype in [
            "patch_batch_planned",
            "patch_batch_prechecked", 
            "patch_batch_applied",
            "patch_batch_validated",
            "patch_batch_blocked",
            "patch_batch_merge_friendly_checked",
        ]:
            patch_batch_events.append(ev)
        
        # Track promotion events
        if etype in [
            "preproduction_promotion_completed",
            "preproduction_promotion_blocked",
            "preproduction_merge_completed",
            "preproduction_validation_passed",
            "preproduction_validation_failed",
        ]:
            promotion_events.append(ev)
            # Track last attempt
            if etype in ["preproduction_promotion_completed", "preproduction_promotion_blocked"]:
                last_promotion_attempt = ev
                last_promotion_success = etype == "preproduction_promotion_completed"

        if etype == "claim_started":
            active_claims_map[claim_key] = {
                "mission_id": mission_id,
                "sprint_id": sprint_id,
                "worker": worker,
                "claimed_at": ev.get("ts", ""),
                "paths": ev.get("paths", []),
            }
        elif etype in ("claim_released", "handoff"):
            active_claims_map.pop(claim_key, None)
            # Track forge evidence from handoff events
            if etype == "handoff":
                if ev.get("forge_evidence"):
                    latest_handoff_forge_evidence = ev.get("forge_evidence")
                handoff_forge_gates_checked = ev.get("forge_gates_checked", handoff_forge_gates_checked)
        elif etype == "heartbeat":
            last_heartbeat_by_worker[worker] = ev.get("ts", "")
        elif etype == "out_of_scope_finding":
            out_of_scope_findings.append({
                "ts": ev.get("ts", ""),
                "worker": worker,
                "task_id": task_id,
                "mission_id": mission_id,
                "sprint_id": sprint_id,
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
                    "sprint_id": sprint_id,
                    "finding": f,
                    "source_event_id": ev.get("event_id", ""),
                    "status": "observed",
                })

    # Also extract out_of_scope_findings from handoff events (legacy compatibility)
    for ev in events:
        if ev.get("type") == "handoff":
            for f in ev.get("out_of_scope_findings", []):
                entry = {
                    "ts": ev.get("ts", ""),
                    "worker": ev.get("worker", ""),
                    "task_id": task_id,
                    "mission_id": ev.get("mission_id"),
                    "sprint_id": ev.get("sprint_id"),
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

    # Build sprint structure for new schema
    # Check if task has sprints (new structure) or flat missions (legacy)
    sprints = task.get("sprints", [])
    
    if sprints:
        # New sprint-based structure
        sprint_statuses = []
        mission_statuses = []
        
        for s in sprints:
            s_research = sprint_research_status.get(s.get("id", ""), "not_started")
            s_missions = []
            
            # Get missions from sprint (inline or referenced)
            for m in s.get("missions", []):
                mid = m["id"]
                active = next((c for c in active_claims if c.get("mission_id") == mid), None)
                last_hb = None
                if active:
                    last_hb = last_heartbeat_by_worker.get(active["worker"])
                
                # Get patch batches for this mission
                mission_patch_batches = []
                for pb_ev in patch_batch_events:
                    if pb_ev.get("mission_id") == mid:
                        pb_entry = {
                            "id": pb_ev.get("patch_batch_id", ""),
                            "status": pb_ev.get("type", "").replace("patch_batch_", ""),
                            "precheck_passed": pb_ev.get("precheck_passed"),
                            "applied_at": pb_ev.get("ts"),
                            "planned_files_count": len(pb_ev.get("planned_files", [])),
                            "actual_files_count": len(pb_ev.get("actual_files", [])),
                        }
                        # Add merge-friendliness info
                        if pb_ev.get("type") == "patch_batch_merge_friendly_checked":
                            pb_entry["merge_friendly_checked"] = True
                            pb_entry["merge_friendly_safe"] = pb_ev.get("safe_to_apply", False)
                            pb_entry["merge_friendly_result"] = pb_ev.get("result", "unknown")
                        else:
                            # Check if there's a merge check for this batch
                            for mf_ev in patch_batch_events:
                                if mf_ev.get("type") == "patch_batch_merge_friendly_checked" and mf_ev.get("patch_batch_id") == pb_ev.get("patch_batch_id"):
                                    pb_entry["merge_friendly_checked"] = True
                                    pb_entry["merge_friendly_safe"] = mf_ev.get("safe_to_apply", False)
                                    pb_entry["merge_friendly_result"] = mf_ev.get("result", "unknown")
                                    break
                        mission_patch_batches.append(pb_entry)
                
                s_missions.append({
                    "id": mid,
                    "title": m["title"],
                    "status": m["status"],
                    "active_claim": active["worker"] if active else None,
                    "last_heartbeat": last_hb,
                    "patch_batches": mission_patch_batches,
                })
                mission_statuses.append({
                    "id": mid,
                    "title": m["title"],
                    "status": m["status"],
                    "active_claim": active["worker"] if active else None,
                    "last_heartbeat": last_hb,
                })
            
            sprint_statuses.append({
                "id": s.get("id", ""),
                "title": s.get("title", ""),
                "status": s.get("status", ""),
                "research_status": s_research,
                "missions": s_missions,
            })
        
        # Compute patch batch summary
        total_planned = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_planned")
        total_prechecked = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_prechecked")
        total_applied = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_applied")
        total_validated = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_validated")
        total_blocked = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_blocked")
        total_merge_checked = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_merge_friendly_checked")
        total_merge_safe = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_merge_friendly_checked" and e.get("safe_to_apply") == True)
        total_merge_blocked = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_merge_friendly_checked" and e.get("safe_to_apply") == False)
        blocked_reasons = list(set(
            e.get("precheck_failed_reason", "") or e.get("apply_failed_reason", "")
            for e in patch_batch_events if e.get("type") == "patch_batch_blocked" and e.get("precheck_failed_reason")
        ))
        merge_blocked_reasons = list(set(
            str(r) for e in patch_batch_events 
            if e.get("type") == "patch_batch_merge_friendly_checked" 
            and not e.get("safe_to_apply", True)
            for r in e.get("blocked_reasons", [])
        ))
    else:
        # Legacy flat missions structure
        sprint_statuses = []
        mission_statuses = []
        for m in task.get("missions", []):
            mid = m["id"]
            active = next((c for c in active_claims if c.get("mission_id") == mid), None)
            last_hb = None
            if active:
                last_hb = last_heartbeat_by_worker.get(active["worker"])
            
            # Get patch batches for legacy missions
            mission_patch_batches = []
            for pb_ev in patch_batch_events:
                if pb_ev.get("mission_id") == mid:
                    pb_entry = {
                        "id": pb_ev.get("patch_batch_id", ""),
                        "status": pb_ev.get("type", "").replace("patch_batch_", ""),
                        "precheck_passed": pb_ev.get("precheck_passed"),
                        "applied_at": pb_ev.get("ts"),
                    }
                    # Add merge-friendliness info
                    if pb_ev.get("type") == "patch_batch_merge_friendly_checked":
                        pb_entry["merge_friendly_checked"] = True
                        pb_entry["merge_friendly_safe"] = pb_ev.get("safe_to_apply", False)
                        pb_entry["merge_friendly_result"] = pb_ev.get("result", "unknown")
                    else:
                        # Check if there's a merge check for this batch
                        for mf_ev in patch_batch_events:
                            if mf_ev.get("type") == "patch_batch_merge_friendly_checked" and mf_ev.get("patch_batch_id") == pb_ev.get("patch_batch_id"):
                                pb_entry["merge_friendly_checked"] = True
                                pb_entry["merge_friendly_safe"] = mf_ev.get("safe_to_apply", False)
                                pb_entry["merge_friendly_result"] = mf_ev.get("result", "unknown")
                                break
                    mission_patch_batches.append(pb_entry)
            
            mission_statuses.append({
                "id": mid,
                "title": m["title"],
                "status": m["status"],
                "active_claim": active["worker"] if active else None,
                "last_heartbeat": last_hb,
                "patch_batches": mission_patch_batches,
            })
        
        # Compute patch batch summary for legacy
        total_planned = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_planned")
        total_prechecked = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_prechecked")
        total_applied = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_applied")
        total_validated = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_validated")
        total_blocked = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_blocked")
        total_merge_checked = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_merge_friendly_checked")
        total_merge_safe = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_merge_friendly_checked" and e.get("safe_to_apply") == True)
        total_merge_blocked = sum(1 for e in patch_batch_events if e.get("type") == "patch_batch_merge_friendly_checked" and e.get("safe_to_apply") == False)
        blocked_reasons = list(set(
            e.get("precheck_failed_reason", "") or e.get("apply_failed_reason", "")
            for e in patch_batch_events if e.get("type") == "patch_batch_blocked" and e.get("precheck_failed_reason")
        ))
        merge_blocked_reasons = list(set(
            str(r) for e in patch_batch_events 
            if e.get("type") == "patch_batch_merge_friendly_checked" 
            and not e.get("safe_to_apply", True)
            for r in e.get("blocked_reasons", [])
        ))

    # Check if research is complete for all sprints
    research_complete = True
    if sprints:
        for s in sprints:
            s_status = sprint_research_status.get(s.get("id", ""), "not_started")
            if s_status != "completed":
                research_complete = False
                break

    # Conflict detection: same mission claimed by multiple workers
    mission_claim_counts: dict[str, list[str]] = {}
    for claim in active_claims:
        mid = claim.get("mission_id") or "_task_"
        mission_claim_counts.setdefault(mid, []).append(claim["worker"])
    for mid, workers in mission_claim_counts.items():
        if len(workers) > 1:
            conflicts.append(f"Mission '{mid}' claimed by multiple workers: {', '.join(workers)}")

    # Next safe action - check research first
    if sprints:
        incomplete_research = [
            s.get("id", "") for s in sprints
            if sprint_research_status.get(s.get("id", ""), "not_started") != "completed"
        ]
        if incomplete_research:
            next_action = f"Complete sprint research for: {', '.join(incomplete_research)}"
        elif conflicts:
            next_action = "Resolve conflicting claims before proceeding."
        elif stale_claims:
            next_action = "Stale claims detected. Run work_handoff.py or work_claim.py --release to clear."
        elif active_claims:
            next_action = "Work in progress. Heartbeat regularly. Run work_handoff.py when complete."
        elif all(m["status"] in ("closed", "ready_for_review") for m in mission_statuses):
            next_action = "All missions complete. Run work_doctor.py then promote."
        else:
            next_action = "Claim an open mission with work_claim.py to begin work."
    else:
        # Legacy
        if conflicts:
            next_action = "Resolve conflicting claims before proceeding."
        elif stale_claims:
            next_action = "Stale claims detected. Run work_handoff.py or work_claim.py --release to clear."
        elif active_claims:
            next_action = "Work in progress. Heartbeat regularly. Run work_handoff.py when complete."
        elif all(m["status"] in ("closed", "ready_for_review") for m in mission_statuses):
            next_action = "All missions complete. Run work_doctor.py then promote."
        else:
            next_action = "Claim an open mission with work_claim.py to begin work."

    return {
        "generated_at": now_iso(),
        "task_id": task_id,
        "adr": task.get("adr", ""),
        "task_status": task.get("status", ""),
        "research_complete": research_complete,
        "sprints": sprint_statuses,
        "missions": mission_statuses,
        "active_claims": active_claims,
        "stale_claims": stale_claims,
        "conflicts": conflicts,
        "last_heartbeat_by_worker": last_heartbeat_by_worker,
        "latest_events": events[-10:],
        "out_of_scope_findings_count": len(out_of_scope_findings),
        "next_safe_action": next_action,
        "patch_batches_summary": {
            "total_planned": total_planned,
            "total_prechecked": total_prechecked,
            "total_applied": total_applied,
            "total_validated": total_validated,
            "total_blocked": total_blocked,
            "total_merge_checked": total_merge_checked,
            "total_merge_safe": total_merge_safe,
            "total_merge_blocked": total_merge_blocked,
            "blocked_reasons": blocked_reasons,
            "merge_blocked_reasons": merge_blocked_reasons,
        },
        "promotion_summary": {
            "rite_of_deterministic_passage_complete": False,  # Will be computed per mission/sprint
            "last_promotion_attempt": last_promotion_attempt.get("ts") if last_promotion_attempt else None,
            "last_promotion_success": last_promotion_success,
            "promotion_target": "preproduction",
            "promotion_source_branch": last_promotion_attempt.get("source_branch") if last_promotion_attempt else None,
            "promotion_gate_failures": last_promotion_attempt.get("blocking_gates_failures", 0) if last_promotion_attempt else 0,
            "preproduction_exists": branch_exists_locally("preproduction"),
        },
        "forge_readiness": {
            "forge_gates_checked": handoff_forge_gates_checked,
            "forge_promotion_ready": latest_handoff_forge_evidence.get("forge_promotion_ready", False) if latest_handoff_forge_evidence else False,
            "reviewability_changed_file_count": latest_handoff_forge_evidence.get("reviewability_changed_file_count", 0) if latest_handoff_forge_evidence else 0,
            "reviewability_max_changed_files": latest_handoff_forge_evidence.get("reviewability_max_changed_files", 300) if latest_handoff_forge_evidence else 300,
            "reviewability_over_budget": latest_handoff_forge_evidence.get("reviewability_over_budget", False) if latest_handoff_forge_evidence else False,
            "reviewability_default_action": latest_handoff_forge_evidence.get("reviewability_default_action", "block_promotion") if latest_handoff_forge_evidence else "block_promotion",
            "forge_target_ref": latest_handoff_forge_evidence.get("forge_target_ref", "preproduction") if latest_handoff_forge_evidence else "preproduction",
            "forge_mode": latest_handoff_forge_evidence.get("forge_mode", "unknown") if latest_handoff_forge_evidence else "unknown",
            "promotion_mode": latest_handoff_forge_evidence.get("promotion_mode", "unknown") if latest_handoff_forge_evidence else "unknown",
        },
        "_out_of_scope_findings": out_of_scope_findings,  # internal, used for notes generation
    }


# ---------------------------------------------------------------------------
# Forge Gate Helpers
# ---------------------------------------------------------------------------

def run_forge_doctor_json(repo_path: str | Path | None = None) -> dict[str, Any]:
    """Run `rig forge doctor --json` and return parsed output.
    
    Args:
        repo_path: Repository path for -C flag. If None, runs in current directory.
        
    Returns:
        Parsed JSON output as dict. On error, returns dict with 'error' key.
    """
    import subprocess
    import json
    from pathlib import Path
    
    cmd = [sys.executable, "-m", "rig", "forge", "doctor", "--json"]
    if repo_path:
        cmd = ["git", "-C", str(repo_path), "-c", 
               f"core.sshCommand=ssh -i {(Path(repo_path) / '.ssh' / 'id_ed25519').resolve() if (Path(repo_path) / '.ssh' / 'id_ed25519').exists() else ''}",
               sys.executable, "-m", "rig", "forge", "doctor", "--json"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "Unknown error", "exit_code": result.returncode}
        return json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def run_forge_promote_dry_run_json(
    repo_path: str | Path | None = None,
    target_ref: str = "preproduction",
    head_ref: str = "HEAD",
    max_changed_files: int | None = None,
) -> dict[str, Any]:
    """Run `rig forge promote --dry-run --json` and return parsed output.
    
    Args:
        repo_path: Repository path for -C flag. If None, runs in current directory.
        target_ref: Target reference for promotion (default: "preproduction")
        head_ref: Head reference for promotion (default: "HEAD")
        max_changed_files: Override max changed files budget
        
    Returns:
        Parsed JSON output as dict. On error, returns dict with 'error' key.
    """
    import subprocess
    import json
    from pathlib import Path
    
    cmd = [sys.executable, "-m", "rig", "forge", "promote", "--dry-run", "--json"]
    if target_ref != "preproduction":
        cmd.extend(["--target-ref", target_ref])
    if head_ref != "HEAD":
        cmd.extend(["--head-ref", head_ref])
    if max_changed_files is not None:
        cmd.extend(["--max-changed-files", str(max_changed_files)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr.strip() or "Unknown error", "exit_code": result.returncode}
        return json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def check_forge_readiness(
    repo_path: str | Path | None = None,
    target_ref: str = "preproduction",
    head_ref: str = "HEAD",
) -> tuple[bool, dict[str, Any]]:
    """Check forge readiness by running doctor and promote --dry-run.
    
    Args:
        repo_path: Repository path
        target_ref: Target reference for promotion
        head_ref: Head reference for promotion
        
    Returns:
        Tuple of (is_ready, evidence_dict).
        evidence_dict contains all forge gate evidence for recording in events.
    """
    doctor_result = run_forge_doctor_json(repo_path)
    promote_result = run_forge_promote_dry_run_json(repo_path, target_ref, head_ref)
    
    # Determine readiness
    has_doctor_error = "error" in doctor_result
    has_promote_error = "error" in promote_result
    # doctor is clean if: no error AND (overall_status is "clean" OR missing/unknown)
    doctor_clean = not has_doctor_error and doctor_result.get("overall_status", "clean") == "clean"
    promote_ready = promote_result.get("ready") is True
    
    is_ready = (
        not has_doctor_error and 
        not has_promote_error and 
        doctor_clean and 
        promote_ready
    )
    
    # Build evidence dict
    evidence: dict[str, Any] = {
        "forge_doctor_status": doctor_result.get("overall_status", "unknown") if not has_doctor_error else "error",
        "forge_doctor_error": doctor_result.get("error") if has_doctor_error else None,
        "forge_promotion_ready": promote_ready,
        "forge_promotion_blockers": promote_result.get("blockers", []),
        "reviewability_changed_file_count": promote_result.get("reviewability", {}).get("changed_file_count", 0),
        "reviewability_max_changed_files": promote_result.get("reviewability", {}).get("max_changed_files", 300),
        "reviewability_over_budget": promote_result.get("reviewability", {}).get("over_budget", False),
        "reviewability_default_action": promote_result.get("reviewability", {}).get("default_action", "block_promotion"),
        "forge_target_ref": target_ref,
        "forge_head_ref": head_ref,
        "forge_mode": promote_result.get("forge_mode", "unknown"),
        "promotion_mode": promote_result.get("mode", "unknown"),
    }
    
    # Add identity info if available
    identity = promote_result.get("identity", {})
    if identity:
        evidence["forge_identity"] = {
            "mode": identity.get("mode"),
            "remote_url": identity.get("remote_url"),
            "host": identity.get("host"),
        }
    
    return is_ready, evidence


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
            if f.get("sprint_id"):
                lines.append(f"- **sprint_id**: {f['sprint_id']}")
            if f.get("mission_id"):
                lines.append(f"- **mission_id**: {f['mission_id']}")
            lines += [
                f"- **finding**: {f['finding']}",
                f"- **source_event_id**: {f['source_event_id']}",
                f"- **status**: {f['status']}",
                "",
            ]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Workflow Chain Integration (ADR 0009 / ADR 0010)
# ---------------------------------------------------------------------------

def run_workflow_context_chain(
    context_id: str,
    repo_path: str | Path | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Run a Rig workflow context chain and return results.
    
    This function integrates with the workflow chain system from ADR 0009.
    It runs deterministic workflow chains instead of manual command checklists.
    
    Args:
        context_id: The workflow context ID to run (e.g., 'mission_handoff', 'promotion_dry_run')
        repo_path: Repository path for running commands. If None, runs in current directory.
        
    Returns:
        Tuple of (passed, evidence_dict).
        passed: True if all required commands in the chain passed.
        evidence_dict: Complete evidence from the workflow run.
        
    Note:
        This function uses `rig workflow run` CLI command internally.
        The workflow chains are defined in src/rig/domain/workflow_chains.py.
        Built-in contexts: 'mission_handoff', 'promotion_dry_run'
        
        All commands use subprocess.run with explicit argument arrays, NEVER shell=True.
        Output is truncated to MAX_OUTPUT_CHARS (10000) for safety.
        Evidence is written to .rig/work/validation/<context_id>-<timestamp>.json
        No tokens/secrets in evidence. No personal names in evidence.
    """
    import subprocess
    import json
    from pathlib import Path
    
    if repo_path is None:
        repo_path = repo_root()
    else:
        repo_path = Path(repo_path)
    
    cmd = [
        sys.executable, "-m", "rig", "workflow", "run",
        context_id,
        "--json",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for full chain
        )
        
        if result.returncode != 0:
            # Try to parse error output
            try:
                error_data = json.loads(result.stdout)
                return False, {
                    "error": error_data.get("error", result.stderr.strip()),
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            except json.JSONDecodeError:
                return False, {
                    "error": result.stderr.strip() or result.stdout.strip() or "Unknown error",
                    "exit_code": result.returncode,
                }
        
        # Parse JSON output
        try:
            evidence = json.loads(result.stdout)
            return evidence.get("passed", False), evidence
        except json.JSONDecodeError:
            return False, {
                "error": "Failed to parse workflow output as JSON",
                "exit_code": 0,
                "raw_output": result.stdout,
                "stderr": result.stderr,
            }
            
    except subprocess.TimeoutExpired:
        return False, {
            "error": "Workflow chain execution timed out (600s)",
            "exit_code": -1,
        }
    except Exception as e:
        return False, {
            "error": str(e),
            "exit_code": -1,
        }


def check_mission_handoff_readiness(
    repo_path: str | Path | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Check mission handoff readiness using workflow chain system.
    
    This is the ADR 0009 preferred integration point.
    Runs the 'mission_handoff' workflow context which includes:
    1. compileall - Syntax check all Python files
    2. pytest_collect - Collect all tests to verify test suite structure
    3. check_fast - Run fast validation suite
    4. forge_doctor - Check forge configuration and capabilities
    5. forge_promote_dry_run - Dry-run promotion planning
    
    All commands are non-mutating and agent-allowed.
    
    Args:
        repo_path: Repository path for running commands. If None, runs in current directory.
        
    Returns:
        Tuple of (is_ready, evidence_dict) matching check_forge_readiness signature.
    """
    passed, evidence = run_workflow_context_chain("mission_handoff", repo_path)
    
    # Transform evidence to match check_forge_readiness format for compatibility
    if passed and "results" in evidence:
        # Extract forge-specific info from workflow results
        forge_doctor_result = None
        forge_promote_result = None
        
        for result in evidence.get("results", []):
            cmd_id = result.get("id", "")
            if cmd_id == "forge_doctor":
                forge_doctor_result = result
            elif cmd_id == "forge_promote_dry_run":
                forge_promote_result = result
        
        # Build compatible evidence format
        compatible_evidence: dict[str, Any] = {
            "forge_doctor_status": "clean" if forge_doctor_result and forge_doctor_result.get("passed") else "error",
            "forge_doctor_error": None,
            "forge_promotion_ready": forge_promote_result and forge_promote_result.get("passed"),
            "forge_promotion_blockers": [],
            "reviewability_changed_file_count": 0,
            "reviewability_max_changed_files": 300,
            "reviewability_over_budget": False,
            "reviewability_default_action": "block_promotion",
            "forge_target_ref": "preproduction",
            "forge_head_ref": "HEAD",
            "forge_mode": "unknown",
            "promotion_mode": "unknown",
            # Add workflow-specific info
            "workflow_context_id": "mission_handoff",
            "workflow_passed": passed,
            "workflow_results": evidence.get("results", []),
        }
        
        # Try to parse forge doctor JSON output if available
        if forge_doctor_result and forge_doctor_result.get("stdout"):
            try:
                doctor_data = json.loads(forge_doctor_result["stdout"])
                compatible_evidence["forge_doctor_raw"] = doctor_data
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Try to parse forge promote dry-run JSON output if available
        if forge_promote_result and forge_promote_result.get("stdout"):
            try:
                promote_data = json.loads(forge_promote_result["stdout"])
                compatible_evidence["forge_promotion_raw"] = promote_data
                compatible_evidence["reviewability_changed_file_count"] = (
                    promote_data.get("reviewability", {}).get("changed_file_count", 0)
                )
                compatible_evidence["reviewability_max_changed_files"] = (
                    promote_data.get("reviewability", {}).get("max_changed_files", 300)
                )
                compatible_evidence["reviewability_over_budget"] = (
                    promote_data.get("reviewability", {}).get("over_budget", False)
                )
                compatible_evidence["reviewability_default_action"] = (
                    promote_data.get("reviewability", {}).get("default_action", "block_promotion")
                )
                compatible_evidence["forge_mode"] = promote_data.get("forge_mode", "unknown")
                compatible_evidence["promotion_mode"] = promote_data.get("mode", "unknown")
                compatible_evidence["forge_promotion_blockers"] = (
                    promote_data.get("blockers", [])
                )
            except (json.JSONDecodeError, TypeError):
                pass
        
        return passed, compatible_evidence
    
    # If workflow failed, return evidence as-is
    return passed, evidence
