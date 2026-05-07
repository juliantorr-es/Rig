from __future__ import annotations

import json
from pathlib import Path

from rig_tools.agent_proposals import create_proposal, decode_raw_output, proposal_to_command_plan
from rig_tools.runtime_registry import provider_for_id
from rig_tools.workspace_governance import WorkspaceGovernance


def register(subparsers, helpers):
    parser = subparsers.add_parser("agent", help="Governed agent proposals")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    propose = sub.add_parser("propose", help="Propose from provider"); propose.add_argument("--workspace", required=True); propose.add_argument("--provider", required=True); propose.add_argument("--model", default="static"); propose.add_argument("--static-output"); propose.set_defaults(handler=lambda args: _propose(helpers, args.workspace, args.provider, args.model, args.static_output))
    decode = sub.add_parser("decode", help="Decode proposal"); decode.add_argument("proposal_id"); decode.set_defaults(handler=lambda args: _decode(helpers, args.proposal_id))
    inspect = sub.add_parser("inspect", help="Inspect proposal"); inspect.add_argument("proposal_id"); inspect.set_defaults(handler=lambda args: _decode(helpers, args.proposal_id))
    accept = sub.add_parser("accept", help="Accept proposal into CommandPlan"); accept.add_argument("proposal_id"); accept.set_defaults(handler=lambda args: _accept(helpers, args.proposal_id))
    reject = sub.add_parser("reject", help="Reject proposal"); reject.add_argument("proposal_id"); reject.set_defaults(handler=lambda args: _reject(helpers, args.proposal_id))


def _proposal_path(repo_root: Path, proposal_id: str) -> Path:
    return repo_root / ".build" / "rig" / "agent-proposals" / f"{proposal_id}.json"


def _load(repo_root: Path, proposal_id: str) -> dict:
    return json.loads(_proposal_path(repo_root, proposal_id).read_text(encoding="utf-8"))


def _propose(helpers, workspace_id: str, provider_id: str, model_id: str, static_output: str | None):
    provider = provider_for_id(helpers.repo_root, provider_id)
    result = provider.invoke({"workspace_id": workspace_id, "model_id": model_id, "static_output": static_output or "{\"intent\":{\"kind\":\"plan\"},\"decoded_actions\":[{\"type\":\"command\",\"argv\":[\"python\",\"-m\",\"pytest\",\"-q\"]}],\"files_referenced\":[],\"confidence\":0.8,\"risk_level\":\"medium\"}"})
    proposal = create_proposal(helpers.repo_root, workspace_id=workspace_id, provider_id=provider_id, model_id=model_id, raw_output=result.raw_output, provider_manifest=provider.manifest())
    print(json.dumps(proposal, indent=2))
    return 0


def _decode(helpers, proposal_id: str):
    proposal = _load(helpers.repo_root, proposal_id)
    print(json.dumps(proposal, indent=2))
    return 0


def _accept(helpers, proposal_id: str):
    proposal = _load(helpers.repo_root, proposal_id)
    plan = proposal_to_command_plan(helpers.repo_root, proposal)
    out = helpers.repo_root / ".build" / "rig" / "agent-plans"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{proposal_id}.json"
    payload = {
        "schema_version": "rig.agent_plan.v1",
        "plan_id": plan.plan_id,
        "task": proposal.get("workspace_id"),
        "agent_id": proposal.get("provider_id"),
        "mode": "review",
        "prompt": json.dumps(proposal.get("intent") or {}),
        "prompt_file": f".build/rig/agent-proposals/{proposal_id}.json",
        "allowed_paths": proposal.get("files_referenced") or [],
        "forbidden_paths": [],
        "expected_outputs": ["governed command plan"],
        "timeout_seconds": plan.timeout_seconds,
        "requires_confirm": True,
        "git_mutation_allowed": False,
        "source_context": proposal.get("files_referenced") or [],
        "created_by": "rig agent accept",
        "authoritative": False,
        "warnings": [],
        "command_plan": {
            "schema_version": "rig.command_plan.v1",
            "plan_id": plan.plan_id,
            "action_id": plan.action_id,
            "mode": plan.mode,
            "argv": plan.argv,
            "working_directory": plan.working_directory,
            "timeout_seconds": plan.timeout_seconds,
            "allowed": plan.allowed,
            "task": plan.task,
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"proposal_id": proposal_id, "status": "planned", "plan_path": str(path.relative_to(helpers.repo_root))}, indent=2))
    return 0


def _reject(helpers, proposal_id: str):
    proposal = _load(helpers.repo_root, proposal_id)
    proposal["status"] = "rejected"
    _proposal_path(helpers.repo_root, proposal_id).write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"proposal_id": proposal_id, "status": "rejected"}, indent=2))
    return 0
