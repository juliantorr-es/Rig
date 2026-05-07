from __future__ import annotations

from rig_tools.release_check import ReleaseReport, ReleaseResult, run_release_check, run_release_check_command


def run_release_readiness(repo_root, *, format_type: str = "text", dry_run_build: bool = True):
    return run_release_check(repo_root)


def run_release_readiness_command(repo_root, *, format_type: str = "text", dry_run_build: bool = True) -> int:
    return run_release_check_command(repo_root, as_json=format_type == "json")
