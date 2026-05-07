#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SLUG_RE = re.compile(r"^[a-z0-9-]+$")
DEFAULT_BASE = "main"


@dataclass(frozen=True)
class WorktreePlan:
    repo_root: Path
    worktree_root: Path
    worktree_path: Path
    branch: str
    base: str


@dataclass(frozen=True)
class AttachedWorktree:
    agent: str
    task: str
    path: Path
    branch: str
    expected_branch: str
    head: str
    dirty: bool
    dirty_files: tuple[str, ...]
    branch_matches_convention: bool


@dataclass(frozen=True)
class CheckpointPlan:
    agent: str
    task: str
    path: Path
    branch: str
    head: str
    dirty_files: tuple[str, ...]
    message: str
    files_to_stage: tuple[str, ...]
    has_conflict: bool
    excluded_files: tuple[str, ...]


def _run_git(args: list[str], *, cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


def _git_output(args: list[str], *, cwd: Path | None = None) -> str:
    result = _run_git(args, cwd=cwd)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return result.stdout.strip()


def repo_common_dir(repo_root: Path) -> Path:
    common_dir = Path(_git_output(["rev-parse", "--git-common-dir"], cwd=repo_root))
    return common_dir if common_dir.is_absolute() else (repo_root / common_dir).resolve()


def validate_slug(value: str, kind: str) -> str:
    if not SLUG_RE.fullmatch(value):
        raise ValueError(f"Invalid {kind} slug '{value}': use lowercase letters, numbers, and hyphen only.")
    return value


def resolve_repo_root() -> Path:
    return Path(_git_output(["rev-parse", "--show-toplevel"])).resolve()


def resolve_worktree_plan(agent: str, task: str, *, repo_root: Path | None = None, base: str = DEFAULT_BASE) -> WorktreePlan:
    agent = validate_slug(agent, "agent")
    task = validate_slug(task, "task")
    repo_root = repo_root or resolve_repo_root()
    worktree_root = repo_root.parent / "Rig-worktrees"
    worktree_path = worktree_root / f"rig-{agent}-{task}"
    branch = f"agent/{task}/{agent}"
    return WorktreePlan(repo_root=repo_root, worktree_root=worktree_root, worktree_path=worktree_path, branch=branch, base=base)


def branch_exists(branch: str, *, cwd: Path) -> bool:
    result = _run_git(["rev-parse", "--verify", "--quiet", branch], cwd=cwd)
    return result.returncode == 0


def print_prompt(agent: str, task: str, plan: WorktreePlan) -> str:
    return "\n".join(
        [
            "Before doing anything, read AGENTS.md and summarize the Git discipline rules you will follow. Do not edit files until you have done that.",
            f"You are working ONLY in:",
            f"{plan.worktree_path}",
            "First run:",
            "  pwd",
            "  git status --short --branch",
            "  git branch --show-current",
            "  git rev-parse --show-toplevel",
            "  git rev-parse --short HEAD",
            f"If pwd or git rev-parse --show-toplevel is not exactly {plan.worktree_path}, stop immediately and report that you are in the wrong directory.",
            "Do not edit files outside this worktree.",
            "Do not run forbidden Git commands.",
            "",
            f"Agent: {agent}",
            f"Task: {task}",
        ]
    )


def worktree_prompt_header(path: Path) -> str:
    return "\n".join(
        [
            "Before doing anything, read AGENTS.md and summarize the Git discipline rules you will follow. Do not edit files until you have done that.",
            f"You are working ONLY in:",
            f"{path}",
            "First run:",
            "  pwd",
            "  git status --short --branch",
            "  git branch --show-current",
            "  git rev-parse --show-toplevel",
            "  git rev-parse --short HEAD",
            f"If pwd or git rev-parse --show-toplevel is not exactly {path}, stop immediately and report that you are in the wrong directory.",
            "Do not edit files outside this worktree.",
            "Do not run forbidden Git commands.",
        ]
    )


def inspect_attached_worktree(agent: str, task: str, path: Path, *, repo_root: Path | None = None) -> AttachedWorktree:
    agent = validate_slug(agent, "agent")
    task = validate_slug(task, "task")
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Worktree path does not exist: {path}")
    repo_root = repo_root or resolve_repo_root()
    path_top = Path(_git_output(["rev-parse", "--show-toplevel"], cwd=path)).resolve()
    path_head = _git_output(["rev-parse", "--short", "HEAD"], cwd=path)
    path_branch = _git_output(["branch", "--show-current"], cwd=path)
    status = _git_output(["status", "--short", "--branch"], cwd=path)
    if repo_common_dir(path_top) != repo_common_dir(repo_root):
        raise ValueError(f"Worktree does not belong to the same repository: {path}")
    dirty_files = tuple(
        line
        for line in status.splitlines()
        if line.strip() and not line.startswith("##")
    )
    expected_branch = f"agent/{task}/{agent}"
    return AttachedWorktree(
        agent=agent,
        task=task,
        path=path,
        branch=path_branch,
        expected_branch=expected_branch,
        head=path_head,
        dirty=bool(dirty_files),
        dirty_files=dirty_files,
        branch_matches_convention=(path_branch == expected_branch),
    )


def parse_porcelain_v1_z(status: bytes | str) -> tuple[tuple[str, ...], bool]:
    if isinstance(status, str):
        status = status.encode("utf-8")
    files: list[str] = []
    has_conflict = False
    records = status.split(b"\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if record.startswith(b"?? "):
            files.append(record[3:].decode("utf-8"))
            continue
        if len(record) < 3:
            continue
        xy = record[:2].decode("utf-8")
        path = record[3:].decode("utf-8")
        if "U" in xy or xy in {"DD", "AA", "AU", "UA", "DU", "UD"}:
            has_conflict = True
        if xy.startswith("R") or xy.startswith("C"):
            if index < len(records) and records[index]:
                path = records[index].decode("utf-8")
                index += 1
        files.append(path)
    return tuple(files), has_conflict


def build_checkpoint_plan(
    agent: str,
    task: str,
    path: Path,
    message: str,
    *,
    include: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    repo_root: Path | None = None,
) -> CheckpointPlan:
    attachment = inspect_attached_worktree(agent, task, path, repo_root=repo_root)
    if attachment.branch == "main":
        raise ValueError("Refusing to checkpoint on main branch.")
    if not message.strip():
        raise ValueError("Commit message must be non-empty.")
    if include and exclude:
        raise ValueError("Refusing to mix include and exclude selection.")
    result = _run_git(["status", "--porcelain=v1", "-z"], cwd=attachment.path)
    if result.returncode != 0:
        message_text = result.stderr.strip() or result.stdout.strip() or "git status failed"
        raise RuntimeError(message_text)
    files_to_stage, has_conflict = parse_porcelain_v1_z(result.stdout)
    if has_conflict:
        raise ValueError("Refusing to checkpoint unresolved merge/conflict states.")
    dirty_set = set(files_to_stage)
    if include:
        missing = [item for item in include if item not in dirty_set]
        if missing:
            raise ValueError(f"Refusing to include non-dirty path(s): {', '.join(missing)}")
        selected = tuple(include)
        excluded_files = tuple()
    elif exclude:
        missing = [item for item in exclude if item not in dirty_set]
        if missing:
            raise ValueError(f"Refusing to exclude non-dirty path(s): {', '.join(missing)}")
        excluded_set = set(exclude)
        selected = tuple(item for item in files_to_stage if item not in excluded_set)
        excluded_files = tuple(exclude)
    else:
        selected = files_to_stage
        excluded_files = tuple()
    if not selected:
        raise ValueError("Refusing to checkpoint with zero selected files.")
    return CheckpointPlan(
        agent=attachment.agent,
        task=attachment.task,
        path=attachment.path,
        branch=attachment.branch,
        head=attachment.head,
        dirty_files=tuple(attachment.dirty_files),
        message=message.strip(),
        files_to_stage=selected,
        has_conflict=has_conflict,
        excluded_files=excluded_files,
    )


def cmd_start(args: argparse.Namespace) -> int:
    plan = resolve_worktree_plan(args.agent, args.task)
    if not plan.worktree_root.exists() and not args.dry_run:
        plan.worktree_root.mkdir(parents=True, exist_ok=True)
    if plan.worktree_path.exists():
        print(f"Refusing to create worktree: path already exists: {plan.worktree_path}", file=sys.stderr)
        return 1
    if branch_exists(plan.branch, cwd=plan.repo_root):
        print(f"Refusing to create worktree: branch already exists: {plan.branch}", file=sys.stderr)
        return 1
    command = ["git", "worktree", "add", str(plan.worktree_path), "-b", plan.branch, plan.base]
    if args.dry_run:
        print("DRY RUN:", " ".join(command))
    else:
        result = _run_git(command, cwd=plan.repo_root)
        if result.returncode != 0:
            print(result.stderr.strip() or result.stdout.strip() or "git worktree add failed", file=sys.stderr)
            return result.returncode or 1
    print(f"worktree path: {plan.worktree_path}")
    print(f"branch: {plan.branch}")
    print(f"base: {plan.base}")
    print("setup commands:")
    print("  python3.14 -m venv .venv")
    print("  source .venv/bin/activate")
    print('  python -m pip install -e ".[ui,dev]"')
    print()
    print(print_prompt(args.agent, args.task, plan))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = resolve_repo_root()
    command = ["git", "worktree", "list"]
    if args.dry_run:
        print("DRY RUN:", " ".join(command))
        return 0
    result = _run_git(command, cwd=root)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def cmd_status(args: argparse.Namespace) -> int:
    root = resolve_repo_root()
    if args.dry_run:
        print("DRY RUN: git rev-parse --show-toplevel")
        print("DRY RUN: git branch --show-current")
        print("DRY RUN: git rev-parse --short HEAD")
        print("DRY RUN: git status --short --branch")
        print("DRY RUN: git worktree list")
        return 0
    print(f"current repo root: {root}")
    print(f"current branch: {_git_output(['branch', '--show-current'], cwd=root)}")
    print(f"short HEAD: {_git_output(['rev-parse', '--short', 'HEAD'], cwd=root)}")
    print("git status --short --branch")
    print(_git_output(["status", "--short", "--branch"], cwd=root))
    print("git worktree list")
    print(_git_output(["worktree", "list"], cwd=root))
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    plan = resolve_worktree_plan(args.agent, args.task)
    print(worktree_prompt_header(plan.worktree_path))
    print()
    print(f"Agent: {args.agent}")
    print(f"Task: {args.task}")
    return 0


def cmd_attach(args: argparse.Namespace) -> int:
    try:
        attachment = inspect_attached_worktree(args.agent, args.task, Path(args.path))
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"agent: {attachment.agent}")
    print(f"task: {attachment.task}")
    print(f"path: {attachment.path}")
    print(f"branch: {attachment.branch}")
    print(f"expected_branch: {attachment.expected_branch}")
    print(f"branch_matches_convention: {str(attachment.branch_matches_convention).lower()}")
    print(f"HEAD: {attachment.head}")
    print(f"dirty: {str(attachment.dirty).lower()}")
    if attachment.dirty_files:
        print("dirty_files:")
        for line in attachment.dirty_files:
            print(f"  {line}")
    if not attachment.branch_matches_convention:
        print("Branch does not match convention. Do not rename while dirty. Consider rename-branch later when clean.")
    print()
    print(worktree_prompt_header(attachment.path))
    print()
    print(f"Agent: {attachment.agent}")
    print(f"Task: {attachment.task}")
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    try:
        include = tuple(getattr(args, "include", None) or ())
        exclude = tuple(getattr(args, "exclude", None) or ())
        plan = build_checkpoint_plan(
            args.agent,
            args.task,
            Path(args.path),
            args.message,
            include=include,
            exclude=exclude,
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"agent: {plan.agent}")
    print(f"task: {plan.task}")
    print(f"path: {plan.path}")
    print(f"branch: {plan.branch}")
    print(f"HEAD: {plan.head}")
    print("dirty_files:")
    for line in plan.dirty_files:
        print(f"  {line}")
    if plan.excluded_files:
        print("excluded_files:")
        for line in plan.excluded_files:
            print(f"  {line}")
    print(f"proposed_commit_message: {plan.message}")
    print("files_to_stage:")
    for item in plan.files_to_stage:
        print(f"  {item}")
    if args.dry_run:
        print()
        print(f"DRY RUN: git -C {plan.path} add -- { ' '.join(plan.files_to_stage) }")
        print(f"DRY RUN: git -C {plan.path} commit -m {plan.message!r}")
        return 0
    result = _run_git(["-C", str(plan.path), "add", "--", *plan.files_to_stage], cwd=plan.path)
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip() or "git add failed", file=sys.stderr)
        return result.returncode or 1
    result = _run_git(["-C", str(plan.path), "commit", "-m", plan.message], cwd=plan.path)
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip() or "git commit failed", file=sys.stderr)
        return result.returncode or 1
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    plan = resolve_worktree_plan(args.agent, args.task)
    if not plan.worktree_path.exists():
        print(f"Refusing to remove worktree: path does not exist: {plan.worktree_path}", file=sys.stderr)
        return 1
    result = _run_git(["-C", str(plan.worktree_path), "status", "--short"], cwd=plan.repo_root)
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip() or "git status failed", file=sys.stderr)
        return result.returncode or 1
    dirty = [line for line in result.stdout.splitlines() if line.strip()]
    if dirty:
        print(f"Refusing to remove dirty worktree: {plan.worktree_path}", file=sys.stderr)
        print("Dirty files:", file=sys.stderr)
        for line in dirty:
            print(line, file=sys.stderr)
        return 1
    command = ["git", "worktree", "remove", str(plan.worktree_path)]
    if args.dry_run:
        print("DRY RUN:", " ".join(command))
        return 0
    result = _run_git(command, cwd=plan.repo_root)
    if result.returncode != 0:
        print(result.stderr.strip() or result.stdout.strip() or "git worktree remove failed", file=sys.stderr)
        return result.returncode or 1
    print(f"removed worktree: {plan.worktree_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Safe per-agent Git worktree helper.")
    parser.add_argument("--dry-run", action="store_true", help="print mutating commands without running them")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("start", "prompt", "remove"):
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("agent")
        command_parser.add_argument("task")

    attach_parser = subparsers.add_parser("attach")
    attach_parser.add_argument("agent")
    attach_parser.add_argument("task")
    attach_parser.add_argument("--path", required=True)

    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_parser.add_argument("agent")
    checkpoint_parser.add_argument("task")
    checkpoint_parser.add_argument("--path", required=True)
    checkpoint_parser.add_argument("--message", required=True)
    checkpoint_parser.add_argument("--include", action="append")
    checkpoint_parser.add_argument("--exclude", action="append")
    checkpoint_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("list")
    subparsers.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "start": cmd_start,
        "list": cmd_list,
        "status": cmd_status,
        "prompt": cmd_prompt,
        "remove": cmd_remove,
        "attach": cmd_attach,
        "checkpoint": cmd_checkpoint,
    }
    try:
        return handlers[args.command](args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
