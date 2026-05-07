from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rig.domain.workspace import WORKSPACE_STATUSES, WorkspaceDomain
from rig.domain.agent_workflow_gates import GATE_A_POLICY


def _git_capture(repo_root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, text=True, check=False)
    return (proc.stdout or "").strip()


def _legacy_workspace_dir(repo_root: Path) -> Path:
    return repo_root / ".build" / "rig" / "workspaces"


def _legacy_workspace_records(repo_root: Path) -> list[dict]:
    workspace_dir = _legacy_workspace_dir(repo_root)
    if not workspace_dir.exists():
        return []
    records: list[dict] = []
    for path in sorted(workspace_dir.glob("*.json")):
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return records


def _recent_receipt_files(repo_root: Path, limit: int = 10) -> list[Path]:
    receipt_dir = repo_root / ".build" / "rig" / "receipts"
    if not receipt_dir.exists():
        return []
    files = sorted(receipt_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def _gate_a_note() -> dict:
    return {
        "current_dogfood_gate": GATE_A_POLICY.gate,
        "allowed": [
            "read-only workspace status/projection/progress",
            "review/recommend",
            "isolated proposal-shaped workflows",
        ],
        "blocked": [
            "direct main writes",
            "autonomous apply",
            "progress-as-proof",
            "progress persistence",
            "receipt creation from progress",
        ],
        "progress_is_transient": True,
        "receipts_created_from_progress": False,
    }


def register(subparsers, helpers):
    parser = subparsers.add_parser("workspace", help="Manage Rig workspaces")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("status", help="Read-only workspace control-plane status").set_defaults(handler=lambda args: status(helpers))
    sub.add_parser("lanes", help="Read-only workspace lane summary").set_defaults(handler=lambda args: lanes(helpers))
    sub.add_parser("projection", help="Read-only workspace projection placeholder").set_defaults(handler=lambda args: projection(helpers))
    sub.add_parser("receipts", help="Read-only workspace receipt summary").set_defaults(handler=lambda args: receipts(helpers))
    sub.add_parser("recommend", help="Read-only workspace next-step recommendation").set_defaults(handler=lambda args: recommend(helpers))

    create = sub.add_parser("create", help="Create workspace")
    create.add_argument("--task", required=True)
    create.set_defaults(handler=lambda args: create_workspace(helpers, args.task))

    sub.add_parser("list", help="List workspaces").set_defaults(handler=lambda args: list_workspaces(helpers))
    review = sub.add_parser("review", help="Generate review bundle")
    review.add_argument("workspace_id")
    review.set_defaults(handler=lambda args: review_workspace(helpers, args.workspace_id))
    apply_cmd = sub.add_parser("apply", help="Apply workspace")
    apply_cmd.add_argument("workspace_id")
    apply_cmd.set_defaults(handler=lambda args: apply_workspace(helpers, args.workspace_id))
    transition = sub.add_parser("transition", help="Transition workspace status")
    transition.add_argument("workspace_id")
    transition.add_argument("status", choices=WORKSPACE_STATUSES)
    transition.set_defaults(handler=lambda args: transition_workspace(helpers, args.workspace_id, args.status))


def status(helpers):
    records = _legacy_workspace_records(helpers.repo_root)
    payload = {
        "repo_root": str(helpers.repo_root),
        "control_plane": "planned",
        "workspace_records": len(records),
        "agent_lane_registry": "not_connected",
        "current_branch": _git_capture(helpers.repo_root, "branch", "--show-current") or "HEAD",
        "current_head": _git_capture(helpers.repo_root, "rev-parse", "--short", "HEAD"),
        "next_action": "Use scripts/rig_agent_worktree.py review/recommend for governed agent lanes.",
        "dogfood_gate": _gate_a_note(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def lanes(helpers):
    records = _legacy_workspace_records(helpers.repo_root)
    payload = {
        "repo_root": str(helpers.repo_root),
        "workspace_records": len(records),
        "agent_lane_registry": "not_connected",
        "message": "Workspace lane integration is not connected yet. This command only reports legacy workspace records.",
        "workspaces": [
            {
                "workspace_id": ws.get("workspace_id"),
                "task": ws.get("task"),
                "status": ws.get("status"),
                "branch": ws.get("branch"),
                "worktree_path": ws.get("worktree_path"),
            }
            for ws in records
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def projection(helpers):
    payload = {
        "revision": 1,
        "screen": "workspace_control_plane_placeholder",
        "widgets": {
            "workspace.header": {
                "type": "WorkspaceHeader",
                "actions": ["intent.refresh_projection"],
            },
            "workspace.git_state": {
                "type": "WorkspaceGitState",
                "actions": ["intent.refresh_projection"],
            },
            "workspace.lane_summary": {
                "type": "WorkspaceLaneSummary",
                "actions": ["intent.refresh_projection"],
            },
            "workspace.proposal_lifecycle": {
                "type": "ProposalLifecycleConsole",
                "actions": ["intent.refresh_projection"],
            },
            "workspace.command_progress": {
                "type": "CommandProgressCard",
                "actions": ["intent.refresh_projection"],
            },
        },
        "intents": ["intent.refresh_projection"],
        "message": "Workspace projection is currently a backend-authored placeholder; agent lane integration is future work.",
        "controls": {
            "repo_root": str(helpers.repo_root),
            "current_branch": _git_capture(helpers.repo_root, "branch", "--show-current") or "HEAD",
            "current_head": _git_capture(helpers.repo_root, "rev-parse", "--short", "HEAD"),
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def receipts(helpers):
    recent = _recent_receipt_files(helpers.repo_root)
    payload = {
        "repo_root": str(helpers.repo_root),
        "receipt_count": len(recent),
        "message": "Workspace receipts are part of the governed control plane; lane-specific receipts are future work.",
        "receipts": [path.name for path in recent],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def recommend(helpers):
    payload = {
        "repo_root": str(helpers.repo_root),
        "control_plane": "planned",
        "recommended_path": "review",
        "ready": False,
        "rationale": "Workspace lane integration is not connected yet. Use scripts/rig_agent_worktree.py review/recommend for governed agent lanes.",
        "next_safe_action": "Review governed agent lane docs and use the agent worktree helper for lane operations.",
        "workspace_records": len(_legacy_workspace_records(helpers.repo_root)),
        "dogfood_gate": _gate_a_note(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def create_workspace(helpers, task):
    domain = WorkspaceDomain(helpers.repo_root)
    record = domain.create_workspace(task)
    print(f"Created workspace: {record.path}")
    return 0


def list_workspaces(helpers):
    domain = WorkspaceDomain(helpers.repo_root)
    for ws in domain.list_workspaces():
        print(f"{ws['workspace_id']} - {ws['task']} ({ws['status']}) {ws.get('branch', '')}")
    return 0


def review_workspace(helpers, workspace_id):
    domain = WorkspaceDomain(helpers.repo_root)
    bundle = domain.build_review_bundle(workspace_id)
    print(bundle["workspace_id"], bundle["apply_eligibility"])
    return 0


def apply_workspace(helpers, workspace_id):
    domain = WorkspaceDomain(helpers.repo_root)
    payload = domain.apply_workspace(workspace_id)
    print(payload["receipt_id"], payload["status"])
    return 0


def transition_workspace(helpers, workspace_id, status):
    domain = WorkspaceDomain(helpers.repo_root)
    payload = domain.transition_workspace(workspace_id, status)
    print(payload["workspace_id"], payload["status"])
    return 0
