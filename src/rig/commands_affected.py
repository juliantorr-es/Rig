from __future__ import annotations

import json
import sys
from pathlib import Path

from rig_tools.affected import compute, write_outputs


def register(subparsers, helpers):
    parser = subparsers.add_parser("affected", help="Affected analysis", description="Determine affected files, targets, risks, and profiles from git changes or stdin.")
    affected_sub = parser.add_subparsers(dest="affected_cmd", required=True)

    files = affected_sub.add_parser("files", help="Show affected files")
    files.add_argument("--base")
    files.add_argument("--head")
    files.add_argument("--stdin", action="store_true")
    files.set_defaults(handler=lambda args: _handle(helpers, args, "files"))

    targets = affected_sub.add_parser("targets", help="Show affected targets")
    targets.add_argument("--base")
    targets.add_argument("--head")
    targets.add_argument("--stdin", action="store_true")
    targets.set_defaults(handler=lambda args: _handle(helpers, args, "targets"))

    risks = affected_sub.add_parser("risks", help="Show affected risks")
    risks.add_argument("--base")
    risks.add_argument("--head")
    risks.add_argument("--stdin", action="store_true")
    risks.set_defaults(handler=lambda args: _handle(helpers, args, "risks"))

    profiles = affected_sub.add_parser("profiles", help="Recommend affected profiles")
    profiles.add_argument("--task", required=True)
    profiles.add_argument("--stdin", action="store_true")
    profiles.set_defaults(handler=lambda args: _handle(helpers, args, "profiles"))

    summary = affected_sub.add_parser("summary", help="Show affected summary")
    summary.add_argument("--task", required=True)
    summary.add_argument("--base")
    summary.add_argument("--head")
    summary.add_argument("--stdin", action="store_true")
    summary.set_defaults(handler=lambda args: _handle(helpers, args, "summary"))

    # Planning-only note for pipeline integration.
    affected_sub.add_parser("pipeline", help="Pipeline integration note", description="Planned: wire --affected into pipeline profiles. Not enabled yet.")


def _handle(helpers, args, selected: str) -> int:
    repo_root = helpers.repo_root
    stdin_files = None
    if getattr(args, "stdin", False):
        stdin_files = [line.rstrip("\n") for line in sys.stdin.readlines()]
    command = ["rig", "affected", selected]
    if getattr(args, "base", None):
        command += ["--base", getattr(args, "base")]
    if getattr(args, "head", None):
        command += ["--head", getattr(args, "head")]
    if getattr(args, "stdin", False):
        command += ["--stdin"]
    if getattr(args, "task", None):
        command += ["--task", getattr(args, "task")]
    run_id = __import__("uuid").uuid4().hex[:12]
    result = compute(
        repo_root,
        mode=selected,
        base=getattr(args, "base", None),
        head=getattr(args, "head", None),
        stdin_files=stdin_files,
        task=getattr(args, "task", None),
        command=command,
    )
    paths = write_outputs(repo_root, result, task=getattr(args, "task", None))

    if helpers.output_mode in {"json", "jsonl", "agent"}:
        payload = {
            "schema_version": "rig.result.v1",
            "run_id": run_id,
            "command_group": "affected",
            "command": "rig affected " + selected,
            "task": getattr(args, "task", None),
            "status": "passed",
            "exit_code": 0,
            "started_at": None,
            "finished_at": None,
            "duration_seconds": 0.0,
            "artifacts": [{"path": str(path.relative_to(repo_root)), "type": path.suffix.lstrip(".") or "artifact"} for path in paths.values()],
            "warnings": [],
            "errors": [],
            "summary": {
                "changed_file_count": len(result.changed_files),
                "affected_risk_count": len(result.affected_risks),
                "directly_affected_targets": result.directly_affected_targets,
                "recommended_profiles": result.recommended_profiles,
            },
            "next_actions": result.recommended_validation_commands,
            "stderr_tail": None,
        }
        latest = repo_root / ".build" / "rig" / "results" / "latest.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (repo_root / ".build" / "rig" / "results" / f"{run_id}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        events_dir = repo_root / ".build" / "rig" / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        if helpers.output_mode in {"jsonl", "agent"}:
            event_lines = [
                {"schema_version": "rig.event.v1", "event_type": "run_started", "timestamp_utc": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()), "run_id": run_id, "command_group": "affected", "command": "rig affected " + selected, "task": getattr(args, "task", None), "attributes": {}},
                {"schema_version": "rig.event.v1", "event_type": "artifact", "timestamp_utc": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()), "run_id": run_id, "command_group": "affected", "command": "rig affected " + selected, "task": getattr(args, "task", None), "attributes": {"path": str(paths["summary_md"].relative_to(repo_root)), "artifact_type": "md"}},
                {"schema_version": "rig.event.v1", "event_type": "run_finished", "timestamp_utc": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()), "run_id": run_id, "command_group": "affected", "command": "rig affected " + selected, "task": getattr(args, "task", None), "attributes": {"status": "passed", "exit_code": 0, "result_path": ".build/rig/results/latest.json"}},
            ]
            event_path = events_dir / f"{run_id}.jsonl"
            event_path.write_text("\n".join(json.dumps(line, sort_keys=True) for line in event_lines) + "\n", encoding="utf-8")
            (events_dir / "latest.jsonl").write_text(event_path.read_text(encoding="utf-8"), encoding="utf-8")
        if helpers.output_mode == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload, sort_keys=True))
        return 0

    if selected == "files":
        print(str(paths["files_json"].relative_to(repo_root)))
    elif selected == "targets":
        print(str(paths["targets_json"].relative_to(repo_root)))
    elif selected == "risks":
        print(str(paths["risks_json"].relative_to(repo_root)))
    elif selected == "profiles":
        print(str(paths["profiles_json"].relative_to(repo_root)))
    elif selected == "summary":
        print(str(paths["summary_md"].relative_to(repo_root)))
    else:
        print(str(paths["summary_md"].relative_to(repo_root)))
    return 0
