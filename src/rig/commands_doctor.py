from __future__ import annotations

import json
from pathlib import Path

from rig_tools.doctor import run_doctor
from rig_tools import orchestration


def _emit(payload):
    print(json.dumps(payload, indent=2, sort_keys=True))


def _queue(repo_root: Path) -> dict[str, object]:
    return orchestration.queue_health(repo_root)


def _repair_queue(repo_root: Path, *, migrate_legacy_queue: bool = False) -> dict[str, object]:
    result = orchestration.queue_health(repo_root, repair=True)
    repaired = dict(result)
    repaired["repair"] = {
        "quarantined": result.get("quarantined", []),
        "migrated": None,
    }
    if migrate_legacy_queue:
        repaired["repair"]["migrated"] = orchestration.migrate_legacy_queue(repo_root)
    return repaired


def register(subparsers, helpers):
    parser = subparsers.add_parser("doctor", help="Integrated Rig OS health checks", description="Integrated runtime and subsystem health checks.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    sub = parser.add_subparsers(dest="doctor_command")
    sub.add_parser("queue", help="Inspect queue health").set_defaults(handler=lambda args: _emit(_queue(helpers.repo_root)))
    repair = sub.add_parser("repair", help="Repair queue health")
    repair.add_argument("--queue", action="store_true")
    repair.add_argument("--migrate-legacy-queue", action="store_true")
    repair.set_defaults(handler=lambda args: _emit(_repair_queue(helpers.repo_root, migrate_legacy_queue=args.migrate_legacy_queue)) if args.queue or args.migrate_legacy_queue else _emit(_queue(helpers.repo_root)))
    parser.set_defaults(handler=lambda args: run_doctor(helpers.repo_root, format_type=args.format))
