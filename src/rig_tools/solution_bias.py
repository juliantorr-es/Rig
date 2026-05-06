import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BIAS_PROFILE_SCHEMA_VERSION = "1.0.0"

def list_profiles(repo_root: Path) -> list[dict[str, Any]]:
    profiles_dir = repo_root / "Docs" / "dev" / "rig" / "bias-profiles"
    if not profiles_dir.exists():
        return []
    
    out = []
    for p in sorted(profiles_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("profile_id"):
                out.append(data)
        except Exception as e:
            logger.warning(f"Failed to load bias profile {p.name}: {e}")
    return out

def get_profile(repo_root: Path, profile_id: str) -> dict[str, Any] | None:
    path = repo_root / "Docs" / "dev" / "rig" / "bias-profiles" / f"{profile_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def validate_profiles(repo_root: Path) -> dict[str, Any]:
    from rig_tools import schema_validation
    
    profiles = list_profiles(repo_root)
    results = []
    all_ok = True
    
    for p in profiles:
        ok = True
        errors = []
        # Basic schema check could be done via schema_validation if we want to be formal
        if not p.get("profile_id"):
            ok = False
            errors.append("missing profile_id")
        
        results.append({
            "profile_id": p.get("profile_id", "unknown"),
            "status": "pass" if ok else "fail",
            "errors": errors
        })
        if not ok:
            all_ok = False
            
    return {
        "status": "pass" if all_ok else "fail",
        "profiles": results
    }

def apply_bias_to_prompt(prompt: str, profiles: list[dict[str, Any]]) -> str:
    if not profiles:
        return prompt
    
    bias_text = "\n## Solution Bias Constraints\n"
    for p in profiles:
        bias_text += f"### {p['display_name']}\n"
        for constraint in p.get("prompt_constraints", []):
            bias_text += f"- {constraint}\n"
    
    return prompt.strip() + "\n" + bias_text

def score_bias_alignment(output_text: str, profiles: list[dict[str, Any]]) -> dict[str, Any]:
    total_alignment_score = 0
    matches = []
    hard_fails = []
    
    for p in profiles:
        profile_score = 0
        weights = p.get("scoring_weights", {})
        
        # Positive indicators
        for ind in p.get("positive_indicators", []):
            if re.search(rf"\b{re.escape(ind)}\b", output_text, re.IGNORECASE):
                # We could have weights for specific indicators, but for MVP we use general weights
                # Let's map indicators to a subset of weight keys or just a flat bonus
                profile_score += 5 
                matches.append(f"positive:{ind}")
        
        # Negative indicators
        for ind in p.get("negative_indicators", []):
            if re.search(rf"\b{re.escape(ind)}\b", output_text, re.IGNORECASE):
                profile_score -= 5
                matches.append(f"negative:{ind}")
        
        # Hard fail rules
        for rule in p.get("hard_fail_rules", []):
            if re.search(rule["pattern"], output_text, re.IGNORECASE):
                hard_fails.append({
                    "profile_id": p["profile_id"],
                    "rule_id": rule["id"],
                    "description": rule["description"]
                })
        
        # Apply weights based on general candidate properties if available
        # (This will be called from proposal_swarm with more context)
        
        total_alignment_score += profile_score
        
    return {
        "bias_alignment_score": total_alignment_score,
        "matches": matches,
        "hard_fails": hard_fails,
        "status": "fail" if hard_fails else "pass"
    }

def rank_candidates(candidates: list[dict[str, Any]], bias_profiles: list[dict[str, Any]]) -> dict[str, Any]:
    # candidates should have 'base_score' and 'bias_alignment_score'
    rankings = []
    for c in candidates:
        final_score = c.get("base_score", 0) + c.get("bias_alignment_score", 0)
        # Penalize hard fails heavily or disqualify
        if c.get("hard_fail"):
            final_score = -1000
            
        rankings.append({
            "candidate_id": c["candidate_id"],
            "base_score": c.get("base_score", 0),
            "bias_alignment_score": c.get("bias_alignment_score", 0),
            "final_score": final_score,
            "hard_fail": c.get("hard_fail", False),
            "hard_fail_reason": c.get("hard_fail_reason", "")
        })
    
    # Sort by final score descending
    rankings.sort(key=lambda x: x["final_score"], reverse=True)
    
    for i, r in enumerate(rankings):
        r["rank"] = i + 1
        
    winner = rankings[0]["candidate_id"] if rankings and rankings[0]["final_score"] > -1000 else None
    
    return {
        "schema_version": "1.0.0",
        "rankings": rankings,
        "winner_candidate_id": winner
    }
