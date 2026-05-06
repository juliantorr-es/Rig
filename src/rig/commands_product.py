from __future__ import annotations

import json
from pathlib import Path

def register(subparsers, helpers):
    parser = subparsers.add_parser("product", help="Productization and flow checks", description="Verify Rig project flow, onboarding, and safety readiness.")
    prod = parser.add_subparsers(dest="product_cmd", required=True)

    # 1. Check
    check = prod.add_parser("check", help="Run full productization check")
    check.set_defaults(handler=lambda args: _run_check(helpers, args))

def _run_check(helpers, args) -> int:
    from rig_tools.productization_check import ProductizationChecker
    pc = ProductizationChecker(helpers.repo_root)
    report = pc.run_check()
    
    if helpers.output_mode == "human":
        print(f"Rig Productization Check: {report['status'].upper()}")
        for c in report["checks"]:
            icon = "✅" if c["status"] == "pass" else "⚠️" if c["status"] == "warn" else "❌"
            print(f"- {icon} [{c['subsystem'].upper()}] {c['check_id']}: {c['detail']}")
            
        if report["recommendations"]:
            print("\nRecommendations:")
            for r in report["recommendations"]:
                print(f"- {r}")
    else:
        print(json.dumps(report, indent=2))
        
    return 0 if report["status"] != "fail" else 1
