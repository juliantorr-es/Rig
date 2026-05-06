from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from rig_tools import architecture_projector


def register(subparsers, helpers):
    parser = subparsers.add_parser("project", help="Project management and digest", description="Map languages, build systems, and recommended adapters.")
    proj = parser.add_subparsers(dest="project_cmd", required=True)

    # 1. Status
    status = proj.add_parser("status", help="Show project status")
    status.set_defaults(handler=lambda args: _run_status(helpers, args))

    # 2. Digest
    digest = proj.add_parser("digest", help="Digest the codebase")
    digest.add_argument("--dry-run", action="store_true")
    digest.set_defaults(handler=lambda args: _run_digest(helpers, args))

    # 3. Adapters
    adapters = proj.add_parser("adapters", help="List available project adapters")
    adapters.set_defaults(handler=lambda args: _run_adapters(helpers, args))

    # 4. Adapter Show
    adapter_show = proj.add_parser("adapter", help="Adapter operations")
    adapter_op = adapter_show.add_subparsers(dest="adapter_cmd", required=True)
    ashow = adapter_op.add_parser("show", help="Show adapter details")
    ashow.add_argument("adapter_id")
    ashow.set_defaults(handler=lambda args: _run_adapter_show(helpers, args))

    # 5. Profile
    profile = proj.add_parser("profile", help="Project profile operations")
    profile_op = profile.add_subparsers(dest="profile_cmd", required=True)
    pshow = profile_op.add_parser("show", help="Show active project profile")
    pshow.set_defaults(handler=lambda args: _run_profile_show(helpers, args))
    papply = profile_op.add_parser("apply", help="Apply project profile")
    papply.add_argument("--adapter", action="append", required=True)
    papply.add_argument("--dry-run", action="store_true")
    papply.set_defaults(handler=lambda args: _run_profile_apply(helpers, args))

    # Existing Architecture commands (migrated to sub-sub)
    arch_top = proj.add_parser("architecture", help="Architecture projections")
    arch_op = arch_top.add_subparsers(dest="arch_cmd", required=False)
    
    arch = arch_op.add_parser("generate", help="Generate architecture projections")
    arch.add_argument("--mode", default="advisory")
    arch.add_argument("--target")
    arch.add_argument("--risk")
    arch.set_defaults(handler=lambda args: _run_arch(helpers, args))

    desired = arch_op.add_parser("desired-state", help="Generate desired-state summary")
    desired.add_argument("--target", required=True)
    desired.set_defaults(handler=lambda args: _run_arch(helpers, args))

    coupling = arch_op.add_parser("coupling", help="Generate coupling summary")
    coupling.add_argument("--target", required=True)
    coupling.set_defaults(handler=lambda args: _run_arch(helpers, args))

    overlap = arch_op.add_parser("overlap", help="Generate overlap summary")
    overlap.add_argument("--target", required=True)
    overlap.set_defaults(handler=lambda args: _run_arch(helpers, args))

    show = arch_op.add_parser("show", help="Show a projection by id")
    show.add_argument("--projection-id", required=True)
    show.set_defaults(handler=lambda args: _run_arch(helpers, args))


def _run_status(helpers, args) -> int:
    from rig_tools import project_profile
    profile = project_profile.get_profile(helpers.repo_root)
    status = {
        "repo_root": str(helpers.repo_root),
        "rig_initialized": (helpers.repo_root / ".rig").is_dir(),
        "profile": profile,
        "digest_present": (helpers.repo_root / ".build" / "rig" / "project" / "latest-digest.json").exists()
    }
    print(json.dumps(status, indent=2))
    return 0

def _run_digest(helpers, args) -> int:
    from rig_tools import project_digest
    digest = project_digest.run_digest(helpers.repo_root)
    if not args.dry_run:
        path = project_digest.write_digest(helpers.repo_root, digest)
        if helpers.output_mode == "human":
            print(f"Digest written to {path}")
    print(json.dumps(digest, indent=2))
    return 0

def _run_adapters(helpers, args) -> int:
    from rig_tools import project_adapters
    adapters = project_adapters.list_adapters()
    summary = [{"id": a["adapter_id"], "name": a["display_name"], "description": a["description"]} for a in adapters]
    print(json.dumps(summary, indent=2))
    return 0

def _run_adapter_show(helpers, args) -> int:
    from rig_tools import project_adapters
    adapter = project_adapters.get_effective_adapter(args.adapter_id)
    if not adapter:
        print(f"Adapter not found: {args.adapter_id}")
        return 1
    print(json.dumps(adapter, indent=2))
    return 0

def _run_profile_show(helpers, args) -> int:
    from rig_tools import project_profile
    profile = project_profile.get_profile(helpers.repo_root)
    if not profile:
        print("No active project profile found.")
        return 1
    print(json.dumps(profile, indent=2))
    return 0

def _run_profile_apply(helpers, args) -> int:
    from rig_tools import project_profile
    plan = project_profile.create_profile_plan(helpers.repo_root, args.adapter)
    path = project_profile.apply_profile(helpers.repo_root, plan, dry_run=args.dry_run)
    if helpers.output_mode == "human":
        print(f"Profile applied to {path}")
    print(json.dumps(plan, indent=2))
    return 0

def _run_arch(helpers, args) -> int:
    # Original _run logic
    run_id = uuid.uuid4().hex[:12]
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    emit_events = helpers.output_mode in {"jsonl", "agent"}
    if emit_events:
        helpers._begin_stream(run_id)  # noqa: SLF001
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_started", "timestamp_utc": started_at, "run_id": run_id, "command_group": "project", "command": "rig project architecture", "task": getattr(args, "target", None), "attributes": {"milestone": "scan_started"}})
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "step_started", "timestamp_utc": started_at, "run_id": run_id, "command_group": "project", "command": "rig project architecture", "task": getattr(args, "target", None), "attributes": {"milestone": "records_loaded"}})
    bundle = architecture_projector.build_projection_bundle(
        helpers.repo_root,
        target=getattr(args, "target", None),
        mode=getattr(args, "mode", "advisory"),
        risk=getattr(args, "risk", None),
    )
    outputs = architecture_projector.write_projection_outputs(helpers.repo_root, bundle)
    if emit_events:
        artifact_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "artifact", "timestamp_utc": artifact_time, "run_id": run_id, "command_group": "project", "command": "rig project architecture", "task": getattr(args, "target", None), "attributes": {"milestone": "artifact_written", "path": ".build/rig/projections/latest.json", "artifact_type": "result"}})
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "step_finished", "timestamp_utc": artifact_time, "run_id": run_id, "command_group": "project", "command": "rig project architecture", "task": getattr(args, "target", None), "attributes": {"milestone": "projection_rules_applied", "status": bundle["latest"]["status"]}})
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_finished", "timestamp_utc": artifact_time, "run_id": run_id, "command_group": "project", "command": "rig project architecture", "task": getattr(args, "target", None), "attributes": {"status": bundle["latest"]["status"], "exit_code": 0, "result_path": ".build/rig/projections/latest.json"}})
        helpers._finish_stream(run_id)  # noqa: SLF001
    payload = {
        "bundle": bundle["latest"],
        "outputs": {key: str(path.relative_to(helpers.repo_root)) for key, path in outputs.items()},
    }
    if helpers.output_mode == "human":
        print(f"projection_count={bundle['latest']['projection_count']} target={getattr(args, 'target', None) or 'all'}")
    elif helpers.output_mode in {"jsonl", "agent"}:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0

