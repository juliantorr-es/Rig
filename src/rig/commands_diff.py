from rig_tools.diff_review import DiffReviewManager

def register(subparsers, helpers):
    parser = subparsers.add_parser("diff", help="Diff review commands")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    
    sub.add_parser("status", help="Diff status").set_defaults(handler=lambda args: status(helpers))
    
    summary = sub.add_parser("summary", help="Show summary")
    summary.set_defaults(handler=lambda args: show_summary(helpers))
    
    review = sub.add_parser("review", help="Generate review")
    review.add_argument("--dry-run", action="store_true")
    review.set_defaults(handler=lambda args: generate_review(helpers, args.dry_run))

def status(helpers):
    print("Diff review subsystem operational.")
    return 0

def show_summary(helpers):
    mgr = DiffReviewManager(helpers.repo_root)
    print(mgr.summary())
    return 0

def generate_review(helpers, dry_run):
    mgr = DiffReviewManager(helpers.repo_root)
    review = mgr.generate_review("default", dry_run=dry_run)
    print(f"Generated review: {review['diff_review_id']}")
    return 0
