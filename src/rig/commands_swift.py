from __future__ import annotations

from pathlib import Path
import sys
import time
import uuid


def _swift_cmd(base: list[str], args: list[str]) -> list[str]:
    return [*base, *args]


def _run_and_report(helpers, command: list[str], *, quiet: bool, target: str | None = None, run_label: str, raw_input_path: Path | None = None, status: str | None = None, tool_missing: str | None = None, recommendation: str | None = None) -> int:
    run_id = uuid.uuid4().hex[:12]
    if helpers.output_mode in {"jsonl", "agent"}:
        helpers._begin_stream(run_id)  # noqa: SLF001
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_started", "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_id": run_id, "command_group": "swift", "command": " ".join(command), "task": None, "attributes": {"run_label": run_label, "target": target}})
    if raw_input_path is None:
        proc = helpers.run(command, quiet)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
        if exit_code == 127 and "missing tool:" in stderr.lower():
            tool_missing = tool_missing or command[0]
            status = status or "skipped"
            recommendation = recommendation or f"Install {command[0]} or run this command on a host where it is available."
    else:
        if not raw_input_path.exists():
            print(f"missing log: {raw_input_path}", file=sys.stderr)
            return 2
        stdout = ""
        stderr = ""
        exit_code = 0
    json_path = helpers.write_swift_diagnostics(
        run_label=run_label,
        command=command,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        target=target,
        raw_input_path=raw_input_path,
        status=status,
        tool_missing=tool_missing,
        recommendation=recommendation,
    )
    if helpers.output_mode in {"jsonl", "agent"}:
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "artifact", "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_id": run_id, "command_group": "swift", "command": " ".join(command), "task": None, "attributes": {"path": str(json_path.relative_to(helpers.repo_root)), "artifact_type": "result"}})
        helpers._emit({"schema_version": "rig.event.v1", "event_type": "run_finished", "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_id": run_id, "command_group": "swift", "command": " ".join(command), "task": None, "attributes": {"status": status or ("passed" if exit_code == 0 else "failed"), "exit_code": exit_code, "result_path": str((helpers.repo_root / ".build" / "rig" / "results" / "latest.json").relative_to(helpers.repo_root))}})  # noqa: SLF001
        helpers._finish_stream(run_id)  # noqa: SLF001
    from rig_tools.result import write_run_result
    result_payload = {
        "schema_version": "rig.result.v1",
        "run_id": run_id,
        "command_group": "swift",
        "command": " ".join(command),
        "task": None,
        "status": "passed" if exit_code == 0 else ("skipped" if exit_code == 127 else "failed"),
        "exit_code": exit_code,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": 0.0,
        "artifacts": [{"path": str(json_path.relative_to(helpers.repo_root)), "type": "json"}],
        "warnings": [],
        "errors": [] if exit_code == 0 else [{"message": recommendation or "swift command failed", "exit_code": exit_code}],
        "summary": {"target": target, "run_label": run_label},
        "next_actions": [],
        "stderr_tail": None,
    }
    write_run_result(helpers.repo_root, run_id, result_payload)
    helpers._write_result_bundle(result_payload, run_id=run_id)  # noqa: SLF001
    print(str(json_path.relative_to(helpers.repo_root)))
    return exit_code


def register(subparsers, helpers):
    parser = subparsers.add_parser("swift", help="Swift diagnostics", description="Deterministic parsing for swift build, swift test, and xcodebuild output.")
    swift_sub = parser.add_subparsers(dest="swift_cmd", required=True)

    def package_path_or_default(value: str | None) -> str:
        return value or "anigma"

    def build_command(args) -> list[str]:
        command = ["swift", "build", "--package-path", package_path_or_default(args.package_path)]
        if args.target:
            command.extend(["--target", args.target])
        if args.configuration:
            command.extend(["--configuration", args.configuration])
        return command

    def test_command(args) -> list[str]:
        command = ["swift", "test", "--package-path", package_path_or_default(args.package_path)]
        if args.filter:
            command.extend(["--filter", args.filter])
        return command

    build = swift_sub.add_parser("build", help="Run swift build and parse diagnostics")
    build.add_argument("--target", required=True)
    build.add_argument("--configuration")
    build.add_argument("--package-path")
    build.set_defaults(handler=lambda args: _run_and_report(
        helpers,
        build_command(args),
        quiet=args.quiet,
        target=args.target,
        run_label=f"swift-build-{args.target}",
    ))

    test = swift_sub.add_parser("test", help="Run swift test and parse diagnostics")
    test.add_argument("--filter")
    test.add_argument("--package-path")
    test.set_defaults(handler=lambda args: _run_and_report(
        helpers,
        test_command(args),
        quiet=args.quiet,
        run_label="swift-test",
    ))

    diag = swift_sub.add_parser("diagnose-log", help="Parse an existing Swift log")
    diag.add_argument("--log", required=True)
    diag.add_argument("--target")
    diag.set_defaults(handler=lambda args: _run_and_report(
        helpers,
        ["swift", "diagnose-log", args.log],
        quiet=args.quiet,
        target=args.target,
        run_label="swift-diagnose-log",
        raw_input_path=Path(args.log),
    ))

    warnings = swift_sub.add_parser("warnings", help="Extract warnings by running a target build")
    warnings.add_argument("--target", required=True)
    warnings.set_defaults(handler=lambda args: _run_and_report(
        helpers,
        ["swift", "build", "--package-path", "anigma", "--target", args.target],
        quiet=args.quiet,
        target=args.target,
        run_label=f"swift-warnings-{args.target}",
    ))

    xcodebuild = swift_sub.add_parser("xcodebuild", help="Run xcodebuild and parse diagnostics")
    xcodebuild.add_argument("--scheme", required=True)
    xcodebuild.add_argument("--project")
    xcodebuild.add_argument("--workspace")
    xcodebuild.set_defaults(handler=lambda args: _run_and_report(
        helpers,
        _swift_cmd(["xcodebuild", "-scheme", args.scheme], [*(["-project", args.project] if args.project else []), *(["-workspace", args.workspace] if args.workspace else [])]),
        quiet=args.quiet,
        run_label=f"xcodebuild-{args.scheme}",
    ))
