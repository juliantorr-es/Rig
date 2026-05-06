from __future__ import annotations


def register(subparsers, helpers):
    parser = subparsers.add_parser("atlas", help="Atlas operations", description="Atlas operations over derived repo context.")
    atlas_sub = parser.add_subparsers(dest="atlas_cmd", required=True)

    build = atlas_sub.add_parser("build", help="Build atlas")
    build.set_defaults(handler=lambda args: helpers.delegate("anigma_build_repo_atlas.py", [], args.quiet))

    query = atlas_sub.add_parser("query", help="Query atlas")
    query.add_argument("query", nargs="?")
    query.add_argument("--symbol")
    query.add_argument("--file")
    query.add_argument("--risk")
    query.add_argument("--target")
    query.add_argument("--language")
    query.add_argument("--native-dependency")
    query.add_argument("--bridge")
    query.add_argument("--entrypoint")
    query.add_argument("--state")
    query.add_argument("--flow")
    query.add_argument("--cohesion")
    query.add_argument("--limit", type=int, default=10)
    query.add_argument("--format", choices=["text", "json"], default="text")
    query.add_argument("--check", action="store_true")
    query.set_defaults(handler=lambda args: helpers.delegate(
        "anigma_context_query.py",
        [
            *([args.query] if args.query else []),
            *([f"--symbol={args.symbol}"] if args.symbol else []),
            *([f"--file={args.file}"] if args.file else []),
            *([f"--risk={args.risk}"] if args.risk else []),
            *([f"--target={args.target}"] if args.target else []),
            *([f"--language={args.language}"] if args.language else []),
            *([f"--native-dependency={args.native_dependency}"] if args.native_dependency else []),
            *([f"--bridge={args.bridge}"] if args.bridge else []),
            *([f"--entrypoint={args.entrypoint}"] if args.entrypoint else []),
            *([f"--state={args.state}"] if args.state else []),
            *([f"--flow={args.flow}"] if args.flow else []),
            *([f"--cohesion={args.cohesion}"] if args.cohesion else []),
            f"--limit={args.limit}",
            f"--format={args.format}",
            *(["--check"] if args.check else []),
        ],
        args.quiet,
    ))

    check = atlas_sub.add_parser("check", help="Check atlas presence")
    check.set_defaults(handler=lambda args: helpers.delegate("anigma_context_query.py", ["--check"], args.quiet))

