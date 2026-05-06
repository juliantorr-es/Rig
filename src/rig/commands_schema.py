from __future__ import annotations

import json
from pathlib import Path

from rig_tools.result import RigResult, write_latest_result, write_run_result
from rig_tools.schema_validation import list_families, validate_artifacts


def _write_outputs(helpers, payload: dict) -> int:
    payload = helpers._apply_notification(payload)  # noqa: SLF001
    write_latest_result(helpers.repo_root, payload)
    run_id = payload.get("run_id")
    if run_id:
        write_run_result(helpers.repo_root, run_id, payload)
    out_dir = helpers.repo_root / ".build" / "rig" / "schema-validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Rig Schema Validation",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Validator: `{payload.get('validator')}`",
        f"- Validated artifacts: `{payload.get('validated_artifact_count')}`",
        f"- Passed: `{payload.get('passed_count')}`",
        f"- Failed: `{payload.get('failed_count')}`",
        f"- Skipped: `{payload.get('skipped_count')}`",
        "",
        "## Results",
    ]
    for result in payload.get("results", []):
        lines.extend([
            f"- `{result.get('artifact_path')}`",
            f"  - Family: `{result.get('schema_family')}`",
            f"  - Status: `{result.get('status')}`",
            f"  - Errors: `{result.get('error_count')}`",
        ])
        for error in result.get("errors", []):
            lines.append(f"    - `{error.get('path')}`: {error.get('message')}")
    (out_dir / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if helpers.output_mode == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
    return 0 if payload.get("status") == "passed" else 1


def register(subparsers, helpers):
    parser = subparsers.add_parser("schema", help="Schema validation", description="Validate Rig JSON machine artifacts against versioned JSON Schema families.")
    schema_sub = parser.add_subparsers(dest="schema_cmd", required=True)

    list_cmd = schema_sub.add_parser("list", help="List schema families")
    list_cmd.set_defaults(handler=lambda args: _handle_list(helpers, args))

    validate = schema_sub.add_parser("validate", help="Validate a Rig artifact or family")
    validate.add_argument("--artifact")
    validate.add_argument("--family")
    validate.set_defaults(handler=lambda args: _handle_validate(helpers, args))


def _handle_list(helpers, args) -> int:
    families = list_families()
    payload = RigResult(
        command_group="schema",
        command="rig schema list",
        status="passed",
        exit_code=0,
        run_id="schema-list",
        summary={"families": families},
        artifacts=[{"path": f"Docs/schemas/{family}.schema.json", "type": "schema"} for family in families],
    ).to_dict()
    if helpers.output_mode in {"json", "jsonl", "agent"}:
        write_latest_result(helpers.repo_root, payload)
        write_run_result(helpers.repo_root, payload["run_id"], payload)
        if helpers.output_mode == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(json.dumps(payload, sort_keys=True))
    else:
        for family in families:
            print(family)
    return 0


def _handle_validate(helpers, args) -> int:
    summary = validate_artifacts(helpers.repo_root, artifact_path=args.artifact, family=args.family)
    validation_dir = helpers.repo_root / ".build" / "rig" / "schema-validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    validation_payload = summary.to_dict()
    validation_payload["artifacts"] = [
        {"path": result.artifact_path, "type": "schema"} for result in summary.results
    ]
    (validation_dir / "latest.json").write_text(json.dumps(validation_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Rig Schema Validation",
        "",
        f"- Status: `{validation_payload.get('status')}`",
        f"- Validator: `{validation_payload.get('validator')}`",
        f"- Validated artifacts: `{validation_payload.get('validated_artifact_count')}`",
        f"- Passed: `{validation_payload.get('passed_count')}`",
        f"- Failed: `{validation_payload.get('failed_count')}`",
        f"- Skipped: `{validation_payload.get('skipped_count')}`",
        "",
        "## Results",
    ]
    for result in validation_payload.get("results", []):
        lines.extend([
            f"- `{result.get('artifact_path')}`",
            f"  - Family: `{result.get('schema_family')}`",
            f"  - Status: `{result.get('status')}`",
            f"  - Errors: `{result.get('error_count')}`",
        ])
        for error in result.get("errors", []):
            lines.append(f"    - `{error.get('path')}`: {error.get('message')}")
    (validation_dir / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = RigResult(
        command_group="schema",
        command="rig schema validate",
        status=summary.status,
        exit_code=0 if summary.status == "passed" else 1,
        run_id="schema-validate",
        task=None,
        summary={
            "validated_artifact_count": summary.validated_artifact_count,
            "passed_count": summary.passed_count,
            "failed_count": summary.failed_count,
            "skipped_count": summary.skipped_count,
            "validator": summary.validator,
            "validation_report": str((validation_dir / "latest.json").relative_to(helpers.repo_root)),
        },
        artifacts=[{"path": result.artifact_path, "type": "schema"} for result in summary.results],
    ).to_dict()
    return _write_outputs(helpers, payload)
