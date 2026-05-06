from __future__ import annotations

import json
from pathlib import Path

from rig_tools import agent_launcher, agent_plan


def register(subparsers, helpers):
    parser = subparsers.add_parser("agent", help="Non-interactive agent launcher", description="Create, validate, and launch allowlisted non-interactive external agents.")
    sub = parser.add_subparsers(dest="agent_cmd", required=True)

    status = sub.add_parser("status", help="Show agent registry status")
    status.add_argument("--probe", action="store_true")
    status.set_defaults(handler=lambda args: _emit(_status_payload(helpers, probe=args.probe)))

    plan = sub.add_parser("plan", help="Draft an advisory agent plan")
    plan.add_argument("--task", required=True)
    plan.add_argument("--backend", default="mlx")
    plan.add_argument("--model")
    plan.add_argument("--agent-id", default="codex")
    plan.add_argument("--mode", default="review", choices=["read_only", "review", "implementation", "validation"])
    plan.set_defaults(handler=lambda args: _handle_plan(helpers, args))

    validate = sub.add_parser("validate-plan", help="Validate an advisory agent plan")
    validate.add_argument("--plan", required=True)
    validate.add_argument("--allow-vibe", action="store_true")
    validate.set_defaults(handler=lambda args: _emit(agent_plan.validate_plan(helpers.repo_root, agent_plan.load_plan(Path(args.plan)), allow_vibe=args.allow_vibe)))

    launch = sub.add_parser("launch", help="Launch a known external agent")
    launch.add_argument("--from-plan", required=True)
    launch.add_argument("--dry-run", action="store_true")
    launch.add_argument("--confirm", action="store_true")
    launch.add_argument("--allow-vibe", action="store_true")
    launch.add_argument("--timeout-seconds", type=int)
    launch.set_defaults(handler=lambda args: _emit(agent_launcher.launch_from_plan(helpers.repo_root, Path(args.from_plan), dry_run=args.dry_run, confirm=args.confirm, allow_vibe=args.allow_vibe, timeout_seconds=args.timeout_seconds)))

    list_runs = sub.add_parser("list", help="List agent runs")
    list_runs.set_defaults(handler=lambda args: _emit({"runs": agent_launcher.list_runs(helpers.repo_root)}))

    tail = sub.add_parser("tail", help="Tail a run's events")
    tail.add_argument("--run-id", required=True)
    tail.set_defaults(handler=lambda args: _emit({"run_id": args.run_id, "events": agent_launcher.tail_run(helpers.repo_root, args.run_id)}))

    collect = sub.add_parser("collect", help="Collect an agent run bundle")
    collect.add_argument("--run-id", required=True)
    collect.set_defaults(handler=lambda args: _emit({"run_id": args.run_id, "run": _collect_run(helpers.repo_root, args.run_id)}))

    discover = sub.add_parser("discover", help="Discover local CLI agents")
    discover.set_defaults(handler=lambda args: _handle_discovery(helpers, args))


def _handle_discovery(helpers, args) -> int:
    from rig_tools import agent_discovery
    return _emit(agent_discovery.discover_agents(helpers.repo_root))


def _handle_plan(helpers, args) -> int:
    plan = agent_plan.draft_agent_plan(helpers.repo_root, task=args.task, model=args.model, agent_id=args.agent_id, mode=args.mode)
    json_path, md_path = agent_plan.write_plan_artifacts(helpers.repo_root, plan)
    plan["plan_path"] = str(json_path.relative_to(helpers.repo_root))
    plan["plan_md_path"] = str(md_path.relative_to(helpers.repo_root))
    return _emit(plan)


def _status_payload(helpers, probe: bool = False) -> dict:
    agents = agent_launcher.probe_agents(helpers.repo_root) if probe else agent_launcher.available_agents(helpers.repo_root)
    missing = [a.get("agent_id") for a in agents if not a.get("available")]
    disabled = [a.get("agent_id") for a in agents if not a.get("enabled")]
    return {
        "registry_path": "Docs/dev/rig/agent-registry.yaml",
        "agents": agents,
        "available_agents": [a for a in agents if a.get("available")],
        "missing_agents": missing,
        "disabled_agents": disabled,
        "supported_launch_modes": sorted({str(a.get("default_mode") or "review") for a in agents}),
        "warnings": sorted({*(missing or []), *(disabled or [])}),
    }


def _collect_run(repo_root: Path, run_id: str) -> dict:
    run_dir = repo_root / ".build" / "rig" / "agents" / "runs" / run_id
    manifest = run_dir / "agent-run.json"
    if not manifest.exists():
        return {"status": "missing"}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        "manifest": str(manifest.relative_to(repo_root)),
        "artifacts": data.get("artifacts", []),
        "prompt": str((run_dir / "prompt.md").relative_to(repo_root)) if (run_dir / "prompt.md").exists() else None,
        "stdout": str((run_dir / "stdout.log").relative_to(repo_root)) if (run_dir / "stdout.log").exists() else None,
        "stderr": str((run_dir / "stderr.log").relative_to(repo_root)) if (run_dir / "stderr.log").exists() else None,
        "events": str((run_dir / "events.jsonl").relative_to(repo_root)) if (run_dir / "events.jsonl").exists() else None,
        "run": data,
    }


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") not in {"failed", "invalid"} else 1
