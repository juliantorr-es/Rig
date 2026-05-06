from __future__ import annotations

import json
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

from rig_tools import mlx_local, prompt_telemetry, schema_validation


SCHEMA_VERSION = "rig.prompt_regression_case.v1"
EXPERIMENT_SCHEMA_VERSION = "rig.prompt_experiment.v1"


def _repo_rel(repo_root: Path, path: Path| Optional) -> str| Optional:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _dir(repo_root: Path, *parts: str) -> Path:
    out = repo_root / ".build" / "rig" / "prompts"
    for part in parts:
        out = out / part
    out.mkdir(parents=True, exist_ok=True)
    return out


def list_quarantine(repo_root: Path) -> list[dict[str, Any]]:
    qroot = prompt_telemetry.telemetry_dir(repo_root) / "quarantine"
    if not qroot.exists():
        return []
    out = []
    for trace_dir in sorted([p for p in qroot.iterdir() if p.is_dir()], key=lambda p: p.name):
        trace = trace_dir / "trace.json"
        if trace.exists():
            try:
                data = json.loads(trace.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    out.append(data)
            except Exception:
                continue
    return out


def add_from_quarantine(repo_root: Path, *, prompt_kind: str, allow_small_sample: bool = False) -> dict[str, Any]:
    cases_dir = _dir(repo_root, "regression", prompt_kind, "cases")
    added = 0
    failures = []
    for trace in list_quarantine(repo_root):
        if trace.get("prompt_kind") != prompt_kind:
            continue
        case_id = f"case-{uuid.uuid4().hex[:10]}"
        case = {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "source_trace_id": trace.get("trace_id"),
            "prompt_kind": prompt_kind,
            "task": trace.get("task"),
            "input_context_path": trace.get("context_pack_path"),
            "expected_contract": trace.get("prompt_template_id"),
            "failure_type": trace.get("failure_type"),
            "failure_summary": trace.get("failure_summary"),
            "validator_kind": "schema_validation",
            "minimal_reproduction_path": trace.get("quarantine_path") or trace.get("raw_output_path"),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "authoritative": False,
        }
        path = cases_dir / f"{case_id}.json"
        path.write_text(json.dumps(case, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        added += 1
    return {"status": "passed", "added": added, "case_dir": _repo_rel(repo_root, cases_dir), "warnings": failures}


def _cases(repo_root: Path, prompt_kind: str) -> list[dict[str, Any]]:
    cases_dir = repo_root / ".build" / "rig" / "prompts" / "regression" / prompt_kind / "cases"
    if not cases_dir.exists():
        return []
    rows = []
    for path in sorted(cases_dir.glob("*.json"), key=lambda p: p.name):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                rows.append(data)
        except Exception:
            continue
    return rows


def _validate_output(raw_output: str) -> tuple[dict[str, Any]| Optional, list[str]]:
    try:
        parsed = json.loads(raw_output)
        if isinstance(parsed, dict):
            return parsed, []
    except Exception as exc:
        return None, [str(exc)]
    return None, ["not_json"]


def _metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"schema_valid_rate": 0.0, "unsafe_rate": 0.0, "timeout_rate": 0.0, "repair_needed_rate": 0.0, "repair_success_rate": 0.0, "exact_contract_pass_rate": 0.0, "mean_output_chars": 0.0, "median_duration_seconds": 0.0, "regression_count": 0, "improvement_count": 0}
    schema_valid = sum(1 for r in results if r.get("status") == "valid")
    unsafe = sum(1 for r in results if r.get("status") == "unsafe")
    timeout = sum(1 for r in results if r.get("status") == "timeout")
    repair_needed = sum(1 for r in results if r.get("repair_attempted"))
    repair_success = sum(1 for r in results if r.get("repair_success"))
    exact_contract = sum(1 for r in results if r.get("exact_contract_pass"))
    return {
        "schema_valid_rate": round(schema_valid / len(results), 3),
        "unsafe_rate": round(unsafe / len(results), 3),
        "timeout_rate": round(timeout / len(results), 3),
        "repair_needed_rate": round(repair_needed / len(results), 3),
        "repair_success_rate": round(repair_success / max(1, repair_needed), 3) if repair_needed else 0.0,
        "exact_contract_pass_rate": round(exact_contract / len(results), 3),
        "mean_output_chars": round(statistics.mean([r.get("output_chars", 0) for r in results]), 1),
        "median_duration_seconds": round(statistics.median([r.get("duration_seconds", 0.0) for r in results]), 3),
        "regression_count": sum(1 for r in results if r.get("regression")),
        "improvement_count": sum(1 for r in results if r.get("improvement")),
    }


def _valid_rate(rows: list[dict[str, Any]]) -> float:
    return round(sum(1 for r in rows if r.get("status") == "valid") / len(rows), 3) if rows else 0.0


def _timeout_rate(rows: list[dict[str, Any]]) -> float:
    return round(sum(1 for r in rows if r.get("status") == "timeout") / len(rows), 3) if rows else 0.0


def _promotion_blockers(*, case_count: int, metrics: dict[str, Any], allow_small_sample: bool, baseline_timeout_rate: float| Optional = None, candidate_timeout_rate: float| Optional = None, unsafe_regression_count: int| Optional = None, critical_regression: bool| Optional = None) -> list[str]:
    blockers: list[str] = []
    if case_count < 5 and not allow_small_sample:
        blockers.append("insufficient_case_count")
    if unsafe_regression_count and unsafe_regression_count > 0:
        blockers.append("unsafe_regression")
    if float(metrics.get("schema_valid_rate") or 0.0) < 1.0:
        blockers.append("schema_valid_rate_not_perfect")
    if baseline_timeout_rate is not None and candidate_timeout_rate is not None and candidate_timeout_rate > baseline_timeout_rate:
        blockers.append("timeout_rate_increased")
    if critical_regression:
        blockers.append("critical_failure_regressed")
    return blockers


def _run_backend(repo_root: Path, prompt: str, *, task: str| Optional, prompt_kind: str, backend: str, model: str| Optional = None, model_path: str| Optional = None, prompt_knobs: dict[str, Any]| Optional = None) -> dict[str, Any]:
    if backend == "llama-cpp":
        from rig_tools import llama_cpp_local
        params = llama_cpp_local.resolve_params(preset=(prompt_knobs or {}).get("preset"), overrides=prompt_knobs)

        result = llama_cpp_local.generate_llama_cpp(
            prompt,
            model_path=model_path,
            preset=params.get("preset"),
            n_batch=params.get("n_batch"),
            max_tokens=int(params.get("max_tokens", 64)),
            temperature=float(params.get("temperature", 0.0)),
            top_p=float(params.get("top_p", 1.0)),
            top_k=params.get("top_k"),
            min_p=params.get("min_p"),
            repeat_penalty=params.get("repeat_penalty"),
            n_ctx=int(params.get("n_ctx", 8192)),
            n_gpu_layers=int(params.get("n_gpu_layers", -1)),
            seed=int(params.get("seed", 0)),
            stop=list(params.get("stop") or []),
            structured_json=bool(params.get("structured_json")),
            grammar_path=Path(params["grammar_path"]) if params.get("grammar_path") else None,
            json_schema_path=Path(params["json_schema"]) if params.get("json_schema") else None,
            timeout_seconds=int(params.get("timeout_seconds", 120)),
        )
        prompt_telemetry.record_trace(
            repo_root,
            task=task,
            prompt_kind=prompt_kind,
            prompt_template_id="rig.prompt_regression.v1",
            backend="llama-cpp",
            model=str(result.get("model_path") or model_path or ""),
            runtime_settings=prompt_knobs or {},
            context_pack_path=None,
            prompt_text=prompt,
            raw_output_text=str(result.get("output") or ""),
            parsed_output_text="",
            validator_text="",
            status="valid" if result.get("status") == "generated" else "error",
            failure_type="unknown" if result.get("status") == "generated" else str(result.get("status") or "error"),
            failure_summary=str(result.get("error") or ""),
            repair_attempted=False,
            repair_success=False,
            quarantined=result.get("status") != "generated",
            model_path=str(result.get("model_path") or model_path) if (result.get("model_path") or model_path) else None,
            model_filename=str(Path(result.get("model_path") or model_path).name) if (result.get("model_path") or model_path) else None,
            n_ctx=result.get("n_ctx"),
            n_gpu_layers=result.get("n_gpu_layers"),
            temperature=result.get("temperature"),
            seed=result.get("seed"),
            structured_json_enabled=result.get("structured_json_enabled"),
            grammar_path=result.get("grammar_path"),
            json_schema_path=result.get("json_schema_path"),
            constrained_decoding_status=result.get("constrained_decoding_status"),
        )
        return result
    return mlx_local.generate_summary(
        prompt=prompt,
        model=model or mlx_local.SUMMARY_MODEL,
        backend=backend,
        max_tokens=int((prompt_knobs or {}).get("max_tokens", 64)),
        timeout_seconds=int((prompt_knobs or {}).get("timeout_seconds", 120)),
    )


def run_regression(repo_root: Path, *, prompt_kind: str, baseline_template: str| Optional = None, candidate_template: str| Optional = None, allow_small_sample: bool = False, backend: str = "mlx", preset: str| Optional = None, model: str| Optional = None, model_path: str| Optional = None, prompt_knobs: dict[str, Any]| Optional = None, baseline_knobs: dict[str, Any]| Optional = None, candidate_knobs: dict[str, Any]| Optional = None, minimum_case_threshold: int = 5) -> dict[str, Any]:
    cases = _cases(repo_root, prompt_kind)
    if backend == "llama-cpp":
        from rig_tools import llama_cpp_local

        if llama_cpp_local.detect_llama_cpp_environment().get("status") != "available":
            return {"status": "failed", "reason": "candidate_backend_unavailable", "case_count": len(cases), "minimum_case_threshold": minimum_case_threshold}
    if backend == "llama-cpp" and not model_path:
        return {"status": "failed", "reason": "model_path_required", "case_count": len(cases), "minimum_case_threshold": minimum_case_threshold}
    if len(cases) < minimum_case_threshold and not allow_small_sample:
        return {"status": "failed", "reason": "insufficient_cases", "case_count": len(cases), "minimum_case_threshold": minimum_case_threshold}
    results = []
    baseline_results = []
    for case in cases:
        prompt = f"Prompt kind: {prompt_kind}\nCase: {case.get('case_id')}\n"
        baseline = _run_backend(repo_root, prompt + (baseline_template or "baseline"), task=case.get("task"), prompt_kind=prompt_kind, backend=backend, model=model, model_path=model_path, prompt_knobs={"preset": preset, **(baseline_knobs or prompt_knobs or {})})
        candidate = _run_backend(repo_root, prompt + (candidate_template or "candidate"), task=case.get("task"), prompt_kind=prompt_kind, backend=backend, model=model, model_path=model_path, prompt_knobs={"preset": preset, **(candidate_knobs or prompt_knobs or {})})
        baseline_parsed, baseline_errs = _validate_output(baseline.get("output") or "")
        candidate_parsed, candidate_errs = _validate_output(candidate.get("output") or "")
        baseline_valid = baseline_parsed is not None and not baseline_errs
        candidate_valid = candidate_parsed is not None and not candidate_errs
        baseline_results.append({
            "case_id": case.get("case_id"),
            "status": "valid" if baseline_valid else "invalid",
            "exact_contract_pass": baseline_valid,
            "output_chars": len(baseline.get("output") or ""),
            "duration_seconds": 0.0,
            "repair_attempted": False,
            "repair_success": False,
        })
        results.append({
            "case_id": case.get("case_id"),
            "status": "valid" if candidate_valid else "invalid",
            "exact_contract_pass": candidate_valid,
            "regression": baseline_valid and not candidate_valid,
            "improvement": not baseline_valid and candidate_valid,
            "output_chars": len(candidate.get("output") or ""),
            "duration_seconds": 0.0,
            "repair_attempted": False,
            "repair_success": False,
        })
    metrics = _metrics(results)
    baseline_schema_valid_rate = _valid_rate(baseline_results)
    candidate_schema_valid_rate = _valid_rate(results)
    baseline_timeout_rate = _timeout_rate(baseline_results)
    candidate_timeout_rate = _timeout_rate(results)
    unsafe_regression_count = sum(1 for r in results if r.get("regression") and r.get("status") == "unsafe")
    promotion_blockers = _promotion_blockers(
        case_count=len(cases),
        metrics=metrics,
        allow_small_sample=allow_small_sample,
        baseline_timeout_rate=baseline_timeout_rate,
        candidate_timeout_rate=candidate_timeout_rate,
        unsafe_regression_count=unsafe_regression_count,
        critical_regression=any(r.get("regression") for r in results if r.get("status") == "invalid"),
    )
    recommendation_reason = "candidate meets gate criteria" if not promotion_blockers else ", ".join(promotion_blockers)
    out_dir = _dir(repo_root, "experiments", f"{prompt_kind}-regression")
    payload = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_id": f"exp-{uuid.uuid4().hex[:10]}",
        "prompt_kind": prompt_kind,
        "baseline_template": baseline_template or "baseline",
        "candidate_template": candidate_template or "candidate",
        "case_count": len(cases),
        "minimum_case_threshold": minimum_case_threshold,
        "metrics": metrics,
        "prompt_knobs_compared": {"baseline": {"preset": preset, **(baseline_knobs or prompt_knobs or {})}, "candidate": {"preset": preset, **(candidate_knobs or prompt_knobs or {})}, "backend": backend, "model": model, "model_path": model_path},
        "baseline_schema_valid_rate": baseline_schema_valid_rate,
        "candidate_schema_valid_rate": candidate_schema_valid_rate,
        "baseline_timeout_rate": baseline_timeout_rate,
        "candidate_timeout_rate": candidate_timeout_rate,
        "unsafe_regression_count": unsafe_regression_count,
        "promotion_blockers": promotion_blockers,
        "recommendation_reason": recommendation_reason,
        "baseline_results": baseline_results,
        "candidate_results": results,
        "regressions": [r for r in results if r.get("regression")],
        "improvements": [r for r in results if r.get("improvement")],
        "promotion_recommendation": "promote" if not promotion_blockers else "hold",
        "warnings": [],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "authoritative": False,
    }
    (out_dir / "latest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "latest.md").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def compare_backends(
    repo_root: Path,
    *,
    prompt_kind: str,
    baseline_backend: str,
    baseline_preset: str| Optional = None,
    baseline_model: str| Optional = None,
    baseline_model_path: str| Optional = None,
    candidate_backend: str,
    candidate_preset: str| Optional = None,
    candidate_model: str| Optional = None,
    candidate_model_path: str| Optional = None,
    allow_small_sample: bool = False,
    minimum_case_threshold: int = 5,
) -> dict[str, Any]:
    baseline = run_regression(
        repo_root,
        prompt_kind=prompt_kind,
        allow_small_sample=allow_small_sample,
        backend=baseline_backend,
        preset=baseline_preset,
        model=baseline_model,
        model_path=baseline_model_path,
        minimum_case_threshold=minimum_case_threshold,
    )
    if baseline.get("status") == "failed":
        return {"status": "failed", "reason": baseline.get("reason") or "baseline_backend_unavailable", "baseline": baseline, "candidate": None}
    candidate = run_regression(
        repo_root,
        prompt_kind=prompt_kind,
        allow_small_sample=allow_small_sample,
        backend=candidate_backend,
        preset=candidate_preset,
        model=candidate_model,
        model_path=candidate_model_path,
        minimum_case_threshold=minimum_case_threshold,
    )
    if candidate.get("status") == "failed":
        return {"status": "failed", "reason": candidate.get("reason") or "candidate_backend_unavailable", "baseline": baseline, "candidate": candidate}
    comparison = {
        "status": "passed",
        "prompt_kind": prompt_kind,
        "baseline_backend": baseline_backend,
        "candidate_backend": candidate_backend,
        "baseline_model": baseline_model,
        "candidate_model": candidate_model,
        "baseline_model_path": baseline_model_path,
        "candidate_model_path": candidate_model_path,
        "baseline_metrics": baseline.get("metrics", {}),
        "candidate_metrics": candidate.get("metrics", {}),
        "promotion_recommendation": "promote" if candidate.get("promotion_recommendation") == "promote" and baseline.get("promotion_recommendation") == "promote" else "hold",
        "warnings": [],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "authoritative": False,
    }
    comparison["metrics"] = {
        "schema_valid_rate": candidate.get("metrics", {}).get("schema_valid_rate", 0.0) - baseline.get("metrics", {}).get("schema_valid_rate", 0.0),
        "malformed_json_rate": 0.0,
        "markdown_fence_rate": 0.0,
        "unsafe_rate": candidate.get("metrics", {}).get("unsafe_rate", 0.0),
        "timeout_rate": candidate.get("metrics", {}).get("timeout_rate", 0.0) - baseline.get("metrics", {}).get("timeout_rate", 0.0),
        "repair_needed_rate": candidate.get("metrics", {}).get("repair_needed_rate", 0.0) - baseline.get("metrics", {}).get("repair_needed_rate", 0.0),
        "output_char_count": candidate.get("metrics", {}).get("mean_output_chars", 0.0),
        "duration_seconds": candidate.get("metrics", {}).get("median_duration_seconds", 0.0),
    }
    out_dir = _dir(repo_root, "experiments", f"{prompt_kind}-backend-compare")
    (out_dir / "latest.json").write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "latest.md").write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return comparison
