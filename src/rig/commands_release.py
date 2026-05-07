from __future__ import annotations

import json


def register(subparsers, helpers):
    parser = subparsers.add_parser("release", help="Release candidate gates")
    release_sub = parser.add_subparsers(dest="release_cmd", required=True)
    check = release_sub.add_parser("check", help="Run the public release gate")
    check.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    check.set_defaults(handler=lambda args: _check(helpers, args))


def _check(helpers, args) -> int:
    from rig_tools.release_readiness import run_release_readiness_command, run_release_readiness

    report = run_release_readiness(helpers.repo_root, format_type="json" if args.json else "text", dry_run_build=True)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Rig release check: {report.status.upper()}")
        for check in report.checks:
            print(f"- [{check.status.upper()}] {check.check_id}")
        if report.warnings:
            print("Warnings:")
            for warning in report.warnings:
                print(f"- {warning}")
    return 0 if report.status != "fail" else 1
