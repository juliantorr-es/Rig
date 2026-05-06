from __future__ import annotations

import json
from pathlib import Path

from rig_tools import session_bundle


def register(subparsers, helpers):
    parser = subparsers.add_parser("bundle", help="Session review bundles", description="Create deterministic session review bundles.")
    bundle_sub = parser.add_subparsers(dest="bundle_cmd", required=True)

    session = bundle_sub.add_parser("session", help="Create a session review zip")
    session.add_argument("--task", required=True)
    session.add_argument("--latest-run", action="store_true")
    session.add_argument("--run-id")
    session.add_argument("--out")
    session.add_argument("--dry-run", action="store_true")
    session.add_argument("--include-untracked", action="store_true")
    session.add_argument("--profile", default="forensic", choices=["forensic", "task-scoped", "rig-v1"])
    session.add_argument("--max-log-bytes", type=int, default=200000)
    session.add_argument("--max-file-bytes", type=int, default=1000000)
    session.set_defaults(handler=lambda args: _session(helpers, args))

    sessions = bundle_sub.add_parser("sessions", help="List session review bundles")
    sessions.set_defaults(handler=lambda args: _list_sessions(helpers, args))


def _session(helpers, args) -> int:
    out = Path(args.out) if args.out else None
    result = session_bundle.write_bundle(
        helpers.repo_root,
        task=args.task,
        run_id=args.run_id,
        latest_run=args.latest_run,
        out=out,
        dry_run=args.dry_run,
        include_untracked=args.include_untracked,
        profile=args.profile,
        max_log_bytes=args.max_log_bytes,
        max_file_bytes=args.max_file_bytes,
    )
    payload = {
        "bundle_path": str(result.bundle_path.relative_to(helpers.repo_root)) if result.bundle_path else None,
        "manifest_path": str(result.manifest_path.relative_to(helpers.repo_root)),
        "summary_path": str(result.summary_path.relative_to(helpers.repo_root)),
        "manifest": result.manifest,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _list_sessions(helpers, args) -> int:
    bundles = session_bundle._list_session_bundles(helpers.repo_root)
    payload = {
        "bundle_dir": str((helpers.repo_root / "Session-bundles").relative_to(helpers.repo_root)),
        "bundles": [str(path.relative_to(helpers.repo_root)) for path in bundles],
        "count": len(bundles),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
