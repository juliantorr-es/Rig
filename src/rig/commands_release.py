from __future__ import annotations

from rig_tools.release_readiness import run_release_readiness_command


def register(subparsers, helpers):
    parser = subparsers.add_parser("release", help="Release-readiness and package build checks", description="Validate the installable rig-control package and its console script.")
    release = parser.add_subparsers(dest="release_cmd", required=True)

    check = release.add_parser("check", help="Check package release readiness")
    check.add_argument("--format", choices=["text", "json"], default="text")
    check.set_defaults(handler=lambda args: run_release_readiness_command(helpers.repo_root, format_type=args.format, dry_run_build=True))

    build = release.add_parser("build", help="Build distributable package artifacts")
    build.add_argument("--dry-run", action="store_true", help="Do not invoke python -m build; only report planned outputs")
    build.set_defaults(handler=lambda args: run_release_readiness_command(helpers.repo_root, format_type="text", dry_run_build=args.dry_run))
