from __future__ import annotations

import ast
import json
import statistics
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rig_tools import context_compression, llama_cpp_local, mlx_local, prompt_regression, prompt_telemetry, solution_bias
from rig_tools.action_manifest import write_action_manifest
from rig_tools.memory_contracts import can_launch_parallel_agents
from rig_tools.settings_store import SettingsStore
from rig_tools.system_pressure import sample_system_pressure


SCHEMA_VERSION = "rig.proposal_swarm.v1"
CANDIDATE_SCHEMA_VERSION = "rig.proposal_candidate.v1"
MIN_CONTEXT_TOKENS = {
    "plan": 4096,
    "validator_error_classification": 4096,
    "docs_normalization_plan": 4096,
    "patch_proposal": 6144,
    "prompt_repair": 4096,
}
STRATEGIES = [
    "conservative_minimal",
    "architecture_first",
    "test_first",
    "docs_schema_first",
    "validator_error_focused",
    "small_patch_decomposition",
]
PROFILE_MAX_PARALLEL = {
    "conservative": 1,
    "balanced": 2,
    "exploratory": 4,
}


def _repo_rel(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _dir(repo_root: Path, swarm_id: str, *parts: str) -> Path:
    out = repo_root / ".build" / "rig" / "swarm" / swarm_id
    for part in parts:
        out = out / part
    out.mkdir(parents=True, exist_ok=True)
    return out


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _available_backend_info(repo_root: Path, backend: str) -> dict[str, Any]:
    if backend == "llama-cpp":
        return llama_cpp_local.detect_llama_cpp_environment()
    return mlx_local.detect_mlx_environment()


def _profile_defaults(profile: str) -> dict[str, Any]:
    return {
        "profile": profile,
        "max_parallel": PROFILE_MAX_PARALLEL.get(profile, 1),
        "strategies": STRATEGIES[:],
    }


def profiles(repo_root: Path) -> dict[str, Any]:
    from rig_tools import system_benchmark
    bench = system_benchmark.get_latest_benchmark(repo_root)
    bench_data = bench.get("recommended_profile", {}) if bench else {}
    
    settings = SettingsStore(repo_root).get_effective_settings()
    swarm = settings.get("swarm", {}) if isinstance(settings, dict) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_profile": bench_data.get("profile_id"),
        "profiles": [
            {"profile": "conservative", "max_parallel": 1, "strategies": STRATEGIES[:2]},
            {"profile": "balanced", "max_parallel": 2, "strategies": STRATEGIES[:4]},
            {"profile": "exploratory", "max_parallel": int(bench_data.get("max_parallel_candidates") or swarm.get("max_parallel_agents", 4) or 4), "strategies": STRATEGIES},
        ],
        "swarm_settings": swarm,
        "warnings": [],
        "authoritative": False,
    }


def status(repo_root: Path) -> dict[str, Any]:
    settings = SettingsStore(repo_root).get_effective_settings()
    pressure = sample_system_pressure(repo_root)
    backend = _available_backend_info(repo_root, "llama-cpp")
    active_backend = "llama-cpp" if backend.get("status") == "available" else "mlx"
    latest = latest_swarm(repo_root)
    profiles_info = profiles(repo_root)
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "active_backend": active_backend,
        "llama_cpp_environment": backend,
        "memory_pressure": pressure,
        "latest_swarm": latest,
        "profiles": profiles_info.get("profiles", []),
        "swarm_settings": settings.get("swarm", {}),
        "warnings": [],
        "authoritative": True,
    }
    if backend.get("status") != "available":
        report["warnings"].append("llama_server_not_configured")
        report["status"] = "warn"
    if not can_launch_parallel_agents(settings, pressure):
        report["warnings"].append("parallel_agents_disabled_under_pressure")
    return report


def latest_swarm(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / ".build" / "rig" / "swarm" / "latest.json"
    return _load_json(path)


def _swarm_template(repo_root: Path, kind: str) -> str:
    path = repo_root / "Docs" / "dev" / "rig" / "prompts" / "swarm" / f"{kind}.md"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    return f"""# Rig Proposal Swarm Candidate

Task: {{task}}
Kind: {{kind}}
Strategy: {{strategy}}
Contract: {{contract}}

Use only the provided context pack.
Return only the requested contract.
No prose outside the contract.
"""

def _candidate_prompt(repo_root: Path, task: str, kind: str, strategy: str, context_markdown: str, contract: str, bias_profiles: list[dict[str, Any]] | None = None) -> str:
    template = _swarm_template(repo_root, kind)
    rendered = template.format(task=task, kind=kind, strategy=strategy, contract=contract)
    prompt = rendered + "\n## Context Pack\n" + context_markdown.strip() + "\n"
    if bias_profiles:
        prompt = solution_bias.apply_bias_to_prompt(prompt, bias_profiles)
    return prompt


def _validate_output(kind: str, output: str) -> tuple[dict[str, Any] | None, list[str], str]:
    text = (output or "").strip()
    if not text:
        return None, ["empty_output"], "malformed"
    if kind == "plan":
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                ok = any(key in parsed for key in ("summary", "steps", "action"))
                return (parsed if ok else None), ([] if ok else ["missing_required_field"]), "json"
        except Exception:
            pass
        if any(head in text.lower() for head in ("#", "##", "###")):
            return {"markdown": text}, [], "markdown"
        return None, ["malformed_output"], "malformed"
    if kind == "validator_error_classification":
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed, [], "json"
        except Exception:
            return None, ["malformed_output"], "malformed"
    if kind == "docs_normalization_plan":
        if "delete" in text.lower():
            return None, ["deletion_detected"], "unsafe"
        return {"text": text}, [], "markdown"
    if kind == "patch_proposal":
        if any(tok in text for tok in ["/.git", ".git/", "../", ".venv-rig", "chmod", "submodule"]):
            return None, ["forbidden_path"], "unsafe"
        if "delete mode" in text.lower():
            return None, ["deletion_detected"], "unsafe"
        if "diff --git" not in text and not text.lstrip().startswith("{"):
            return None, ["no_patch_found"], "malformed"
        return {"text": text}, [], "patch"
    if kind == "prompt_repair":
        if "repair" not in text.lower() and "template" not in text.lower():
            return None, ["missing_required_field"], "malformed"
        return {"text": text}, [], "markdown"
    return {"text": text}, [], "text"


def _score_candidate(*, repo_root: Path, parsed: dict[str, Any] | list[Any] | None, validation_errors: list[str], output_text: str, bias_profiles: list[dict[str, Any]] | None = None, current_task: str | None = None) -> dict[str, Any]:
    score = 0
    components = {
        "schema_parse": 20 if parsed is not None else 0,
        "safety_pass": 20 if not validation_errors else 0,
        "validation_pass": 30 if parsed is not None and not validation_errors else 0,
        "small_scope": 10 if len(output_text) < 4000 else 0,
        "deterministic_output": 10 if output_text.strip() else 0,
    }
    
    bias_info = {"bias_alignment_score": 0, "matches": [], "hard_fails": [], "status": "pass"}
    if bias_profiles and output_text:
        bias_info = solution_bias.score_bias_alignment(output_text, bias_profiles)
        components["bias_alignment"] = bias_info["bias_alignment_score"]

    intent_info = {"status": "none", "matched_action_id": None, "score": 0}
    if output_text:
        from rig_tools import intent_decoder
        decoded = intent_decoder.decode_intent(repo_root, output_text, current_task=current_task)
        intent_info["status"] = decoded["status"]
        intent_info["matched_action_id"] = decoded["matched_action_id"]
        if decoded["status"] in {"decoded", "repaired"}:
            intent_info["score"] = 10 if decoded["status"] == "decoded" else 5
            components["intent_decodability"] = intent_info["score"]
        elif decoded["status"] == "rejected":
             score -= 20 # Penalty for forbidden/destructive intents
             components["intent_rejection"] = -20

    score = sum(components.values()) - (10 if validation_errors else 0)
    return {
        "score": score,
        "components": components,
        "bias_info": bias_info,
        "intent_info": intent_info
    }


def _backend_generate(repo_root: Path, *, backend: str, model: str | None, model_path: str | None, prompt: str, prompt_kind: str, strategy: str, candidate_dir: Path, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {
            "status": "planned",
            "output": "",
            "error": None,
            "backend": backend,
            "model": model or model_path,
            "warnings": ["dry_run"],
            "planned_only": True,
        }
    if backend == "llama-cpp":
        env = llama_cpp_local.detect_llama_cpp_environment()
        if env.get("status") != "available":
            return {"status": "blocked", "error": "llama_server_not_configured", "warnings": ["llama_server_not_configured"], "backend": backend, "model": model_path}
        result = llama_cpp_local.generate_llama_cpp(prompt, model_path=model_path, preset="deterministic-json", max_tokens=400, temperature=0.0, top_p=1.0, n_ctx=8192, n_gpu_layers=-1, seed=0, structured_json=prompt_kind in {"plan", "validator_error_classification"}, timeout_seconds=120)
        return result
    result = mlx_local.generate_summary(prompt=prompt, model=model or mlx_local.SUMMARY_MODEL, backend=backend, max_tokens=400, timeout_seconds=120)
    return result


def _write_candidate_artifacts(candidate_dir: Path, *, prompt: str, output: str, parsed: dict[str, Any] | list[Any] | None, validation: dict[str, Any], score: dict[str, Any], dry_run: bool = False) -> None:
    candidate_dir.mkdir(parents=True, exist_ok=True)
    (candidate_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    (candidate_dir / "raw-output.txt").write_text(output, encoding="utf-8")
    (candidate_dir / "parsed.json").write_text(json.dumps(parsed if parsed is not None else {}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (candidate_dir / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (candidate_dir / "score.json").write_text(json.dumps(score, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def propose_swarm(
    repo_root: Path,
    *,
    task: str,
    kind: str,
    candidates: int,
    dry_run: bool = False,
    backend: str = "llama-cpp",
    model: str | None = None,
    model_path: str | None = None,
    profile: str = "balanced",
    max_parallel: int | None = None,
    use_llm_context: bool = False,
    bias_profiles: list[str] | None = None,
) -> dict[str, Any]:
    settings = SettingsStore(repo_root).get_effective_settings()
    pressure = sample_system_pressure(repo_root)
    backend_info = _available_backend_info(repo_root, backend)
    profile_data = _profile_defaults(profile)
    profile_limit = int(max_parallel or settings.get("swarm", {}).get("max_parallel_agents") or profile_data["max_parallel"] or 1)
    max_parallel = profile_limit
    ctx_size = int((settings.get("swarm", {}) or {}).get("ctx_size") or 8192)
    effective_context_per_candidate = int(ctx_size / max(1, max_parallel))
    minimum = int((settings.get("swarm", {}) or {}).get("minimum_context_tokens_per_candidate", {}).get(kind) or MIN_CONTEXT_TOKENS.get(kind, 4096))
    swarm_id = f"swarm-{uuid.uuid4().hex[:10]}"
    swarm_dir = _dir(repo_root, swarm_id)
    context_pack = context_compression.build_context_pack(repo_root, task=task, purpose="agent-plan", max_chars=ctx_size, use_llm=use_llm_context)
    context_path = swarm_dir / "context-pack.md"
    context_path.write_text(context_pack["markdown"], encoding="utf-8")
    warnings: list[str] = []
    status = "planned"
    blocked_reason: str | None = None
    if not can_launch_parallel_agents(settings, pressure):
        blocked_reason = "high_memory_pressure"
    elif candidates > max_parallel:
        blocked_reason = "candidate_count_exceeds_profile"
    elif effective_context_per_candidate < minimum:
        blocked_reason = "context_too_small_per_candidate"
        warnings.append(f"effective_context_per_candidate={effective_context_per_candidate} minimum={minimum}")
    elif backend == "llama-cpp" and backend_info.get("status") != "available":
        blocked_reason = "llama_server_unavailable"
    if dry_run:
        status = "dry_run" if blocked_reason is None else "blocked"
    elif blocked_reason:
        status = "blocked"

    # Load bias profiles
    bias_profile_data = []
    if bias_profiles:
        for bp_id in bias_profiles:
            bp = solution_bias.get_profile(repo_root, bp_id)
            if bp:
                bias_profile_data.append(bp)
            else:
                warnings.append(f"unknown_bias_profile={bp_id}")

    candidates_payload: list[dict[str, Any]] = []
    scoreboard_rows: list[dict[str, Any]] = []
    candidate_strategy_cycle = STRATEGIES[:]
    if kind == "patch_proposal":
        candidate_strategy_cycle = ["small_patch_decomposition", "conservative_minimal", "validator_error_focused", "docs_schema_first"]
    elif kind == "validator_error_classification":
        candidate_strategy_cycle = ["validator_error_focused", "conservative_minimal", "test_first", "docs_schema_first"]
    elif kind == "docs_normalization_plan":
        candidate_strategy_cycle = ["docs_schema_first", "conservative_minimal", "architecture_first", "test_first"]
    elif kind == "prompt_repair":
        candidate_strategy_cycle = ["validator_error_focused", "conservative_minimal", "test_first", "small_patch_decomposition"]
    winner_id: str | None = None
    if not blocked_reason or dry_run:
        for idx in range(candidates):
            candidate_id = f"cand-{idx+1:02d}"
            strategy = candidate_strategy_cycle[idx % len(candidate_strategy_cycle)]
            candidate_dir = swarm_dir / "candidates" / candidate_id
            prompt = _candidate_prompt(repo_root, task, kind, strategy, context_pack["markdown"], contract=f"rig.{kind}.v1", bias_profiles=bias_profile_data)
            if dry_run:
                result = {
                    "status": "planned",
                    "output": "",
                    "error": None,
                    "backend": backend,
                    "model": model or model_path,
                    "warnings": ["dry_run"],
                    "planned_only": True,
                }
                output = ""
                parsed = None
                validation_errors = []
                parse_mode = "planned"
                candidate_status = "planned"
                score_data = _score_candidate(repo_root=repo_root, parsed=None, validation_errors=[], output_text="", bias_profiles=bias_profile_data, current_task=task)
            else:
                result = _backend_generate(repo_root, backend=backend, model=model, model_path=model_path, prompt=prompt, prompt_kind=kind, strategy=strategy, candidate_dir=candidate_dir, dry_run=dry_run)
                output = str(result.get("output") or "")
                parsed, validation_errors, parse_mode = _validate_output(kind, output)
                score_data = _score_candidate(repo_root=repo_root, parsed=parsed, validation_errors=validation_errors, output_text=output, bias_profiles=bias_profile_data, current_task=task)
                candidate_status = "quarantined" if validation_errors or result.get("status") not in {"generated", "planned"} else "passed"
                
                # Check for hard fails
                if score_data["bias_info"]["hard_fails"]:
                    candidate_status = "quarantined"
                    validation_errors.append(f"bias_hard_fail={score_data['bias_info']['hard_fails'][0]['rule_id']}")

            score = score_data["score"]
            validation = {
                "schema_version": CANDIDATE_SCHEMA_VERSION,
                "swarm_id": swarm_id,
                "candidate_id": candidate_id,
                "task": task,
                "kind": kind,
                "strategy": strategy,
                "prompt_path": _repo_rel(repo_root, candidate_dir / "prompt.md"),
                "raw_output_path": _repo_rel(repo_root, candidate_dir / "raw-output.txt"),
                "parsed_output_path": _repo_rel(repo_root, candidate_dir / "parsed.json"),
                "validation_path": _repo_rel(repo_root, candidate_dir / "validation.json"),
                "score_path": _repo_rel(repo_root, candidate_dir / "score.json"),
                "status": candidate_status,
                "score": score,
                "bias_alignment": score_data["bias_info"]["bias_alignment_score"],
                "failure_type": validation_errors[0] if validation_errors else None,
                "warnings": ["dry_run"] if dry_run else (result.get("warnings", []) if isinstance(result, dict) else []),
                "authoritative": False,
                "parse_mode": parse_mode,
                "validation_errors": validation_errors,
                "backend_result_status": result.get("status"),
                "dry_run": dry_run,
            }
            _write_candidate_artifacts(candidate_dir, prompt=prompt, output=output, parsed=parsed, validation=validation, score=score_data, dry_run=dry_run)
            trace = None
            if not dry_run:
                trace = prompt_telemetry.record_trace(
                    repo_root,
                    task=task,
                    prompt_kind=f"proposal_swarm:{kind}",
                    prompt_template_id=f"rig.proposal_swarm.{kind}",
                    backend=backend,
                    model=str(result.get("model") or result.get("model_path") or model or model_path or ""),
                    runtime_settings={"backend": backend, "profile": profile, "strategy": strategy, "swarm_id": swarm_id, "bias_profiles": bias_profiles},
                    context_pack_path=context_path,
                    prompt_text=prompt,
                    raw_output_text=output,
                    parsed_output_text=json.dumps(parsed, indent=2, sort_keys=True) if isinstance(parsed, (dict, list)) else "",
                    validator_text=json.dumps(validation, indent=2, sort_keys=True),
                    status="valid" if not validation_errors and result.get("status") in {"generated", "planned"} else "invalid",
                    failure_type=validation_errors[0] if validation_errors else ("unknown" if result.get("status") in {"generated", "planned"} else str(result.get("status"))),
                    failure_summary="; ".join(validation_errors) if validation_errors else "",
                    repair_attempted=False,
                    repair_success=False,
                    quarantined=bool(validation_errors or result.get("status") not in {"generated", "planned"}),
                    prompt_path=candidate_dir / "prompt.md",
                    raw_output_path=candidate_dir / "raw-output.txt",
                    parsed_output_path=candidate_dir / "parsed.json",
                    validator_path=candidate_dir / "validation.json",
                    validator_kind="schema_validation",
                    validator_artifact=f"rig.{kind}.v1",
                    expected_contract=f"rig.{kind}.v1",
                    prompt_knobs={"strategy": strategy, "profile": profile, "candidate_index": idx + 1, "bias_profiles": bias_profiles},
                    context_char_count=context_pack.get("char_count"),
                    model_runtime_settings=result if isinstance(result, dict) else {},
                    section_order=[sec.get("section_type") for sec in context_pack.get("sections", []) if isinstance(sec, dict)],
                    retry_count=0,
                    related_loop_run_id=None,
                    related_agent_run_id=None,
                    model_path=str(result.get("model_path") or model_path) if (result.get("model_path") or model_path) else None,
                    model_filename=str(Path(result.get("model_path") or model_path).name) if (result.get("model_path") or model_path) else None,
                    preset=result.get("preset") or "deterministic-json",
                    n_batch=result.get("n_batch"),
                    n_ctx=result.get("n_ctx"),
                    n_gpu_layers=result.get("n_gpu_layers"),
                    temperature=result.get("temperature"),
                    top_p=result.get("top_p"),
                    top_k=result.get("top_k"),
                    min_p=result.get("min_p"),
                    repeat_penalty=result.get("repeat_penalty"),
                    seed=result.get("seed"),
                    max_tokens=result.get("max_tokens"),
                    stop=result.get("stop"),
                    structured_json_enabled=result.get("structured_json_enabled"),
                    grammar_path=result.get("grammar_path"),
                    json_schema_path=result.get("json_schema_path"),
                    constrained_decoding_status=result.get("constrained_decoding_status"),
                )
                
                # Record model behavior observation
                obs = {
                    "schema_version": "1.0.0",
                    "observation_id": f"obs-{uuid.uuid4().hex[:8]}",
                    "created_at": _utc_now(),
                    "swarm_id": swarm_id,
                    "candidate_id": candidate_id,
                    "model": str(result.get("model") or ""),
                    "backend": backend,
                    "prompt_template": f"rig.proposal_swarm.{kind}",
                    "bias_profiles": bias_profiles or [],
                    "strategy": strategy,
                    "temperature": result.get("temperature"),
                    "context_pack_hash": context_pack.get("hash"),
                    "output_status": candidate_status,
                    "failure_type": validation_errors[0] if validation_errors else None,
                    "validator_results": validation,
                    "score": score,
                    "quarantined": candidate_status == "quarantined",
                    "artifacts": [
                        _repo_rel(repo_root, candidate_dir / "prompt.md"),
                        _repo_rel(repo_root, candidate_dir / "raw-output.txt"),
                        _repo_rel(repo_root, candidate_dir / "parsed.json")
                    ],
                    "authoritative": False
                }
                (candidate_dir / "observation.json").write_text(json.dumps(obs, indent=2, sort_keys=True), encoding="utf-8")

                if validation_errors:
                    prompt_regression.add_from_quarantine(repo_root, prompt_kind=kind, allow_small_sample=True)

            candidates_payload.append(validation)
            scoreboard_rows.append({
                "candidate_id": candidate_id,
                "strategy": strategy,
                "score": score,
                "bias_alignment": score_data["bias_info"]["bias_alignment_score"],
                "status": candidate_status,
                "failure_type": validation_errors[0] if validation_errors else None,
                "prompt_trace_id": trace.get("trace_id") if isinstance(trace, dict) else None
            })
        valid_rows = [row for row in scoreboard_rows if row["status"] == "passed"]
        if valid_rows:
            winner_id = sorted(valid_rows, key=lambda row: (-row["score"], row["candidate_id"]))[0]["candidate_id"]
        elif scoreboard_rows:
            winner_id = sorted(scoreboard_rows, key=lambda row: (-row["score"], row["candidate_id"]))[0]["candidate_id"]
    scoreboard = {
        "schema_version": SCHEMA_VERSION,
        "swarm_id": swarm_id,
        "task": task,
        "kind": kind,
        "created_at": _utc_now(),
        "backend": backend,
        "model": model,
        "profile": profile,
        "bias_profiles": bias_profiles or [],
        "candidate_count": candidates,
        "max_parallel": max_parallel,
        "effective_context_per_candidate": effective_context_per_candidate,
        "context_pack_path": _repo_rel(repo_root, context_path),
        "status": status,
        "candidates": candidates_payload,
        "winner_candidate_id": winner_id,
        "scoreboard_path": _repo_rel(repo_root, swarm_dir / "scoreboard.json"),
        "warnings": warnings + ([blocked_reason] if blocked_reason else []),
        "authoritative": True,
    }
    (swarm_dir / "swarm-run.json").write_text(json.dumps(scoreboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (swarm_dir / "scoreboard.json").write_text(json.dumps({"swarm_id": swarm_id, "candidates": scoreboard_rows, "winner_candidate_id": winner_id, "status": status}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (swarm_dir / "scoreboard.md").write_text("\n".join([
        "# Rig Proposal Swarm Scoreboard",
        f"- Swarm: `{swarm_id}`",
        f"- Status: `{status}`",
        f"- Winner: `{winner_id or 'none'}`",
        "",
        "## Candidates",
        *[f"- `{row['candidate_id']}` strategy=`{row['strategy']}` score=`{row['score']}` status=`{row['status']}`" for row in scoreboard_rows],
    ]) + "\n", encoding="utf-8")
    (repo_root / ".build" / "rig" / "swarm").mkdir(parents=True, exist_ok=True)
    (repo_root / ".build" / "rig" / "swarm" / "latest.json").write_text(json.dumps(scoreboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (repo_root / ".build" / "rig" / "swarm" / "latest.md").write_text((swarm_dir / "scoreboard.md").read_text(encoding="utf-8"), encoding="utf-8")
    write_action_manifest(
        repo_root,
        task=task,
        action_kind="swarm.propose",
        command_group="swarm",
        command=["python", "scripts/rig.py", "swarm", "propose", "--task", task, "--kind", kind, "--candidates", str(candidates)],
        inputs=[{"path": _repo_rel(repo_root, context_path), "kind": "context_pack"}],
        outputs=[{"path": _repo_rel(repo_root, swarm_dir / "swarm-run.json"), "kind": "swarm_run", "status": "produced"}, {"path": _repo_rel(repo_root, swarm_dir / "scoreboard.json"), "kind": "scoreboard", "status": "produced"}],
        status="pass" if status != "blocked" else "warn",
        exit_code=0,
        result_path=swarm_dir / "swarm-run.json",
    )
    return scoreboard


def show_swarm(repo_root: Path, swarm_id: str) -> dict[str, Any]:
    path = repo_root / ".build" / "rig" / "swarm" / swarm_id / "swarm-run.json"
    return _load_json(path, {"status": "missing", "swarm_id": swarm_id})


def scoreboard(repo_root: Path, swarm_id: str) -> dict[str, Any]:
    path = repo_root / ".build" / "rig" / "swarm" / swarm_id / "scoreboard.json"
    return _load_json(path, {"status": "missing", "swarm_id": swarm_id})
