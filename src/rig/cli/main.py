from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from rig.config.loader import merge_config
from rig.config.paths import config_file, repo_state_root, cache_home, worktree_root
from rig.logging.jsonl_logger import JsonlLogger
from rig import commands_doctor, commands_execute, commands_tui, commands_validate, commands_workspace, commands_runtime, commands_model, commands_system, commands_agent_phase5, commands_job, commands_run, commands_benchmark, commands_provider, commands_context, commands_debug, commands_release, commands_ui, commands_window


def _repo_root() -> Path:
    return Path.cwd()


def _legacy_queue_path(repo_root: Path) -> Path:
    return repo_root / ".build" / "rig" / "queue" / "queue.json"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if sys.version_info < (3, 14):
        print(f"Rig requires Python 3.14 or newer.\nCurrent: {sys.version.split()[0]}\nExecutable: {sys.executable}", file=sys.stderr)
        return 1
    parser = argparse.ArgumentParser(prog="rig", description="Rig product shell")
    parser.add_argument("--debug", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
    status = sub.add_parser("status", help="Show repo, queue, providers, and next gates")
    status.set_defaults(handler=lambda args: _status(repo))
    init = sub.add_parser("init", help="Initialize Rig")
    init.add_argument("--yes", action="store_true")
    init.add_argument("--dry-run", action="store_true")
    init.add_argument("--config-target", choices=["pyproject", "dotrig"], default="pyproject")
    cfg = sub.add_parser("config")
    cfg_sub = cfg.add_subparsers(dest="subcmd", required=True)
    cfg_sub.add_parser("inspect", help="Inspect resolved config")
    log = sub.add_parser("log")
    log_sub = log.add_subparsers(dest="subcmd", required=True)
    log_sub.add_parser("list", help="List logs")
    show = log_sub.add_parser("show", help="Show run log"); show.add_argument("run_id")
    tail = log_sub.add_parser("tail", help="Tail run log"); tail.add_argument("run_id")
    commands_workspace.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_doctor.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_execute.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_window.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_validate.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_ui.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_tui.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_runtime.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_model.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_system.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_agent_phase5.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_job.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_benchmark.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_provider.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_context.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_run.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_debug.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_release.register(sub, type("H", (), {"repo_root": _repo_root()})())
    args = parser.parse_args(argv)
    repo = _repo_root()
    if args.debug:
        os.environ["RIG_DEBUG"] = "1"
    if args.cmd == "init":
        return _init(repo, dry_run=args.dry_run, yes=args.yes, config_target=args.config_target)
    if args.cmd == "config":
        return _config_inspect(repo)
    if args.cmd == "log":
        return _log_command(repo, args)
    if hasattr(args, "handler"):
        return args.handler(args)
    return 0


def _status(repo_root: Path) -> int:
    from rig_tools import orchestration, provider_registry
    payload = {
        "repo_root": str(repo_root),
        "queue": orchestration.queue_health(repo_root),
        "jobs": orchestration.list_jobs_summary(repo_root)[:10],
        "providers": provider_registry.list_providers(repo_root)[:10],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _init(repo_root: Path, *, dry_run: bool, yes: bool, config_target: str) -> int:
    cfg = config_file()
    pyproject = repo_root / "pyproject.toml"
    dotrig = repo_root / ".rig" / "config.toml"
    target = pyproject if config_target == "pyproject" else dotrig
    if not yes and not dry_run:
        print("Initialize Rig in this repository? [y/N] ", end="", flush=True)
        answer = sys.stdin.readline().strip().lower()
        if answer not in {"y", "yes"}:
            print("Rig init cancelled.")
            return 1
    if dry_run:
        writes = [str(repo_root / ".gitignore"), str(target)]
        if _legacy_queue_path(repo_root).exists():
            print("Legacy queue state detected at .build/rig/queue/queue.json.\nRig now uses .build/rig/jobs/.\nRun:\n  rig doctor repair --migrate-legacy-queue")
        print(json.dumps({"would_write": writes}, indent=2))
        return 0
    if config_target == "dotrig":
        dotrig.parent.mkdir(parents=True, exist_ok=True)
        if dotrig.exists():
            print("Refusing to overwrite existing .rig/config.toml without an explicit migration step.", file=sys.stderr)
            return 1
        dotrig.write_text("default_mode = \"safe\"\n", encoding="utf-8")
    else:
        if pyproject.exists():
            text = pyproject.read_text(encoding="utf-8")
            if "[tool.rig]" not in text:
                if not text.endswith("\n"):
                    text += "\n"
                text += "\n[tool.rig]\n"
                pyproject.write_text(text, encoding="utf-8")
        else:
            pyproject.write_text("[build-system]\nrequires = [\"setuptools>=69\", \"wheel\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[project]\nname = \"rig\"\nversion = \"0.1.0\"\n", encoding="utf-8")
    gitignore = repo_root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    for line in ["# Rig local state", ".build/rig/", ".rig/tmp/", ".rig/cache/"]:
        if line not in existing:
            existing += ("" if existing.endswith("\n") or not existing else "\n") + line + "\n"
    gitignore.write_text(existing, encoding="utf-8")
    if _legacy_queue_path(repo_root).exists():
        print("Legacy queue state detected at .build/rig/queue/queue.json.\nRig now uses .build/rig/jobs/.\nRun:\n  rig doctor repair --migrate-legacy-queue")
    print("Rig initialized.\nNext:\n  rig ui\n  rig run --task <task-id> --provider custom-command")
    return 0


def _config_inspect(repo_root: Path) -> int:
    payload = merge_config(repo_root)
    print(json.dumps({
        "config_file": payload["config_file"],
        "state_dir": payload["state_dir"],
        "cache_dir": str(cache_home() / "rig"),
        "repo_root": payload["repo_root"],
        "repo_state_dir": str(repo_state_root(repo_root)),
        "external_worktree_root": str(worktree_root(repo_root)),
        "active": payload,
    }, indent=2))
    return 0


def _log_command(repo_root: Path, args) -> int:
    logger = JsonlLogger(repo_state_root(repo_root) / "logs")
    if args.subcmd == "list":
        for p in sorted(logger.log_dir.glob("run_*.jsonl")):
            print(p.name.removeprefix("run_").removesuffix(".jsonl"))
        return 0
    path = logger.path_for_run(args.run_id)
    if not path.exists():
        print(f"missing log: {args.run_id}", file=sys.stderr)
        return 1
    lines = path.read_text(encoding="utf-8").splitlines()
    if args.subcmd == "show":
        print("\n".join(lines))
    else:
        for line in lines[-20:]:
            print(line)
    return 0
