from __future__ import annotations

import json


def register(subparsers, helpers):
    parser = subparsers.add_parser("release", help="Release candidate gates")
    release_sub = parser.add_subparsers(dest="release_cmd", required=True)
    check = release_sub.add_parser("check", help="Run the public release gate")
    check.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    check.set_defaults(handler=lambda args: _check(helpers, args))


def _check(helpers, args) -> int:
    from rig_tools.release_check import run_release_check, run_release_check_command

    if args.json:
        return run_release_check_command(helpers.repo_root, as_json=True)
    report = run_release_check(helpers.repo_root)
    print(f"Rig release check: {report.status.upper()}")
    for check in getattr(report, "checks", []):
        print(f"- [{check.status.upper()}] {check.category}:{check.id} :: {check.message}")
        if check.next_action:
            print(f"  next: {check.next_action}")
    return 0 if report.status != "fail" else 1
