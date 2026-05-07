from __future__ import annotations

import json

from rig_tools import orchestration


def register(subparsers, helpers):
    parser = subparsers.add_parser("run", help="Product orchestration runner")
    parser.add_argument("--task", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--workspace")
    parser.add_argument("--until")
    parser.add_argument("--dry-run", action="store_true")
    parser.set_defaults(handler=lambda args: _run(helpers, args))


def _run(helpers, args):
    if args.dry_run:
        payload = {
            "status": "dry_run",
            "would_create_job": True,
            "task": args.task,
            "provider_id": args.provider,
            "workspace_id": args.workspace,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    job = orchestration.create_job(helpers.repo_root, task=args.task, provider_id=args.provider, workspace_id=args.workspace)
    result = orchestration.run_job(helpers.repo_root, job["job_id"], until=args.until, dry_run=False)
    payload = {
        "job_id": job["job_id"],
        "workspace_id": result.get("job", {}).get("workspace_id") or job.get("workspace_id"),
        "status": result.get("status"),
        "blocked_reason": result.get("job", {}).get("blocked_reason") or result.get("blocked_reason"),
        "next": result.get("next"),
        "job_path": f".build/rig/jobs/{job['job_id']}.json",
        "receipt_path": f".build/rig/receipts/{job['job_id']}_orchestration.json",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
