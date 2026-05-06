from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "rig.prompt_trace.v1"
MAX_TEXT_BYTES = 120000
MAX_CONTEXT_BYTES = 48000


def _repo_rel(repo_root: Path, path: Path| Optional) -> str| Optional:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _safe_text(text: str, limit: int) -> str:
    text = text or ""
    if len(text.encode("utf-8", errors="ignore")) <= limit:
        return text
    return text[:limit]


def telemetry_dir(repo_root: Path) -> Path:
    out = repo_root / ".build" / "rig" / "prompts"
    out.mkdir(parents=True, exist_ok=True)
    return out


def trace_dir(repo_root: Path, trace_id: str) -> Path:
    out = telemetry_dir(repo_root) / "traces" / trace_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def quarantine_dir(repo_root: Path, trace_id: str) -> Path:
    out = telemetry_dir(repo_root) / "quarantine" / trace_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def regression_dir(repo_root: Path, prompt_kind: str) -> Path:
    out = telemetry_dir(repo_root) / "regression" / prompt_kind
    out.mkdir(parents=True, exist_ok=True)
    return out


def experiments_dir(repo_root: Path, experiment_id: str) -> Path:
    out = telemetry_dir(repo_root) / "experiments" / experiment_id
    out.mkdir(parents=True, exist_ok=True)
    return out


def prompt_templates_dir(repo_root: Path) -> Path:
    out = repo_root / "Docs" / "dev" / "rig" / "prompts"
    out.mkdir(parents=True, exist_ok=True)
    return out


def classify_failure(*, raw_output: str, parsed_output: Any, validator_errors: list[str]| Optional, unsafe: bool = False, timeout: bool = False, error: str| Optional = None) -> str:
    if timeout:
        return "timeout"
    if unsafe:
        return "unsafe_action"
    if not raw_output.strip():
        return "empty_output"
    if "```" in raw_output:
        return "markdown_fence"
    if raw_output.lstrip().startswith("{") and parsed_output is None:
        return "malformed_json"
    if not raw_output.lstrip().startswith("{") and parsed_output is None:
        return "prose_before_json" if any(ch in raw_output for ch in ["{", "}"]) else "malformed_json"
    if validator_errors:
        for item in validator_errors:
            if "missing required field" in item:
                return "missing_required_field"
            if "expected one of" in item:
                return "wrong_enum"
            if "path" in item or "allowlist" in item:
                return "path_outside_allowlist"
        return "unknown"
    if error:
        return "error"
    return "unknown"


def _manifest(repo_root: Path, *, trace_id: str, task: str| Optional, prompt_kind: str, prompt_template_id: str, backend: str, model: str, runtime_settings: dict[str, Any], context_pack_path: Path| Optional, prompt_path: Path, raw_output_path: Path, parsed_output_path: Path| Optional, validator_path: Path| Optional, status: str, failure_type: str, failure_summary: str, repair_attempted: bool, repair_success: bool, quarantined: bool, prompt_text: str, raw_output_text: str, parsed_output_text: str, validator_text: str, validator_kind: str| Optional = None, validator_artifact: str| Optional = None, expected_contract: str| Optional = None, repair_strategy: str| Optional = None, prompt_knobs: dict[str, Any]| Optional = None, context_char_count: int| Optional = None, model_runtime_settings: dict[str, Any]| Optional = None, section_order: list[str]| Optional = None, retry_count: int| Optional = None, related_patch_id: str| Optional = None, related_loop_run_id: str| Optional = None, related_agent_run_id: str| Optional = None, model_path: str| Optional = None, model_filename: str| Optional = None, preset: str| Optional = None, n_batch: int| Optional = None, n_ctx: int| Optional = None, n_gpu_layers: int| Optional = None, temperature: float| Optional = None, top_p: float| Optional = None, top_k: int| Optional = None, min_p: float| Optional = None, repeat_penalty: float| Optional = None, seed: int| Optional = None, max_tokens: int| Optional = None, stop: list[str]| Optional = None, structured_json_enabled: bool| Optional = None, grammar_path: str| Optional = None, json_schema_path: str| Optional = None, constrained_decoding_status: str| Optional = None, intent_status: str| Optional = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "trace_id": trace_id,
        "task": task,
        "prompt_kind": prompt_kind,
        "prompt_template_id": prompt_template_id,
        "backend": backend,
        "model": model,
        "model_path": model_path,
        "model_filename": model_filename,
        "preset": preset,
        "n_batch": n_batch,
        "runtime_settings": runtime_settings,
        "model_runtime_settings": model_runtime_settings or runtime_settings,
        "n_ctx": n_ctx,
        "n_gpu_layers": n_gpu_layers,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "min_p": min_p,
        "repeat_penalty": repeat_penalty,
        "seed": seed,
        "max_tokens": max_tokens,
        "stop": stop or [],
        "structured_json_enabled": structured_json_enabled,
        "grammar_path": grammar_path,
        "json_schema_path": json_schema_path,
        "constrained_decoding_status": constrained_decoding_status,
        "intent_status": intent_status,
        "context_pack_path": _repo_rel(repo_root, context_pack_path) if context_pack_path else None,
        "context_hash": _sha256_text(_safe_text(prompt_text, MAX_CONTEXT_BYTES)),
        "context_char_count": context_char_count if context_char_count is not None else len(_safe_text(prompt_text, MAX_CONTEXT_BYTES)),
        "prompt_path": _repo_rel(repo_root, prompt_path),
        "raw_output_path": _repo_rel(repo_root, raw_output_path),
        "parsed_output_path": _repo_rel(repo_root, parsed_output_path) if parsed_output_path else None,
        "validator_path": _repo_rel(repo_root, validator_path) if validator_path else None,
        "validator_kind": validator_kind,
        "validator_artifact": validator_artifact,
        "expected_contract": expected_contract,
        "repair_strategy": repair_strategy,
        "prompt_knobs": prompt_knobs or {},
        "section_order": section_order or [],
        "retry_count": retry_count,
        "related_patch_id": related_patch_id,
        "related_loop_run_id": related_loop_run_id,
        "related_agent_run_id": related_agent_run_id,
        "status": status,
        "failure_type": failure_type,
        "failure_summary": failure_summary,
        "repair_attempted": repair_attempted,
        "repair_success": repair_success,
        "quarantined": quarantined,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "authoritative": False,
        "hashes": {
            "prompt_sha256": _sha256_text(_safe_text(prompt_text, MAX_TEXT_BYTES)),
            "raw_output_sha256": _sha256_text(_safe_text(raw_output_text, MAX_TEXT_BYTES)),
            "parsed_output_sha256": _sha256_text(_safe_text(parsed_output_text, MAX_TEXT_BYTES)) if parsed_output_text else None,
            "validator_sha256": _sha256_text(_safe_text(validator_text, MAX_TEXT_BYTES)) if validator_text else None,
        },
    }


def write_trace(repo_root: Path, *, task: str| Optional, prompt_kind: str, prompt_template_id: str, backend: str, model: str, runtime_settings: dict[str, Any], context_pack_path: Path| Optional, prompt_text: str, raw_output_text: str, parsed_output_text: str = "", validator_text: str = "", status: str = "valid", failure_type: str = "unknown", failure_summary: str = "", repair_attempted: bool = False, repair_success: bool = False, quarantined: bool = False, prompt_path: Path| Optional = None, raw_output_path: Path| Optional = None, parsed_output_path: Path| Optional = None, validator_path: Path| Optional = None, validator_kind: str| Optional = None, validator_artifact: str| Optional = None, expected_contract: str| Optional = None, repair_strategy: str| Optional = None, prompt_knobs: dict[str, Any]| Optional = None, context_char_count: int| Optional = None, model_runtime_settings: dict[str, Any]| Optional = None, section_order: list[str]| Optional = None, retry_count: int| Optional = None, related_patch_id: str| Optional = None, related_loop_run_id: str| Optional = None, related_agent_run_id: str| Optional = None, model_path: str| Optional = None, model_filename: str| Optional = None, preset: str| Optional = None, n_batch: int| Optional = None, n_ctx: int| Optional = None, n_gpu_layers: int| Optional = None, temperature: float| Optional = None, top_p: float| Optional = None, top_k: int| Optional = None, min_p: float| Optional = None, repeat_penalty: float| Optional = None, seed: int| Optional = None, max_tokens: int| Optional = None, stop: list[str]| Optional = None, structured_json_enabled: bool| Optional = None, grammar_path: str| Optional = None, json_schema_path: str| Optional = None, constrained_decoding_status: str| Optional = None, intent_status: str| Optional = None) -> dict[str, Any]:
    trace_id = f"trace-{uuid.uuid4().hex[:10]}"
    tdir = trace_dir(repo_root, trace_id)
    prompt_path = prompt_path or (tdir / "prompt.txt")
    raw_output_path = raw_output_path or (tdir / "raw-output.txt")
    parsed_output_path = parsed_output_path or (tdir / "parsed-output.json")
    validator_path = validator_path or (tdir / "validator.txt")
    prompt_path.write_text(_safe_text(prompt_text, MAX_TEXT_BYTES), encoding="utf-8")
    raw_output_path.write_text(_safe_text(raw_output_text, MAX_TEXT_BYTES), encoding="utf-8")
    parsed_output_path.write_text(_safe_text(parsed_output_text, MAX_TEXT_BYTES), encoding="utf-8")
    validator_path.write_text(_safe_text(validator_text, MAX_TEXT_BYTES), encoding="utf-8")
    payload = _manifest(
        repo_root,
        trace_id=trace_id,
        task=task,
        prompt_kind=prompt_kind,
        prompt_template_id=prompt_template_id,
        backend=backend,
        model=model,
        runtime_settings=runtime_settings,
        context_pack_path=context_pack_path,
        prompt_path=prompt_path,
        raw_output_path=raw_output_path,
        parsed_output_path=parsed_output_path,
        validator_path=validator_path,
        status=status,
        failure_type=failure_type,
        failure_summary=failure_summary,
        repair_attempted=repair_attempted,
        repair_success=repair_success,
        quarantined=quarantined,
        prompt_text=prompt_text,
        raw_output_text=raw_output_text,
        parsed_output_text=parsed_output_text,
        validator_text=validator_text,
        validator_kind=validator_kind,
        validator_artifact=validator_artifact,
        expected_contract=expected_contract,
        repair_strategy=repair_strategy,
        prompt_knobs=prompt_knobs,
        context_char_count=context_char_count,
        model_runtime_settings=model_runtime_settings,
        section_order=section_order,
        retry_count=retry_count,
        related_patch_id=related_patch_id,
        related_loop_run_id=related_loop_run_id,
        related_agent_run_id=related_agent_run_id,
        model_path=model_path,
        model_filename=model_filename,
        preset=preset,
        n_batch=n_batch,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        repeat_penalty=repeat_penalty,
        seed=seed,
        max_tokens=max_tokens,
        stop=stop,
        structured_json_enabled=structured_json_enabled,
        grammar_path=grammar_path,
        json_schema_path=json_schema_path,
        constrained_decoding_status=constrained_decoding_status,
        intent_status=intent_status,
    )
    (tdir / "trace.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (telemetry_dir(repo_root) / "latest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def quarantine_trace(repo_root: Path, trace: dict[str, Any], *, validator_errors: list[str]| Optional = None) -> dict[str, Any]:
    qdir = quarantine_dir(repo_root, str(trace["trace_id"]))
    payload = dict(trace)
    payload["quarantined"] = True
    payload["validator_errors"] = validator_errors or []
    payload["quarantine_reason"] = payload.get("failure_type")
    (qdir / "trace.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for key in ["prompt_path", "raw_output_path", "parsed_output_path", "validator_path"]:
        rel = payload.get(key)
        if rel:
            src = repo_root / rel
            if src.exists():
                target = qdir / Path(rel).name
                target.write_text(src.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    summary = qdir / "summary.md"
    summary.write_text("\n".join([
        "# Rig Prompt Quarantine",
        "",
        f"- Trace ID: `{trace['trace_id']}`",
        f"- Prompt kind: `{trace.get('prompt_kind')}`",
        f"- Failure type: `{payload.get('failure_type')}`",
        f"- Failure summary: `{payload.get('failure_summary')}`",
    ]) + "\n", encoding="utf-8")
    payload["quarantine_path"] = _repo_rel(repo_root, qdir)
    payload["quarantine_summary_path"] = _repo_rel(repo_root, summary)
    return payload


def load_trace(repo_root: Path, trace_id: str) -> dict[str, Any]| Optional:
    path = telemetry_dir(repo_root) / "traces" / trace_id / "trace.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def list_traces(repo_root: Path) -> list[dict[str, Any]]:
    root = telemetry_dir(repo_root) / "traces"
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/trace.json"), key=lambda p: p.parent.name):
        data = load_trace(repo_root, path.parent.name)
        if data:
            rows.append(data)
    return rows


def latest_trace(repo_root: Path) -> dict[str, Any]| Optional:
    path = telemetry_dir(repo_root) / "latest.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def top_failure_types(repo_root: Path, limit: int = 5) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for trace in list_traces(repo_root):
        failure = str(trace.get("failure_type") or "unknown")
        counts[failure] = counts.get(failure, 0) + 1
    qroot = telemetry_dir(repo_root) / "quarantine"
    if qroot.exists():
        for trace_dir in sorted([p for p in qroot.iterdir() if p.is_dir()], key=lambda p: p.name):
            path = trace_dir / "trace.json"
            if not path.exists():
                continue
            try:
                trace = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(trace, dict):
                failure = str(trace.get("failure_type") or "unknown")
                counts[failure] = counts.get(failure, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return [{"failure_type": failure_type, "count": count} for failure_type, count in ordered]


def record_trace(
    repo_root: Path,
    *,
    task: str| Optional,
    prompt_kind: str,
    prompt_template_id: str,
    backend: str,
    model: str,
    runtime_settings: dict[str, Any],
    context_pack_path: Path| Optional,
    prompt_text: str,
    raw_output_text: str,
    parsed_output_text: str = "",
    validator_text: str = "",
    status: str = "valid",
    failure_type: str = "unknown",
    failure_summary: str = "",
    repair_attempted: bool = False,
    repair_success: bool = False,
    quarantined: bool = False,
    validator_errors: list[str]| Optional = None,
    prompt_path: Path| Optional = None,
    raw_output_path: Path| Optional = None,
    parsed_output_path: Path| Optional = None,
    validator_path: Path| Optional = None,
    validator_kind: str| Optional = None,
    validator_artifact: str| Optional = None,
    expected_contract: str| Optional = None,
    repair_strategy: str| Optional = None,
    prompt_knobs: dict[str, Any]| Optional = None,
    context_char_count: int| Optional = None,
    model_runtime_settings: dict[str, Any]| Optional = None,
    section_order: list[str]| Optional = None,
    retry_count: int| Optional = None,
    related_patch_id: str| Optional = None,
    related_loop_run_id: str| Optional = None,
    related_agent_run_id: str| Optional = None,
    model_path: str| Optional = None,
    model_filename: str| Optional = None,
    preset: str| Optional = None,
    n_batch: int| Optional = None,
    n_ctx: int| Optional = None,
    n_gpu_layers: int| Optional = None,
    temperature: float| Optional = None,
    top_p: float| Optional = None,
    top_k: int| Optional = None,
    min_p: float| Optional = None,
    repeat_penalty: float| Optional = None,
    seed: int| Optional = None,
    max_tokens: int| Optional = None,
    stop: list[str]| Optional = None,
    structured_json_enabled: bool| Optional = None,
    grammar_path: str| Optional = None,
    json_schema_path: str| Optional = None,
    constrained_decoding_status: str| Optional = None,
) -> dict[str, Any]:
    trace = write_trace(
        repo_root,
        task=task,
        prompt_kind=prompt_kind,
        prompt_template_id=prompt_template_id,
        backend=backend,
        model=model,
        runtime_settings=runtime_settings,
        context_pack_path=context_pack_path,
        prompt_text=prompt_text,
        raw_output_text=raw_output_text,
        parsed_output_text=parsed_output_text,
        validator_text=validator_text,
        status=status,
        failure_type=failure_type,
        failure_summary=failure_summary,
        repair_attempted=repair_attempted,
        repair_success=repair_success,
        quarantined=quarantined or status != "valid",
        prompt_path=prompt_path,
        raw_output_path=raw_output_path,
        parsed_output_path=parsed_output_path,
        validator_path=validator_path,
        validator_kind=validator_kind,
        validator_artifact=validator_artifact,
        expected_contract=expected_contract,
        repair_strategy=repair_strategy,
        prompt_knobs=prompt_knobs,
        context_char_count=context_char_count,
        model_runtime_settings=model_runtime_settings,
        section_order=section_order,
        retry_count=retry_count,
        related_patch_id=related_patch_id,
        related_loop_run_id=related_loop_run_id,
        related_agent_run_id=related_agent_run_id,
        model_path=model_path,
        model_filename=model_filename,
        preset=preset,
        n_batch=n_batch,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        min_p=min_p,
        repeat_penalty=repeat_penalty,
        seed=seed,
        max_tokens=max_tokens,
        stop=stop,
        structured_json_enabled=structured_json_enabled,
        grammar_path=grammar_path,
        json_schema_path=json_schema_path,
        constrained_decoding_status=constrained_decoding_status,
    )
    if trace.get("status") != "valid" or trace.get("quarantined"):
        trace = quarantine_trace(repo_root, trace, validator_errors=validator_errors)
    return trace
