from rig_tools.productization_check import ProductizationChecker
import json

def register(subparsers, helpers):
    parser = subparsers.add_parser("product", help="Productization checks")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    
    check = sub.add_parser("check", help="Run productization checks")
    check.add_argument("--format", choices=["json", "text"], default="text")
    check.set_defaults(handler=lambda args: run_check(helpers, args.format))

def run_check(helpers, fmt):
    checker = ProductizationChecker(helpers.repo_root)
    report = checker.check()
    if fmt == "json":
        print(json.dumps(report, indent=2))
    else:
        print(f"Productization status: {report['status']}")
    return 0
