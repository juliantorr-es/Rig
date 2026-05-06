from __future__ import annotations

import json

from rig_tools import mlx_local


def register(subparsers, helpers):
    parser = subparsers.add_parser("embeddings", help="Optional MLX embeddings", description="Build and query local retrieval embeddings.")
    emb = parser.add_subparsers(dest="emb_cmd", required=True)

    status = emb.add_parser("status", help="Show embeddings backend status")
    status.add_argument("--backend", default="mlx")
    status.set_defaults(handler=lambda args: _emit(mlx_local.status(args.backend)))

    smoke = emb.add_parser("smoke", help="Smoke-test embeddings")
    smoke.add_argument("--backend", default="mlx")
    smoke.add_argument("--model")
    smoke.set_defaults(handler=lambda args: _emit(mlx_local.smoke_embeddings(helpers.repo_root, model=args.model)))

    build = emb.add_parser("build", help="Build local embeddings")
    build.add_argument("--backend", default="mlx")
    build.add_argument("--model")
    build.add_argument("--limit", type=int)
    build.set_defaults(handler=lambda args: _emit(mlx_local.build_embeddings(helpers.repo_root, model=args.model, limit=args.limit)))

    query = emb.add_parser("query", help="Query embeddings")
    query.add_argument("--backend", default="mlx")
    query.add_argument("query")
    query.add_argument("--model")
    query.add_argument("--top-k", type=int, default=10, dest="top_k")
    query.set_defaults(handler=lambda args: _emit(mlx_local.query_embeddings(helpers.repo_root, args.query, model=args.model, top_k=args.top_k)))


def _emit(payload) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
