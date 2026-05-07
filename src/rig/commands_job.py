from __future__ import annotations

import json

from rig_tools import orchestration


def register(subparsers, helpers):
    parser = subparsers.add_parser("job", help="Governed orchestration jobs")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    create = sub.add_parser("create", help="Create job")
    create.add_argument("--task", required=True)
    create.add_argument("--provider", required=True)
    create.add_argument("--model")
    create.set_defaults(handler=lambda args: _emit(orchestration.create_job(helpers.repo_root, task=args.task, provider_id=args.provider, model_id=args.model)))
    sub.add_parser("list", help="List jobs").set_defaults(handler=lambda args: _emit({"jobs": orchestration.list_jobs_summary(helpers.repo_root)}))
    inspect = sub.add_parser("inspect", help="Inspect job")
    inspect.add_argument("job_id")
    inspect.set_defaults(handler=lambda args: _emit(orchestration.inspect_job(helpers.repo_root, args.job_id)))
    run = sub.add_parser("run", help="Run job")
    run.add_argument("job_id")
    run.add_argument("--until")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(handler=lambda args: _emit(orchestration.run_job(helpers.repo_root, args.job_id, until=args.until, dry_run=args.dry_run)))
    cancel = sub.add_parser("cancel", help="Cancel job")
    cancel.add_argument("job_id")
    cancel.set_defaults(handler=lambda args: _emit(orchestration.cancel_job(helpers.repo_root, args.job_id)))
    retry = sub.add_parser("retry", help="Retry job")
    retry.add_argument("job_id")
    retry.set_defaults(handler=lambda args: _emit(orchestration.retry_job(helpers.repo_root, args.job_id)))


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0

