from __future__ import annotations

import json
from pathlib import Path

def register(subparsers, helpers):
    parser = subparsers.add_parser("diff", help="Diff review and classification", description="Safe, read-only summary and risk classification of changes.")
    dif = parser.add_subparsers(dest="diff_cmd", required=True)

    # 1. Status
    status = dif.add_parser("status", help="Show diff status")
    status.set_defaults(handler=lambda args: _run_status(helpers, args))

    # 2. Summary
    summary = dif.add_parser("summary", help="Show summary of changes")
    summary.add_argument("--workspace", help="Associate with workspace")
    summary.set_defaults(handler=lambda args: _run_summary(helpers, args))

    # 3. Review
    review = dif.add_parser("review", help="Run full diff review and classification")
    review.add_argument("--workspace", help="Associate with workspace")
    review.add_argument("--dry-run", action="store_true")
    review.set_defaults(handler=lambda args: _run_review(helpers, args))

def _run_status(helpers, args) -> int:
    from rig_tools.diff_review import DiffReviewer
    dr = DiffReviewer(helpers.repo_root)
    # Check if git
    if not (helpers.repo_root / ".git").exists():
        print(json.dumps({"status": "not_a_git_repo"}, indent=2))
        return 0
        
    latest_path = helpers.repo_root / ".build" / "rig" / "diff" / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else None
    
    print(json.dumps({
        "status": "ready",
        "latest_review": latest["diff_review_id"] if latest else None,
        "created_at": latest["created_at"] if latest else None
    }, indent=2))
    return 0

def _run_summary(helpers, args) -> int:
    from rig_tools.diff_review import DiffReviewer
    dr = DiffReviewer(helpers.repo_root)
    # Run review in dry-run mode to get current summary without writing artifacts
    res = dr.run_review(workspace_id=args.workspace, dry_run=True)
    print(json.dumps(res, indent=2))
    return 0

def _run_review(helpers, args) -> int:
    from rig_tools.diff_review import DiffReviewer
    dr = DiffReviewer(helpers.repo_root)
    res = dr.run_review(workspace_id=args.workspace, dry_run=args.dry_run)
    
    if args.dry_run:
        print("Dry run: would classify current changes and write review receipt.")
    print(json.dumps(res, indent=2))
    return 0
