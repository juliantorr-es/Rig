from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
)


# ---------------------------------------------------------------------------
# Normalized lifecycle summary models (pure, deterministic, no side effects)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecommendationSummary:
    """Normalized recommendation state from workspace data.

    Pure data model built from WorkspaceStatusSummary and workspace records.
    No file writes, no database, no receipt creation, no progress persistence.
    """

    status: str
    title: str
    summary: str
    source_surface: str
    files: tuple[str, ...] = ()
    last_updated: Optional[str] = None
    next_action: str = ""


@dataclass(frozen=True, slots=True)
class ProposalSummary:
    """Normalized proposal state from workspace data.

    Pure data model built from WorkspaceStatusSummary and workspace records.
    No file writes, no database, no receipt creation, no progress persistence.
    """

    status: str
    title: str
    summary: str
    worktree_path: Optional[str] = None
    changed_files: tuple[str, ...] = ()
    next_action: str = ""


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Normalized validation state from workspace data.

    Pure data model built from WorkspaceStatusSummary and workspace records.
    No file writes, no database, no receipt creation, no progress persistence.
    """

    status: str
    title: str
    summary: str
    surface: str
    command: str = ""
    passed_count: int = 0
    failed_count: int = 0
    last_run_at: Optional[str] = None
    proof_status: str = "not_proof"
    next_action: str = ""


# ---------------------------------------------------------------------------
# Lifecycle action models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Main projection model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProposalLifecycleProjection:
    """Enriched proposal lifecycle projection for workspace.proposal_lifecycle widget.

    Built from WorkspaceStatusSummary canonical data.
    Pure, deterministic: no file writes, no database, no receipt creation.
    """

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


# ---------------------------------------------------------------------------
# State-aware stage resolution
# ---------------------------------------------------------------------------


def _resolve_stage(
    selected: bool,
    workspace_path: Optional[str],
    workspace_status: str,
    recommendation: RecommendationSummary,
    proposal: ProposalSummary,
    validation: ValidationSummary,
) -> str:
    """Determine lifecycle stage from canonical state."""
    # No selected workspace
    if not selected:
        return "workspace_unselected"

    # Workspace selected but no workspace_path (edge case)
    if not workspace_path:
        return "workspace_ready"

    # Gate A is always active
    # Check validation failed first (highest priority blocker)
    if validation.status == "failed":
        return "validation_failed"

    # Check workspace status directly for review_ready (takes precedence)
    # This handles the case where workspace status is "review_ready" but
    # validation_status in WorkspaceStatusSummary may not be "passed"
    if workspace_status == "review_ready":
        return "review_ready"

    # Check validation passed + proposal/review state
    if validation.status == "passed":
        if proposal.status in ("review_ready", "validated"):
            return "review_ready"
        return "validation_passed"

    # Check recommendation available
    if recommendation.status == "available":
        return "recommendation_available"

    # Check proposal state
    if proposal.status not in ("not_created", "unknown"):
        return "proposal_pending"

    # Check validation pending
    if validation.status in (" running", "pending"):
        return "validation_pending"

    # Default to gate_a_active for selected workspace with Gate A
    return "gate_a_active"


# ---------------------------------------------------------------------------
# State-aware next_safe_action resolution
# ---------------------------------------------------------------------------


def _resolve_next_safe_action(
    selected: bool,
    workspace_path: Optional[str],
    recommendation: RecommendationSummary,
    proposal: ProposalSummary,
    validation: ValidationSummary,
) -> str:
    """Determine next safe action from canonical state."""
    # No selected workspace
    if not selected:
        return "Select or create a workspace before reviewing proposals."

    # Check validation failed
    if validation.status == "failed":
        return "Inspect validation failures before proposing apply."

    # Check validation passed/review ready
    if validation.status == "passed":
        return "Review proposed changes; apply remains blocked under Gate A."

    # Check recommendation available
    if recommendation.status == "available":
        return "Run read-only validation summary before review."

    # Check no recommendation
    if recommendation.status in ("unknown", "unavailable", "not_created"):
        return "Run review/recommend in an isolated proposal lane."

    # Default
    return "Review proposed changes; apply remains blocked under Gate A."


# ---------------------------------------------------------------------------
# Build normalized summaries from WorkspaceStatusSummary
# ---------------------------------------------------------------------------


def _build_recommendation_summary(
    workspace_summary: WorkspaceStatusSummary,
) -> RecommendationSummary:
    """BuildRecommendationSummary from WorkspaceStatusSummary.

    Uses real state if available. If not available, uses explicit placeholders.
    """
    # Check if workspace has recommendation data in metadata
    # For now, use workspace_summary.proposal_state as proxy
    # since recommendation is not yet separate in the substrate

    # Map workspace status to recommendation status
    ws_status = workspace_summary.status
    ws_selected = workspace_summary.selected

    if not ws_selected:
        return RecommendationSummary(
            status="unknown",
            title="Recommendation unavailable",
            summary="No workspace is currently selected.",
            source_surface="workspace.recommend",
            files=(),
            last_updated=None,
            next_action="Select or create a workspace before reviewing proposals.",
        )

    # Check if validation passed -> recommendation available
    if ws_status == "review_ready":
        return RecommendationSummary(
            status="available",
            title="Recommendation available",
            summary="Validation passed and the workspace is review-ready.",
            source_surface="workspace.recommend",
            files=(),
            last_updated=workspace_summary.head,
            next_action="Review proposed changes; apply remains blocked under Gate A.",
        )

    # Check if validation passed
    if ws_status == "validated":
        return RecommendationSummary(
            status="available",
            title="Recommendation available",
            summary="Validation passed.",
            source_surface="workspace.recommend",
            files=(),
            last_updated=workspace_summary.head,
            next_action="Run read-only validation summary before review.",
        )

    # Default: no recommendation available
    return RecommendationSummary(
        status="unavailable",
        title="No recommendation yet",
        summary="No recommendation has been projected yet.",
        source_surface="workspace.recommend",
        files=(),
        last_updated=None,
        next_action="Run review/recommend in an isolated proposal lane.",
    )


def _build_proposal_summary(
    workspace_summary: WorkspaceStatusSummary,
) -> ProposalSummary:
    """Build ProposalSummary from WorkspaceStatusSummary.

    Uses real state if available. If not available, uses explicit placeholders.
    """
    ws_status = workspace_summary.status
    ws_selected = workspace_summary.selected
    workspace_path = workspace_summary.workspace_path

    if not ws_selected:
        return ProposalSummary(
            status="not_created",
            title="No proposal",
            summary="No proposal has been projected yet.",
            worktree_path=None,
            changed_files=(),
            next_action="Select or create a workspace before reviewing proposals.",
        )

    # Use workspace_summary.proposal_state status
    proposal_status = workspace_summary.proposal_state.status

    if proposal_status == "review_ready":
        return ProposalSummary(
            status="review_ready",
            title="Proposal",
            summary="Workspace proposal data is visible from the current workspace record.",
            worktree_path=workspace_path,
            changed_files=(),
            next_action="Review proposed changes; apply remains blocked under Gate A.",
        )

    if proposal_status == "not_created":
        return ProposalSummary(
            status="not_created",
            title="No proposal",
            summary="No proposal has been projected yet.",
            worktree_path=workspace_path,
            changed_files=(),
            next_action="Run review/recommend in an isolated proposal lane.",
        )

    # Default proposal state
    return ProposalSummary(
        status=proposal_status,
        title="Proposal",
        summary="Workspace proposal data is visible from the current workspace record.",
        worktree_path=workspace_path,
        changed_files=(),
        next_action="Review proposed changes; apply remains blocked under Gate A.",
    )


def _build_validation_summary(
    workspace_summary: WorkspaceStatusSummary,
) -> ValidationSummary:
    """Build ValidationSummary from WorkspaceStatusSummary.

    Uses real state if available. If not available, uses explicit placeholders.
    Also considers workspace status directly since WorkspaceStatusSummary's
    validation_state mapping may not cover all cases.
    """
    ws_status = workspace_summary.status
    ws_selected = workspace_summary.selected

    if not ws_selected:
        return ValidationSummary(
            status="not_run",
            title="Validation not run",
            summary="No validation summary has been projected yet.",
            surface="workspace.validation_result",
            command="",
            passed_count=0,
            failed_count=0,
            last_run_at=None,
            proof_status="not_proof",
            next_action="Run read-only validation summary before review.",
        )

    # Check workspace status directly for cases where validation should be passed
    # The WorkspaceStatusSummary validation_state mapping only maps "validated" -> "passed"
    # but "review_ready" also implies validation passed
    if ws_status == "review_ready":
        return ValidationSummary(
            status="passed",
            title="Validation passed",
            summary="Validation result is available from the workspace record.",
            surface="workspace.validation_result",
            command="python -m pytest",
            passed_count=1,
            failed_count=0,
            last_run_at=workspace_summary.head,
            proof_status="not_proof",
            next_action="Review proposed changes; apply remains blocked under Gate A.",
        )

    validation_status = workspace_summary.validation_state.status

    if validation_status == "passed":
        return ValidationSummary(
            status="passed",
            title="Validation passed",
            summary="Validation result is available from the workspace record.",
            surface="workspace.validation_result",
            command="python -m pytest",
            passed_count=1,
            failed_count=0,
            last_run_at=workspace_summary.head,
            proof_status="not_proof",
            next_action="Review proposed changes; apply remains blocked under Gate A.",
        )

    if validation_status == "failed":
        return ValidationSummary(
            status="failed",
            title="Validation failed",
            summary="Validation result is available from the workspace record.",
            surface="workspace.validation_result",
            command="python -m pytest",
            passed_count=0,
            failed_count=1,
            last_run_at=workspace_summary.head,
            proof_status="not_proof",
            next_action="Inspect validation failures before proposing apply.",
        )

    if validation_status == "not_run":
        return ValidationSummary(
            status="not_run",
            title="Validation not run",
            summary="No validation summary has been projected yet.",
            surface="workspace.validation_result",
            command="",
            passed_count=0,
            failed_count=0,
            last_run_at=None,
            proof_status="not_proof",
            next_action="Run read-only validation summary before review.",
        )

    # Default
    return ValidationSummary(
        status=validation_status,
        title=f"Validation {validation_status}",
        summary=workspace_summary.validation_state.summary,
        surface="workspace.validation_result",
        command="python -m pytest",
        passed_count=0,
        failed_count=0,
        last_run_at=workspace_summary.head,
        proof_status="not_proof",
        next_action=workspace_summary.validation_state.next_action,
    )


# ---------------------------------------------------------------------------
# Action builders
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Main projection builder
# ---------------------------------------------------------------------------


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
    """Build an enriched ProposalLifecycleProjection.

    Primary entry point uses WorkspaceStatusSummary canonical data.
    Falls back to building one if workspace_summary is not provided.

    Pure function: no file writes, no database, no receipt creation,
    no progress persistence, no frontend state input, no workspace mutation.
    """
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
    summary_status = workspace_status
    if workspace_summary:
        summary_workspace_path = workspace_summary.workspace_path
        summary_active_workspace = workspace_summary.selected
        summary_status = workspace_summary.status
        # Update status from workspace_summary if available
        if workspace_summary.status != "unselected":
            active_workspace = workspace_summary.selected
            workspace_status = workspace_summary.status

    # Build normalized summaries from WorkspaceStatusSummary
    # These are pure data transformations with explicit placeholders
    if workspace_summary:
        recommendation = _build_recommendation_summary(workspace_summary)
        proposal = _build_proposal_summary(workspace_summary)
        validation = _build_validation_summary(workspace_summary)
    else:
        # Fallback to unknown placeholders
        recommendation = RecommendationSummary(
            status="unknown",
            title="Recommendation unavailable",
            summary="No workspace summary available.",
            source_surface="workspace.recommend",
            next_action="Select or create a workspace before reviewing proposals.",
        )
        proposal = ProposalSummary(
            status="unknown",
            title="No proposal",
            summary="No proposal has been projected yet.",
            next_action="Select or create a workspace before reviewing proposals.",
        )
        validation = ValidationSummary(
            status="unknown",
            title="Validation status unknown",
            summary="No validation summary available.",
            surface="workspace.validation_result",
            proof_status="not_proof",
            next_action="Select or create a workspace before reviewing proposals.",
        )

    # Resolve stage state-aware
    stage = _resolve_stage(
        selected=summary_active_workspace,
        workspace_path=summary_workspace_path,
        workspace_status=summary_status or "",
        recommendation=recommendation,
        proposal=proposal,
        validation=validation,
    )

    # Resolve next_safe_action state-aware
    next_safe_action = _resolve_next_safe_action(
        selected=summary_active_workspace,
        workspace_path=summary_workspace_path,
        recommendation=recommendation,
        proposal=proposal,
        validation=validation,
    )

    # Title and summary
    title = "Proposal Lifecycle Console"
    if summary_active_workspace and summary_workspace_path:
        summary = (
            f"Dogfood Gate A is active for workspace at {summary_workspace_path}. "
            "Read-only workspace status, projection, and progress are visible; "
            "apply-to-main remains blocked."
        )
    else:
        summary = "Select a workspace to inspect proposal lifecycle state."

    allowed_actions = _gate_a_allowed_actions()
    blocked_actions = _gate_a_blocked_actions()

    # Preserve auditability/progress boundaries per requirements
    # These are explicit and MUST NOT be changed:
    # - progress_state.transient remains true
    # - progress_state.source remains "progress_event"
    # - auditability_state.progress_receipts remains "not_created"
    # - auditability_state.progress_receipt_plan remains "advisory_only"
    # - auditability_state.receipt_candidate remains "inert"
    # - auditability_state.evidence_refs remains "inert"
    # - no receipts are created
    # - no progress events are persisted

    effective_progress_state = progress_state or {"transient": True, "source": "progress_event"}
    effective_auditability_state = auditability_state or {
        "progress_receipts": "not_created",
        "progress_receipt_plan": "advisory_only",
        "receipt_candidate": "inert",
        "evidence_refs": "inert",
    }

    # Ensure boundaries are preserved
    effective_progress_state["transient"] = True
    effective_progress_state["source"] = "progress_event"
    effective_auditability_state["progress_receipts"] = "not_created"
    effective_auditability_state["progress_receipt_plan"] = "advisory_only"
    effective_auditability_state["receipt_candidate"] = "inert"
    effective_auditability_state["evidence_refs"] = "inert"

    # Build explicit next_action for each state for backward compat
    # with existing projection consumption
    effective_recommendation_state = recommendation_state or {
        "status": recommendation.status,
        "title": recommendation.title,
        "summary": recommendation.summary,
        "source_surface": recommendation.source_surface,
        "files": list(recommendation.files) if recommendation.files else [],
        "last_updated": recommendation.last_updated,
        "next_action": recommendation.next_action,
    }
    effective_proposal_state = proposal_state or {
        "status": proposal.status,
        "title": proposal.title,
        "summary": proposal.summary,
        "worktree_path": proposal.worktree_path,
        "changed_files": list(proposal.changed_files) if proposal.changed_files else [],
        "next_action": proposal.next_action,
    }
    effective_validation_state = validation_state or {
        "status": validation.status,
        "title": validation.title,
        "summary": validation.summary,
        "surface": validation.surface,
        "command": validation.command,
        "passed_count": validation.passed_count,
        "failed_count": validation.failed_count,
        "last_run_at": validation.last_run_at,
        "proof_status": validation.proof_status,
        "next_action": validation.next_action,
    }

    warnings = (
        "Progress telemetry is transient.",
        "ProgressReceiptPlan is advisory-only.",
        "receipt_candidate is inert.",
        "evidence_refs are inert.",
        "Apply remains blocked under Dogfood Gate A.",
    )

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
        recommendation_state=effective_recommendation_state,
        proposal_state=effective_proposal_state,
        validation_state=effective_validation_state,
        progress_state=effective_progress_state,
        auditability_state=effective_auditability_state,
        warnings=warnings,
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
