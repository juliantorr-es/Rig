from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path
from rig.domain.projections import (
    UIProjection, WidgetProjection, IntentProjection, ProjectionLayout, 
    ChatProjection, ChatMessage, ValidatorStackProjection, ValidatorItem
)

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def build_projection(repo_root: Path, revision: int = 1, chat_history: Optional[List[ChatMessage]] = None) -> UIProjection:
    from rig.domain.workspace import WorkspaceDomain
    from rig_tools.tui_snapshot import load_snapshot
    from rig_tools.core.io import read_json

    domain = WorkspaceDomain(repo_root)
    snapshot = load_snapshot(repo_root)
    workspaces = domain.list_workspaces()
    
    # Simple heuristic for active workspace: the one most recently modified that isn't 'applied'
    active_ws = None
    for ws in sorted(workspaces, key=lambda x: x.get("status_history", [{"at": "" }])[-1]["at"], reverse=True):
        if ws.get("status") != "applied":
            active_ws = ws
            break

    jobs_count = len(snapshot.get("jobs", []))
    workspaces_count = len([w for w in workspaces if w.get("status") != "applied"])
    providers_count = len(snapshot.get("providers", []))
    
    chat = None
    if chat_history is not None:
        chat = ChatProjection(messages=chat_history)

    if not active_ws:
        return _build_empty_projection(revision, chat, jobs_count, workspaces_count, providers_count)

    ws_id = active_ws["workspace_id"]
    status = active_ws.get("status", "unknown")
    
    # Build Validator Stack
    val_items = []
    val_status = {"label": "Missing", "severity": "idle"}
    val_summary = "No validation performed yet."
    
    val_path = active_ws.get("validation_result_path")
    if val_path and Path(val_path).exists():
        val_data = read_json(Path(val_path))
        status_map = {"passed": "success", "failed": "danger", "warning": "attention"}
        val_status = {
            "label": val_data.get("status", "unknown").capitalize(),
            "severity": status_map.get(val_data.get("status"), "info")
        }
        passed = len([v for v in val_data.get("validators", []) if v.get("exit_code") == 0])
        total = len(val_data.get("validators", []))
        val_summary = f"{passed} passed · {total - passed} failed"
        
        for v in val_data.get("validators", []):
            val_items.append(ValidatorItem(
                id=v.get("validator_id"),
                label=v.get("validator_id"),
                state="passed" if v.get("exit_code") == 0 else "failed",
                detail=v.get("stderr_tail") if v.get("exit_code") != 0 else None
            ))
    else:
        # Show what validators are configured even if not run
        for v_cfg in domain.read_validator_config():
            val_items.append(ValidatorItem(
                id=v_cfg.get("id") or v_cfg["argv"][0],
                label=v_cfg.get("id") or v_cfg["argv"][0],
                state="missing"
            ))

    widgets = {
        "app.title": WidgetProjection("AppTitle", "app.title", {"title": "Rig", "subtitle": f"Workspace: {ws_id}"}),
        "next.gate": WidgetProjection("GateBadge", "next.gate", {"label": f"Status: {status}", "severity": "info" if status == "validated" else "attention"}),
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
            "items": [asdict(i) for i in val_items]
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
        "backend.status": WidgetProjection("BackendStatus", "backend.status", {
            "title": "Native bridge",
            "body": "pywebview · WebSocket streaming",
            "revision": revision
        })
    }

    return UIProjection(
        revision=revision,
        generated_at=utc_now(),
        screen="active_run",
        shell={"title": "Rig", "subtitle": f"Workspace {ws_id}"},
        chat=chat,
        layout=ProjectionLayout({
            "header": ["app.title", "next.gate"],
            "sidebar": ["queue.summary"],
            "main": ["workspace.info", "validator.stack"],
            "inspector": ["evidence.current"],
            "footer": ["backend.status"]
        }),
        widgets=widgets,
        intents={
            "intent.refresh_projection": IntentProjection("rig.intent.refresh_projection", "Refresh", True),
            "intent.run_validators": IntentProjection("rig.intent.run_validators", "Run Validators", True, target={"workspace_id": ws_id}),
            "intent.chat.submit": IntentProjection("rig.intent.chat.submit", "Send", True),
            "intent.apply_patch": IntentProjection("rig.intent.apply_patch", "Apply Patch", False, disabled_reason="Requires validation and approval.")
        }
    )

def _build_empty_projection(revision: int, chat: Optional[ChatProjection], jobs, workspaces, providers) -> UIProjection:
    return UIProjection(
        revision=revision,
        generated_at=utc_now(),
        screen="empty_workspace",
        shell={"title": "Rig", "subtitle": "Local agent governance", "state": {"label": "No active workspace", "severity": "idle"}},
        chat=chat,
        layout=ProjectionLayout({
            "header": ["app.title", "next.gate"],
            "sidebar": ["queue.summary"],
            "main": ["workspace.empty"],
            "inspector": ["evidence.current"],
            "footer": ["backend.status"]
        }),
        widgets={
            "app.title": WidgetProjection("AppTitle", "app.title", {"title": "Rig", "subtitle": "Local agent governance"}),
            "next.gate": WidgetProjection("GateBadge", "next.gate", {"label": "No active gate", "severity": "idle"}),
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
                {"title": "No workspace is active", "body": "Open or initialize a repository to begin governed work."},
                actions=["intent.open_workspace", "intent.initialize_current_folder", "intent.refresh_projection"]
            ),
            "evidence.current": WidgetProjection("EvidenceCard", "evidence.current", {
                "title": "Evidence",
                "state": {"label": "No active workspace", "severity": "idle"},
                "body": "Evidence appears after Rig opens a governed workspace."
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
            "intent.open_workspace": IntentProjection("rig.intent.open_workspace", "Open Repository", False, disabled_reason="Not implemented."),
            "intent.initialize_current_folder": IntentProjection("rig.intent.initialize_current_folder", "Initialize", False, disabled_reason="Not implemented.")
        }
    )

from dataclasses import asdict
