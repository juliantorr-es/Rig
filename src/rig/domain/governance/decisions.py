from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, List, Optional

@dataclass(frozen=True)
class DecisionReason:
    code: str
    message: str
    severity: Literal["info", "warning", "error"] = "info"

@dataclass(frozen=True)
class EvidenceRequirement:
    type: str
    description: str
    satisfied: bool = False

@dataclass(frozen=True)
class BlockedIntent:
    intent_id: str
    reason: str

@dataclass(frozen=True)
class GateDecision:
    workspace_id: str
    decision: Literal["allowed", "blocked", "requires_review", "not_applicable"]
    gate: str
    proposal_id: Optional[str] = None
    reasons: List[DecisionReason] = field(default_factory=list)
    required_evidence: List[EvidenceRequirement] = field(default_factory=list)
    allowed_intents: List[str] = field(default_factory=list)
    blocked_intents: List[BlockedIntent] = field(default_factory=list)
