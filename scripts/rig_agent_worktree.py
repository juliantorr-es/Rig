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


@dataclass(frozen=True)
class ReviewReport:
    agent: str
    task: str
    path: Path
    branch: str
    expected_branch: str
    branch_matches_convention: bool
    base: str
    head: str
    dirty: bool
    dirty_files: tuple[str, ...]
    ahead: int
    behind: int
    changed_files: tuple[str, ...]
    commits: tuple[str, ...]
    ready_for_review: bool
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    next_actions: tuple[str, ...]


@dataclass(frozen=True)
class PromoteReport:
    agent: str
    task: str
    path: Path
    source_branch: str
    expected_branch: str
    branch_matches_convention: bool
    head: str
    base: str
    target: str
    strategy: str
    dirty: bool
    dirty_files: tuple[str, ...]
    ahead: int
    behind: int
    commits: tuple[str, ...]
    changed_files: tuple[str, ...]
    required_validations: tuple[str, ...]
    planned_operations: tuple[str, ...]
    future_commands: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    dry_run: bool
    would_mutate: bool
    ready_to_promote: bool


@dataclass(frozen=True)
class RecommendationReport:
    agent: str
    task: str
    path: Path
    base: str
    target: str
    source_branch: str
    expected_branch: str
    branch_matches_convention: bool
    head: str
    dirty: bool
    ahead: int
    behind: int
    changed_files: tuple[str, ...]
    commits: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    preferred_path: str
    recommended_path: str
    ready: bool
    rationale: str
    future_commands: tuple[str, ...]
    validations_to_run: tuple[str, ...]
    dry_run: bool
    would_mutate: bool
    next_safe_action: str


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


def build_review_report(
    agent: str,
    task: str,
    path: Path,
    *,
    base: str = DEFAULT_BASE,
    repo_root: Path | None = None,
) -> ReviewReport:
    attachment = inspect_attached_worktree(agent, task, path, repo_root=repo_root)
    blockers: list[str] = []
    warnings: list[str] = []
    ready_for_review = False
    ahead = 0
    behind = 0
    changed_files: tuple[str, ...] = tuple()
    commits: tuple[str, ...] = tuple()

    if attachment.branch == "main":
        blockers.append("branch is main")

    try:
        base_result = _run_git(["rev-parse", "--verify", base], cwd=attachment.path)
        if base_result.returncode != 0:
            raise RuntimeError(base_result.stderr.strip() or base_result.stdout.strip() or f"unable to resolve base ref: {base}")
    except RuntimeError as exc:
        blockers.append(str(exc))
        return ReviewReport(
            agent=attachment.agent,
            task=attachment.task,
            path=attachment.path,
            branch=attachment.branch,
            expected_branch=attachment.expected_branch,
            branch_matches_convention=attachment.branch_matches_convention,
            base=base,
            head=attachment.head,
            dirty=attachment.dirty,
            dirty_files=attachment.dirty_files,
            ahead=ahead,
            behind=behind,
            changed_files=changed_files,
            commits=commits,
            ready_for_review=False,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            next_actions=("resolve base ref", "re-run review"),
        )

    counts = _run_git(["rev-list", "--left-right", "--count", f"{base}...HEAD"], cwd=attachment.path)
    if counts.returncode != 0:
        blockers.append(counts.stderr.strip() or counts.stdout.strip() or "git rev-list failed")
    else:
        left_right = counts.stdout.strip().split()
        if len(left_right) == 2:
            behind = int(left_right[0])
            ahead = int(left_right[1])
        else:
            blockers.append("unable to parse ahead/behind counts")

    diff = _run_git(["diff", "--name-status", f"{base}...HEAD"], cwd=attachment.path)
    if diff.returncode != 0:
        blockers.append(diff.stderr.strip() or diff.stdout.strip() or "git diff failed")
    else:
        changed_files = tuple(line.strip() for line in diff.stdout.splitlines() if line.strip())

    log = _run_git(["log", "--oneline", "--decorate", f"{base}..HEAD"], cwd=attachment.path)
    if log.returncode != 0:
        blockers.append(log.stderr.strip() or log.stdout.strip() or "git log failed")
    else:
        commits = tuple(line.strip() for line in log.stdout.splitlines() if line.strip())

    if attachment.dirty:
        blockers.append("worktree is dirty")
    if not attachment.branch_matches_convention:
        warnings.append("branch does not match preferred agent convention")
    if behind > 0:
        warnings.append("lane is behind base")
    if ahead <= 0:
        blockers.append("lane has no commits ahead of base")
    if not blockers:
        ready_for_review = attachment.branch != "main" and not attachment.dirty and ahead > 0

    next_actions = (
        "review diff",
        "promote to sprint branch or human review path",
    )
    return ReviewReport(
        agent=attachment.agent,
        task=attachment.task,
        path=attachment.path,
        branch=attachment.branch,
        expected_branch=attachment.expected_branch,
        branch_matches_convention=attachment.branch_matches_convention,
        base=base,
        head=attachment.head,
        dirty=attachment.dirty,
        dirty_files=attachment.dirty_files,
        ahead=ahead,
        behind=behind,
        changed_files=changed_files,
        commits=commits,
        ready_for_review=ready_for_review,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        next_actions=next_actions,
    )


def _resolve_target_branch(task: str, target: str | None) -> str:
    if target is not None:
        target = target.strip()
        if not target:
            raise ValueError("Target branch must be non-empty.")
        return target
    return f"sprint/{task}"


def required_validation_commands() -> tuple[str, ...]:
    return (
        "python3.14 -m compileall -q scripts tests",
        "python3.14 -m pytest tests/test_rig_agent_worktree.py -v",
        "python3.14 -m compileall -q src tests",
        "python3.14 -m pytest tests/test_ui_repo_selection.py -v",
        "python3.14 -m pytest tests/test_ui_intent_contract.py -v",
        "python3.14 -m pytest tests/test_ui_frontend_logic.py -v",
        "python3.14 -m rig ui --help",
        "python3.14 -m rig window open --dry-run",
    )


def _promotion_future_commands(
    report: ReviewReport,
    *,
    target: str,
    strategy: str,
) -> tuple[str, ...]:
    if strategy == "pr":
        return (
            f"gh pr create --base {target} --head {report.branch} --title \"{report.task}: {report.agent} lane\" --body \"Promote {report.agent} {report.task} lane\"",
        )
    if strategy == "squash":
        return (
            f"rig agent lane promote {report.agent} {report.task} --strategy squash --target {target} --dry-run",
        )
    if strategy == "cherry-pick":
        return (
            f"rig agent lane promote {report.agent} {report.task} --strategy cherry-pick --target {target} --dry-run",
        )
    return (
        f"python scripts/rig_agent_worktree.py review {report.agent} {report.task} --path {report.path}",
        f"python scripts/rig_agent_worktree.py promote {report.agent} {report.task} --path {report.path} --strategy manual --dry-run",
        f"git diff {report.base}...HEAD",
    )


def _infer_recommendation_path(
    report: ReviewReport,
    *,
    target_exists: bool,
    prefer: str,
) -> tuple[str, bool, str]:
    if prefer == "hold":
        return "hold", False, "user requested hold"
    if report.blockers:
        return "hold", False, "blockers must be resolved before promotion"
    if prefer in {"pr", "squash", "cherry-pick"}:
        if prefer == "cherry-pick" and len(report.commits) > 3:
            return "review", True, "lane is promotable but has enough commits that human review is safer"
        if prefer == "pr":
            return "pr", True, "user prefers PR flow and the lane is clean and review-ready"
        if prefer == "squash":
            return "squash", True, "user prefers squash promotion and the lane is clean and review-ready"
        return "cherry-pick", True, "user prefers cherry-pick and the lane has a small commit count"
    if report.branch_matches_convention and target_exists and report.behind == 0:
        return "review", True, "lane is clean and review-ready, but default policy is human review before mutation"
    return "review", True, "lane is clean and review-ready; human review remains the safest next path"


def build_promote_report(
    agent: str,
    task: str,
    path: Path,
    *,
    base: str = DEFAULT_BASE,
    target: str | None = None,
    strategy: str = "manual",
    dry_run: bool = False,
    repo_root: Path | None = None,
) -> PromoteReport:
    if not dry_run:
        raise ValueError("Promotion planner requires --dry-run for now.")

    strategy = strategy.strip().lower()
    if strategy not in {"manual", "pr", "squash", "cherry-pick"}:
        raise ValueError(f"Unknown promotion strategy: {strategy}")

    attachment = inspect_attached_worktree(agent, task, path, repo_root=repo_root)
    review = build_review_report(agent, task, path, base=base, repo_root=repo_root)
    target_branch = _resolve_target_branch(task, target)
    blockers = list(review.blockers)
    warnings = list(review.warnings)
    required_validations = required_validation_commands()

    if attachment.branch == "main":
        blockers.append("branch is main")
    if review.dirty:
        blockers.append("worktree is dirty")
    if review.ahead <= 0:
        blockers.append("lane has no commits ahead of base")
    if not review.branch_matches_convention:
        warnings.append("branch does not match preferred agent convention")
    if review.behind > 0:
        warnings.append("lane is behind base")

    target_exists = _run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}"], cwd=attachment.path)
    if target_exists.returncode != 0:
        warnings.append("target branch does not exist yet")
    elif target_branch != base:
        warnings.append("target branch already exists")
    if target_branch == attachment.branch:
        blockers.append("target branch equals source branch")
    if target_branch == "main":
        warnings.append("target branch is main; promotion should stay in human review / PR path")
    if strategy == "pr" and target_branch == "main":
        warnings.append("PR flow to main will require protected-branch review and may prompt a push later")
    if strategy == "pr":
        planned_operations = (
            f"plan future PR from {attachment.branch} into {target_branch}",
            f"future: gh pr create --base {target_branch} --head {attachment.branch} --title \"{task}: {agent} lane\" --body \"Promote {agent} {task} lane\"",
        )
        future_commands = (
            f"gh pr create --base {target_branch} --head {attachment.branch} --title \"{task}: {agent} lane\" --body \"Promote {agent} {task} lane\"",
        )
    elif strategy == "squash":
        planned_operations = (
            f"plan future squash promotion into {target_branch}",
            f"source commits: {base}..HEAD",
            f"file list: {base}...HEAD",
        )
        future_commands = (
            f"git checkout -b {target_branch}",
            f"git merge --squash {attachment.branch}",
            f"git commit -m \"{task}: {agent} lane\"",
        )
    elif strategy == "cherry-pick":
        planned_operations = (
            f"plan future cherry-pick promotion into {target_branch}",
            f"source commits: {base}..HEAD",
        )
        future_commands = tuple(f"git cherry-pick {commit.split()[0]}" for commit in review.commits) or ("git cherry-pick <commit>",)
    else:
        planned_operations = (
            "review diff first",
            f"plan human promotion path toward {target_branch}",
        )
        future_commands = (
            f"review diff {base}...HEAD",
            f"prepare human promotion path toward {target_branch}",
        )

    changed_files = review.changed_files
    if strategy == "squash":
        planned_operations = planned_operations + (f"apply diff from {base}...HEAD to {target_branch}", "create one squash commit")
    elif strategy == "cherry-pick":
        planned_operations = planned_operations + ("apply commits one by one",)

    if target_branch == "main" and strategy not in {"pr", "manual"}:
        warnings.append("target branch is main; human review or PR is still required")

    ready_to_promote = bool(
        strategy in {"manual", "pr", "squash", "cherry-pick"}
        and not blockers
        and review.ready_for_review
    )
    if strategy == "manual":
        future_commands = future_commands + ("review diff",)

    blockers_tuple = tuple(dict.fromkeys(blockers))
    warnings_tuple = tuple(dict.fromkeys(warnings))

    return PromoteReport(
        agent=attachment.agent,
        task=attachment.task,
        path=attachment.path,
        source_branch=attachment.branch,
        expected_branch=attachment.expected_branch,
        branch_matches_convention=attachment.branch_matches_convention,
        head=attachment.head,
        base=base,
        target=target_branch,
        strategy=strategy,
        dirty=review.dirty,
        dirty_files=review.dirty_files,
        ahead=review.ahead,
        behind=review.behind,
        commits=review.commits,
        changed_files=changed_files,
        required_validations=required_validations,
        planned_operations=planned_operations,
        future_commands=future_commands,
        blockers=blockers_tuple,
        warnings=warnings_tuple,
        dry_run=True,
        would_mutate=False,
        ready_to_promote=ready_to_promote,
    )


def build_recommendation_report(
    agent: str,
    task: str,
    path: Path,
    *,
    base: str = DEFAULT_BASE,
    target: str | None = None,
    prefer: str = "review",
    repo_root: Path | None = None,
) -> RecommendationReport:
    review = build_review_report(agent, task, path, base=base, repo_root=repo_root)
    target_branch = _resolve_target_branch(task, target)
    prefer = prefer.strip().lower()
    known_preference = prefer in {"review", "pr", "squash", "cherry-pick", "hold"}
    if not known_preference:
        prefer = "hold"
    warnings = list(review.warnings)
    target_exists = _run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}"], cwd=review.path).returncode == 0
    if not target_exists:
        warnings.append("target branch does not exist yet")
    recommended_path, ready, rationale = _infer_recommendation_path(
        review,
        target_exists=target_exists,
        prefer=prefer,
    )
    if not known_preference:
        rationale = "preference was invalid; holding until the user supplies a known next path"
    elif prefer == "hold":
        ready = False
        rationale = "user explicitly requested hold"

    if recommended_path == "hold":
        future_commands = (
            "resolve blockers",
            f"python scripts/rig_agent_worktree.py review {agent} {task} --path {path}",
        )
        next_safe_action = "resolve blockers before re-running review"
    elif recommended_path == "review":
        future_commands = _promotion_future_commands(review, target=target_branch, strategy="manual")
        next_safe_action = "review diff / inspect cockpit manually / decide promotion path"
    else:
        future_commands = _promotion_future_commands(review, target=target_branch, strategy=recommended_path)
        if recommended_path == "pr":
            next_safe_action = "prepare a future PR path; do not run gh yet"
            warnings.append("gh pr create may prompt to push; do not invoke it during recommendation")
        elif recommended_path == "squash":
            next_safe_action = "prepare a future squash promotion path"
        else:
            next_safe_action = "prepare a future cherry-pick promotion path"

    return RecommendationReport(
        agent=review.agent,
        task=review.task,
        path=review.path,
        base=review.base,
        target=target_branch,
        source_branch=review.branch,
        expected_branch=review.expected_branch,
        branch_matches_convention=review.branch_matches_convention,
        head=review.head,
        dirty=review.dirty,
        ahead=review.ahead,
        behind=review.behind,
        changed_files=review.changed_files,
        commits=review.commits,
        blockers=review.blockers,
        warnings=tuple(dict.fromkeys(warnings)),
        preferred_path=prefer,
        recommended_path=recommended_path,
        ready=ready,
        rationale=rationale,
        future_commands=future_commands,
        validations_to_run=required_validation_commands(),
        dry_run=True,
        would_mutate=False,
        next_safe_action=next_safe_action,
    )


def cmd_recommend(args: argparse.Namespace) -> int:
    try:
        report = build_recommendation_report(
            args.agent,
            args.task,
            Path(args.path),
            base=getattr(args, "base", DEFAULT_BASE),
            target=getattr(args, "target", None),
            prefer=getattr(args, "prefer", "review"),
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"agent: {report.agent}")
    print(f"task: {report.task}")
    print(f"path: {report.path}")
    print(f"base: {report.base}")
    print(f"target: {report.target}")
    print(f"source_branch: {report.source_branch}")
    print(f"expected_branch: {report.expected_branch}")
    print(f"branch_matches_convention: {str(report.branch_matches_convention).lower()}")
    print(f"head: {report.head}")
    print(f"dirty: {str(report.dirty).lower()}")
    print(f"ahead: {report.ahead}")
    print(f"behind: {report.behind}")
    print("changed_files:")
    for line in report.changed_files:
        print(f"  {line}")
    print("commits:")
    for line in report.commits:
        print(f"  {line}")
    print("blockers:")
    for line in report.blockers:
        print(f"  {line}")
    print("warnings:")
    for line in report.warnings:
        print(f"  {line}")
    print(f"preferred_path: {report.preferred_path}")
    print(f"recommended_path: {report.recommended_path}")
    print(f"ready: {str(report.ready).lower()}")
    print(f"rationale: {report.rationale}")
    print("future_commands:")
    for line in report.future_commands:
        print(f"  {line}")
    print("validations_to_run:")
    for line in report.validations_to_run:
        print(f"  {line}")
    print(f"dry_run: {str(report.dry_run).lower()}")
    print(f"would_mutate: {str(report.would_mutate).lower()}")
    print(f"next_safe_action: {report.next_safe_action}")
    return 0


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


def cmd_review(args: argparse.Namespace) -> int:
    try:
        report = build_review_report(
            args.agent,
            args.task,
            Path(args.path),
            base=getattr(args, "base", DEFAULT_BASE),
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"agent: {report.agent}")
    print(f"task: {report.task}")
    print(f"path: {report.path}")
    print(f"branch: {report.branch}")
    print(f"expected_branch: {report.expected_branch}")
    print(f"branch_matches_convention: {str(report.branch_matches_convention).lower()}")
    print(f"base: {report.base}")
    print(f"head: {report.head}")
    print(f"dirty: {str(report.dirty).lower()}")
    print(f"ahead: {report.ahead}")
    print(f"behind: {report.behind}")
    print("changed_files:")
    for line in report.changed_files:
        print(f"  {line}")
    print("commits:")
    for line in report.commits:
        print(f"  {line}")
    print(f"ready_for_review: {str(report.ready_for_review).lower()}")
    print("blockers:")
    for line in report.blockers:
        print(f"  {line}")
    print("warnings:")
    for line in report.warnings:
        print(f"  {line}")
    print("next_actions:")
    for line in report.next_actions:
        print(f"  {line}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    if not getattr(args, "dry_run", False):
        print("Promotion planner requires --dry-run for now.", file=sys.stderr)
        return 1
    try:
        report = build_promote_report(
            args.agent,
            args.task,
            Path(args.path),
            base=getattr(args, "base", DEFAULT_BASE),
            target=getattr(args, "target", None),
            strategy=getattr(args, "strategy", "manual"),
            dry_run=True,
        )
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"agent: {report.agent}")
    print(f"task: {report.task}")
    print(f"path: {report.path}")
    print(f"source_branch: {report.source_branch}")
    print(f"expected_branch: {report.expected_branch}")
    print(f"branch_matches_convention: {str(report.branch_matches_convention).lower()}")
    print(f"head: {report.head}")
    print(f"base: {report.base}")
    print(f"target: {report.target}")
    print(f"strategy: {report.strategy}")
    print(f"dirty: {str(report.dirty).lower()}")
    print(f"ahead: {report.ahead}")
    print(f"behind: {report.behind}")
    print("commits:")
    for line in report.commits:
        print(f"  {line}")
    print("changed_files:")
    for line in report.changed_files:
        print(f"  {line}")
    print("required_validations:")
    for line in report.required_validations:
        print(f"  {line}")
    print("planned_operations:")
    for line in report.planned_operations:
        print(f"  {line}")
    print("future_commands:")
    for line in report.future_commands:
        print(f"  {line}")
    print(f"blockers: {', '.join(report.blockers) if report.blockers else 'none'}")
    print(f"warnings: {', '.join(report.warnings) if report.warnings else 'none'}")
    print(f"dry_run: {str(report.dry_run).lower()}")
    print(f"would_mutate: {str(report.would_mutate).lower()}")
    print(f"ready_to_promote: {str(report.ready_to_promote).lower()}")
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

    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("agent")
    review_parser.add_argument("task")
    review_parser.add_argument("--path", required=True)
    review_parser.add_argument("--base", default=DEFAULT_BASE)

    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("agent")
    promote_parser.add_argument("task")
    promote_parser.add_argument("--path", required=True)
    promote_parser.add_argument("--base", default=DEFAULT_BASE)
    promote_parser.add_argument("--target")
    promote_parser.add_argument("--strategy", default="manual")
    promote_parser.add_argument("--dry-run", action="store_true")

    recommend_parser = subparsers.add_parser("recommend")
    recommend_parser.add_argument("agent")
    recommend_parser.add_argument("task")
    recommend_parser.add_argument("--path", required=True)
    recommend_parser.add_argument("--base", default=DEFAULT_BASE)
    recommend_parser.add_argument("--target")
    recommend_parser.add_argument("--prefer", default="review")

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
        "review": cmd_review,
        "promote": cmd_promote,
        "recommend": cmd_recommend,
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
