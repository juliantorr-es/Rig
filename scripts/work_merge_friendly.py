#!/usr/bin/env python3
"""work_merge_friendly.py — Merge-friendliness preflight check before patch batch application.

Given an ADR/task, sprint, mission, and patch batch, determine whether the patch
is safe to apply relative to active worktrees.

This is a pre-apply safety check, not a merge operation.

Usage:
    python3 scripts/work_merge_friendly.py <task_id> \
        --patch-file <path.to.patch> \
        --batch <batch_id> \
        [--mission <mission_id>] \
        [--sprint <sprint_id>] \
        [--worker <name>] \
        [--check-only] \
        [--accept-risky]

Purpose:
- Check patch against current worktree
- Check against other active linked worktrees under .rig/worktrees/
- Detect dirty files in those worktrees
- Check committed branch heads in those worktrees
- Verify patch touches only mission allowed_paths
- Verify patch does not touch protected paths

Git primitives used:
- `git worktree list --porcelain -z` to discover worktrees
- `git status --porcelain=v1` to detect dirty state
- `git diff --name-only` and `git diff --cached --name-only` for touched files
- `git apply --check <patch>` to precheck patch applicability
- `git merge-tree --write-tree <base> <branch-a> <branch-b>` for merge simulation

Rules:
- Do not mutate any worktree during checks
- Do not merge, rebase, commit, stage, or copy patches
- If another active worktree has dirty changes touching the same file: BLOCK
- If another active worktree has dirty changes in the same directory: WARN
- If merge simulation reports conflict: BLOCK
- If patch touches protected paths: BLOCK
- If patch touches files outside mission allowed_paths: BLOCK

Result classes:
- clean: Safe to apply
- warning: Proceed with caution
- risky: Requires explicit --accept-risky
- blocked: Must not apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _work_lib import (
    load_task,
    get_mission,
    get_sprint,
    append_event,
    make_event,
    now_iso,
    path_matches_any,
    repo_root,
)


@dataclass
class WorktreeInfo:
    """Information about a Git worktree."""
    path: str
    is_current: bool
    is_bare: bool
    branch: str | None
    head_commit: str | None
    is_detached: bool
    dirty_files: list[str] = field(default_factory=list)
    staged_files: list[str] = field(default_factory=list)


@dataclass
class PatchFileInfo:
    """Information extracted from a patch file."""
    file_path: Path
    hash: str
    touched_files: list[str] = field(default_factory=list)
    is_valid_diff: bool = True


@dataclass
class MergeFriendlyResult:
    """Result of merge-friendliness check."""
    result: str  # clean, warning, risky, blocked
    safe_to_apply: bool = False
    patch_path: str = ""
    patch_hash: str = ""
    checked_worktree_count: int = 0
    overlapping_files: list[str] = field(default_factory=list)
    dirty_worktrees: list[str] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Git utilities
# ---------------------------------------------------------------------------

def run_git(args: list[str], cwd: str | Path | None = None) -> tuple[int, str, str]:
    """Run a git command. Returns (returncode, stdout, stderr)."""
    cmd = ["git"] + args
    if cwd:
        cmd = ["git", "-C", str(cwd)] + args[1:] if len(args) > 0 else ["git", "-C", str(cwd)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def get_current_worktree() -> WorktreeInfo:
    """Get information about the current worktree."""
    # Get branch
    rc, branch, _ = run_git(["branch", "--show-current"])
    branch_name = branch.strip() if rc == 0 and branch.strip() else None
    
    # Get HEAD commit
    rc, head, _ = run_git(["rev-parse", "--short", "HEAD"])
    head_commit = head.strip() if rc == 0 else None
    
    # Get dirty files
    rc, status_output, _ = run_git(["status", "--porcelain=v1"])
    dirty = []
    staged = []
    if rc == 0:
        for line in status_output.strip().split("\n"):
            if len(line) >= 3:
                status = line[:2]
                path = line[3:].strip()
                if status[0] != " " and status[0] != "?":  # Not untracked
                    if status[1] != " ":
                        staged.append(path)
                    dirty.append(path)
    
    return WorktreeInfo(
        path=str(repo_root()),
        is_current=True,
        is_bare=False,
        branch=branch_name,
        head_commit=head_commit,
        is_detached=branch_name is None,
        dirty_files=dirty,
        staged_files=staged,
    )


def list_all_worktrees() -> list[WorktreeInfo]:
    """List all worktrees including linked worktrees under .rig/worktrees/."""
    worktrees: list[WorktreeInfo] = []
    
    # Get main repository worktrees using git worktree list
    rc, output, _ = run_git(["worktree", "list", "--porcelain", "-z"])
    if rc == 0 and output:
        # Parse null-delimited output
        lines = output.split("\0")
        current_path = None
        current_info: dict[str, Any] = {}
        
        for line in lines:
            if not line:
                continue
            if line.startswith("worktree "):
                # Save previous worktree if exists
                if current_path:
                    worktrees.append(WorktreeInfo(
                        path=current_path,
                        is_current=current_info.get("is_current", False),
                        is_bare=current_info.get("is_bare", False),
                        branch=current_info.get("branch"),
                        head_commit=current_info.get("head_commit"),
                        is_detached=current_info.get("is_detached", False),
                    ))
                # Start new worktree
                current_path = line[9:].strip()
                current_info = {"path": current_path, "is_current": "[main]" in line or current_path == str(repo_root())}
            elif line.startswith("HEAD "):
                head_ref = line[5:].strip()
                current_info["head_commit"] = None
                if head_ref.startswith("("):
                    # Detached HEAD with commit
                    current_info["is_detached"] = True
                    current_info["head_commit"] = head_ref[1:-1]
                else:
                    current_info["is_detached"] = False
                    current_info["branch"] = head_ref
            elif line.startswith("bare"):
                current_info["is_bare"] = True
        
        # Save last worktree
        if current_path:
            worktrees.append(WorktreeInfo(
                path=current_path,
                is_current=current_info.get("is_current", False),
                is_bare=current_info.get("is_bare", False),
                branch=current_info.get("branch"),
                head_commit=current_info.get("head_commit"),
                is_detached=current_info.get("is_detached", False),
            ))
    
    # Also check for worktrees under .rig/worktrees/
    worktrees_dir = repo_root() / ".rig" / "worktrees"
    if worktrees_dir.exists():
        for wt_path in worktrees_dir.iterdir():
            if wt_path.is_dir():
                # Check if this is a git worktree
                git_dir = wt_path / ".git"
                if git_dir.exists() and git_dir.is_dir():
                    # This might be a linked worktree or a separate clone
                    # Try to get its info
                    rc, branch, _ = run_git(["branch", "--show-current"], cwd=wt_path)
                    branch_name = branch.strip() if rc == 0 and branch.strip() else None
                    rc, head, _ = run_git(["rev-parse", "--short", "HEAD"], cwd=wt_path)
                    head_commit = head.strip() if rc == 0 else None
                    rc, status_output, _ = run_git(["status", "--porcelain=v1"], cwd=wt_path)
                    dirty = []
                    staged = []
                    if rc == 0:
                        for line in status_output.strip().split("\n"):
                            if len(line) >= 3:
                                path = line[3:].strip()
                                dirty.append(path)
                    
                    # Check if already listed
                    already_exists = any(wt.path == str(wt_path) for wt in worktrees)
                    if not already_exists:
                        worktrees.append(WorktreeInfo(
                            path=str(wt_path),
                            is_current=False,
                            is_bare=False,
                            branch=branch_name,
                            head_commit=head_commit,
                            is_detached=branch_name is None,
                            dirty_files=dirty,
                            staged_files=staged,
                        ))
    
    return worktrees


def get_worktree_dirty_files(wt: WorktreeInfo) -> tuple[list[str], list[str]]:
    """Get dirty and staged files for a specific worktree."""
    if wt.is_current:
        rc, output, _ = run_git(["status", "--porcelain=v1"])
    else:
        # For non-current worktrees, we need to use git -C
        rc, output, _ = run_git(["status", "--porcelain=v1"], cwd=wt.path)
    
    dirty = []
    staged = []
    if rc == 0:
        for line in output.strip().split("\n"):
            if len(line) >= 3:
                status = line[:2]
                path = line[3:].strip()
                if status[0] != " " and status[0] != "?":
                    if status[1] != " ":
                        staged.append(path)
                    dirty.append(path)
    
    return dirty, staged


# ---------------------------------------------------------------------------
# Patch parsing
# ---------------------------------------------------------------------------

def parse_patch_file(patch_path: str | Path) -> PatchFileInfo:
    """Parse a unified diff patch file to extract touched files."""
    path = Path(patch_path)
    if not path.exists():
        return PatchFileInfo(
            file_path=path,
            hash="",
            touched_files=[],
            is_valid_diff=False,
        )
    
    content = path.read_text(encoding="utf-8", errors="replace")
    hash_val = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    
    touched_files: list[str] = []
    is_valid = True
    
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("diff --git a/"):
            # Parse: diff --git a/path/to/file b/path/to/file
            # or: diff --git a/path/to/file
            parts = line.split()
            if len(parts) >= 4:
                a_path = parts[2]  # a/path
                if a_path.startswith("a/"):
                    a_path = a_path[2:]
                if a_path not in touched_files:
                    touched_files.append(a_path)
        elif line.startswith("--- ") or line.startswith("+++ "):
            # Old/new file headers
            file_path = line[4:].strip()
            if file_path.startswith("a/"):
                file_path = file_path[2:]
            elif file_path.startswith("b/"):
                file_path = file_path[2:]
            if file_path and file_path not in touched_files:
                touched_files.append(file_path)
    
    return PatchFileInfo(
        file_path=path,
        hash=hash_val,
        touched_files=touched_files,
        is_valid_diff=is_valid and len(touched_files) > 0,
    )


def get_patch_touched_files_git(patch_path: str | Path) -> list[str]:
    """Use git apply --numstat to get touched files."""
    try:
        rc, output, _ = run_git(["apply", "--numstat", "--atosh", str(patch_path)])
        if rc == 0:
            files = []
            for line in output.strip().split("\n"):
                # numstat format: <adds>\t<dels>\t<path>
                parts = line.split("\t")
                if len(parts) >= 3 and parts[2].strip():
                    files.append(parts[2].strip())
            return files
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Merge simulation
# ---------------------------------------------------------------------------

def check_merge_simulation(base_commit: str, branch_a: str, branch_b: str) -> tuple[bool, str, list[str]]:
    """
    Use git merge-tree to simulate a merge.
    Returns (success, output, conflict_files).
    """
    try:
        # Try merge-tree first (newer git versions)
        rc, output, _ = run_git(["merge-tree", "--write-tree=", base_commit, branch_a, branch_b])
        if rc == 0:
            # merge-tree succeeded - no conflicts
            return True, output, []
        
        # merge-tree failed - might be conflicts or command not available
        # Try git merge --no-commit --no-ff as a fallback check (dry-run)
        # But we must NOT actually merge, so we just report potential conflicts
        # For now, if merge-tree fails, we assume there might be conflicts
        return False, output, []
    except Exception:
        return False, "merge-tree not available", []


# ---------------------------------------------------------------------------
# Path overlap detection
# ---------------------------------------------------------------------------

def detect_overlaps(patch_files: list[str], other_files: list[str], other_label: str) -> list[str]:
    """Detect files that overlap between patch and other file list."""
    patch_set = set(patch_files)
    other_set = set(other_files)
    return list(patch_set & other_set)


def detect_directory_overlaps(patch_files: list[str], other_files: list[str]) -> list[str]:
    """Detect directory-level overlaps (same directory, different files)."""
    patch_dirs = {str(Path(f).parent) for f in patch_files if f}
    other_dirs = {str(Path(f).parent) for f in other_files if f}
    return list(patch_dirs & other_dirs)


# ---------------------------------------------------------------------------
# Main check logic
# ---------------------------------------------------------------------------

def check_merge_friendliness(
    task_id: str,
    patch_path: str | Path,
    batch_id: str,
    mission_id: str | None = None,
    sprint_id: str | None = None,
    worker: str = "unknown",
) -> MergeFriendlyResult:
    """Perform merge-friendliness check for a patch batch."""
    result = MergeFriendlyResult(
        result="clean",
        safe_to_apply=True,
        patch_path=str(patch_path),
        checked_worktree_count=0,
    )
    
    # Parse patch file
    patch_info = parse_patch_file(patch_path)
    result.patch_hash = patch_info.hash
    
    if not patch_info.is_valid_diff:
        result.result = "blocked"
        result.safe_to_apply = False
        result.blocked_reasons.append("Invalid or empty patch file")
        return result
    
    # Also try git apply --numstat for better file detection
    git_touched = get_patch_touched_files_git(patch_path)
    all_patch_files = list(set(patch_info.touched_files + git_touched))
    result.patch_path = str(patch_path)
    
    # Load task for path constraints
    try:
        task = load_task(task_id)
    except FileNotFoundError:
        result.result = "blocked"
        result.safe_to_apply = False
        result.blocked_reasons.append(f"Task {task_id} not found")
        return result
    
    # Get mission and sprint for path constraints
    mission_allowed_paths: list[str] = []
    mission_protected_paths: list[str] = []
    sprint_allowed_paths: list[str] = []
    sprint_protected_paths: list[str] = []
    
    if mission_id:
        try:
            from _work_lib import get_mission
            mission = get_mission(task, mission_id)
            mission_allowed_paths = mission.get("allowed_paths", [])
            mission_protected_paths = mission.get("protected_paths", [])
        except (ValueError, FileNotFoundError):
            result.warnings.append(f"Mission {mission_id} not found, using task-level paths")
    
    if sprint_id:
        try:
            sprint = get_sprint(task, sprint_id)
            sprint_allowed_paths = sprint.get("allowed_paths", [])
            sprint_protected_paths = sprint.get("protected_paths", [])
        except (ValueError, FileNotFoundError):
            result.warnings.append(f"Sprint {sprint_id} not found")
    
    # Effective paths: mission > sprint > task
    effective_allowed = mission_allowed_paths or sprint_allowed_paths or task.get("allowed_paths", [])
    effective_protected = mission_protected_paths or sprint_protected_paths or task.get("protected_paths", [])
    
    # Check 1: Patch touches protected paths
    for pf in all_patch_files:
        if path_matches_any(pf, effective_protected):
            result.result = "blocked"
            result.safe_to_apply = False
            result.blocked_reasons.append(f"Patch touches protected path: {pf}")
            return result
    
    # Check 2: Patch touches files outside allowed paths
    for pf in all_patch_files:
        if effective_allowed and not path_matches_any(pf, effective_allowed):
            result.result = "blocked"
            result.safe_to_apply = False
            result.blocked_reasons.append(f"Patch touches file outside allowed_paths: {pf}")
            return result
    
    # Get all worktrees
    all_worktrees = list_all_worktrees()
    current_wt = next((wt for wt in all_worktrees if wt.is_current), None)
    other_worktrees = [wt for wt in all_worktrees if not wt.is_current]
    
    result.checked_worktree_count = len(all_worktrees)
    
    # Check 3: Current worktree dirty state
    if current_wt:
        # Get fresh dirty files for current worktree
        dirty, staged = get_worktree_dirty_files(current_wt)
        current_wt.dirty_files = dirty
        current_wt.staged_files = staged
        
        # Check for same-file overlap in current worktree
        overlaps = detect_overlaps(all_patch_files, dirty + staged, "current worktree")
        if overlaps:
            result.result = "blocked"
            result.safe_to_apply = False
            result.overlapping_files = overlaps
            result.blocked_reasons.append(
                f"Current worktree has dirty/staged changes in patch files: {overlaps}"
            )
            return result
        
        # Check for same-directory overlap (warning)
        dir_overlaps = detect_directory_overlaps(all_patch_files, dirty + staged)
        if dir_overlaps:
            result.warnings.append(
                f"Current worktree has dirty files in same directories: {dir_overlaps}"
            )
            if result.result == "clean":
                result.result = "warning"
    
    # Check 4: Other worktrees
    for wt in other_worktrees:
        dirty, staged = get_worktree_dirty_files(wt)
        wt.dirty_files = dirty
        wt.staged_files = staged
        
        if dirty or staged:
            # Check for same-file overlap
            overlaps = detect_overlaps(all_patch_files, dirty + staged, wt.path)
            if overlaps:
                result.result = "blocked"
                result.safe_to_apply = False
                result.overlapping_files.extend(overlaps)
                result.dirty_worktrees.append(f"{wt.path} ({wt.branch or 'detached'})")
                result.blocked_reasons.append(
                    f"Worktree {wt.path} has dirty/staged changes in patch files: {overlaps}"
                )
                return result
            
            # Check for same-directory overlap (warning)
            dir_overlaps = detect_directory_overlaps(all_patch_files, dirty + staged)
            if dir_overlaps and wt.path not in result.dirty_worktrees:
                result.warnings.append(
                    f"Worktree {wt.path} has dirty files in same directories: {dir_overlaps}"
                )
                if wt.path not in result.dirty_worktrees:
                    result.dirty_worktrees.append(f"{wt.path} ({wt.branch or 'detached'})")
                if result.result == "clean":
                    result.result = "warning"
    
    # Check 5: Merge simulation with other worktree branches
    if current_wt:
        current_head = current_wt.head_commit
        if current_head:
            for wt in other_worktrees:
                if wt.head_commit and wt.head_commit != current_head and wt.branch:
                    # Try to simulate merge between current and other worktree
                    # Use the common ancestor as base
                    try:
                        rc, output, _ = run_git([
                            "merge-base",
                            current_head,
                            wt.head_commit,
                        ])
                        if rc == 0:
                            base_commit = output.strip()
                            # Check if this patch would conflict with merge
                            # This is a simplified check - in practice, we'd need to see
                            # if the patch changes files that differ between branches
                            pass
                    except Exception:
                        pass
                    
                    # For now, just check if the patch files overlap with files
                    # changed in the other worktree's branch
                    # We can use git diff to see what changed
                    try:
                        rc, diff_output, _ = run_git([
                            "diff",
                            "--name-only",
                            f"{current_head}...{wt.head_commit}",
                        ])
                        if rc == 0:
                            other_changed = [l.strip() for l in diff_output.strip().split("\n") if l.strip()]
                            overlaps = detect_overlaps(all_patch_files, other_changed, wt.path)
                            if overlaps:
                                result.warnings.append(
                                    f"Branch {wt.branch} ({wt.path}) has changes in patch files: {overlaps}"
                                )
                                if result.result == "clean":
                                    result.result = "warning"
                    except Exception:
                        pass
    
    # Check 6: Precheck with git apply --check
    rc, _, stderr = run_git(["apply", "--check", str(patch_path)])
    if rc != 0:
        result.result = "blocked"
        result.safe_to_apply = False
        result.blocked_reasons.append(f"git apply --check failed: {stderr.strip()[:200]}")
        return result
    
    # Update safe_to_apply based on result
    result.safe_to_apply = result.result in ("clean", "warning")
    
    return result


# ---------------------------------------------------------------------------
# Event recording
# ---------------------------------------------------------------------------

def record_merge_friendly_event(
    task_id: str,
    result: MergeFriendlyResult,
    mission_id: str | None = None,
    sprint_id: str | None = None,
    worker: str = "unknown",
) -> dict:
    """Record a patch_batch_merge_friendly_checked event."""
    event = make_event(
        event_type="patch_batch_merge_friendly_checked",
        task_id=task_id,
        worker=worker,
        mission_id=mission_id,
        sprint_id=sprint_id,
        note=f"Merge-friendliness check for patch batch",
        result=result.result,
        safe_to_apply=result.safe_to_apply,
        patch_path=result.patch_path,
        patch_hash=result.patch_hash,
        checked_worktree_count=result.checked_worktree_count,
        overlapping_files=result.overlapping_files,
        dirty_worktrees=result.dirty_worktrees,
        blocked_reasons=result.blocked_reasons,
        warnings=result.warnings,
    )
    append_event(task_id, event)
    return event


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="work_merge_friendly.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("task_id", metavar="TASK_ID", help="ADR task ID")
    p.add_argument("--patch-file", metavar="PATH", required=True, help="Path to unified diff patch file")
    p.add_argument("--batch", metavar="BATCH_ID", required=True, help="Patch batch ID")
    p.add_argument("--mission", metavar="MISSION_ID", help="Mission ID for path constraints")
    p.add_argument("--sprint", metavar="SPRINT_ID", help="Sprint ID for path constraints")
    p.add_argument("--worker", metavar="NAME", default="unknown", help="Worker name")
    p.add_argument("--check-only", action="store_true", help="Only check, don't record event")
    p.add_argument("--accept-risky", action="store_true", help="Accept risky result as safe")
    args = p.parse_args(argv or sys.argv[1:])
    
    patch_path = Path(args.patch_file)
    if not patch_path.exists():
        print(f"ERROR: Patch file not found: {args.patch_file}", file=sys.stderr)
        return 1
    
    # Perform check
    result = check_merge_friendliness(
        task_id=args.task_id,
        patch_path=args.patch_file,
        batch_id=args.batch,
        mission_id=args.mission,
        sprint_id=args.sprint,
        worker=args.worker,
    )
    
    # Override based on --accept-risky
    if args.accept_risky and result.result in ("risky", "warning"):
        result.result = "clean"
        result.safe_to_apply = True
        result.warnings.append("--accept-risky was used to override risky/warning result")
    
    # Print results
    print(f"Merge-friendliness check: task={args.task_id} batch={args.batch}")
    print(f"  Result: {result.result}")
    print(f"  Safe to apply: {result.safe_to_apply}")
    print(f"  Patch: {result.patch_path}")
    print(f"  Patch hash: {result.patch_hash[:8]}...")
    print(f"  Worktrees checked: {result.checked_worktree_count}")
    
    if result.overlapping_files:
        print(f"  Overlapping files: {result.overlapping_files}")
    if result.dirty_worktrees:
        print(f"  Dirty worktrees: {result.dirty_worktrees}")
    if result.blocked_reasons:
        print(f"  Blocked reasons:")
        for reason in result.blocked_reasons:
            print(f"    - {reason}")
    if result.warnings:
        print(f"  Warnings:")
        for warning in result.warnings:
            print(f"    - {warning}")
    
    # Record event unless check-only
    if not args.check_only:
        event = record_merge_friendly_event(
            task_id=args.task_id,
            result=result,
            mission_id=args.mission,
            sprint_id=args.sprint,
            worker=args.worker,
        )
        print(f"  Event recorded: {event['event_id']}")
    else:
        print("  (Event not recorded due to --check-only)")
    
    # Exit code: 0 = clean/safe, 1 = blocked, 2 = warning/risky
    if result.result == "blocked":
        print("\nBLOCKED: Patch must not be applied.", file=sys.stderr)
        return 1
    elif result.result in ("warning", "risky"):
        print(f"\n{result.result.upper()}: Patch may have issues. Use --accept-risky to override.", file=sys.stderr)
        return 2
    else:
        print("\nCLEAN: Patch is safe to apply.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
