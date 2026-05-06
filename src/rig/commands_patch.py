from __future__ import annotations

import json
from pathlib import Path

from rig_tools import local_patch


def register(subparsers, helpers):
    parser = subparsers.add_parser("patch", help="Local patch proposal lane", description="Propose, validate, and sandbox-apply advisory local patches.")
    sub = parser.add_subparsers(dest="patch_cmd", required=True)

    status = sub.add_parser("status", help="Show patch lane status")
    status.set_defaults(handler=lambda args: _emit(local_patch.status(helpers.repo_root)))

    propose = sub.add_parser("propose", help="Propose a patch with the local model")
    propose.add_argument("--task", required=True)
    propose.add_argument("--backend", default="mlx")
    propose.add_argument("--model")
    propose.add_argument("--allowed-path", action="append", default=[])
    propose.add_argument("--dry-run", action="store_true")
    propose.add_argument("--max-repair-attempts", type=int, default=3)
    propose.add_argument("--repair-timeout-seconds", type=int, default=120)
    propose.add_argument("--no-repair", action="store_true")
    propose.add_argument("--keep-failed-attempts", action="store_true", default=True)
    propose.set_defaults(handler=lambda args: _emit(local_patch.propose_patch(helpers.repo_root, task=args.task, backend=args.backend, model=args.model, allowed_paths=args.allowed_path, dry_run=args.dry_run, max_repair_attempts=args.max_repair_attempts, repair_timeout_seconds=args.repair_timeout_seconds, no_repair=args.no_repair, keep_failed_attempts=args.keep_failed_attempts)))

    check = sub.add_parser("check", help="Check patch applicability")
    check.add_argument("--patch", required=True)
    check.set_defaults(handler=lambda args: _emit(local_patch.check_patch(helpers.repo_root, Path(args.patch))))

    apply_sandbox = sub.add_parser("apply-sandbox", help="Apply a patch in a sandbox only")
    apply_sandbox.add_argument("--patch", required=True)
    apply_sandbox.set_defaults(handler=lambda args: _emit(local_patch.apply_sandbox(helpers.repo_root, Path(args.patch))))

    validate = sub.add_parser("validate", help="Validate patch structure and sandbox application")
    validate.add_argument("--patch", required=True)
    validate.set_defaults(handler=lambda args: _emit(local_patch.validate_patch(helpers.repo_root, Path(args.patch))))

    list_ = sub.add_parser("list", help="List patches")
    list_.set_defaults(handler=lambda args: _emit({"patches": local_patch.list_patches(helpers.repo_root)}))

    show = sub.add_parser("show", help="Show a patch")
    show.add_argument("--patch-id", required=True)
    show.set_defaults(handler=lambda args: _emit(local_patch.show_patch(helpers.repo_root, args.patch_id)))


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    if isinstance(payload, dict) and payload.get("status") in {"failed", "invalid", "rejected"}:
        return 1
    return 0
