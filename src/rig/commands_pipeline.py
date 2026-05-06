from __future__ import annotations


def register(subparsers, helpers):
    parser = subparsers.add_parser("pipeline", help="Pipeline operations", description="Run and package deterministic pipeline workflows.")
    pipeline_sub = parser.add_subparsers(dest="pipeline_cmd", required=True)

    run = pipeline_sub.add_parser("run", help="Run a profile")
    run.add_argument("--profile", required=True)
    run.add_argument("--task", required=True)
    run.add_argument("--target")
    run.set_defaults(handler=lambda args: helpers.delegate(
        "anigma_pipeline.py",
        [f"run", f"--profile={args.profile}", f"--task={args.task}", *( [f"--target={args.target}"] if args.target else [] )],
        args.quiet,
    ))

    bundle = pipeline_sub.add_parser("bundle", help="Create a review bundle")
    bundle.add_argument("--task", required=True)
    bundle.add_argument("--latest-run", action="store_true")
    bundle.add_argument("--run-id")
    bundle.add_argument("--out")
    bundle.set_defaults(handler=lambda args: helpers.delegate(
        "anigma_pipeline.py",
        [f"bundle", f"--task={args.task}", *(["--latest-run"] if args.latest_run else []), *( [f"--run-id={args.run_id}"] if args.run_id else [] ), *( [f"--out={args.out}"] if args.out else [] )],
        args.quiet,
    ))

    latest = pipeline_sub.add_parser("latest-run", help="Show latest run directory")
    latest.add_argument("--task", required=True)
    latest.add_argument("--profile")
    latest.set_defaults(handler=lambda args: helpers.latest_run(args))

