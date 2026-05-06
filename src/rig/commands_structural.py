from __future__ import annotations

import json
from pathlib import Path

def register(subparsers, helpers):
    parser = subparsers.add_parser("structural", help="Structural validators", description="Run syntax-aware structural code scans.")
    struct = parser.add_subparsers(dest="struct_cmd", required=True)

    # 1. Status
    status = struct.add_parser("status", help="Show structural validator status")
    status.set_defaults(handler=lambda args: _run_status(helpers, args))

    # 2. Scan
    scan = struct.add_parser("scan", help="Run structural scan")
    scan.add_argument("--language", action="append")
    scan.add_argument("--dry-run", action="store_true")
    scan.set_defaults(handler=lambda args: _run_scan(helpers, args))

    # 3. Report
    report = struct.add_parser("report", help="Show latest structural report")
    report.add_argument("--format", choices=["json", "human"], default="json")
    report.set_defaults(handler=lambda args: _run_report(helpers, args))

def _run_status(helpers, helpers_args) -> int:
    status = {
        "engines": {
            "python_ast": "available (built-in)",
            "textual_import_scan": "available (built-in)",
            "textual_inventory_scan": "available (built-in)",
            "tree_sitter": "unavailable (optional extra)",
            "semgrep": "unavailable (optional extra)"
        },
        "latest_report": str((helpers.repo_root / ".build" / "rig" / "structural" / "latest.json").relative_to(helpers.repo_root)) if (helpers.repo_root / ".build" / "rig" / "structural" / "latest.json").exists() else None
    }
    print(json.dumps(status, indent=2))
    return 0

def _run_scan(helpers, args) -> int:
    from rig_tools import structural_validators
    report = structural_validators.run_scan(helpers.repo_root, languages=args.language)
    if not args.dry_run:
        path = structural_validators.write_report(helpers.repo_root, report)
        if helpers.output_mode == "human":
            print(f"Report written to {path}")
    print(json.dumps(report, indent=2))
    return 0

def _run_report(helpers, args) -> int:
    report_path = helpers.repo_root / ".build" / "rig" / "structural" / "latest.json"
    if not report_path.exists():
        print("No structural report found.")
        return 1
    print(report_path.read_text(encoding="utf-8"))
    return 0
