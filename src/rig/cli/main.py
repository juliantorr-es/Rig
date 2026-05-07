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
from rig_tools.workspace_governance import WorkspaceGovernance
from rig import commands_execute, commands_tui, commands_validate, commands_workspace, commands_runtime, commands_model, commands_system, commands_agent_phase5


def _repo_root() -> Path:
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="rig", description="Rig product shell")
    parser.add_argument("--debug", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
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
    commands_execute.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_validate.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_tui.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_runtime.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_model.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_system.register(sub, type("H", (), {"repo_root": _repo_root()})())
    commands_agent_phase5.register(sub, type("H", (), {"repo_root": _repo_root()})())
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


def _init(repo_root: Path, *, dry_run: bool, yes: bool, config_target: str) -> int:
    cfg = config_file()
    if dry_run:
        print(json.dumps({"would_write": [str(cfg), str(repo_root / ".gitignore")]}, indent=2))
        return 0
    cfg.parent.mkdir(parents=True, exist_ok=True)
    if not cfg.exists() and config_target == "dotrig":
        (repo_root / ".rig").mkdir(parents=True, exist_ok=True)
        cfg.write_text("default_mode = \"safe\"\n", encoding="utf-8")
    elif not cfg.exists():
        cfg.write_text("[tool.rig]\n", encoding="utf-8")
    gitignore = repo_root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    for line in ["# Rig local state", ".build/rig/", ".rig/tmp/", ".rig/cache/"]:
        if line not in existing:
            existing += ("" if existing.endswith("\n") or not existing else "\n") + line + "\n"
    gitignore.write_text(existing, encoding="utf-8")
    print("Rig initialized.\nRun `rig tui` to open the command center.\nRun `rig workspace create --task <task-id>` to create your first governed workspace.")
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
