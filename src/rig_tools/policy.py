from __future__ import annotations

import json
import uuid
import yaml
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def check_auto_policy(repo_root: Path, *, action: str, policy_path: Path, budgets: dict[str, Any], target_path: Path | None = None) -> dict[str, Any]:
    try:
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"decision": "deny", "reason": f"invalid_policy: {exc}", "requires_confirm": True}

    matched_rules = ["auto_approve_mode"]
    risk_level = "medium"
    decision = "allow"
    reason = "auto_approved"
    requires_confirm = False

    # 1. Action Gate
    if action in policy.get("forbidden_actions", []):
        decision = "deny"
        reason = "forbidden_action"
    elif action not in policy.get("allowed_actions", []):
        decision = "deny"
        reason = "unauthorized_action"
    
    # 2. Budget Gate
    if budgets.get("runtime_minutes", 0) >= policy.get("max_runtime_minutes", 60):
        decision = "deny"
        reason = "budget_exceeded:runtime"
    if action == "agent.launch" and budgets.get("agent_runs", 0) >= policy.get("max_agent_runs", 2):
        decision = "deny"
        reason = "budget_exceeded:agent_runs"
    if action == "patch.propose" and budgets.get("patch_attempts", 0) >= policy.get("max_patch_attempts", 3):
        decision = "deny"
        reason = "budget_exceeded:patch_attempts"

    # 3. Path Scope Gate
    if target_path:
        rel_path = _repo_rel(repo_root, target_path)
        if rel_path:
            forbidden_paths = policy.get("forbidden_paths", [])
            for fp in forbidden_paths:
                if rel_path.startswith(fp):
                    decision = "deny"
                    reason = "forbidden_path"
                    break
            
            allowed_paths = policy.get("allowed_paths", [])
            if decision == "allow" and allowed_paths:
                is_allowed = False
                for ap in allowed_paths:
                    if rel_path.startswith(ap):
                        is_allowed = True
                        break
                if not is_allowed:
                    decision = "deny"
                    reason = "out_of_scope_path"

    # 4. Authority Gate (Locks)
    if not policy.get("allow_git_mutation", False) and (action.startswith("git.") or action in {"commit", "push", "pull"}):
        decision = "deny"
        reason = "git_mutation_blocked"
    if not policy.get("allow_main_worktree_patch_apply", False) and action == "patch.apply_main":
        decision = "deny"
        reason = "main_worktree_mutation_blocked"

    decision_payload = PolicyDecision(
        decision_id=f"auto-{uuid.uuid4().hex[:10]}",
        task=policy.get("task"),
        action_kind=action,
        risk_level=risk_level,
        decision=decision,
        reason=reason,
        matched_rules=matched_rules,
        requires_confirm=requires_confirm,
    ).to_dict() | {"policy_id": policy.get("policy_id")}
    
    out_dir = repo_root / ".build" / "rig" / "policy"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(out_dir / f"{decision_payload['decision_id']}.json", decision_payload)
    return decision_payload

SCHEMA_VERSION = "rig.policy_decision.v1"


@dataclass
class PolicyDecision:
    decision_id: str
    task: str | None
    action_kind: str
    risk_level: str
    decision: str
    reason: str
    matched_rules: list[str]
    requires_confirm: bool
    authoritative: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "decision_id": self.decision_id,
            "task": self.task,
            "action_kind": self.action_kind,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "reason": self.reason,
            "matched_rules": self.matched_rules,
            "requires_confirm": self.requires_confirm,
            "authoritative": self.authoritative,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_rel(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check(repo_root: Path, *, action: str, mode: str, allow_local_patches: bool = False) -> dict[str, Any]:
    matched_rules: list[str] = []
    risk_level = "low"
    decision = "allow"
    reason = "allowed"
    requires_confirm = mode != "read-only"

    if action in {"patch.apply-sandbox", "patch.propose"}:
        risk_level = "medium"
        matched_rules.append("local_patch_lane")
        if not allow_local_patches:
            decision = "deny"
            reason = "local_patches_disabled"
    if action == "patch.apply-sandbox":
        matched_rules.append("sandbox_only")
    if action == "patch.apply-main":
        risk_level = "high"
        matched_rules.append("main_worktree_mutation_forbidden")
        decision = "deny"
        reason = "git_mutation_forbidden"
    if action == "agent.launch":
        risk_level = "high"
        matched_rules.append("confirmed_external_agent_forbidden")
        if mode != "read-only":
            decision = "needs_human_approval"
            reason = "confirmed_external_agent_requires_approval"
    if action == "loop.run":
        matched_rules.append("bounded_loop")
        if mode == "implementation":
            decision = "deny"
            reason = "implementation_reserved"
    if action == "context.build":
        matched_rules.append("deterministic_context_pack")
    if action.startswith("git.") or action in {"git_mutation", "commit", "push", "pull"}:
        risk_level = "high"
        matched_rules.append("git_mutation_forbidden")
        decision = "deny"
        reason = "git_mutation_forbidden"
    if action in {"swift.build", "swift.test"}:
        matched_rules.append("read_only_validator")
    if decision == "allow" and mode in {"review", "agent_dry_run", "patch_sandbox"}:
        requires_confirm = True
    decision_payload = PolicyDecision(
        decision_id=f"pol-{uuid.uuid4().hex[:10]}",
        task=None,
        action_kind=action,
        risk_level=risk_level,
        decision=decision,
        reason=reason,
        matched_rules=sorted(set(matched_rules)),
        requires_confirm=requires_confirm,
    ).to_dict() | {"repo_root": _repo_rel(repo_root, repo_root)}
    out_dir = repo_root / ".build" / "rig" / "policy"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{decision_payload['decision_id']}.json"
    path.write_text(json.dumps(decision_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "latest.json").write_text(json.dumps(decision_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    decision_payload["artifact_path"] = _repo_rel(repo_root, path)
    return decision_payload


def list_policies(repo_root: Path) -> list[dict[str, Any]]:
    return [
        {"policy": "read_only", "risk": "low", "allows": ["inspect", "query", "validate"], "denies": ["source edits", "git mutation", "confirmed external agents"]},
        {"policy": "review", "risk": "medium", "allows": ["plan", "dry-run", "bundle"], "denies": ["confirmed external agents", "source edits", "git mutation"]},
        {"policy": "agent_dry_run", "risk": "medium", "allows": ["agent plan", "agent launch --dry-run"], "denies": ["confirmed external agents", "git mutation"]},
        {"policy": "patch_sandbox", "risk": "high", "allows": ["sandbox validation"], "denies": ["main worktree mutation", "git mutation"]},
        {"policy": "implementation_reserved", "risk": "high", "allows": [], "denies": ["implementation mode in v1"]},
        {"policy": "git_mutation_forbidden", "risk": "critical", "allows": [], "denies": ["commit", "push", "pull", "rebase", "merge"]},
    ]
