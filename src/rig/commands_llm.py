from __future__ import annotations

import json
from pathlib import Path

from rig_tools import mlx_local, prompt_telemetry


def register(subparsers, helpers):
    parser = subparsers.add_parser("llm", help="Optional MLX local advisory summaries", description="Generate advisory-only summaries using local MLX models.")
    llm = parser.add_subparsers(dest="llm_cmd", required=True)

    status = llm.add_parser("status", help="Show MLX backend status")
    status.add_argument("--backend", default="mlx")
    status.set_defaults(handler=lambda args: _emit(mlx_local.status(args.backend)))

    smoke = llm.add_parser("smoke", help="Smoke-test MLX summary generation")
    smoke.add_argument("--backend", default="mlx")
    smoke.add_argument("--preset")
    smoke.add_argument("--model")
    smoke.add_argument("--model-path")
    smoke.add_argument("--max-tokens", type=int, default=80, dest="max_tokens")
    smoke.add_argument("--n-ctx", type=int, default=8192)
    smoke.add_argument("--n-gpu-layers", type=int, default=-1)
    smoke.add_argument("--n-batch", type=int)
    smoke.add_argument("--temperature", type=float, default=0.0)
    smoke.add_argument("--top-p", type=float, default=1.0)
    smoke.add_argument("--top-k", type=int)
    smoke.add_argument("--min-p", type=float)
    smoke.add_argument("--repeat-penalty", type=float)
    smoke.add_argument("--seed", type=int, default=0)
    smoke.add_argument("--stop", action="append")
    smoke.add_argument("--structured-json", action="store_true")
    smoke.add_argument("--grammar-path")
    smoke.add_argument("--json-schema")
    smoke.add_argument("--schema-family")
    smoke.add_argument("--force-large-context", action="store_true")
    smoke.set_defaults(handler=lambda args: _emit(_smoke(helpers.repo_root, args)))

    summarize = llm.add_parser("summarize", help="Summarize a Rig artifact")
    summarize.add_argument("--backend", default="mlx")
    summarize.add_argument("--preset")
    summarize.add_argument("--artifact", required=True)
    summarize.add_argument("--model")
    summarize.add_argument("--model-path")
    summarize.set_defaults(handler=lambda args: _emit(mlx_local.summarize_artifact(helpers.repo_root, artifact=Path(args.artifact), model=args.model, backend=args.backend, model_path=args.model_path)))

    summarize_session = llm.add_parser("summarize-session", help="Summarize a Rig session")
    summarize_session.add_argument("--backend", default="mlx")
    summarize_session.add_argument("--preset")
    summarize_session.add_argument("--task", required=True)
    summarize_session.add_argument("--model")
    summarize_session.add_argument("--model-path")
    summarize_session.set_defaults(handler=lambda args: _emit(mlx_local.summarize_session(helpers.repo_root, task=args.task, model=args.model, backend=args.backend, model_path=args.model_path)))

    proof = llm.add_parser("compress-proof", help="Compress a proof into an advisory summary")
    proof.add_argument("--backend", default="mlx")
    proof.add_argument("--preset")
    proof.add_argument("--proof", required=True)
    proof.add_argument("--model")
    proof.add_argument("--model-path")
    proof.set_defaults(handler=lambda args: _emit(mlx_local.compress_proof(helpers.repo_root, proof=Path(args.proof), model=args.model, backend=args.backend, model_path=args.model_path)))

    commit = llm.add_parser("draft-commit-summary", help="Draft an advisory commit summary")
    commit.add_argument("--backend", default="mlx")
    commit.add_argument("--preset")
    commit.add_argument("--task", required=True)
    commit.add_argument("--model")
    commit.add_argument("--model-path")
    commit.set_defaults(handler=lambda args: _emit(mlx_local.draft_commit_summary(helpers.repo_root, task=args.task, model=args.model, backend=args.backend, model_path=args.model_path)))


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _smoke(repo_root: Path, args):
    if args.backend == "llama-cpp":
        from rig_tools import llama_cpp_local
        schema_path = None
        if args.schema_family:
            schema_path = repo_root / "Docs" / "schemas" / f"{args.schema_family}.schema.json"

        prompt = mlx_local.build_prompt(task=None, kind="smoke", source_artifacts=[], context="Say hello in one short sentence.")
        params = llama_cpp_local.resolve_params(
            preset=args.preset,
            overrides={
                "n_ctx": args.n_ctx,
                "n_gpu_layers": args.n_gpu_layers,
                "n_batch": args.n_batch,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "top_k": args.top_k,
                "min_p": args.min_p,
                "repeat_penalty": args.repeat_penalty,
                "seed": args.seed,
                "max_tokens": args.max_tokens,
                "stop": args.stop or [],
                "structured_json": args.structured_json,
                "grammar_path": args.grammar_path,
                "json_schema": str(schema_path) if schema_path else args.json_schema,
            },
            force_large_context=args.force_large_context,
        )
        result = llama_cpp_local.generate_llama_cpp(
            prompt,
            preset=params.get("preset"),
            model_path=args.model_path,
            max_tokens=int(params.get("max_tokens", args.max_tokens)),
            temperature=float(params.get("temperature", args.temperature)),
            top_p=float(params.get("top_p", args.top_p)),
            top_k=params.get("top_k"),
            min_p=params.get("min_p"),
            repeat_penalty=params.get("repeat_penalty"),
            n_ctx=int(params.get("n_ctx", args.n_ctx)),
            n_gpu_layers=int(params.get("n_gpu_layers", args.n_gpu_layers)),
            seed=int(params.get("seed", args.seed)),
            n_batch=params.get("n_batch"),
            stop=list(params.get("stop") or []),
            grammar_path=Path(params["grammar_path"]) if params.get("grammar_path") else None,
            json_schema_path=Path(params["json_schema"]) if params.get("json_schema") else None,
            structured_json=bool(params.get("structured_json")),
            timeout_seconds=180,
        )
        if args.force_large_context:
            result["force_large_context"] = True
        prompt_telemetry.record_trace(
            repo_root,
            task=None,
            prompt_kind="smoke",
            prompt_template_id="rig.llama_cpp_smoke.v1",
            backend="llama-cpp",
            model=str(args.model_path or args.model or ""),
            runtime_settings={"preset": params.get("preset"), "max_tokens": params.get("max_tokens"), "temperature": params.get("temperature"), "top_p": params.get("top_p"), "top_k": params.get("top_k"), "min_p": params.get("min_p"), "repeat_penalty": params.get("repeat_penalty"), "n_ctx": params.get("n_ctx"), "n_gpu_layers": params.get("n_gpu_layers"), "n_batch": params.get("n_batch"), "seed": params.get("seed"), "stop": params.get("stop"), "structured_json": params.get("structured_json"), "schema_family": args.schema_family, "json_schema": params.get("json_schema"), "grammar_path": params.get("grammar_path")},
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
            model_path=str(result.get("model_path") or args.model_path) if (result.get("model_path") or args.model_path) else None,
            model_filename=str(Path(result.get("model_path") or args.model_path).name) if (result.get("model_path") or args.model_path) else None,
            n_ctx=result.get("n_ctx"),
            n_gpu_layers=result.get("n_gpu_layers"),
            temperature=result.get("temperature"),
            seed=result.get("seed"),
            structured_json_enabled=result.get("structured_json_enabled"),
            grammar_path=result.get("grammar_path"),
            json_schema_path=result.get("json_schema_path"),
            constrained_decoding_status=result.get("constrained_decoding_status"),
        )
        if args.schema_family:
            result["schema_family"] = args.schema_family
        return result
    if args.backend != "mlx":
        return {"status": "failed", "backend": args.backend, "error": "unsupported_backend", "warnings": []}
    prompt = mlx_local.build_prompt(task=None, kind="smoke", source_artifacts=[], context="Say hello in one short sentence.")
    return mlx_local.smoke_generate_mlx_lm(args.model or mlx_local.SUMMARY_MODEL, prompt, args.max_tokens, 180)
