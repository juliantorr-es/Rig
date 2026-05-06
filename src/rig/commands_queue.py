from __future__ import annotations

import json
from pathlib import Path

from rig_tools import work_queue


def register(subparsers, helpers):
    parser = subparsers.add_parser("queue", help="Durable supervisor-loop queue", description="Queue bounded read-only Rig jobs with checkpoints.")
    sub = parser.add_subparsers(dest="queue_cmd", required=True)

    add = sub.add_parser("add", help="Add a queued job")
    add.add_argument("--task", required=True)
    add.add_argument("--mode", default="read-only")
    add.add_argument("--max-steps", type=int, default=5)
    add.set_defaults(handler=lambda args: _emit(work_queue.add_job(helpers.repo_root, task=args.task, mode=args.mode, max_steps=args.max_steps)))

    list_ = sub.add_parser("list", help="List queue jobs")
    list_.set_defaults(handler=lambda args: _emit({"schema_version": work_queue.QUEUE_SCHEMA_VERSION, "jobs": work_queue.list_jobs(helpers.repo_root)}))

    status = sub.add_parser("status", help="Show queue status")
    status.set_defaults(handler=lambda args: _emit(work_queue.status(helpers.repo_root)))

    run = sub.add_parser("run", help="Run queued jobs")
    run.add_argument("--max-jobs", type=int, default=1)
    run.set_defaults(handler=lambda args: _emit(work_queue.run_jobs(helpers.repo_root, max_jobs=args.max_jobs)))

    pause = sub.add_parser("pause", help="Pause a job")
    pause.add_argument("--job-id", required=True)
    pause.set_defaults(handler=lambda args: _emit(work_queue.pause_job(helpers.repo_root, args.job_id)))

    resume = sub.add_parser("resume", help="Resume a job")
    resume.add_argument("--job-id", required=True)
    resume.set_defaults(handler=lambda args: _emit(work_queue.resume_job(helpers.repo_root, args.job_id)))

    cancel = sub.add_parser("cancel", help="Cancel a job")
    cancel.add_argument("--job-id", required=True)
    cancel.set_defaults(handler=lambda args: _emit(work_queue.cancel_job(helpers.repo_root, args.job_id)))

    show = sub.add_parser("show", help="Show a job and checkpoint")
    show.add_argument("--job-id", required=True)
    show.set_defaults(handler=lambda args: _emit(work_queue.show_job(helpers.repo_root, args.job_id)))


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    if isinstance(payload, dict) and payload.get("status") in {"failed", "invalid"}:
        return 1
    return 0
