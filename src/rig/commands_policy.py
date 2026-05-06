from __future__ import annotations

import json

from rig_tools import policy


def register(subparsers, helpers):
    parser = subparsers.add_parser("policy", help="Rig policy decisions", description="Check explicit human-gate policy decisions.")
    sub = parser.add_subparsers(dest="policy_cmd", required=True)

    check = sub.add_parser("check", help="Check a policy decision")
    check.add_argument("--action", required=True)
    check.add_argument("--mode", required=True)
    check.add_argument("--allow-local-patches", action="store_true")
    check.set_defaults(handler=lambda args: _emit(policy.check(helpers.repo_root, action=args.action, mode=args.mode, allow_local_patches=args.allow_local_patches)))

    list_ = sub.add_parser("list", help="List policy tiers")
    list_.set_defaults(handler=lambda args: _emit({"schema_version": policy.SCHEMA_VERSION, "policies": policy.list_policies(helpers.repo_root)}))


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") not in {"failed", "invalid", "deny"} else 1

