from __future__ import annotations

import json
from pathlib import Path
from dataclasses import asdict
from rig_tools.loop_engine import LoopEngine

def register(subparsers, helpers):
    """Registers the 'loop' command group."""
    parser = subparsers.add_parser("loop", help="Rig OS supervisor loop commands")
    sub = parser.add_subparsers(dest="loop_command")
    
    # Policy Show
    policy_parser = sub.add_parser("policy", help="Show loop policies")
    policy_sub = policy_parser.add_subparsers(dest="policy_command")
    policy_show = policy_sub.add_parser("show", help="Show current loop policy")
    policy_show.add_argument("--task", help="Task ID to show policy for")
    policy_show.set_defaults(handler=lambda args: run_policy_show(helpers, task=args.task))
    
    # Loop Run
    run_parser = sub.add_parser("run", help="Run the supervisor loop")
    run_parser.add_argument("--task", required=True, help="Task ID to supervise")
    run_parser.add_argument("--mode", default="read_only", choices=["read_only", "bounded", "review"], help="Execution mode")
    run_parser.add_argument("--max-steps", type=int, default=3, help="Maximum steps to run")
    run_parser.add_argument("--dry-run", action="store_true", help="Do not execute subprocesses")
    run_parser.set_defaults(handler=lambda args: run_loop(helpers, task=args.task, mode=args.mode, max_steps=args.max_steps, dry_run=args.dry_run))
    
    # Loop Status
    status_parser = sub.add_parser("status", help="Show loop status")
    status_parser.set_defaults(handler=lambda args: run_status(helpers))
    
    # Loop Latest
    latest_parser = sub.add_parser("latest", help="Show latest loop run")
    latest_parser.set_defaults(handler=lambda args: run_latest(helpers))

def run_policy_show(helpers, task: str | None = None):
    engine = LoopEngine(helpers.repo_root)
    policy = engine.create_policy(task=task or "default")
    print(json.dumps(asdict(policy), indent=2))
    return 0

def run_loop(helpers, task: str, mode: str, max_steps: int, dry_run: bool):
    engine = LoopEngine(helpers.repo_root)
    policy = engine.create_policy(task=task, mode=mode, max_steps=max_steps)
    
    if helpers.output_mode == "human":
        print(f"Starting loop for task: {task} (mode: {mode}, max_steps: {max_steps})")
        if dry_run:
            print("DRY RUN ENABLED")
            
    run = engine.run(policy, dry_run=dry_run)
    
    if helpers.output_mode == "human":
        print(f"\nLoop Finished: {run.status.upper()}")
        print(f"Run ID: {run.run_id}")
        print(f"Stop Reason: {run.stop_reason}")
    else:
        print(json.dumps(asdict(run), indent=2))
        
    return 0 if run.status in ("passed", "stopped") else 1

def run_status(helpers):
    engine = LoopEngine(helpers.repo_root)
    latest_json = engine.loops_dir / "latest.json"
    if not latest_json.exists():
        print("No loop runs found.")
        return 0
        
    data = json.loads(latest_json.read_text())
    print(f"Latest Loop Run: {data['run_id']}")
    print(f"Status: {data['status'].upper()}")
    print(f"Task: {data['task']}")
    return 0

def run_latest(helpers):
    engine = LoopEngine(helpers.repo_root)
    latest_json = engine.loops_dir / "latest.json"
    if not latest_json.exists():
        print("No loop runs found.")
        return 1
    print(latest_json.read_text())
    return 0
