from __future__ import annotations

import json
from pathlib import Path

from rig_tools import prompt_regression, prompt_telemetry


def register(subparsers, helpers):
    parser = subparsers.add_parser("prompt", help="Prompt telemetry and regression harness", description="Inspect, quarantine, replay, and compare local LLM prompt traces.")
    sub = parser.add_subparsers(dest="prompt_cmd", required=True)

    status = sub.add_parser("status", help="Show prompt telemetry status")
    status.set_defaults(handler=lambda args: _emit(_status(helpers.repo_root)))

    quarantine = sub.add_parser("quarantine", help="Quarantined prompt traces")
    quarantine_sub = quarantine.add_subparsers(dest="quarantine_cmd", required=True)
    quarantine_list = quarantine_sub.add_parser("list", help="List quarantined traces")
    quarantine_list.set_defaults(handler=lambda args: _emit({"schema_version": prompt_telemetry.SCHEMA_VERSION, "traces": prompt_regression.list_quarantine(helpers.repo_root)}))

    trace = sub.add_parser("trace", help="Prompt trace inspection")
    trace_sub = trace.add_subparsers(dest="trace_cmd", required=True)
    trace_show = trace_sub.add_parser("show", help="Show a trace")
    trace_show.add_argument("--trace-id", required=True)
    trace_show.set_defaults(handler=lambda args: _emit(prompt_telemetry.load_trace(helpers.repo_root, args.trace_id) or {"status": "missing"}))

    regression = sub.add_parser("regression", help="Prompt regression cases and replay")
    regression_sub = regression.add_subparsers(dest="regression_cmd", required=True)
    regression_add = regression_sub.add_parser("add", help="Add quarantined traces to regression cases")
    regression_add.add_argument("--from-quarantine", action="store_true")
    regression_add.add_argument("--prompt-kind", required=True)
    regression_add.add_argument("--allow-small-sample", action="store_true")
    regression_add.set_defaults(handler=lambda args: _emit(prompt_regression.add_from_quarantine(helpers.repo_root, prompt_kind=args.prompt_kind, allow_small_sample=args.allow_small_sample)))
    regression_run = regression_sub.add_parser("run", help="Run prompt regression")
    regression_run.add_argument("--prompt-kind", required=True)
    regression_run.add_argument("--backend", default="mlx")
    regression_run.add_argument("--preset")
    regression_run.add_argument("--model")
    regression_run.add_argument("--model-path")
    regression_run.add_argument("--allow-small-sample", action="store_true")
    regression_run.set_defaults(handler=lambda args: _emit(prompt_regression.run_regression(helpers.repo_root, prompt_kind=args.prompt_kind, allow_small_sample=args.allow_small_sample, backend=args.backend, preset=args.preset, model=args.model, model_path=args.model_path, prompt_knobs={"preset": args.preset} if args.preset else None)))

    experiment = sub.add_parser("experiment", help="Compare prompt templates")
    experiment_sub = experiment.add_subparsers(dest="experiment_cmd", required=True)
    experiment_run = experiment_sub.add_parser("run", help="Run prompt experiment")
    experiment_run.add_argument("--prompt-kind", required=True)
    experiment_run.add_argument("--baseline-template", default=str(helpers.repo_root / "Docs" / "dev" / "rig" / "prompts" / "loop_plan.v1.md"))
    experiment_run.add_argument("--candidate-template", required=True)
    experiment_run.add_argument("--allow-small-sample", action="store_true")
    experiment_run.set_defaults(handler=lambda args: _emit(_run_experiment(helpers.repo_root, args.prompt_kind, Path(args.baseline_template), Path(args.candidate_template), args.allow_small_sample)))
    compare = experiment_sub.add_parser("compare-backends", help="Compare prompt performance between backends")
    compare.add_argument("--prompt-kind", required=True)
    compare.add_argument("--baseline-backend", default="mlx")
    compare.add_argument("--baseline-preset")
    compare.add_argument("--baseline-model")
    compare.add_argument("--baseline-model-path")
    compare.add_argument("--candidate-backend", required=True)
    compare.add_argument("--candidate-preset")
    compare.add_argument("--candidate-model")
    compare.add_argument("--candidate-model-path")
    compare.add_argument("--allow-small-sample", action="store_true")
    compare.set_defaults(handler=lambda args: _emit(_compare_backends(helpers.repo_root, args.prompt_kind, args.baseline_backend, args.baseline_preset, args.baseline_model, args.baseline_model_path, args.candidate_backend, args.candidate_preset, args.candidate_model, args.candidate_model_path, args.allow_small_sample)))

    promote = sub.add_parser("promote", help="Promote a prompt template")
    promote.add_argument("--experiment-id", required=True)
    promote.add_argument("--dry-run", action="store_true", default=False)
    promote.add_argument("--apply", action="store_true")
    promote.set_defaults(handler=lambda args: _emit(_promote(helpers.repo_root, args.experiment_id, apply=args.apply, dry_run=(not args.apply) or args.dry_run)))


def _status(repo_root: Path) -> dict:
    traces = prompt_telemetry.list_traces(repo_root)
    quarantined = prompt_regression.list_quarantine(repo_root)
    return {
        "schema_version": prompt_telemetry.SCHEMA_VERSION,
        "status": "passed",
        "trace_count": len(traces),
        "quarantine_count": len(quarantined),
        "latest_trace": traces[-1] if traces else None,
        "latest_quarantine": quarantined[-1] if quarantined else None,
        "warnings": [],
        "authoritative": False,
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _run_experiment(repo_root: Path, prompt_kind: str, baseline_template: Path, candidate_template: Path, allow_small_sample: bool) -> dict:
    baseline_text = _read_text(baseline_template)
    candidate_text = _read_text(candidate_template)
    result = prompt_regression.run_regression(
        repo_root,
        prompt_kind=prompt_kind,
        baseline_template=baseline_text or None,
        candidate_template=candidate_text or None,
        allow_small_sample=allow_small_sample,
    )
    result["baseline_template_path"] = str(baseline_template)
    result["candidate_template_path"] = str(candidate_template)
    return result


def _compare_backends(repo_root: Path, prompt_kind: str, baseline_backend: str, baseline_preset: str | None, baseline_model: str | None, baseline_model_path: str | None, candidate_backend: str, candidate_preset: str | None, candidate_model: str | None, candidate_model_path: str | None, allow_small_sample: bool) -> dict:
    return prompt_regression.compare_backends(
        repo_root,
        prompt_kind=prompt_kind,
        baseline_backend=baseline_backend,
        baseline_preset=baseline_preset,
        baseline_model=baseline_model,
        baseline_model_path=baseline_model_path,
        candidate_backend=candidate_backend,
        candidate_preset=candidate_preset,
        candidate_model=candidate_model,
        candidate_model_path=candidate_model_path,
        allow_small_sample=allow_small_sample,
    )


def _promote(repo_root: Path, experiment_id: str, *, apply: bool, dry_run: bool) -> dict:
    exp_dir = prompt_telemetry.experiments_dir(repo_root, experiment_id)
    latest = exp_dir / "latest.json"
    if not latest.exists():
        return {"status": "missing", "experiment_id": experiment_id}
    data = json.loads(latest.read_text(encoding="utf-8"))
    recommended = data.get("promotion_recommendation")
    blockers = data.get("promotion_blockers") or []
    result = {"status": "dry_run" if dry_run or not apply else "passed", "experiment_id": experiment_id, "promotion_recommendation": recommended if not blockers else "hold", "promotion_blockers": blockers, "applied": False, "warnings": []}
    if blockers:
        result["status"] = "failed"
        result["warnings"].append("promotion_blocked")
        return result
    if apply and not dry_run:
        candidate = data.get("candidate_template_path")
        baseline = data.get("baseline_template_path")
        if candidate and baseline:
            candidate_path = Path(candidate)
            baseline_path = Path(baseline)
            if candidate_path.exists():
                baseline_path.write_text(candidate_path.read_text(encoding="utf-8"), encoding="utf-8")
                result["applied"] = True
    return result


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    if isinstance(payload, dict) and payload.get("status") in {"failed", "invalid", "rejected"}:
        return 1
    return 0
