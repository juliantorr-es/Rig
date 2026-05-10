from dataclasses import asdict, replace
from datetime import datetime, timezone
import subprocess
from typing import Any, List, Optional
import importlib
from pathlib import Path
from rig.domain.projections import (
    UIProjection, WidgetProjection, IntentProjection, ProjectionLayout,
    ChatProjection, ChatMessage, ValidatorItem
)
from rig.domain.proposal_lifecycle import build_proposal_lifecycle_projection
from rig.domain.workspace_status import WorkspaceStatusSummary, build_workspace_status_summary, list_workspaces_read_only
from rig.domain.receipts import get_receipt_store
from rig.domain.workspace_audit import (
    build_auditability_state,
    WorkspaceAuditTrail,
    PLACEHOLDER_UNKNOWN,
    PLACEHOLDER_NOT_CREATED,
)
from rig.domain.git_helper import get_git_info

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _compute_integrity_status(
    repo_root: Path,
    projection_data: Optional[dict] = None,
) -> dict[str, Any]:
    """Compute integrity status data for the projection.
    
    Returns a dict with:
    - integrity_status
    - contract_status
    - projection_violation_count
    - authority_mismatch_count
    - receipt_backing_failure_count
    - audit_backing_failure_count
    - next_integrity_action
    - stale_receipt_detected
    - orphaned_receipt_detected
    - orphaned_audit_detected
    
    Pure function: no file writes, no mutation.
    """
    try:
        from rig.domain.integrity import validate_repository_integrity
        from rig.domain.projection_contracts import build_projection_contract_summary
        
        # Get repository-level integrity
        repo_integrity = validate_repository_integrity(repo_root)
        
        # Build projection contract summary if projection_data is available
        if projection_data is not None:
            contract_summary = build_projection_contract_summary(projection_data, repo_root)
            projection_violation_count = contract_summary.total_violations
            authority_binding_failures = contract_summary.authority_binding_failures
            receipt_backing_failures = contract_summary.receipt_backing_failures
            audit_backing_failures = contract_summary.audit_backing_failures
            placeholder_violations = contract_summary.placeholder_violations
        else:
            projection_violation_count = 0
            authority_binding_failures = 0
            receipt_backing_failures = 0
            audit_backing_failures = 0
            placeholder_violations = 0
        
        # Determine integrity status from repository integrity
        integrity_status = repo_integrity.overall_status
        
        # Determine contract status
        if projection_violation_count > 0:
            contract_status = "violations_found"
        elif projection_violation_count == 0 and contract_summary.total_contracts > 0:
            contract_status = "all_passed"
        else:
            contract_status = "unknown"
        
        # Detect stale/orphaned items from repository integrity
        stale_receipt_detected = False
        orphaned_receipt_detected = False
        orphaned_audit_detected = False
        
        # Check for specific violation codes in repo integrity
        for finding in repo_integrity.all_findings:
            if hasattr(finding, 'violation_code'):
                code = finding.violation_code.value if hasattr(finding.violation_code, 'value') else str(finding.violation_code)
                if 'STALE' in code or 'STALE_' in code:
                    stale_receipt_detected = True
                if 'ORPHANED_RECEIPT' in code:
                    orphaned_receipt_detected = True
                if 'ORPHANED_AUDIT' in code:
                    orphaned_audit_detected = True
        
        # Build next integrity action
        actions = []
        if stale_receipt_detected:
            actions.append("Review stale receipts")
        if orphaned_receipt_detected:
            actions.append("Remove orphaned receipts")
        if orphaned_audit_detected:
            actions.append("Remove orphaned audit events")
        if projection_violation_count > 0:
            actions.append("Review projection contract violations")
        if authority_binding_failures > 0:
            actions.append("Fix authority binding failures")
        if receipt_backing_failures > 0:
            actions.append("Create missing receipts")
        if audit_backing_failures > 0:
            actions.append("Create missing audit events")
        
        if actions:
            next_integrity_action = "; ".join(actions)
        else:
            next_integrity_action = "No integrity issues detected"
        
        # Check if any receipts are stale by scanning receipt directory
        try:
            receipt_dir = repo_root / ".build" / "rig" / "receipts"
            if receipt_dir.exists():
                from rig.domain.receipts import get_receipt_store
                store = get_receipt_store(repo_root)
                receipts = store.list(limit=100)
                # Check for stale receipts (this is a simplified check)
                # Full stale detection is handled by integrity validation
                pass
        except Exception:
            pass
        
        return {
            "integrity_status": integrity_status,
            "contract_status": contract_status,
            "projection_violation_count": projection_violation_count,
            "authority_mismatch_count": authority_binding_failures,
            "receipt_backing_failure_count": receipt_backing_failures,
            "audit_backing_failure_count": audit_backing_failures,
            "next_integrity_action": next_integrity_action,
            "stale_receipt_detected": stale_receipt_detected,
            "orphaned_receipt_detected": orphaned_receipt_detected,
            "orphaned_audit_detected": orphaned_audit_detected,
        }
    except Exception:
        # Fallback to safe defaults
        return {
            "integrity_status": "unknown",
            "contract_status": "unknown",
            "projection_violation_count": 0,
            "authority_mismatch_count": 0,
            "receipt_backing_failure_count": 0,
            "audit_backing_failure_count": 0,
            "next_integrity_action": "Integrity status unavailable",
            "stale_receipt_detected": False,
            "orphaned_receipt_detected": False,
            "orphaned_audit_detected": False,
        }


def _integrity_status_widget(
    repo_root: Path,
    integrity_data: dict[str, Any],
    revision: int,
) -> WidgetProjection:
    """Create IntegrityStatusCard widget with integrity data."""
    return WidgetProjection(
        "IntegrityStatusCard",
        "integrity.status",
        {
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "integrity_status": integrity_data["integrity_status"],
            "contract_status": integrity_data["contract_status"],
            "projection_violation_count": integrity_data["projection_violation_count"],
            "authority_mismatch_count": integrity_data["authority_mismatch_count"],
            "receipt_backing_failure_count": integrity_data["receipt_backing_failure_count"],
            "audit_backing_failure_count": integrity_data["audit_backing_failure_count"],
            "next_integrity_action": integrity_data["next_integrity_action"],
            "stale_receipt_detected": integrity_data["stale_receipt_detected"],
            "orphaned_receipt_detected": integrity_data["orphaned_receipt_detected"],
            "orphaned_audit_detected": integrity_data["orphaned_audit_detected"],
        },
    )


def _git_capture(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
    return (proc.stdout or "").strip()


def _git_status_entries(repo_root: Path) -> list[str]:
    raw = _git_capture(repo_root, "status", "--porcelain=v1", "-z")
    return [entry for entry in raw.split("\0") if entry]


def _workspace_header_widget(repo_root: Path, workspace_summary: WorkspaceStatusSummary, revision: int) -> WidgetProjection:
    return WidgetProjection(
        "WorkspaceHeader",
        "workspace.header",
        {
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "repo_root": str(repo_root),
            "workspace_id": workspace_summary.workspace_id,
            "workspace_status": workspace_summary.status,
            "workspace_path": workspace_summary.workspace_path,
            "branch": workspace_summary.branch,
            "head": workspace_summary.head,
            "authority_label": "Workspace control plane (future lane registry)",
        },
    )


def _workspace_git_state_widget(repo_root: Path, revision: int) -> WidgetProjection:
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
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "branch": branch,
            "head": head,
            "dirty": dirty,
            "dirty_files_count": dirty_files_count,
            "safe_to_commit": safe_to_commit,
            "reason": reason,
        },
    )


def _workspace_lane_summary_widget(workspace_records: int, revision: int) -> WidgetProjection:
    connected = False
    return WidgetProjection(
        "WorkspaceLaneSummary",
        "workspace.lane_summary",
        {
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
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


def _workspace_command_progress_widget(revision: int) -> WidgetProjection:
    return WidgetProjection(
        "CommandProgressCard",
        "workspace.command_progress",
        {
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "command": "",
            "phase": "operation.log",
            "status": "unknown",
            "level": "info",
            "message": "No active command progress yet.",
            "sequence": 0,
            "timestamp": utc_now(),
            "events": [],
            "metadata": {},
        },
    )


def _build_receipt_list_projection(repo_root: Path):
    """Build a small receipt list projection for receipt-focused tests."""
    store = get_receipt_store(repo_root)
    receipts: list[Any] = []
    for receipt in store.list(limit=100):
        rid = getattr(receipt, "receipt_id", None) or getattr(receipt, "id", None)
        receipts.append(
            type(
                "ReceiptProjection",
                (),
                {
                    "id": rid,
                    "kind": getattr(receipt, "kind", ""),
                    "summary": getattr(receipt, "summary", "") or "",
                },
            )()
        )
    return type("ReceiptListProjection", (), {"title": "Receipt Log", "receipts": receipts})()


def _workspace_proposal_lifecycle_widget(
    repo_root: Path,
    active_ws: Optional[dict],
    workspace_summary: WorkspaceStatusSummary,
) -> WidgetProjection:
    lifecycle = build_proposal_lifecycle_projection(
        repo_root,
        workspace_summary=workspace_summary,
        workspace_path=workspace_summary.workspace_path if workspace_summary else None,
        active_workspace=workspace_summary.selected if workspace_summary else False,
    )
    return WidgetProjection("ProposalLifecycleConsole", "workspace.proposal_lifecycle", lifecycle.to_dict())


def _workspace_audit_trail_widget(
    repo_root: Path,
    active_ws: Optional[dict],
    workspace_summary: WorkspaceStatusSummary,
) -> WidgetProjection:
    """Build audit trail widget for workspace auditability projection.
    
    Dumb rendering only - data comes from backend projection.
    Pure function: no fetching, no authority decisions.
    """
    from rig.domain.workspace_audit import (
        PLACEHOLDER_UNKNOWN,
        PLACEHOLDER_NOT_CREATED,
        PLACEHOLDER_NO_RECEIPT,
    )
    
    # Build auditability state from filesystem evidence
    ws_id = (active_ws or {}).get("workspace_id") or None
    audit_dir = repo_root / ".build" / "rig" / "audit"
    
    # Count audit event files for this workspace
    authoritative_events = 0
    advisory_only_events = 0
    missing_receipts: list[str] = []
    last_event_id = None
    
    if ws_id and audit_dir.exists():
        # Count files matching workspace patterns
        patterns = [
            f"ws_create_{ws_id}.json",
            f"ws_apply_{ws_id}.json",
        ]
        # Also try transition patterns
        for path in audit_dir.iterdir():
            if path.is_file() and path.suffix == ".json":
                name = path.name
                if name.startswith(f"ws_create_{ws_id}"):
                    authoritative_events += 1
                    last_event_id = name.replace(".json", "")
                elif name.startswith(f"ws_apply_{ws_id}"):
                    authoritative_events += 1
                    last_event_id = name.replace(".json", "")
                elif name.startswith(f"ws_trans_{ws_id}"):
                    authoritative_events += 1
                    last_event_id = name.replace(".json", "")
    
    # Determine completeness
    if authoritative_events == 0:
        audit_completeness = PLACEHOLDER_NOT_CREATED
    elif authoritative_events >= 2:
        audit_completeness = "complete"
    else:
        audit_completeness = "not_proof"
    
    # Check for any workspace files as fallback
    receipt_dir = repo_root / ".build" / "rig" / "receipts"
    workspace_receipts = list(receipt_dir.glob(f"{ws_id}_*.json")) if ws_id else []
    public_intake_receipts = list((repo_root / ".build" / "rig" / "public_intake" / "receipts").glob("*.json"))
    
    return WidgetProjection(
        "AuditTrailCard",
        "workspace.audit_trail",
        {
            "audit_completeness": audit_completeness,
            "last_authoritative_event_id": last_event_id or PLACEHOLDER_UNKNOWN,
            "receipt_status_summary": {
                "workspace_receipts": len(workspace_receipts),
                "public_intake_receipts": len(public_intake_receipts),
            },
            "missing_receipts": missing_receipts,
            "advisory_only_events": advisory_only_events,
            "authoritative_events": authoritative_events,
            "advisory_only_warning": "Public intake and funding data is advisory_only. External systems are NOT authoritative.",
            "next_missing_audit_action": PLACEHOLDER_NO_RECEIPT,
        },
    )

def build_projection(repo_root: Path, revision: int = 1, chat_history: Optional[List[ChatMessage]] = None) -> UIProjection:
    from rig_tools.core.io import read_json

    # Try to load snapshot from gridline if available, otherwise use empty dict
    # tui_snapshot was retired with Textual TUI
    try:
        tui_snapshot = importlib.import_module("rig_tools.tui_snapshot")
        snapshot = tui_snapshot.load_snapshot(repo_root)
    except (ImportError, ModuleNotFoundError, AttributeError):
        snapshot = {}

    workspaces = list_workspaces_read_only(repo_root)
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

    workspace_summary = build_workspace_status_summary(repo_root, workspace_record=active_ws)

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
        # Use validator config from workspace_summary metadata if available
        # or read from pyproject.toml
        from rig.domain.workspace_status import read_validator_config
        validator_configs = read_validator_config(repo_root)
        for i, v_cfg in enumerate(validator_configs):
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

    git_info = get_git_info(repo_root)
    # Build projection data for integrity status computation
    # We need to construct the full projection dict to pass to contract validation
    projection_for_contract = {
        "revision": revision,
        "screen": "active_run",
        "widgets": {},
    }
    
    # Compute integrity status
    integrity_data = _compute_integrity_status(
        repo_root,
        projection_data=projection_for_contract,
    )
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

    widgets = {
        "app.title": WidgetProjection("AppTitle", "app.title", {
            "title": "Rig",
            "subtitle": "Governed control plane"
        }),
        "workspace.header": WidgetProjection("WorkspaceHeader", "workspace.header", {
            "repository": str(repo_root),
            "branch": git_info["branch"],
            "head": git_info["head"],
            "dirty_state": f"{len(git_info['dirty_files'])} uncommitted changes" if git_info["dirty"] else "clean",
            "workspace_status": status,
            "authority": "local backend projection"
        }),
        "git.state": WidgetProjection("GitStateCard", "git.state", {
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "branch": git_info["branch"],
            "head": git_info["head"],
            "dirty_files": git_info["dirty_files"],
            "safe_to_commit": not git_info["dirty"],
            "safe_to_commit_reason": "Working tree is dirty" if git_info["dirty"] else "Working tree clean"
        }),
        "next.gate": WidgetProjection("GateBadge", "next.gate", {"label": f"Status: {status}", "severity": "info" if status == "validated" else "attention"}),
        "workspace.header": _workspace_header_widget(repo_root, workspace_summary, revision),
        "workspace.git_state": _workspace_git_state_widget(repo_root, revision),
        "workspace.lane_summary": _workspace_lane_summary_widget(len(workspaces), revision),
        "workspace.proposal_lifecycle": _workspace_proposal_lifecycle_widget(repo_root, active_ws, workspace_summary),
        "workspace.audit_trail": _workspace_audit_trail_widget(repo_root, active_ws, workspace_summary),
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
        }),
        "intent.buttons": WidgetProjection("IntentButtonRow", "intent.buttons", {
            "title": "Available Actions"
        }, actions=["intent.run_validators", "intent.apply_patch", "intent.open_workspace"]),
        "workspace.info": WidgetProjection("EmptyStateCard", "workspace.info", {
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "title": f"Workspace {ws_id}",
            "body": f"Current status: {status}. Ready for validation or review."
        }, actions=["intent.refresh_projection", "intent.run_validators"]),
        "next.action": WidgetProjection("NextSafeActionCard", "next.action", {
            "action": "Run validators" if run_validators_enabled else "Review or apply workspace",
            "command": "rig ui --run-validators" if run_validators_enabled else "rig proposal apply",
            "why": run_validators_disabled_reason or "Validators have not been run on this state."
        }),
        "evidence.current": WidgetProjection("EvidenceCard", "evidence.current", {
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "title": "Evidence",
            "state": {"label": "Available" if val_path else "None", "severity": "info" if val_path else "idle"},
            "body": f"Evidence for {ws_id}."
        }),
        "evidence.receipts": WidgetProjection("ReceiptList", "evidence.receipts", {
            "title": "Receipts",
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "receipts": [
                replace(r.to_projection(), projection_revision=revision)
                for r in recent_receipts
            ] if recent_receipts else []
        }),
        "workspace.command_progress": _workspace_command_progress_widget(revision),
        "backend.status": WidgetProjection("BackendStatus", "backend.status", {
            "title": "Native bridge",
            "body": "pywebview · WebSocket streaming",
            "schema_version": "rig.ui.projection.v1",
            "revision": revision
        }),
        "integrity.status": _integrity_status_widget(repo_root, integrity_data, revision),
    }
    
    return UIProjection(
        revision=revision,
        generated_at=utc_now(),
        screen="active_run",
        shell={"title": "Rig", "subtitle": f"Workspace {ws_id}"},
        chat=chat,
        layout=ProjectionLayout({
            "header": ["workspace.header", "next.gate", "intent.buttons"],
            "sidebar": ["git.state", "queue.summary", "next.action"],
            "main": ["validator.stack", "workspace.info"],
            "inspector": ["evidence.current", "evidence.receipts"],
            "footer": ["workspace.command_progress", "backend.status"]
        }),
        widgets=widgets,
        intents={
            "intent.refresh_projection": IntentProjection("rig.intent.refresh_projection", "Refresh", True),
            "intent.workspace_status": IntentProjection("rig.intent.workspace_status", "Workspace Status", True),
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
    
    # Compute integrity status for empty projection
    projection_for_contract = {
        "revision": revision,
        "screen": "empty_workspace",
        "widgets": {},
    }
    integrity_data = _compute_integrity_status(
        repo_root,
        projection_data=projection_for_contract,
    )
    
    widgets = {
        "app.title": WidgetProjection("AppTitle", "app.title", {
            "title": "Rig",
            "subtitle": "Governed control plane"
        }),
        "workspace.header": WidgetProjection("WorkspaceHeader", "workspace.header", {
            "repository": "None",
            "branch": "N/A",
            "head": "N/A",
            "dirty_state": "N/A",
            "workspace_status": "No active workspace",
            "authority": "local backend projection"
        }),
        "next.gate": WidgetProjection("GateBadge", "next.gate", {"label": "No active gate", "severity": "idle"}),
        "workspace.header": _workspace_header_widget(repo_root, build_workspace_status_summary(repo_root), revision),
        "workspace.git_state": _workspace_git_state_widget(repo_root, revision),
        "workspace.lane_summary": _workspace_lane_summary_widget(workspaces, revision),
        "workspace.proposal_lifecycle": _workspace_proposal_lifecycle_widget(
            repo_root,
            None,
            build_workspace_status_summary(repo_root),
        ),
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
            {
                "schema_version": "rig.ui.projection.v1",
                "projection_revision": revision,
                "title": "No workspace is active",
                "body": "Open or initialize a repository to begin governed work. Use the agent lane helper for current lane operations.",
            },
            actions=["intent.open_workspace", "intent.initialize_current_folder", "intent.refresh_projection"]
        ),
        "evidence.current": WidgetProjection("EvidenceCard", "evidence.current", {
            "schema_version": "rig.ui.projection.v1",
            "projection_revision": revision,
            "title": "Evidence",
            "state": {"label": "No active workspace", "severity": "idle"},
            "body": "Evidence appears after Rig opens a governed workspace."
        }),
            "evidence.receipts": WidgetProjection("ReceiptList", "evidence.receipts", {
                "title": "Receipts",
                "schema_version": "rig.ui.projection.v1",
                "projection_revision": revision,
                "receipts": []
            }),
        "workspace.command_progress": _workspace_command_progress_widget(revision),
        "backend.status": WidgetProjection("BackendStatus", "backend.status", {
            "title": "Native bridge",
            "body": "pywebview · WebSocket streaming",
            "schema_version": "rig.ui.projection.v1",
            "revision": revision
        }),
        "integrity.status": _integrity_status_widget(repo_root, integrity_data, revision),
    }
    
    return UIProjection(
        revision=revision,
        generated_at=utc_now(),
        screen="empty_workspace",
        shell={"title": "Rig", "subtitle": "Local agent governance", "state": {"label": "No active workspace", "severity": "idle"}},
        chat=chat,
        layout=ProjectionLayout({
            "header": ["app.title", "workspace.header", "next.gate"],
            "sidebar": ["queue.summary"],
            "main": ["workspace.empty"],
            "inspector": ["evidence.current", "evidence.receipts"],
            "footer": ["workspace.command_progress", "backend.status", "integrity.status"]
        }),
        widgets={
            "app.title": WidgetProjection("AppTitle", "app.title", {
                "title": "Rig",
                "subtitle": "Governed control plane"
            }),
            "workspace.header": WidgetProjection("WorkspaceHeader", "workspace.header", {
                "repository": "None",
                "branch": "N/A",
                "head": "N/A",
                "dirty_state": "N/A",
                "workspace_status": "No active workspace",
                "authority": "local backend projection"
            }),
            "next.gate": WidgetProjection("GateBadge", "next.gate", {"label": "No active gate", "severity": "idle"}),
            "workspace.header": _workspace_header_widget(repo_root, build_workspace_status_summary(repo_root), revision),
            "workspace.git_state": _workspace_git_state_widget(repo_root, revision),
            "workspace.lane_summary": _workspace_lane_summary_widget(workspaces, revision),
            "workspace.proposal_lifecycle": _workspace_proposal_lifecycle_widget(
                repo_root,
                None,
                build_workspace_status_summary(repo_root),
            ),
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
                "schema_version": "rig.ui.projection.v1",
                "projection_revision": revision,
                "title": "Evidence",
                "state": {"label": "No active workspace", "severity": "idle"},
                "body": "Evidence appears after Rig opens a governed workspace."
            }),
            "evidence.receipts": WidgetProjection("ReceiptList", "evidence.receipts", {
                "title": "Receipts",
                "receipts": []
            }),
            "workspace.command_progress": _workspace_command_progress_widget(revision),
            "backend.status": WidgetProjection("BackendStatus", "backend.status", {
                "title": "Native bridge",
                "body": "pywebview · WebSocket streaming",
                "revision": revision
            }),
            "integrity.status": _integrity_status_widget(repo_root, integrity_data, revision),
        },
        intents={
            "intent.refresh_projection": IntentProjection("rig.intent.refresh_projection", "Refresh", True),
            "intent.workspace_status": IntentProjection("rig.intent.workspace_status", "Workspace Status", True),
            "intent.chat.submit": IntentProjection("rig.intent.chat.submit", "Send", True),
            "intent.open_workspace": IntentProjection(
                "rig.intent.open_workspace",
                "Open Repository",
                False,
                disabled_reason="Select or enter a repository path manually before continuing.",
            ),
            "intent.initialize_current_folder": IntentProjection(
                "rig.intent.initialize_current_folder",
                "Initialize",
                False,
                disabled_reason="Repository path is required before initialization from the browser or manual path.",
            )
        }
    )
