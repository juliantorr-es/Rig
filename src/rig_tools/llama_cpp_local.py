from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


DEFAULT_MODEL_CONTEXT = 8192
PRESETS = {
    "fast-smoke": {"n_ctx": 4096, "n_gpu_layers": -1, "temperature": 0.0, "top_p": 1.0, "seed": 0, "max_tokens": 80},
    "deterministic-json": {"n_ctx": 8192, "n_gpu_layers": -1, "n_batch": 512, "temperature": 0.0, "top_p": 1.0, "top_k": 40, "repeat_penalty": 1.05, "seed": 0, "max_tokens": 400, "structured_json": True},
    "patch-diff": {"n_ctx": 8192, "n_gpu_layers": -1, "temperature": 0.0, "top_p": 1.0, "top_k": 40, "repeat_penalty": 1.03, "seed": 0, "max_tokens": 1200},
    "long-context-review": {"n_ctx": 16384, "n_gpu_layers": -1, "temperature": 0.0, "top_p": 1.0, "seed": 0, "max_tokens": 800},
}


def _import_llama_cpp():
    try:
        return importlib.import_module("llama_cpp")
    except Exception:
        return None


def _version() -> str | None:
    try:
        from importlib.metadata import version

        return version("llama-cpp-python")
    except Exception:
        module = _import_llama_cpp()
        return getattr(module, "__version__", None) if module else None


def detect_llama_cpp_environment() -> dict[str, Any]:
    module = _import_llama_cpp()
    warnings: list[str] = []
    if module is None:
        warnings.append("llama_cpp_unavailable")
    machine = os.uname().machine if hasattr(os, "uname") else os.environ.get("PROCESSOR_ARCHITECTURE")
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "platform_machine": machine,
        "llama_cpp": module is not None,
        "llama_cpp_version": _version() if module else None,
        "metal_capability": "unknown",
        "server_package_available": None,
        "status": "available" if module else "tool_missing",
        "warnings": warnings,
    }


def _structured_failure(*, status: str, error: str, warnings: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    payload = {
        "status": status,
        "backend": "llama-cpp",
        "warnings": warnings or [],
        "error": error,
    }
    payload.update(extra)
    return payload


def resolve_params(*, preset: str | None = None, overrides: dict[str, Any] | None = None, force_large_context: bool = False) -> dict[str, Any]:
    overrides = overrides or {}
    params: dict[str, Any] = {
        "preset": preset,
        "n_ctx": DEFAULT_MODEL_CONTEXT,
        "n_gpu_layers": -1,
        "n_batch": None,
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": None,
        "min_p": None,
        "repeat_penalty": None,
        "seed": 0,
        "max_tokens": 80,
        "stop": [],
        "structured_json": False,
        "schema_family": None,
        "json_schema": None,
        "grammar_path": None,
        "warnings": [],
    }
    if preset:
        if preset not in PRESETS:
            raise ValueError("invalid preset")
        params.update(PRESETS[preset])
    params.update({k: v for k, v in overrides.items() if v is not None})
    if int(params["n_ctx"]) < 512:
        raise ValueError("n_ctx too small")
    if int(params["max_tokens"]) < 0:
        raise ValueError("max_tokens must be non-negative")
    if int(params["n_ctx"]) > 16384 and not force_large_context:
        params["warnings"].append("large_context_warning")
    return params


def _load_grammar(grammar_path: Path | None, json_schema_path: Path | None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if grammar_path and grammar_path.exists():
        data["grammar_path"] = str(grammar_path)
        data["grammar"] = grammar_path.read_text(encoding="utf-8")
    if json_schema_path and json_schema_path.exists():
        data["json_schema_path"] = str(json_schema_path)
        data["json_schema"] = json_schema_path.read_text(encoding="utf-8")
    return data


def generate_llama_cpp(
    prompt: str,
    *,
    model_path: str | Path | None,
    preset: str | None = None,
    n_batch: int | None = None,
    max_tokens: int,
    temperature: float = 0.0,
    top_p: float = 1.0,
    top_k: int | None = None,
    min_p: float | None = None,
    repeat_penalty: float | None = None,
    n_ctx: int = DEFAULT_MODEL_CONTEXT,
    n_gpu_layers: int = -1,
    seed: int = 0,
    stop: list[str] | None = None,
    grammar_path: Path | None = None,
    json_schema_path: Path | None = None,
    structured_json: bool = False,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    if not model_path:
        return _structured_failure(status="failed", error="model_path_required", warnings=["model_path_required"])
    model_path = Path(model_path)
    if not model_path.exists():
        return _structured_failure(status="failed", error="model_path_not_found", warnings=["model_path_not_found"], model_path=str(model_path))
    llama_cpp = _import_llama_cpp()
    if llama_cpp is None:
        return _structured_failure(status="tool_missing", error="llama_cpp_unavailable", warnings=["llama_cpp_unavailable"], model_path=str(model_path), preset=preset, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, n_batch=n_batch, temperature=temperature, top_p=top_p, top_k=top_k, min_p=min_p, repeat_penalty=repeat_penalty, seed=seed, max_tokens=max_tokens, stop=stop or [], structured_json=structured_json, schema_family=None, json_schema_path=str(json_schema_path) if json_schema_path else None, grammar_path=str(grammar_path) if grammar_path else None)

    kwargs: dict[str, Any] = {
        "model_path": str(model_path),
        "n_ctx": n_ctx,
        "n_gpu_layers": n_gpu_layers,
        "verbose": False,
    }
    if hasattr(llama_cpp, "Llama"):
        try:
            if (grammar_path or json_schema_path) and not hasattr(llama_cpp, "LlamaGrammar"):
                return _structured_failure(status="structured_output_unavailable", error="structured_output_unavailable", warnings=["structured_output_unavailable"], model_path=str(model_path))
            llm = llama_cpp.Llama(**kwargs)
            extra = _load_grammar(grammar_path, json_schema_path)
            if "grammar" in extra and hasattr(llama_cpp, "LlamaGrammar"):
                try:
                    grammar = llama_cpp.LlamaGrammar.from_string(extra["grammar"])
                    extra["grammar"] = grammar
                except Exception:
                    return _structured_failure(status="structured_output_unavailable", error="grammar_load_failed", warnings=["grammar_load_failed"], model_path=str(model_path), **extra)
            start = time.perf_counter()
            completion_kwargs = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "seed": seed,
            }
            if top_k is not None:
                completion_kwargs["top_k"] = top_k
            if min_p is not None:
                completion_kwargs["min_p"] = min_p
            if repeat_penalty is not None:
                completion_kwargs["repeat_penalty"] = repeat_penalty
            if stop:
                completion_kwargs["stop"] = stop
            if "grammar" in extra:
                completion_kwargs["grammar"] = extra["grammar"]
            if structured_json and "json_schema" in extra and hasattr(llm, "create_chat_completion"):
                completion_kwargs["response_format"] = {"type": "json_object"}
            output = llm.create_completion(**completion_kwargs)
            duration = time.perf_counter() - start
            text = ""
            if isinstance(output, dict):
                choices = output.get("choices") or []
                if choices:
                    text = str(choices[0].get("text") or "")
            elif hasattr(output, "choices"):
                choices = getattr(output, "choices") or []
                if choices:
                    text = str(choices[0].get("text") if isinstance(choices[0], dict) else getattr(choices[0], "text", ""))
            return {
                "status": "generated" if text.strip() else "failed",
                "backend": "llama-cpp",
                "model_path": str(model_path),
                "model_filename": model_path.name,
                "preset": preset,
                "n_batch": n_batch,
                "output": text.strip(),
                "duration_seconds": round(duration, 3),
                "warnings": [],
                "error": None if text.strip() else "empty_output",
                "n_ctx": n_ctx,
                "n_gpu_layers": n_gpu_layers,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "min_p": min_p,
                "repeat_penalty": repeat_penalty,
                "seed": seed,
                "stop": stop or [],
                "structured_json_enabled": bool(structured_json or json_schema_path or grammar_path),
                "grammar_path": str(grammar_path) if grammar_path else None,
                "json_schema_path": str(json_schema_path) if json_schema_path else None,
                "constrained_decoding_status": "enabled" if grammar_path or json_schema_path else "disabled",
            }
        except Exception as exc:
            return _structured_failure(status="failed", error=str(exc), warnings=[f"llama_cpp_error:{exc}"], model_path=str(model_path))
    return _structured_failure(status="tool_missing", error="llama_cpp_unavailable", warnings=["llama_cpp_unavailable"], model_path=str(model_path))
