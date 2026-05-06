from __future__ import annotations

import json
from pathlib import Path

from rig_tools import proposal_swarm


def register(subparsers, helpers):
    parser = subparsers.add_parser(
        "swarm",
        help="Proposal swarm planning and scoring",
        description="Run bounded deterministic candidate swarms against a shared compressed context pack.",
    )
    sub = parser.add_subparsers(dest="swarm_cmd", required=True)

    status = sub.add_parser("status", help="Show swarm readiness")
    status.set_defaults(handler=lambda args: _emit(proposal_swarm.status(helpers.repo_root)))

    profiles = sub.add_parser("profiles", help="List swarm profiles")
    profiles.set_defaults(handler=lambda args: _emit(proposal_swarm.profiles(helpers.repo_root)))

    propose = sub.add_parser("propose", help="Run or plan a proposal swarm")
    propose.add_argument("--task", required=True)
    propose.add_argument("--kind", required=True, choices=["plan", "validator_error_classification", "docs_normalization_plan", "patch_proposal", "prompt_repair"])
    propose.add_argument("--candidates", type=int, default=4)
    propose.add_argument("--bias", action="append", help="Solution bias profiles to apply (repeatable)")
    propose.add_argument("--backend", default="llama-cpp", choices=["mlx", "llama-cpp"])
    propose.add_argument("--model")
    propose.add_argument("--model-path")
    propose.add_argument("--profile", default="balanced", choices=["conservative", "balanced", "exploratory"])
    propose.add_argument("--max-parallel", type=int)
    propose.add_argument("--use-llm-context", action="store_true")
    propose.add_argument("--dry-run", action="store_true")
    propose.set_defaults(handler=lambda args: _emit(proposal_swarm.propose_swarm(
        helpers.repo_root,
        task=args.task,
        kind=args.kind,
        candidates=args.candidates,
        dry_run=args.dry_run,
        backend=args.backend,
        model=args.model,
        model_path=args.model_path,
        profile=args.profile,
        max_parallel=args.max_parallel,
        use_llm_context=args.use_llm_context,
        bias_profiles=args.bias,
    )))

    show = sub.add_parser("show", help="Show a swarm run")
    show.add_argument("--swarm-id", required=True)
    show.set_defaults(handler=lambda args: _emit(proposal_swarm.show_swarm(helpers.repo_root, args.swarm_id)))

    board = sub.add_parser("scoreboard", help="Show swarm scoreboard")
    board.add_argument("--swarm-id", required=True)
    board.set_defaults(handler=lambda args: _emit(proposal_swarm.scoreboard(helpers.repo_root, args.swarm_id)))


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    if isinstance(payload, dict) and payload.get("status") in {"failed", "invalid", "rejected", "blocked"}:
        return 1
    return 0
