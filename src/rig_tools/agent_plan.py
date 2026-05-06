from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rig_tools import action_manifest, context_compression, mlx_local, prompt_telemetry


SCHEMA_VERSION = "rig.agent_plan.v1"
DEFAULT_TIMEOUT_SECONDS = 1800
MAX_PROMPT_CHARS = 12000


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _repo_rel(repo_root: Path, path: Path| Optional) -> str| Optional:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def load_registry(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "Docs" / "dev" / "rig" / "agent-registry.yaml"
    data = _load_json(path, {})
    if not isinstance(data, dict):
        return {"agents": []}
    agents = data.get("agents")
    return {"agents": agents if isinstance(agents, list) else []}


def registry_agents(repo_root: Path) -> list[dict[str, Any]]:
    return [agent for agent in load_registry(repo_root).get("agents", []) if isinstance(agent, dict)]


def detect_agents(repo_root: Path) -> list[dict[str, Any]]:
    agents = []
    for agent in registry_agents(repo_root):
        exe = agent.get("executable") or agent.get("agent_id")
        enabled = bool(agent.get("enabled"))
        found = False
        if isinstance(exe, str) and exe:
            found = _which(exe)
        agents.append({
            **agent,
            "enabled": enabled and found,
            "available": found,
            "missing_reason": None if found else "executable_not_found",
        })
    return agents


def _which(name: str) -> bool:
    from shutil import which

    return which(name) is not None


def _read_text(path: Path, limit: int = 3000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""


def collect_context(repo_root: Path, task: str) -> dict[str, Any]:
    pack_path = repo_root / ".build" / "rig" / "context" / "latest.md"
    if pack_path.exists():
        return {
            "source_artifacts": [_repo_rel(repo_root, repo_root / ".build" / "rig" / "context" / "latest.json"), _repo_rel(repo_root, pack_path)],
            "context": _read_text(pack_path, MAX_PROMPT_CHARS),
        }
    pack = context_compression.build_context_pack(repo_root, task=task, purpose="agent-plan", max_chars=MAX_PROMPT_CHARS, use_llm=False)
    return {
        "source_artifacts": pack["selected_artifacts"] or pack["input_artifacts"],
        "context": pack["markdown"][:MAX_PROMPT_CHARS],
    }


def build_prompt(repo_root: Path, *, task: str, mode: str, agent_id: str, source_artifacts: list[str], context: str) -> str:
    return "\n".join([
        "You are a local advisory planner for Rig.",
        "You are not executing tools.",
        "You must output JSON matching rig.agent_plan.v1 only.",
        "Do not include shell commands.",
        "Do not request Git mutation.",
        "Do not mention hidden state.",
        "Keep the plan bounded and task-scoped.",
        "Mark the output non-authoritative.",
        f"Task: {task}",
        f"Requested mode: {mode}",
        f"Requested agent: {agent_id}",
        "Source artifacts:",
        *[f"- {item}" for item in sorted(set(source_artifacts))],
        "",
        "Context:",
        context[:MAX_PROMPT_CHARS],
        "",
        "Return a JSON object with keys:",
        'schema_version, plan_id, task, agent_id, mode, prompt, prompt_file, allowed_paths, forbidden_paths, expected_outputs, timeout_seconds, requires_confirm, git_mutation_allowed, source_context, created_by, authoritative, warnings',
    ]) + "\n"


def _extract_json(text: str) -> dict[str, Any]| Optional:
    candidates = []
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:
            continue
    return None


def _fallback_plan(*, repo_root: Path, task: str, agent_id: str, mode: str, prompt: str, source_artifacts: list[str], warnings: list[str]) -> dict[str, Any]:
    plan_id = f"{task}-{agent_id}-plan"
    return {
        "schema_version": SCHEMA_VERSION,
        "plan_id": plan_id,
        "task": task,
        "agent_id": agent_id,
        "mode": mode,
        "prompt": prompt[:MAX_PROMPT_CHARS],
        "prompt_file": f".build/rig/agents/plans/{plan_id}.prompt.md",
        "allowed_paths": [],
        "forbidden_paths": [],
        "expected_outputs": ["advisory review"],
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "requires_confirm": True,
        "git_mutation_allowed": False,
        "source_context": source_artifacts,
        "created_by": "rig.py agent plan",
        "authoritative": False,
        "warnings": warnings + ["llm_output_unparseable"],
        "generation_status": "failed",
        "raw_output_path": f".build/rig/agents/plans/{plan_id}.raw.txt",
    }


def draft_agent_plan(repo_root: Path, *, task: str, model: str| Optional = None, agent_id: str = "codex", mode: str = "review") -> dict[str, Any]:
    context = collect_context(repo_root, task)
    prompt = build_prompt(repo_root, task=task, mode=mode, agent_id=agent_id, source_artifacts=context["source_artifacts"], context=context["context"])
    model = model or mlx_local.SUMMARY_MODEL
    result = mlx_local.generate_summary(
        prompt=prompt,
        model=model,
        max_tokens=512,
        timeout_seconds=600,
        task=task,
        prompt_kind="agent_plan",
        prompt_template_id="rig.agent_plan.v1",
        context_pack_path=repo_root / ".build" / "rig" / "context" / "latest.md",
    )
    parsed = _extract_json(result.get("output") or "")
    if not parsed:
        parsed = _fallback_plan(repo_root=repo_root, task=task, agent_id=agent_id, mode=mode, prompt=prompt, source_artifacts=context["source_artifacts"], warnings=result.get("warnings") or [])
        raw_path = repo_root / parsed["raw_output_path"]
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(result.get("output") or "", encoding="utf-8")
        parsed["warnings"].append("raw_llm_output_written")
    parsed.setdefault("schema_version", SCHEMA_VERSION)
    parsed.setdefault("plan_id", f"{task}-{agent_id}-plan")
    parsed.setdefault("task", task)
    parsed.setdefault("agent_id", agent_id)
    parsed.setdefault("mode", mode)
    parsed.setdefault("prompt", prompt[:MAX_PROMPT_CHARS])
    parsed.setdefault("prompt_file", f".build/rig/agents/plans/{parsed['plan_id']}.prompt.md")
    parsed.setdefault("allowed_paths", [])
    parsed.setdefault("forbidden_paths", [])
    parsed.setdefault("expected_outputs", ["advisory review"])
    parsed.setdefault("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    parsed.setdefault("requires_confirm", True)
    parsed.setdefault("git_mutation_allowed", False)
    parsed.setdefault("source_context", context["source_artifacts"])
    parsed.setdefault("created_by", "rig.py agent plan")
    parsed.setdefault("authoritative", False)
    parsed.setdefault("warnings", [])
    if not isinstance(parsed["warnings"], list):
        parsed["warnings"] = [str(parsed["warnings"])]
    parsed["warnings"].extend(result.get("warnings") or [])
    parsed["warnings"] = sorted(set(str(item) for item in parsed["warnings"]))
    if len(parsed["prompt"]) > MAX_PROMPT_CHARS:
        parsed["warnings"].append("prompt_truncated")
        parsed["prompt"] = parsed["prompt"][:MAX_PROMPT_CHARS]
    parsed.setdefault("generation_status", result.get("status") or "generated")
    if result.get("output") and not parsed.get("raw_output_path"):
        parsed["raw_output_path"] = None
    prompt_telemetry.record_trace(
        repo_root,
        task=task,
        prompt_kind="agent_plan",
        prompt_template_id="rig.agent_plan.v1",
        backend=result.get("backend") or "mlx",
        model=result.get("model") or model,
        runtime_settings={"max_tokens": 512, "timeout_seconds": 600},
        context_pack_path=repo_root / ".build" / "rig" / "context" / "latest.md",
        prompt_text=prompt,
        raw_output_text=result.get("output") or "",
        parsed_output_text=json.dumps(parsed, indent=2, sort_keys=True) if parsed else "",
        validator_text="",
        status="valid" if parsed and parsed.get("schema_version") == SCHEMA_VERSION else "invalid",
        failure_type="malformed_json" if not parsed else "unknown",
        failure_summary="llm output unparseable" if not parsed else "",
        repair_attempted=False,
        repair_success=bool(parsed),
        quarantined=not parsed,
    )
    json_path, md_path = write_plan_artifacts(repo_root, parsed)
    action_manifest.write_action_manifest(
        repo_root,
        task=task,
        action_kind="agent.plan",
        command_group="agent",
        command=["python", "scripts/rig.py", "agent", "plan", "--task", task, "--agent-id", agent_id, "--mode", mode],
        inputs=[{"path": str(repo_root / ".build" / "rig" / "context" / "latest.md"), "kind": "context_pack"}],
        outputs=[{"path": str(json_path), "kind": "agent_plan", "status": "produced"}, {"path": str(md_path), "kind": "agent_plan", "status": "produced"}],
        status="passed" if parsed.get("generation_status") != "failed" else "failed",
        exit_code=0 if parsed.get("generation_status") != "failed" else 1,
        result_path=json_path,
    )
    parsed["plan_path"] = str(json_path.relative_to(repo_root))
    parsed["plan_md_path"] = str(md_path.relative_to(repo_root))
    return parsed


def validate_plan(repo_root: Path, plan: dict[str, Any], *, allow_vibe: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    registry = {agent.get("agent_id"): agent for agent in registry_agents(repo_root) if isinstance(agent, dict)}
    agent_id = plan.get("agent_id")
    if agent_id not in registry:
        errors.append("unknown_agent_id")
    else:
        agent = registry[agent_id]
        if agent_id == "vibe" and not allow_vibe:
            errors.append("vibe_disabled")
    if plan.get("schema_version") != SCHEMA_VERSION:
        errors.append("bad_schema_version")
    if plan.get("authoritative") is not False:
        errors.append("must_be_non_authoritative")
    prompt = plan.get("prompt") or ""
    if not isinstance(prompt, str) or not prompt.strip():
        errors.append("missing_prompt")
    if isinstance(prompt, str) and len(prompt) > MAX_PROMPT_CHARS:
        errors.append("prompt_too_long")
    if any(tok in prompt.lower() for tok in ["shell=", "subprocess.run", "os.system", "rm -rf", "git push", "git pull", "git rebase", "git merge"]):
        errors.append("forbidden_instruction")
    if plan.get("git_mutation_allowed"):
        errors.append("git_mutation_not_allowed_by_default")
    allowed_paths = plan.get("allowed_paths")
    if not isinstance(allowed_paths, list):
        errors.append("bad_allowed_paths")
    forbidden_paths = plan.get("forbidden_paths")
    if not isinstance(forbidden_paths, list):
        errors.append("bad_forbidden_paths")
    timeout_seconds = plan.get("timeout_seconds")
    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        errors.append("bad_timeout_seconds")
    requires_confirm = plan.get("requires_confirm")
    if requires_confirm is not True:
        errors.append("requires_confirm_must_be_true")
    if isinstance(plan.get("prompt_file"), str) and ".." in str(plan["prompt_file"]):
        errors.append("prompt_file_must_be_repo_relative")
    forbidden_path_tokens = {".git", ".venv-rig", "DerivedData", "__pycache__", ".pytest_cache"}
    for path_list_name in ("allowed_paths", "forbidden_paths"):
        value = plan.get(path_list_name)
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    errors.append(f"{path_list_name}_must_be_string_paths")
                    continue
                if any(token in item for token in forbidden_path_tokens):
                    errors.append(f"{path_list_name}_contains_forbidden_path")
                if item.startswith("/") and not item.startswith(str(repo_root)):
                    errors.append(f"{path_list_name}_must_be_repo_relative")
                if "git push" in item or "git pull" in item or "git rebase" in item or "git merge" in item:
                    errors.append(f"{path_list_name}_contains_forbidden_action")
    status = "passed" if not errors else "failed"
    return {"status": status, "errors": errors, "warnings": warnings}


def write_plan_artifacts(repo_root: Path, plan: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = repo_root / ".build" / "rig" / "agents" / "plans"
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_id = plan["plan_id"]
    json_path = out_dir / f"{plan_id}.json"
    md_path = out_dir / f"{plan_id}.md"
    json_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text("\n".join([
        "# Rig Agent Plan",
        "",
        f"- Plan ID: `{plan_id}`",
        f"- Task: `{plan.get('task')}`",
        f"- Agent: `{plan.get('agent_id')}`",
        f"- Mode: `{plan.get('mode')}`",
        f"- Requires confirm: `{plan.get('requires_confirm')}`",
        f"- Git mutation allowed: `{plan.get('git_mutation_allowed')}`",
        "",
        "## Prompt",
        "",
        "```text",
        plan.get("prompt") or "",
        "```",
    ]) + "\n", encoding="utf-8")
    return json_path, md_path


def load_plan(path: Path) -> dict[str, Any]:
    data = _load_json(path, {})
    return data if isinstance(data, dict) else {}
