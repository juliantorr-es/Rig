from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkflowGatePolicy:
    gate: str
    allowed_operations: tuple[str, ...] = ()
    blocked_operations: tuple[str, ...] = ()
    blocked_practices: tuple[str, ...] = ()
    workflow_prompt: str = ""
    notes: tuple[str, ...] = ()
    advisory_only: bool = True


GATE_A_POLICY = WorkflowGatePolicy(
    gate="A",
    allowed_operations=(
        "rig.intent.workspace_status",
        "rig.intent.refresh_projection",
        "rig.intent.review",
        "rig.intent.recommend",
        "scripts/rig_agent_worktree.py review",
        "scripts/rig_agent_worktree.py recommend",
    ),
    blocked_operations=(
        "rig.intent.apply_patch",
        "rig.intent.approve_gate",
        "rig.intent.promote_execute",
        "main worktree writes",
    ),
    blocked_practices=(
        "claiming transient progress as proof",
        "creating receipts from progress",
        "persisting progress events",
        "treating receipt_candidate as authority",
        "treating evidence_refs as resolved evidence",
        "using frontend progress-store as source of truth",
    ),
    workflow_prompt=(
        "Use Rig as the workflow control plane when available. "
        "Start with Rig workspace status and projection, report progress and validations, "
        "do not mutate main directly, and stop rather than bypass failed gates."
    ),
    notes=(
        "Gate A is read-only status/projection/progress plus isolated proposal-shaped workflows.",
        "Gate A is advisory only until command enforcement exists.",
    ),
)

