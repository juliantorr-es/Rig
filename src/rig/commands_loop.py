from __future__ import annotations

import json
from pathlib import Path

from rig_tools import supervisor_loop


def register(subparsers, helpers):
    parser = subparsers.add_parser("loop", help="Supervisor loop MVP", description="Run a bounded background orchestration loop over allowed Rig actions.")
    sub = parser.add_subparsers(dest="loop_cmd", required=True)

    status = sub.add_parser("status", help="Show loop action status")
    status.add_argument("--allow-local-patches", action="store_true")
    status.set_defaults(handler=lambda args: _emit(supervisor_loop.status(helpers.repo_root, allow_local_patches=args.allow_local_patches)))

    plan = sub.add_parser("plan", help="Draft a loop plan")
    plan.add_argument("--task", required=True)
    plan.add_argument("--backend", default="mlx")
    plan.add_argument("--model", required=True)
    plan.add_argument("--mode", default="read-only", choices=["read-only", "review", "implementation"])
    plan.add_argument("--max-steps", type=int, default=5)
    plan.add_argument("--allow-local-patches", action="store_true")
    plan.set_defaults(handler=lambda args: _handle_plan(helpers, args))

    validate = sub.add_parser("validate-plan", help="Validate a loop plan")
    validate.add_argument("--plan", required=True)
    validate.add_argument("--experimental-implementation", action="store_true")
    validate.set_defaults(handler=lambda args: _emit(supervisor_loop.validate_plan(helpers.repo_root, json.loads(Path(args.plan).read_text(encoding="utf-8")), experimental_implementation=args.experimental_implementation)))

    run = sub.add_parser("run", help="Run the supervisor loop")
    run.add_argument("--task", required=True)
    run.add_argument("--mode", default="read-only", choices=["read-only", "review", "implementation"])
    run.add_argument("--max-steps", type=int, default=5)
    run.add_argument("--backend", default="mlx")
    run.add_argument("--model", required=True)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--experimental-implementation", action="store_true")
    run.add_argument("--allow-local-patches", action="store_true")
    run.set_defaults(handler=lambda args: _emit(supervisor_loop.run_loop(helpers.repo_root, task=args.task, mode=args.mode, backend=args.backend, model=args.model, max_steps=args.max_steps, dry_run=args.dry_run, experimental_implementation=args.experimental_implementation, allow_local_patches=args.allow_local_patches)))

    list_runs = sub.add_parser("list", help="List loop runs")
    list_runs.set_defaults(handler=lambda args: _emit({"runs": _list_runs(helpers.repo_root)}))

    tail = sub.add_parser("tail", help="Tail a loop run")
    tail.add_argument("--run-id", required=True)
    tail.set_defaults(handler=lambda args: _emit({"run_id": args.run_id, "events": _tail(helpers.repo_root, args.run_id)}))


def _handle_plan(helpers, args) -> int:
    plan, path = supervisor_loop.draft_plan(helpers.repo_root, task=args.task, mode=args.mode, backend=args.backend, model=args.model, max_steps=args.max_steps, allow_local_patches=getattr(args, "allow_local_patches", False))
    plan["plan_path"] = str(path.relative_to(helpers.repo_root))
    return _emit(plan)


def _list_runs(repo_root: Path) -> list[dict]:
    runs_dir = repo_root / ".build" / "rig" / "loop" / "runs"
    if not runs_dir.exists():
        return []
    rows = []
    for path in sorted(runs_dir.glob("*/loop-run.json"), key=lambda p: p.parent.name):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return rows


def _tail(repo_root: Path, run_id: str) -> list[dict]:
    path = repo_root / ".build" / "rig" / "loop" / "runs" / run_id / "events.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"schema_version": "rig.event.v1", "event_type": "parse_error", "raw": line})
    return out


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") not in {"failed", "invalid"} else 1
