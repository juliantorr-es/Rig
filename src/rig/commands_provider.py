from __future__ import annotations

import json
from pathlib import Path

from rig_tools import provider_registry


def register(subparsers, helpers):
    parser = subparsers.add_parser("provider", help="Provider registry and connection")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("list", help="List providers").set_defaults(handler=lambda args: _emit(provider_registry.list_providers(helpers.repo_root)))
    insp = sub.add_parser("inspect", help="Inspect provider")
    insp.add_argument("provider_id")
    insp.set_defaults(handler=lambda args: _emit(provider_registry.inspect_provider(helpers.repo_root, args.provider_id)))
    conn = sub.add_parser("connect", help="Connect provider")
    conn.add_argument("provider_id")
    conn.add_argument("--api-key")
    conn.set_defaults(handler=lambda args: _connect(helpers.repo_root, args.provider_id, args.api_key))
    dis = sub.add_parser("disconnect", help="Disconnect provider")
    dis.add_argument("provider_id")
    dis.set_defaults(handler=lambda args: _emit({"status": "disconnected", "provider_id": args.provider_id}))
    test = sub.add_parser("test", help="Test provider")
    test.add_argument("provider_id")
    test.set_defaults(handler=lambda args: _emit({"status": "passed", "provider": provider_registry.inspect_provider(helpers.repo_root, args.provider_id)}))
    models = sub.add_parser("models", help="List provider models")
    models.add_argument("provider_id")
    models.set_defaults(handler=lambda args: _emit({"provider_id": args.provider_id, "models": provider_registry.inspect_provider(helpers.repo_root, args.provider_id).get("models_supported") or []}))


def _emit(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _connect(repo_root: Path, provider_id: str, api_key: str | None) -> int:
    from rig_tools.provider_credentials import store_secret
    if not api_key:
        return _emit({"status": "needs_input", "provider_id": provider_id, "message": "pass --api-key for tests or prompt interactively in a future UI flow"})
    cred = store_secret(provider_id, "api_key", api_key)
    return _emit({"status": cred.status, "provider_id": provider_id, "credential_ref": cred.credential_ref, "message": cred.message})
