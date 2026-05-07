from __future__ import annotations

import json
from pathlib import Path


def register(subparsers, helpers):
    parser = subparsers.add_parser("debug", help="Export debug bundles")
    debug_sub = parser.add_subparsers(dest="debug_cmd", required=True)
    bundle = debug_sub.add_parser("bundle", help="Create a redacted debug bundle")
    bundle.add_argument("--output", type=Path, default=None)
    bundle.add_argument("--include-logs", action="store_true")
    bundle.add_argument("--include-receipts", action="store_true")
    bundle.add_argument("--include-context", action="store_true")
    bundle.add_argument("--include-tui", action="store_true")
    bundle.add_argument("--redact", action="store_true", default=True)
    bundle.add_argument("--dry-run", action="store_true")
    bundle.set_defaults(handler=lambda args: _bundle(helpers, args))


def _bundle(helpers, args) -> int:
    from rig_tools.debug_bundle import build_bundle

    result = build_bundle(
        helpers.repo_root,
        output=args.output,
        include_logs=args.include_logs,
        include_receipts=args.include_receipts,
        include_context=args.include_context,
        include_tui=args.include_tui,
        redact=args.redact,
        dry_run=args.dry_run,
    )
    print(json.dumps({"bundle_path": str(result.bundle_path) if result.bundle_path else None, "manifest": result.manifest}, indent=2, sort_keys=True))
    return 0
