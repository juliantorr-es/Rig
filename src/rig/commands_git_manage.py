from __future__ import annotations

import json
import sys
from pathlib import Path

from rig_tools import git_manage


def register(subparsers, helpers):
    parser = subparsers.add_parser("git", help="Git hygiene operations", description="Read-only git hygiene plus deterministic commit planning and task-scoped staging.")
    git_sub = parser.add_subparsers(dest="git_cmd", required=True)

    plan = git_sub.add_parser("plan-commit", help="Plan a task-scoped commit")
    plan.add_argument("--task", required=True)
    plan.add_argument("--allowed-path", action="append", default=[])
    plan.set_defaults(handler=lambda args: _plan_commit(helpers, args))

    msg = git_sub.add_parser("commit-message", help="Suggest commit message")
    msg.add_argument("--task", required=True)
    msg.set_defaults(handler=lambda args: _commit_message(helpers, args))

    stage = git_sub.add_parser("stage", help="Stage files from a commit plan")
    stage.add_argument("--task", required=True)
    stage.add_argument("--from-plan", required=True)
    stage.add_argument("--confirm", action="store_true")
    stage.set_defaults(handler=lambda args: _stage(helpers, args))

    commit = git_sub.add_parser("commit", help="Commit files from a plan")
    commit.add_argument("--task", required=True)
    commit.add_argument("--from-plan", required=True)
    commit.add_argument("--confirm", action="store_true")
    commit.add_argument("--dry-run", action="store_true")
    commit.add_argument("--allow-head-change", action="store_true")
    commit.set_defaults(handler=lambda args: _commit(helpers, args))

    task_status = git_sub.add_parser("task-status", help="Task-scoped git status")
    task_status.add_argument("--task", required=True)
    task_status.set_defaults(handler=lambda args: _task_status(helpers, args))


def _plan_commit(helpers, args) -> int:
    plan = git_manage.plan_commit(helpers.repo_root, args.task, args.allowed_path)
    json_path, md_path = git_manage.write_plan(helpers.repo_root, plan)
    output = {
        **plan,
        "plan_path": str(json_path.relative_to(helpers.repo_root)),
        "plan_md_path": str(md_path.relative_to(helpers.repo_root)),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if plan["status"] != "blocked" else 1


def _commit_message(helpers, args) -> int:
    plan_path = helpers.repo_root / ".build" / "rig" / "git" / f"commit-plan-{args.task}.json"
    if plan_path.exists():
        plan = git_manage.load_plan(plan_path)
        msg = plan.get("commit_message") or git_manage.generate_commit_message(args.task, plan.get("included_files", []), plan.get("proof_artifact"), plan.get("latest_registry_gate"), plan.get("latest_rig_result"), plan.get("latest_schema_validation"))
    else:
        status = git_manage.collect_status(helpers.repo_root)
        msg = git_manage.generate_commit_message(args.task, status.get("changed_files", []), git_manage.latest_proof(helpers.repo_root), git_manage.latest_registry_gate(helpers.repo_root), git_manage.latest_result(helpers.repo_root), git_manage.latest_schema_validation(helpers.repo_root))
    print(msg.rstrip())
    return 0


def _stage(helpers, args) -> int:
    plan = git_manage.load_plan(Path(args.from_plan))
    res = git_manage.stage_from_plan(helpers.repo_root, plan, args.confirm)
    if res.stdout:
        print(res.stdout, end="")
    if res.stderr:
        print(res.stderr, end="", file=sys.stderr)
    return res.returncode


def _commit(helpers, args) -> int:
    if args.dry_run:
        plan = git_manage.load_plan(Path(args.from_plan))
        print(json.dumps({"dry_run": True, "plan": plan}, indent=2, sort_keys=True))
        return 0
    plan = git_manage.load_plan(Path(args.from_plan))
    res = git_manage.commit_from_plan(helpers.repo_root, plan, args.confirm, allow_head_change=args.allow_head_change)
    if res.stdout:
        print(res.stdout, end="")
    if res.stderr:
        print(res.stderr, end="", file=sys.stderr)
    return res.returncode


def _task_status(helpers, args) -> int:
    status = git_manage.collect_status(helpers.repo_root)
    plan_path = helpers.repo_root / ".build" / "rig" / "git" / f"commit-plan-{args.task}.json"
    plan = git_manage.load_plan(plan_path) if plan_path.exists() else None
    payload = {
        "task": args.task,
        "git_status": status,
        "commit_plan_path": str(plan_path.relative_to(helpers.repo_root)) if plan_path.exists() else None,
        "plan_status": plan.get("status") if plan else None,
        "registry_gate_status": plan.get("registry_gate_status") if plan else None,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
