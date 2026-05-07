from __future__ import annotations
from typing import Dict, Any, List, Optional
from .decisions import GateDecision, DecisionReason, EvidenceRequirement, BlockedIntent

class GovernanceEngine:
    """
    Pure-ish evaluation of Rig governance gates.
    Answers: what is allowed, what is blocked, and why?
    """

    def evaluate_action_legality(
        self,
        workspace_id: str,
        workspace_active: bool,
        proposal: Optional[Dict[str, Any]] = None,
        evidence: Optional[List[Dict[str, Any]]] = None,
        policy: Optional[Dict[str, Any]] = None,
    ) -> GateDecision:
        reasons = []
        allowed_intents = ["intent.refresh_projection", "intent.chat.submit"]
        blocked_intents = []
        decision: Any = "not_applicable"
        gate = "rig.gate.apply"

        if not workspace_active:
            reasons.append(DecisionReason("no_active_workspace", "No active workspace", "error"))
            decision = "blocked"
            blocked_intents.extend([
                BlockedIntent("intent.apply_patch", "No active workspace"),
                BlockedIntent("intent.approve_gate", "No active workspace"),
                BlockedIntent("intent.run_validators", "No active workspace")
            ])
            return GateDecision(
                workspace_id=workspace_id,
                decision=decision,
                gate=gate,
                reasons=reasons,
                allowed_intents=allowed_intents,
                blocked_intents=blocked_intents
            )

        # Workspace is active
        allowed_intents.append("intent.run_validators")

        if not proposal:
            reasons.append(DecisionReason("no_proposal", "No active proposal to evaluate", "info"))
            decision = "not_applicable"
            blocked_intents.extend([
                BlockedIntent("intent.apply_patch", "No proposal present"),
                BlockedIntent("intent.approve_gate", "No proposal present")
            ])
        else:
            proposal_id = proposal.get("proposal_id")
            status = proposal.get("status")
            
            # check if validators have run based on evidence
            validators_run = False
            validators_passed = False
            if evidence:
                # Simple logic for MVP: look for validator result evidence
                for item in evidence:
                    if item.get("type") == "rig.evidence.validator_result":
                        validators_run = True
                        if item.get("status") == "passed":
                            validators_passed = True
                        break

            if status == "blocked":
                decision = "blocked"
                reasons.append(DecisionReason("proposal_blocked", "Proposal is explicitly blocked", "error"))
                blocked_intents.extend([
                    BlockedIntent("intent.apply_patch", "Proposal is blocked"),
                    BlockedIntent("intent.approve_gate", "Proposal is blocked")
                ])
            elif not validators_run:
                decision = "requires_review"
                reasons.append(DecisionReason("validators_missing", "Validators have not run for this proposal", "warning"))
                blocked_intents.extend([
                    BlockedIntent("intent.apply_patch", "Validators must run first"),
                    BlockedIntent("intent.approve_gate", "Validators must run first")
                ])
            elif not validators_passed:
                decision = "blocked"
                reasons.append(DecisionReason("validators_failed", "Validators failed for this proposal", "error"))
                blocked_intents.extend([
                    BlockedIntent("intent.apply_patch", "Validators failed"),
                    BlockedIntent("intent.approve_gate", "Validators failed")
                ])
            else:
                # Validators passed
                decision = "allowed"
                reasons.append(DecisionReason("validators_passed", "All governance gates satisfied", "info"))
                allowed_intents.extend(["intent.apply_patch", "intent.approve_gate"])

            return GateDecision(
                workspace_id=workspace_id,
                proposal_id=proposal_id,
                decision=decision,
                gate=gate,
                reasons=reasons,
                allowed_intents=allowed_intents,
                blocked_intents=blocked_intents
            )

        return GateDecision(
            workspace_id=workspace_id,
            decision=decision,
            gate=gate,
            reasons=reasons,
            allowed_intents=allowed_intents,
            blocked_intents=blocked_intents
        )
