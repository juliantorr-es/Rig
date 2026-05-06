from __future__ import annotations

import json
from pathlib import Path

from rig_tools import action_manifest


def register(subparsers, helpers):
    parser = subparsers.add_parser("action", help="Rig action manifests", description="Inspect canonical Rig action manifests.")
    sub = parser.add_subparsers(dest="action_cmd", required=True)

    list_ = sub.add_parser("list", help="List action manifests")
    list_.set_defaults(handler=lambda args: _emit({"schema_version": action_manifest.SCHEMA_VERSION, "actions": action_manifest.list_actions(helpers.repo_root)}))

    latest = sub.add_parser("latest", help="Show the latest action manifest")
    latest.set_defaults(handler=lambda args: _emit(_load_latest(helpers.repo_root)))

    show = sub.add_parser("show", help="Show an action manifest")
    show.add_argument("--action-id", required=True)
    show.set_defaults(handler=lambda args: _emit(action_manifest.load_action(helpers.repo_root, args.action_id) or {"status": "missing"}))

    validate = sub.add_parser("validate", help="Validate an action manifest")
    validate.add_argument("--action-id", required=True)
    validate.set_defaults(handler=lambda args: _emit(_validate_action(helpers.repo_root, args.action_id)))


def _load_latest(repo_root: Path) -> dict:
    path = repo_root / ".build" / "rig" / "actions" / "latest.json"
    if not path.exists():
        return {"status": "missing"}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "invalid"}


def _validate_action(repo_root: Path, action_id: str) -> dict:
    action = action_manifest.load_action(repo_root, action_id)
    if not action:
        return {"status": "missing"}
    errors = []
    if action.get("schema_version") != action_manifest.SCHEMA_VERSION:
        errors.append("bad_schema_version")
    if action.get("authoritative") is not False:
        errors.append("must_be_non_authoritative")
    status = "passed" if not errors else "failed"
    return {"status": status, "errors": errors, "action_id": action_id, "artifact": f".build/rig/actions/{action_id}.json"}


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") not in {"failed", "invalid"} else 1

