from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rig_tools.tui_events import render_human_event_line
from rig_tools.tui_state import clamp_mode


def _read_json(path: Path) -> dict[str, Any]| Optional:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def latest_receipt_paths(repo_root: Path) -> dict[str, str| Optional]:
    base = repo_root / ".build" / "rig"
    return {
        "doctor": str((base / "doctor" / "latest.json").relative_to(repo_root)) if (base / "doctor" / "latest.json").exists() else None,
        "audit": str((base / "audit" / "contracts" / "latest.json").relative_to(repo_root)) if (base / "audit" / "contracts" / "latest.json").exists() else None,
        "sentinel": str((base / "os-sentinel" / "latest.json").relative_to(repo_root)) if (base / "os-sentinel" / "latest.json").exists() else None,
        "loop": str((base / "loop" / "latest.json").relative_to(repo_root)) if (base / "loop" / "latest.json").exists() else None,
        "swarm": str((base / "swarm" / "latest.json").relative_to(repo_root)) if (base / "swarm" / "latest.json").exists() else None,
        "vault": str((base / "vault" / "latest.json").relative_to(repo_root)) if (base / "vault" / "latest.json").exists() else None,
    }


def recommend_next_action(snapshot: dict[str, Any]) -> str:
    if (snapshot.get("doctor") or {}).get("status") != "pass":
        return "Run Doctor"
    if (snapshot.get("audit") or {}).get("status") != "pass":
        return "Run Contract Audit"
    if (snapshot.get("swarm") or {}).get("status") == "blocked":
        return "Open Swarm"
    if (snapshot.get("loop") or {}).get("status") in {"blocked", "failed"}:
        return "Plan Loop Dry-Run"
    return "Open Board"


def cap_event_tail(events: list[dict[str, Any]], max_events: int = 500) -> list[dict[str, Any]]:
    tail = events[-max_events:] if max_events > 0 else []
    deduped: list[dict[str, Any]] = []
    last_sig: tuple[Any, ...]| Optional = None
    for event in tail:
        sig = (
            event.get("event_type"),
            (event.get("attributes") or {}).get("message"),
            (event.get("attributes") or {}).get("status"),
            (event.get("attributes") or {}).get("task"),
        )
        if sig == last_sig:
            continue
        deduped.append(event)
        last_sig = sig
    return deduped


def human_event_lines(events: list[dict[str, Any]], *, max_events: int = 500, focus_task_id: str| Optional = None) -> list[str]:
    lines: list[str] = []
    for event in cap_event_tail(events, max_events=max_events):
        line = render_human_event_line(event, focus_task_id=focus_task_id)
        if line:
            lines.append(line)
    return lines


def board_layout_mode(width: int) -> str:
    return "stacked" if width < 100 else "columns"


def semantic_status_class(status: str, *, disabled: bool = False, selected: bool = False) -> str:
    s = str(status or "").lower()
    if selected:
        return "semantic-selected"
    if disabled:
        return "semantic-disabled"
    if s in {"fail", "failed", "error", "unsafe", "blocked"}:
        return "semantic-fail"
    if s in {"pass", "passed", "ready", "safe", "complete", "completed", "allowed"}:
        return "semantic-pass"
    if s in {"warn", "warning", "pending", "review"}:
        return "semantic-warn"
    return "semantic-info"


def _task_inspector(card: dict[str, Any]| Optional, *, selected_task_id: str| Optional) -> dict[str, Any]:
    if not card:
        return {
            "selected_task_id": selected_task_id,
            "title": "No task selected",
            "status": "idle",
            "risk": "low",
            "allowed_actions": [],
            "receipt_paths": [],
        }
    allowed_actions = [
        action
        for action in ["refresh_status", "monitor_snapshot", "context_build", "loop_plan", "bundle_session_dry_run", "queue_add_read_only_x3"]
        if action
    ]
    receipt_paths = [card.get(key) for key in ("latest_proof_path", "latest_bundle_path", "latest_gate_status_path", "latest_loop_receipt_path") if card.get(key)]
    return {
        "selected_task_id": selected_task_id,
        "title": card.get("title") or card.get("task_id") or "Task",
        "status": card.get("status") or "ready",
        "risk": card.get("risk") or "low",
        "allowed_actions": allowed_actions,
        "receipt_paths": receipt_paths,
        "recommended_next_action": card.get("recommended_next_action") or "refresh_status",
        "recommendation_reason": card.get("recommendation_reason") or "",
    }


def action_affordances(snapshot: dict[str, Any], *, selected_task_id: str| Optional, mode: str) -> dict[str, dict[str, str | bool]]:
    board = snapshot.get("board") or {}
    cards = board.get("cards") or []
    task_exists = bool(selected_task_id and any(card.get("task_id") == selected_task_id for card in cards))
    mode = clamp_mode(mode)

    def afford(*, requires_task: bool = False, safe: bool = False, action: bool = False, auto: bool = False, available: bool = True, mutating: bool = False, backend: bool = True) -> dict[str, str | bool]:
        if not available:
            return {"enabled": False, "reason": "unavailable command"}
        if not backend:
            return {"enabled": False, "reason": "missing backend"}
        if requires_task and not task_exists:
            return {"enabled": False, "reason": "requires task"}
        if mutating and mode == "safe":
            return {"enabled": False, "reason": "unsafe/mutating"}
        if safe and mode not in {"safe", "action", "auto-approve"}:
            return {"enabled": False, "reason": "wrong mode"}
        if action and mode not in {"action", "auto-approve"}:
            return {"enabled": False, "reason": "wrong mode"}
        if auto and mode != "auto-approve":
            return {"enabled": False, "reason": "wrong mode"}
        return {"enabled": True, "reason": ""}

    return {
        "doctor_run": afford(),
        "open_board": afford(),
        "open_swarm": afford(),
        "open_vault": afford(),
        "workspace_next_safe_action": afford(requires_task=True, safe=True),
        "workspace_loop_dry_run": afford(requires_task=True, safe=True),
        "queue_add_read_only_x3": afford(requires_task=True, action=True),
        "bundle_session_dry_run": afford(requires_task=True, safe=True),
        "swarm_open_winner": afford(),
        "swarm_compare_candidates": afford(),
        "doctor_run_health": afford(),
        "vault_open_uri": afford(),
        "settings_show_effective": afford(),
        "copy_receipt_path": afford(),
        "open_receipt_path": afford(),
    }


def render_task_card_summary(card: dict[str, Any], *, selected_task_id: str| Optional) -> dict[str, Any]:
    selected = card.get("task_id") == selected_task_id
    status = str(card.get("status") or "ready")
    risk = str(card.get("risk") or "low")
    next_action = str(card.get("recommended_next_action") or "refresh_status")
    return {
        "task_id": card.get("task_id"),
        "title": card.get("title") or card.get("task_id") or "Task",
        "status": status,
        "risk": risk,
        "next_action": next_action,
        "selected": selected,
        "status_class": semantic_status_class(status, selected=selected),
        "risk_class": semantic_status_class(risk),
        "badge_class": semantic_status_class(status, selected=selected),
        "selected_class": "semantic-selected" if selected else "semantic-info",
        "primary_action": next_action,
        "receipt_paths": [path for path in [
            card.get("latest_proof_path"),
            card.get("latest_bundle_path"),
            card.get("latest_loop_status"),
            card.get("latest_gate_status"),
        ] if path],
    }


def render_command_center_snapshot(
    snapshot: dict[str, Any],
    *,
    repo_root: Path,
    selected_task_id: str| Optional,
    max_events: int = 500,
) -> dict[str, Any]:
    latest_receipts = latest_receipt_paths(repo_root)
    queue_receipt = str((repo_root / ".build" / "rig" / "queue" / "queue.json").relative_to(repo_root)) if (repo_root / ".build" / "rig" / "queue" / "queue.json").exists() else None
    doctor = snapshot.get("doctor") or {}
    audit = snapshot.get("audit") or {}
    sentinel = snapshot.get("sentinel") or {}
    pressure = snapshot.get("pressure") or {}
    queue = snapshot.get("queue") or {}
    loop = snapshot.get("loop") or {}
    swarm = snapshot.get("swarm") or {}
    project = snapshot.get("project") or {}
    workspaces = snapshot.get("workspaces") or []
    latest_workspace = snapshot.get("latest_workspace") or {}
    product_report = snapshot.get("product_report") or {}

    warnings: list[str] = []
    for source in ("doctor", "audit", "sentinel", "loop", "queue", "swarm", "project", "product_report"):
        payload = snapshot.get(source) or {}
        for item in payload.get("warnings", []) if isinstance(payload.get("warnings"), list) else []:
            warnings.append(f"{source}: {item}")
    
    events = human_event_lines(snapshot.get("recent_events") or [], max_events=max_events, focus_task_id=selected_task_id)
    return {
        "top_bar": {
            "wordmark": "RIG",
            "mode": (snapshot.get("state") or {}).get("mode") or (snapshot.get("settings") or {}).get("default_mode") or "safe",
            "doctor": doctor.get("status") or "unknown",
            "audit": audit.get("status") or "unknown",
            "sentinel": sentinel.get("status") or "unknown",
            "pressure": pressure.get("status") or "unknown",
            "repo": snapshot.get("repo_name") or repo_root.name,
            "project_initialized": project.get("rig_initialized", False),
            "project_digest_present": project.get("digest_present", False),
            "active_workspaces": len([w for w in workspaces if w.get("status") == "active"]),
        },
        "next_action": recommend_next_action(snapshot),
        "health_cards": [
            {"label": "Product", "status": product_report.get("status") or "unknown", "receipt": "latest"},
            {"label": "Doctor", "status": doctor.get("status") or "unknown", "receipt": latest_receipts["doctor"]},
            {"label": "Audit", "status": audit.get("status") or "unknown", "receipt": latest_receipts["audit"]},
            {"label": "Sentinel", "status": sentinel.get("status") or "unknown", "receipt": latest_receipts["sentinel"]},
            {"label": "Queue", "status": (queue.get("status") or "unknown"), "receipt": queue_receipt},
            {"label": "Workspace", "status": latest_workspace.get("workspace_id") or "none", "receipt": latest_workspace.get("mode")},
            {"label": "Loop", "status": loop.get("status") or "unknown", "receipt": latest_receipts["loop"]},
            {"label": "Swarm", "status": swarm.get("status") or "unknown", "receipt": latest_receipts["swarm"]},
        ],
        "active_jobs": [
            {"label": "queue", "status": queue.get("status") or "unknown", "count": len(queue.get("jobs") or []), "receipt": queue_receipt},
            {"label": "loop", "status": loop.get("status") or "unknown", "run_id": loop.get("run_id"), "receipt": latest_receipts["loop"]},
            {"label": "swarm", "status": swarm.get("status") or "unknown", "swarm_id": swarm.get("swarm_id"), "receipt": latest_receipts["swarm"]},
        ],
        "warnings": warnings[:10],
        "event_lines": events[:max_events],
        "receipt_paths": latest_receipts,
        "widget_ids": [
            "top-bar",
            "command-center-next",
            "command-center-health",
            "command-center-jobs",
            "command-center-warnings",
            "command-center-event-log",
        ],
    }


def render_board_snapshot(snapshot: dict[str, Any], *, selected_task_id: str| Optional, width: int) -> dict[str, Any]:
    board = snapshot.get("board") or {}
    cards = board.get("cards") or []
    card = next((item for item in cards if item.get("task_id") == selected_task_id), None)
    inspector = _task_inspector(card, selected_task_id=selected_task_id)
    return {
        "layout_mode": board_layout_mode(width),
        "selected_task_id": selected_task_id,
        "cards": cards,
        "inspector": inspector,
        "visible_columns": ["ready", "running", "approval", "blocked", "review"],
        "receipt_paths": inspector["receipt_paths"],
    }


def render_workspace_snapshot(snapshot: dict[str, Any], *, selected_task_id: str| Optional, mode: str, repo_root: Path) -> dict[str, Any]:
    board = snapshot.get("board") or {}
    card = next((item for item in board.get("cards") or [] if item.get("task_id") == selected_task_id), None)
    loop = snapshot.get("loop") or {}
    workspaces = snapshot.get("workspaces") or []
    latest_workspace = workspaces[-1] if workspaces else {}
    affordances = action_affordances(snapshot, selected_task_id=selected_task_id, mode=mode)
    receipts = latest_receipt_paths(repo_root)
    return {
        "selected_task_id": selected_task_id,
        "task_title": (card or {}).get("title") or selected_task_id or "No task selected",
        "mode": clamp_mode(mode),
        "workspace": {
            "workspace_id": latest_workspace.get("workspace_id"),
            "task": latest_workspace.get("task"),
            "status": latest_workspace.get("status"),
            "branch": latest_workspace.get("branch"),
            "worktree_path": latest_workspace.get("worktree_path"),
            "execution_receipt_status": (snapshot.get("latest_workspace") or {}).get("receipt_status"),
            "validation_status": latest_workspace.get("validation_status"),
        },
        "loop": {
            "status": loop.get("status") or "unknown",
            "run_id": loop.get("run_id"),
            "stop_reason": loop.get("stop_reason"),
        },
        "artifacts": [
            path for path in [
                (card or {}).get("latest_proof_path"),
                (card or {}).get("latest_bundle_path"),
                (card or {}).get("latest_loop_status"),
                (card or {}).get("latest_gate_status"),
            ] if path
        ],
        "receipt_paths": receipts,
        "action_affordances": affordances,
    }


def render_swarm_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    swarm = snapshot.get("swarm") or {}
    candidates = swarm.get("candidates") or []
    rows = []
    for cand in candidates:
        failure_type = str(cand.get("failure_type") or "")
        status = str(cand.get("status") or "unknown")
        rows.append(
            " · ".join(
                [
                    str(cand.get("candidate_id") or "candidate"),
                    str(cand.get("strategy") or "strategy"),
                    f"score {cand.get('score')} ({cand.get('bias_alignment', 0)})",
                    str(cand.get("status") or "unknown"),
                    str(cand.get("prompt_path") or ""),
                ]
            ).strip()
        )
        cand["visual_class"] = semantic_status_class(status)
        cand["failure_class"] = semantic_status_class(failure_type, disabled=status == "quarantined")
        cand["score_class"] = "semantic-pass" if isinstance(cand.get("score"), (int, float)) and cand.get("score", 0) >= 80 else "semantic-warn"
        cand["winner_class"] = "semantic-selected" if cand.get("candidate_id") == swarm.get("winner_candidate_id") else "semantic-info"
    return {
        "swarm_id": swarm.get("swarm_id"),
        "status": swarm.get("status") or "unknown",
        "bias_profiles": swarm.get("bias_profiles") or [],
        "winner_candidate_id": swarm.get("winner_candidate_id"),
        "candidates": candidates,
        "candidate_rows": rows,
    }


def render_swarm_candidate_detail(snapshot: dict[str, Any], candidate_id: str| Optional) -> dict[str, Any]:
    swarm = snapshot.get("swarm") or {}
    candidate = next((item for item in swarm.get("candidates") or [] if item.get("candidate_id") == candidate_id), None)
    if not candidate:
        return {
            "candidate_id": candidate_id,
            "status": "none",
            "strategy": "",
            "score": None,
            "failure_type": "",
            "prompt_path": "",
            "raw_output_path": "",
            "validation_path": "",
        }
    return {
        "candidate_id": candidate.get("candidate_id"),
        "status": candidate.get("status") or "unknown",
        "strategy": candidate.get("strategy") or "",
        "score": candidate.get("score"),
        "bias_alignment": candidate.get("bias_alignment"),
        "hard_fail": candidate.get("hard_fail", False),
        "failure_type": candidate.get("failure_type") or "",
        "prompt_path": candidate.get("prompt_path") or "",
        "raw_output_path": candidate.get("raw_output_path") or "",
        "validation_path": candidate.get("validation_path") or "",
        "warning": candidate.get("warning") or "",
    }


def render_project_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    project = snapshot.get("project") or {}
    digest = project.get("latest_digest") or {}
    return {
        "rig_initialized": project.get("rig_initialized", False),
        "digest_present": project.get("digest_present", False),
        "languages": digest.get("languages") or [],
        "detected_stacks": digest.get("detected_stacks") or [],
        "recommended_adapters": digest.get("recommended_adapters") or [],
        "source_roots": digest.get("source_roots") or [],
        "test_roots": digest.get("test_roots") or [],
        "docs_roots": digest.get("docs_roots") or [],
    }


def render_health_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[str]] = {}
    for subsystem in ("sentinel", "doctor", "audit", "anigma"):
        payload = snapshot.get(subsystem) or {}
        items: list[str] = []
        for key in ("warnings", "failures"):
            values = payload.get(key)
            if isinstance(values, list):
                items.extend(str(item) for item in values)
        if items:
            grouped[subsystem] = items
    return {
        "sentinel": (snapshot.get("sentinel") or {}).get("status") or "unknown",
        "doctor": (snapshot.get("doctor") or {}).get("status") or "unknown",
        "audit": (snapshot.get("audit") or {}).get("status") or "unknown",
        "subsystem_classes": {
            subsystem: semantic_status_class((snapshot.get(subsystem) or {}).get("status") or "unknown")
            for subsystem in ("sentinel", "doctor", "audit")
        },
        "groups": grouped,
    }


def help_keybindings() -> list[tuple[str, str]]:
    return [
        ("q", "quit"),
        ("?", "help"),
        ("tab / shift-tab", "focus"),
        ("enter", "activate"),
        ("r", "refresh"),
        ("s", "safe mode"),
        ("a", "action mode"),
        ("m", "cycle mode"),
        ("y", "request auto-approve"),
        ("f", "focus selected task/events"),
    ]


def render_health_detail(snapshot: dict[str, Any], subsystem: str, issue: str| Optional) -> dict[str, Any]:
    payload = snapshot.get(subsystem) or {}
    issues = []
    for key in ("warnings", "failures"):
        values = payload.get(key)
        if isinstance(values, list):
            issues.extend(str(item) for item in values)
    selected = issue if issue in issues else (issues[0] if issues else None)
    return {
        "subsystem": subsystem,
        "issue": selected or "",
        "recommendation": payload.get("recommendation") or "",
        "artifact_path": payload.get("artifact_path") or "",
        "issues": issues,
    }


def human_warning_label(subsystem: str, warning: str) -> str:
    if subsystem == "proposal_swarm" and warning == "proposal_swarm":
        return "Proposal Swarm limited: llama-server unavailable; MLX fallback only."
    return warning.replace("_", " ").strip().capitalize()
