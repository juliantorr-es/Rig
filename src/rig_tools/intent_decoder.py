from __future__ import annotations

import re
import uuid
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

SCHEMA_VERSION = "1.0.0"

SAFE_ALIASES = {
    "run_doctor": ["health check", "run doctor", "doctor", "system health"],
    "run_contract_audit": ["audit contracts", "run audit", "contract audit"],
    "run_os_sentinel": ["sentinel", "os sentinel", "run sentinel"],
    "run_schema_validate": ["schema check", "validate schema", "check schema"],
    "run_structural_scan": ["structural scan", "code scan", "run scan"],
    "run_gc_plan": ["clean up plan", "gc plan", "garbage collect plan"],
    "run_vault_export_dry_run": ["export vault", "vault export", "backup vault"],
    "run_swarm_propose_dry_run": ["swarm propose", "propose candidates", "get suggestions"],
    "run_loop_plan_dry_run": ["loop plan", "plan loop", "orchestrate plan"],
    "bundle_session_dry_run": ["make bundle", "bundle session", "package results"],
    "inspect_receipt": ["show receipt", "view result", "inspect"],
    "open_vault_uri": ["open note", "open vault"]
}

FORBIDDEN_KEYWORDS = {
    "git push", "git pull", "git rebase", "git merge", "rm -rf", "curl", "wget", "chmod +x"
}

def decode_intent(repo_root: Path, input_text: str, current_task: str | None = None) -> Dict[str, Any]:
    """Decodes a model intent into a result."""
    decode_id = f"dec-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    
    # 1. Parsing
    intent_data = _parse_input(input_text)
    intent_id = intent_data.get("intent_id", f"int-{uuid.uuid4().hex[:8]}")
    
    # 2. Rejection check
    rejection = _check_for_rejection(input_text, intent_data)
    if rejection:
        return {
            "schema_version": SCHEMA_VERSION,
            "decode_id": decode_id,
            "created_at": now,
            "intent_id": intent_id,
            "status": "rejected",
            "matched_action_id": None,
            "normalized_args": {},
            "repairs": [],
            "rejection_reason": rejection,
            "warnings": [],
            "authoritative": True
        }

    # 3. Action Mapping
    matched_action, repairs = _map_to_action(intent_data)
    if not matched_action:
        return {
            "schema_version": SCHEMA_VERSION,
            "decode_id": decode_id,
            "created_at": now,
            "intent_id": intent_id,
            "status": "rejected",
            "matched_action_id": None,
            "normalized_args": {},
            "repairs": [],
            "rejection_reason": f"Unknown action requested: {intent_data.get('requested_action')}",
            "warnings": [],
            "authoritative": True
        }

    # 4. Arg Normalization
    args = intent_data.get("requested_args", {})
    normalized_args, arg_repairs = _normalize_args(matched_action, args, current_task)
    repairs.extend(arg_repairs)

    return {
        "schema_version": SCHEMA_VERSION,
        "decode_id": decode_id,
        "created_at": now,
        "intent_id": intent_id,
        "status": "repaired" if repairs else "decoded",
        "matched_action_id": matched_action,
        "command_plan_path": None, # Will be filled by command generation
        "normalized_args": normalized_args,
        "repairs": repairs,
        "rejection_reason": None,
        "warnings": [],
        "authoritative": True
    }

def _parse_input(text: str) -> Dict[str, Any]:
    # Check for JSON in backticks
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except Exception:
            pass
            
    # Try pure JSON
    try:
        return json.loads(text)
    except Exception:
        pass
        
    # Heuristic/Alias check
    text_lower = text.lower()
    for action_id, aliases in SAFE_ALIASES.items():
        if any(alias in text_lower for alias in aliases):
            # Find which alias matched
            matched_alias = next(a for a in aliases if a in text_lower)
            # Basic argument extraction for plain text
            args = {}
            if "json" in text_lower:
                args["format"] = "json"
            return {
                "intent_kind": "run_action",
                "requested_action": action_id,
                "raw_requested": matched_alias,
                "requested_args": args,
                "authoritative": False
            }
            
    return {"intent_kind": "run_action", "requested_action": "unknown", "authoritative": False}

def _check_for_rejection(text: str, data: Dict[str, Any]) -> Optional[str]:
    text_lower = text.lower()
    for forbidden in FORBIDDEN_KEYWORDS:
        if forbidden in text_lower:
            return f"Forbidden action or keyword detected: {forbidden}"
            
    # Path traversal check
    requested_paths = data.get("requested_paths", [])
    for path in requested_paths:
        if ".." in path or path.startswith("/"):
             return f"Unsafe path detected: {path}"
             
    return None

def _map_to_action(data: Dict[str, Any]) -> tuple[Optional[str], List[str]]:
    requested = data.get("requested_action", "unknown")
    raw = data.get("raw_requested")
    repairs = []
    
    if raw and raw != requested:
        repairs.append(f"Normalized action alias '{raw}' to {requested}")
    
    # Direct match
    if requested in SAFE_ALIASES:
        return requested, repairs
        
    # Deep alias normalization (for cases where requested wasn't pre-mapped)
    for action_id, aliases in SAFE_ALIASES.items():
        if requested in aliases:
            repairs.append(f"Normalized action {requested} to {action_id}")
            return action_id, repairs
            
    return None, repairs

def _normalize_args(action_id: str, args: Dict[str, Any], current_task: str | None) -> tuple[Dict[str, Any], List[str]]:
    normalized = args.copy()
    repairs = []
    
    # 1. --json -> format: json
    if "--json" in normalized:
        normalized["format"] = "json"
        del normalized["--json"]
        repairs.append("Converted --json to format: json")
        
    # 2. task requirement
    task_required = {"run_swarm_propose_dry_run", "run_loop_plan_dry_run", "bundle_session_dry_run", "open_vault_uri"}
    if action_id in task_required and "task" not in normalized and current_task:
        normalized["task"] = current_task
        repairs.append(f"Auto-filled missing task with {current_task}")
        
    # 3. Force dry-run for some MVP intents
    if action_id.endswith("_dry_run") and normalized.get("dry_run") is not True:
        normalized["dry_run"] = True
        repairs.append("Enforced mandatory dry_run for MVP intent")
        
    return normalized, repairs
