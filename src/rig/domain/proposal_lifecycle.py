from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from rig.domain.agent_workflow_gates import GATE_A_POLICY
from rig.domain.workspace_status import WorkspaceStatusSummary, build_workspace_status_summary

LIFECYCLE_STAGES = (
    "workspace_unselected",
    "workspace_ready",
    "gate_a_active",
    "recommendation_available",
    "proposal_pending",
    "validation_pending",
    "validation_passed",
    "validation_failed",
    "review_ready",
    "apply_blocked",
    "apply_available_future",
)


@dataclass(frozen=True, slots=True)
class LifecycleAction:
    id: str
    label: str
    enabled: bool = True
    description: str = ""


@dataclass(frozen=True, slots=True)
class LifecycleBlockedAction:
    id: str
    label: str
    reason: str


@dataclass(frozen=True, slots=True)
class LifecycleStateBadge:
    label: str
    severity: str = "info"


@dataclass(frozen=True, slots=True)
class ProposalLifecycleProjection:
    lifecycle_id: str
    stage: str
    title: str
    summary: str
    workspace_path: Optional[str] = None
    current_gate: str = "A"
    allowed_actions: tuple[LifecycleAction, ...] = ()
    blocked_actions: tuple[LifecycleBlockedAction, ...] = ()
    next_safe_action: str = ""
    recommendation_state: dict[str, Any] = field(default_factory=dict)
    proposal_state: dict[str, Any] = field(default_factory=dict)
    validation_state: dict[str, Any] = field(default_factory=dict)
    progress_state: dict[str, Any] = field(default_factory=dict)
    auditability_state: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _gate_a_allowed_actions() -> tuple[LifecycleAction, ...]:
    return tuple(
        LifecycleAction(
            id=operation,
            label=operation.removeprefix("rig.intent.").replace("_", " ").title(),
            description="Gate A allowed action",
        )
        for operation in GATE_A_POLICY.allowed_operations
        if operation.startswith("rig.intent.")
    )


def _gate_a_blocked_actions() -> tuple[LifecycleBlockedAction, ...]:
    return tuple(
        LifecycleBlockedAction(
            id=operation,
            label=operation.removeprefix("rig.intent.").replace("_", " ").title()
            if operation.startswith("rig.intent.")
            else operation,
            reason="Blocked by Dogfood Gate A",
        )
        for operation in GATE_A_POLICY.blocked_operations
    )


def build_proposal_lifecycle_projection(
    repo_root: Path,
    *,
    workspace_path: Optional[str] = None,
    active_workspace: bool = False,
    workspace_status: Optional[str] = None,
    workspace_summary: Optional[WorkspaceStatusSummary] = None,
    recommendation_state: Optional[dict[str, Any]] = None,
    proposal_state: Optional[dict[str, Any]] = None,
    validation_state: Optional[dict[str, Any]] = None,
    progress_state: Optional[dict[str, Any]] = None,
    auditability_state: Optional[dict[str, Any]] = None,
) -> ProposalLifecycleProjection:
    # Prefer explicit workspace_summary, fall back to building one
    if workspace_summary is None and (workspace_path or workspace_status or active_workspace):
        workspace_summary = build_workspace_status_summary(
            repo_root,
            workspace_record={
                "workspace_id": None,
                "status": workspace_status,
                "worktree_path": workspace_path,
            }
            if workspace_path or workspace_status or active_workspace
            else None,
        )

    # Use workspace_summary for canonical identity if available
    summary_workspace_path = workspace_path
    summary_active_workspace = active_workspace
    if workspace_summary:
        summary_workspace_path = workspace_summary.workspace_path
        summary_active_workspace = workspace_summary.selected
        # Update status from workspace_summary if available
        if workspace_summary.status != "unselected":
            active_workspace = workspace_summary.selected
            workspace_status = workspace_summary.status

    stage = "gate_a_active" if summary_active_workspace else "workspace_unselected"
    if workspace_summary and workspace_summary.workspace_path and not workspace_summary.selected:
        stage = "workspace_ready"
    if workspace_summary and workspace_summary.status == "review_ready":
        stage = "review_ready"

    title = "Proposal Lifecycle Console"
    summary = (
        "Dogfood Gate A is active. Read-only workspace status, projection, and progress are visible; "
        "apply-to-main remains blocked."
        if summary_active_workspace
        else "Select a workspace to inspect proposal lifecycle state."
    )
    next_safe_action = "Inspect workspace status and review recommendation."
    allowed_actions = _gate_a_allowed_actions()
    blocked_actions = _gate_a_blocked_actions()

    return ProposalLifecycleProjection(
        lifecycle_id="workspace.proposal_lifecycle",
        stage=stage,
        title=title,
        summary=summary,
        workspace_path=summary_workspace_path,
        current_gate=GATE_A_POLICY.gate,
        allowed_actions=allowed_actions,
        blocked_actions=blocked_actions,
        next_safe_action=next_safe_action,
        recommendation_state=recommendation_state or {"status": "unknown", "summary": "No recommendation has been projected yet."},
        proposal_state=proposal_state or {"status": "not_created", "summary": "No proposal has been projected yet."},
        validation_state=validation_state or {
            "status": "not_run",
            "summary": "No validation summary has been projected yet.",
            "proof_status": "not_proof",
        },
        progress_state=progress_state or {"transient": True, "source": "progress_event"},
        auditability_state=auditability_state or {
            "progress_receipts": "not_created",
            "progress_receipt_plan": "advisory_only",
            "receipt_candidate": "inert",
            "evidence_refs": "inert",
        },
        warnings=(
            "Progress telemetry is transient.",
            "ProgressReceiptPlan is advisory-only.",
            "receipt_candidate is inert.",
            "evidence_refs are inert.",
        ),
        metadata={
            "gate_policy": {
                "allowed": GATE_A_POLICY.allowed_operations,
                "blocked": GATE_A_POLICY.blocked_operations,
            },
            "workflow_summary": {
                "workspace": workspace_summary.to_dict() if workspace_summary else {},
            },
            "repo_root": str(repo_root),
        },
    )
