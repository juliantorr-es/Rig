from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from rig_tools import context_compression
from rig_tools.result import RigResult, write_latest_result, write_run_result


def register(subparsers, helpers):
    parser = subparsers.add_parser("context", help="Build and inspect compressed Rig context packs", description="Create deterministic, task-scoped context packs for local LLM planning and review.")
    sub = parser.add_subparsers(dest="context_cmd", required=True)

    build = sub.add_parser("build", help="Build a context pack")
    build.add_argument("--task", required=True)
    build.add_argument("--purpose", default="review")
    build.add_argument("--max-chars", type=int)
    build.add_argument("--use-llm", action="store_true")
    build.add_argument("--model")
    build.set_defaults(handler=lambda args: _emit_result(helpers, _handle_build(helpers, args)))

    budget = sub.add_parser("budget", help="Show the recommended budget")
    budget.add_argument("--task", required=True)
    budget.add_argument("--purpose", default="review")
    budget.set_defaults(handler=lambda args: _emit_result(helpers, _handle_budget(helpers, args)))

    show = sub.add_parser("show", help="Show the latest context pack")
    show.add_argument("--latest", action="store_true")
    show.set_defaults(handler=lambda args: _handle_show(helpers, args))


def _emit_result(helpers, payload: dict) -> int:
    payload = helpers._apply_notification(payload)  # noqa: SLF001
    write_latest_result(helpers.repo_root, payload)
    if payload.get("run_id"):
        write_run_result(helpers.repo_root, payload["run_id"], payload)
    if helpers.output_mode == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))
    return int(payload.get("exit_code", 0))


def _result_payload(helpers, *, command: str, task: str | None, status: str, exit_code: int, summary: dict, artifacts: list[dict]) -> dict:
    run_id = uuid.uuid4().hex[:12]
    started = time.time()
    finished = time.time()
    return RigResult(
        command_group="context",
        command=command,
        status=status,
        exit_code=exit_code,
        run_id=run_id,
        task=task,
        summary=summary,
        artifacts=artifacts,
    ).to_dict() | {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(finished)),
        "duration_seconds": round(finished - started, 3),
    }


def _handle_build(helpers, args) -> dict:
    pack = context_compression.write_context_pack(
        helpers.repo_root,
        task=args.task,
        purpose=args.purpose,
        max_chars=args.max_chars,
        use_llm=args.use_llm,
        model=args.model,
    )
    return _result_payload(
        helpers,
        command=f"rig context build --task {args.task} --purpose {args.purpose}",
        task=args.task,
        status="passed",
        exit_code=0,
        summary={
            "task": args.task,
            "purpose": args.purpose,
            "max_chars": pack["max_chars"],
            "char_count": pack["char_count"],
            "compression_ratio": pack["compression_ratio"],
            "selected_artifact_count": len(pack["selected_artifacts"]),
            "omitted_artifact_count": len(pack["omitted_artifacts"]),
            "json_path": pack["json_path"],
            "md_path": pack["md_path"],
        },
        artifacts=[
            {"path": str(Path(pack["json_path"]).relative_to(helpers.repo_root)), "type": "context_pack"},
            {"path": str(Path(pack["md_path"]).relative_to(helpers.repo_root)), "type": "context_pack"},
        ],
    )


def _handle_budget(helpers, args) -> dict:
    return _result_payload(
        helpers,
        command=f"rig context budget --task {args.task} --purpose {args.purpose}",
        task=args.task,
        status="passed",
        exit_code=0,
        summary={
            "task": args.task,
            "purpose": args.purpose,
            "max_chars": context_compression.budget_for_purpose(args.purpose),
        },
        artifacts=[],
    )


def _handle_show(helpers, args) -> int:
    path = helpers.repo_root / ".build" / "rig" / "context" / "latest.md"
    if not path.exists():
        print(json.dumps({"status": "failed", "error": "missing_latest_context_pack"}, indent=2))
        return 1
    print(path.read_text(encoding="utf-8"))
    return 0
