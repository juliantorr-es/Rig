from __future__ import annotations


def register(subparsers, helpers):
    parser = subparsers.add_parser("brief", help="Task brief generation", description="Generate deterministic task briefs.")
    brief_sub = parser.add_subparsers(dest="brief_cmd", required=True)

    generate = brief_sub.add_parser("generate", help="Generate a brief")
    generate.add_argument("--task", required=True)
    generate.add_argument("--template", default="cleanup_executable_consolidation")
    generate.add_argument("--risk")
    generate.add_argument("--target")
    generate.add_argument("--query")
    generate.add_argument("--limit", type=int, default=10)
    generate.add_argument("--format", choices=["markdown", "json"], default="markdown")
    generate.add_argument("--dry-run", action="store_true")
    generate.add_argument("--write")
    generate.set_defaults(handler=lambda args: helpers.delegate(
        "anigma_generate_task_brief.py",
        [
            f"--task={args.task}",
            f"--template={args.template}",
            *( [f"--risk={args.risk}"] if args.risk else [] ),
            *( [f"--target={args.target}"] if args.target else [] ),
            *( [f"--query={args.query}"] if args.query else [] ),
            f"--limit={args.limit}",
            f"--format={args.format}",
            *(["--dry-run"] if args.dry_run else []),
            *( [f"--write={args.write}"] if args.write else [] ),
        ],
        args.quiet,
    ))

    list_t = brief_sub.add_parser("list-templates", help="List available templates")
    list_t.set_defaults(handler=lambda args: helpers.delegate("anigma_generate_task_brief.py", ["--list-templates"], args.quiet))

