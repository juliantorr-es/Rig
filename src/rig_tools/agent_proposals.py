from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from rig_tools.contracts import CommandPlan, CommandSafety
from rig_tools.runtime_registry import provider_for_id, TRUST_TIERS


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_wrappers(text: str) -> str:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S)
    return fenced.group(1).strip() if fenced else text


def decode_raw_output(raw_output: str, *, provider_manifest: dict[str, Any]) -> dict[str, Any]:
    text = _strip_wrappers(raw_output)
    candidates = []
    try:
        candidates.append(json.loads(text))
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            candidates.append(json.loads(m.group(0)))
        except Exception:
            pass
    if not candidates:
        return {
            "intent": {"kind": "unknown", "raw_text": text},
            "decoded_actions": [],
            "files_referenced": [],
            "risk_level": "high",
            "confidence": 0.0,
            "status": "blocked",
            "rejection_reason": "unparseable_output",
        }
    payload = candidates[0]
    actions = payload.get("decoded_actions") or payload.get("actions") or []
    files = payload.get("files_referenced") or payload.get("files") or []
    trust = provider_manifest.get("trust_tier", "blocked")
    risky = any(isinstance(action, dict) and action.get("type") in {"command", "shell", "exec"} for action in actions)
    if trust == "advisory" and risky:
        return {
            "intent": payload.get("intent") or payload,
            "decoded_actions": actions,
            "files_referenced": files,
            "risk_level": "blocked",
            "confidence": float(payload.get("confidence", 0.0) or 0.0),
            "status": "blocked",
            "rejection_reason": "trust_tier_violation",
        }
    return {
        "intent": payload.get("intent") or payload,
        "decoded_actions": actions,
        "files_referenced": files,
        "risk_level": payload.get("risk_level") or "medium",
        "confidence": float(payload.get("confidence", 0.5) or 0.0),
        "status": "decoded",
    }


def create_proposal(repo_root: Path, *, workspace_id: str, provider_id: str, model_id: str, raw_output: str, provider_manifest: dict[str, Any], context_packet_id: str | None = None, context_packet_hash: str | None = None) -> dict[str, Any]:
    decoded = decode_raw_output(raw_output, provider_manifest=provider_manifest)
    proposal = {
        "schema_version": "rig.agent_proposal.v1",
        "proposal_id": uuid.uuid4().hex[:12],
        "workspace_id": workspace_id,
        "provider_id": provider_id,
        "model_id": model_id,
        "intent": decoded.get("intent") or {},
        "raw_output_hash": sha256_text(raw_output),
        "decoded_actions": decoded.get("decoded_actions") or [],
        "files_referenced": decoded.get("files_referenced") or [],
        "risk_level": decoded.get("risk_level") or "medium",
        "confidence": decoded.get("confidence") or 0.0,
        "status": decoded.get("status") or "decoded",
        "authoritative": True,
        "rejection_reason": decoded.get("rejection_reason"),
        "context_packet_id": context_packet_id,
        "context_packet_hash": context_packet_hash,
    }
    out_dir = repo_root / ".build" / "rig" / "agent-proposals"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{proposal['proposal_id']}.json").write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return proposal


def proposal_to_command_plan(repo_root: Path, proposal: dict[str, Any]) -> CommandPlan:
    if proposal.get("status") == "blocked":
        raise ValueError(proposal.get("rejection_reason") or "proposal blocked")
    actions = proposal.get("decoded_actions") or []
    argv = actions[0].get("argv") if actions and isinstance(actions[0], dict) else []
    if not argv:
        raise ValueError("no decoded command")
    return CommandPlan(
        plan_id=proposal["proposal_id"],
        action_id="agent.proposal.accepted",
        mode="safe",
        argv=[str(part) for part in argv],
        working_directory=str(repo_root),
        timeout_seconds=300,
        allowed=True,
        safety=CommandSafety(shell=False, mutates_git=False, mutates_main_worktree=False, launches_external_agent=False),
        task=proposal.get("workspace_id"),
        disabled_reason=None,
    )
