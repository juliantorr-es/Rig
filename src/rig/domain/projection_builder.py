from dataclasses import asdict
from datetime import datetime, timezone
import subprocess
from typing import List, Optional
import importlib
from pathlib import Path
from rig.domain.projections import (
    UIProjection, WidgetProjection, IntentProjection, ProjectionLayout,
    ChatProjection, ChatMessage, ValidatorItem
)
from rig.domain.receipts import get_receipt_store

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_capture(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
    return (proc.stdout or "").strip()


def _git_status_entries(repo_root: Path) -> list[str]:
    raw = _git_capture(repo_root, "status", "--porcelain=v1", "-z")
    return [entry for entry in raw.split("\0") if entry]


def _workspace_header_widget(repo_root: Path, active_ws: Optional[dict]) -> WidgetProjection:
    branch = _git_capture(repo_root, "branch", "--show-current") or "HEAD"
    head = _git_capture(repo_root, "rev-parse", "--short", "HEAD")
    workspace_id = active_ws.get("workspace_id") if active_ws else None
    workspace_status = active_ws.get("status") if active_ws else "no_active_workspace"
    return WidgetProjection(
        "WorkspaceHeader",
        "workspace.header",
        {
            "repo_root": str(repo_root),
            "workspace_id": workspace_id,
            "workspace_status": workspace_status,
            "branch": branch,
            "head": head,
            "authority_label": "Workspace control plane (future lane registry)",
        },
    )


def _workspace_git_state_widget(repo_root: Path) -> WidgetProjection:
    branch = _git_capture(repo_root, "branch", "--show-current") or "HEAD"
    head = _git_capture(repo_root, "rev-parse", "--short", "HEAD")
    dirty_entries = _git_status_entries(repo_root)
    dirty = bool(dirty_entries)
    dirty_files_count = len(dirty_entries)
    safe_to_commit = not dirty and branch != "main"
    reason = "Clean non-main workspace root" if safe_to_commit else (
        "Workspace is dirty" if dirty else "Current branch is main"
    )
    return WidgetProjection(
        "WorkspaceGitState",
        "workspace.git_state",
        {
            "branch": branch,
            "head": head,
            "dirty": dirty,
            "dirty_files_count": dirty_files_count,
            "safe_to_commit": safe_to_commit,
            "reason": reason,
        },
    )


def _workspace_lane_summary_widget(workspace_records: int) -> WidgetProjection:
    connected = False
    return WidgetProjection(
        "WorkspaceLaneSummary",
        "workspace.lane_summary",
        {
            "status": "not_connected",
            "lane_count": 0,
            "active_lanes": 0,
            "clean_lanes": 0,
            "review_ready_lanes": 0,
            "workspace_records": workspace_records,
            "connected": connected,
            "message": "Agent lane data is not connected to the workspace projection yet.",
            "next_action": "Use scripts/rig_agent_worktree.py review/recommend from CLI until workspace integration lands.",
        },
    )

def build_projection(repo_root: Path, revision: int = 1, chat_history: Optional[List[ChatMessage]] = None) -> UIProjection:
    from rig.domain.workspace import WorkspaceDomain
    from rig_tools.core.io import read_json

    # Try to load snapshot from gridline if available, otherwise use empty dict
    # tui_snapshot was retired with Textual TUI
    try:
        tui_snapshot = importlib.import_module("rig_tools.tui_snapshot")
        snapshot = tui_snapshot.load_snapshot(repo_root)
    except (ImportError, ModuleNotFoundError, AttributeError):
        snapshot = {}

    domain = WorkspaceDomain(repo_root)
    workspaces = domain.list_workspaces()
    
    # Simple heuristic for active workspace: the one most recently modified
    # Use any non-applied workspace first, fall back to applied if that's all we have
    active_ws = None
    def _workspace_sort_key(ws: dict) -> str:
        history = ws.get("status_history")
        if isinstance(history, list) and history:
            last = history[-1]
            if isinstance(last, dict):
                return str(last.get("at", ""))
        return ""

    for ws in sorted(workspaces, key=_workspace_sort_key, reverse=True):
        if ws.get("status") != "applied":
            active_ws = ws
            break
    
    # If no non-applied workspace, use the most recent applied one
    if active_ws is None and workspaces:
        active_ws = workspaces[0]

    jobs_count = len(snapshot.get("jobs", []))
    workspaces_count = len([w for w in workspaces if w.get("status") != "applied"])
    providers_count = len(snapshot.get("providers", []))
    
    chat = None
    if chat_history is not None:
        chat = ChatProjection(messages=chat_history)

    if not active_ws:
        return _build_empty_projection(revision, chat, jobs_count, workspaces_count, providers_count, repo_root=repo_root)

    ws_id = active_ws["workspace_id"]
    status = active_ws.get("status", "unknown")
    
    # Build Validator Stack
    val_items = []
    val_status = {"label": "Missing", "severity": "idle"}
    val_summary = "No validation performed yet."
    
    # Check receipt store for recent validator runs to determine running state
    run_in_progress = False
    running_validator_id: Optional[str] = None
    recent_receipts: List = []
    
    try:
        store = get_receipt_store(repo_root)
        recent_receipts = store.list(
            workspace_id=ws_id,
            kind="validator_run",
            limit=5
        )
        now = datetime.now(timezone.utc)
        for receipt in recent_receipts:
            if hasattr(receipt, "timestamp"):
                try:
                    receipt_time = datetime.fromisoformat(receipt.timestamp.replace("Z", "+00:00"))
                    if (now - receipt_time).total_seconds() < 5:
                        run_in_progress = True
                        if hasattr(receipt, "validator_id") and receipt.validator_id:
                            running_validator_id = receipt.validator_id
                        break
                except (ValueError, TypeError):
                    continue
    except Exception:
        pass
    
    val_path = active_ws.get("validation_result_path")
    if val_path and Path(val_path).exists():
        val_data_raw = read_json(Path(val_path))
        val_data = val_data_raw if isinstance(val_data_raw, dict) else {}
        status_map = {"passed": "success", "failed": "danger", "warning": "attention"}
        status_value = str(val_data.get("status") or "unknown")
        val_status = {
            "label": status_value.capitalize(),
            "severity": status_map.get(status_value, "info")
        }
        validators_obj = val_data.get("validators")
        validators = validators_obj if isinstance(validators_obj, list) else []
        if not isinstance(validators, list):
            validators = []
        passed = len([v for v in validators if isinstance(v, dict) and v.get("exit_code") == 0])
        total = len(validators)
        val_summary = f"{passed} passed · {total - passed} failed"
        
        for v in validators:
            if not isinstance(v, dict):
                continue
            validator_id = str(v.get("validator_id") or "")
            val_items.append(ValidatorItem(
                id=validator_id,
                label=validator_id,
                state="passed" if v.get("exit_code") == 0 else "failed",
                detail=v.get("stderr_tail") if v.get("exit_code") != 0 else None
            ))
    else:
        # Show what validators are configured even if not run
        for i, v_cfg in enumerate(domain.read_validator_config()):
            state = "missing"
            # If validation is in progress, mark first validator as running
            if run_in_progress and running_validator_id is None:
                state = "running"
                running_validator_id = v_cfg.get("id") or v_cfg["argv"][0]
            val_items.append(ValidatorItem(
                id=v_cfg.get("id") or v_cfg["argv"][0],
                label=v_cfg.get("id") or v_cfg["argv"][0],
                state=state
            ))

    widgets = {
        "app.title": WidgetProjection("AppTitle", "app.title", {"title": "Rig", "subtitle": f"Workspace: {ws_id}"}),
        "next.gate": WidgetProjection("GateBadge", "next.gate", {"label": f"Status: {status}", "severity": "info" if status == "validated" else "attention"}),
        "workspace.header": _workspace_header_widget(repo_root, active_ws),
        "workspace.git_state": _workspace_git_state_widget(repo_root),
        "workspace.lane_summary": _workspace_lane_summary_widget(len(workspaces)),
        "queue.summary": WidgetProjection("MetricStack", "queue.summary", {
            "title": "Queue",
            "items": [
                {"label": "Jobs indexed", "value": jobs_count, "severity": "info"},
                {"label": "Active workspaces", "value": workspaces_count, "severity": "info"},
                {"label": "Providers available", "value": providers_count, "severity": "attention"}
            ]
        }),
        "validator.stack": WidgetProjection("ValidatorStack", "validator.stack", {
            "title": "Validators",
            "state": val_status,
            "summary": val_summary,
            "items": [asdict(i) for i in val_items],
            "run_in_progress": run_in_progress,
            "running_validator_id": running_validator_id
        }, actions=["intent.run_validators"]),
        "workspace.info": WidgetProjection("EmptyStateCard", "workspace.info", {
            "title": f"Workspace {ws_id}",
            "body": f"Current status: {status}. Ready for validation or review."
        }, actions=["intent.refresh_projection", "intent.run_validators"]),
        "evidence.current": WidgetProjection("EvidenceCard", "evidence.current", {
            "title": "Evidence",
            "state": {"label": "Available" if val_path else "None", "severity": "info" if val_path else "idle"},
            "body": f"Evidence for {ws_id}."
        }),
        "evidence.receipts": WidgetProjection("ReceiptList", "evidence.receipts", {
            "title": "Receipts",
            "receipts": [r.to_projection() for r in recent_receipts] if recent_receipts else []
        }),
        "backend.status": WidgetProjection("BackendStatus", "backend.status", {
            "title": "Native bridge",
            "body": "pywebview · WebSocket streaming",
            "revision": revision
        })
    }

    # Determine run_validators enable/disable based on workspace state
    run_validators_enabled = status in ("planned", "active", "executed", "blocked")
    run_validators_disabled_reason: Optional[str] = None
    if not run_validators_enabled:
        if status == "validated":
            run_validators_disabled_reason = "Already validated. Re-run to refresh."
        elif status == "review_ready":
            run_validators_disabled_reason = "Review ready. Apply or re-run from workspace."
        elif status == "applied":
            run_validators_disabled_reason = "Workspace already applied."
        else:
            run_validators_disabled_reason = f"Cannot run in state: {status}"
    
    return UIProjection(
        revision=revision,
        generated_at=utc_now(),
        screen="active_run",
        shell={"title": "Rig", "subtitle": f"Workspace {ws_id}"},
        chat=chat,
        layout=ProjectionLayout({
            "header": ["app.title", "next.gate", "workspace.header"],
            "sidebar": ["queue.summary", "workspace.git_state"],
            "main": ["workspace.info", "workspace.lane_summary", "validator.stack"],
            "inspector": ["evidence.current", "evidence.receipts"],
            "footer": ["backend.status"]
        }),
        widgets=widgets,
        intents={
            "intent.refresh_projection": IntentProjection("rig.intent.refresh_projection", "Refresh", True),
            "intent.run_validators": IntentProjection(
                "rig.intent.run_validators",
                "Run Validators",
                run_validators_enabled,
                target={"workspace_id": ws_id},
                disabled_reason=run_validators_disabled_reason
            ),
            "intent.chat.submit": IntentProjection("rig.intent.chat.submit", "Send", True),
            "intent.apply_patch": IntentProjection("rig.intent.apply_patch", "Apply Patch", False, disabled_reason="Requires validation and approval.")
        }
    )

def _build_empty_projection(
    revision: int,
    chat: Optional[ChatProjection],
    jobs,
    workspaces,
    providers,
    repo_root: Optional[Path] = None,
) -> UIProjection:
    repo_root = repo_root or Path.cwd()
    return UIProjection(
        revision=revision,
        generated_at=utc_now(),
        screen="empty_workspace",
        shell={"title": "Rig", "subtitle": "Local agent governance", "state": {"label": "No active workspace", "severity": "idle"}},
        chat=chat,
        layout=ProjectionLayout({
            "header": ["app.title", "next.gate", "workspace.header"],
            "sidebar": ["queue.summary", "workspace.git_state"],
            "main": ["workspace.empty", "workspace.lane_summary"],
            "inspector": ["evidence.current", "evidence.receipts"],
            "footer": ["backend.status"]
        }),
        widgets={
            "app.title": WidgetProjection("AppTitle", "app.title", {"title": "Rig", "subtitle": "Local agent governance"}),
            "next.gate": WidgetProjection("GateBadge", "next.gate", {"label": "No active gate", "severity": "idle"}),
            "workspace.header": _workspace_header_widget(repo_root, None),
            "workspace.git_state": _workspace_git_state_widget(repo_root),
            "workspace.lane_summary": _workspace_lane_summary_widget(workspaces),
            "queue.summary": WidgetProjection("MetricStack", "queue.summary", {
                "title": "Queue",
                "items": [
                    {"label": "Jobs indexed", "value": jobs, "severity": "info"},
                    {"label": "Active workspaces", "value": workspaces, "severity": "idle"},
                    {"label": "Providers available", "value": providers, "severity": "attention"}
                ]
            }),
            "workspace.empty": WidgetProjection(
                "EmptyStateCard", "workspace.empty",
                {"title": "No workspace is active", "body": "Open or initialize a repository to begin governed work. Use the agent lane helper for current lane operations."},
                actions=["intent.open_workspace", "intent.initialize_current_folder", "intent.refresh_projection"]
            ),
            "evidence.current": WidgetProjection("EvidenceCard", "evidence.current", {
                "title": "Evidence",
                "state": {"label": "No active workspace", "severity": "idle"},
                "body": "Evidence appears after Rig opens a governed workspace."
            }),
            "evidence.receipts": WidgetProjection("ReceiptList", "evidence.receipts", {
                "title": "Receipts",
                "receipts": []
            }),
            "backend.status": WidgetProjection("BackendStatus", "backend.status", {
                "title": "Native bridge",
                "body": "pywebview · WebSocket streaming",
                "revision": revision
            })
        },
        intents={
            "intent.refresh_projection": IntentProjection("rig.intent.refresh_projection", "Refresh", True),
            "intent.chat.submit": IntentProjection("rig.intent.chat.submit", "Send", True),
            "intent.open_workspace": IntentProjection(
                "rig.intent.open_workspace",
                "Open Repository",
                False,
                disabled_reason="Select or enter a repository path before continuing.",
            ),
            "intent.initialize_current_folder": IntentProjection(
                "rig.intent.initialize_current_folder",
                "Initialize",
                False,
                disabled_reason="Repository path is required before initialization.",
            )
        }
    )
