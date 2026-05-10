#!/usr/bin/env python3
"""worktree_normalize.py — Normalize linked Git worktrees under .rig/worktrees/

Purpose
-------
Move Rig-owned Git worktrees that currently live as siblings of the main
repository root into the canonical location:

    <repo_root>/.rig/worktrees/<basename>

Candidate set is determined *solely* by ``git worktree list --porcelain``.
No arbitrary sibling directory is ever touched.

Usage
-----
    # Inspect what would move (no mutations):
    python scripts/worktree_normalize.py --dry-run --worker <name>

    # Apply moves (mutates Git metadata):
    python scripts/worktree_normalize.py --apply --worker <name>

Flags
-----
    --dry-run           (default) Report candidates; mutate nothing; append no events.
    --apply             Actually move worktrees; append events.
    --worker NAME       Required. Name/slug of the calling agent or user.
    --include-locked    Include locked worktrees (default: skip with blocked event).
    --allow-dirty       Move worktrees with uncommitted changes (default: refuse).
    --allow-submodules  Move worktrees that contain submodules (default: refuse).
    --rename-conflicts  If dest basename already exists, suffix with -2, -3, …
                        (default: refuse on conflict).

Events
------
Appended to: <repo_root>/.rig/work/events/worktree-normalize.jsonl  (local, gitignored)
Schema:      docs/schemas/work-stream-event.schema.json              (tracked)
Types:       worktree_moved, worktree_move_blocked

Durability
----------
This file (scripts/worktree_normalize.py) is the canonical tracked implementation.
.rig/work/scripts/worktree_normalize.py is an optional local wrapper that delegates here.
.rig/work/events/ and .rig/worktrees/ are local runtime state and are gitignored.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Known legacy/ambiguous worktree names that should be migrated
LEGACY_WORKTREE_NAMES = frozenset({
    "rig-consolidation",
    "rig-main-merge",
    "ui-cockpit",
})

# Reserved worktree names that must not be used for ADR implementation
RESERVED_WORKTREE_NAMES = frozenset({"preproduction", "main"})


# ---------------------------------------------------------------------------
# Canonical slug helpers (shared with _work_lib.py logic)
# ---------------------------------------------------------------------------

def _canonical_slug(text: str) -> str:
    """Derive canonical slug from text (same logic as scripts/_work_lib.py)."""
    if not text:
        return ""
    text = text.lower()
    text = text.strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    text = text.strip('-')
    return text


def _is_reserved_worktree_name(name: str) -> bool:
    """Check if a worktree basename is reserved."""
    return _canonical_slug(name) in RESERVED_WORKTREE_NAMES


def _is_legacy_worktree_name(name: str) -> bool:
    """Check if a worktree basename is a known legacy name."""
    return _canonical_slug(name) in {_canonical_slug(n) for n in LEGACY_WORKTREE_NAMES}


def _propose_canonical_name(legacy_name: str, branch: str) -> str | None:
    """Propose a canonical name for a legacy worktree based on its branch.
    
    Returns None if no clear mapping can be determined.
    """
    legacy_slug = _canonical_slug(legacy_name)
    
    # If already canonical, no proposal
    if not _is_legacy_worktree_name(legacy_name):
        return None
    
    # If legacy name is preproduction, it maps to reserved name
    if legacy_slug == "rig-consolidation":
        return "preproduction"
    
    # Try to extract ADR info from branch using patterns
    branch_lower = branch.lower()
    
    # Pattern: sprint/adrNNNN-title or agent/adrNNNN-mission or promotion/adrNNNN-title
    adr_pattern = re.search(r'(?:sprint|agent|promotion)/adr(\d{4})[-_](.+)', branch_lower)
    if adr_pattern:
        adr_id = f"adr{adr_pattern.group(1)}"
        title_part = adr_pattern.group(2)
        title_slug = re.sub(r'[^a-z0-9]+', '-', title_part).strip('-')
        return f"{adr_id}-{title_slug}"
    
    # Pattern: sprint/NNNN-title or agent/NNNN-mission  
    adr_pattern2 = re.search(r'(?:sprint|agent|promotion)/(\d{4})[-_](.+)', branch_lower)
    if adr_pattern2:
        adr_id = f"adr{adr_pattern2.group(1)}"
        title_part = adr_pattern2.group(2)
        title_slug = re.sub(r'[^a-z0-9]+', '-', title_part).strip('-')
        return f"{adr_id}-{title_slug}"
    
    # Fallback: use canonical slug of branch (remove refs/heads/ prefix)
    clean_branch = branch_lower.replace("refs/heads/", "")
    return _canonical_slug(clean_branch)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedWorktree:
    path: Path
    head: str
    branch: str       # empty string for detached HEAD
    is_main: bool
    is_prunable: bool
    is_locked: bool


@dataclass
class CandidateDecision:
    worktree: ParsedWorktree
    dest: Path | None = None
    action: str = "skip"         # move | blocked | skip | rename
    reason: str = ""
    dirty: bool = False
    has_submodules: bool = False
    legacy_name: bool = False
    canonical_proposal: str | None = None  # Proposed canonical name for legacy worktrees


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)


def _git(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], cwd=cwd)


def _git_out(args: list[str], *, cwd: Path | None = None) -> str:
    r = _git(args, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "git error").strip())
    return r.stdout.strip()


def repo_root() -> Path:
    return Path(_git_out(["rev-parse", "--show-toplevel"])).resolve()


# ---------------------------------------------------------------------------
# Worktree parsing
# ---------------------------------------------------------------------------

def parse_worktree_list(raw: str) -> list[ParsedWorktree]:
    """Parse the output of ``git worktree list --porcelain``.

    The first stanza in porcelain output is always the main worktree.
    """
    worktrees: list[ParsedWorktree] = []
    blocks = raw.strip().split("\n\n")
    for block in blocks:
        if not block.strip():
            continue
        lines = block.strip().splitlines()
        kv: dict[str, str] = {}
        flags: set[str] = set()
        for line in lines:
            if " " in line:
                k, _, v = line.partition(" ")
                kv[k] = v.strip()
            elif line.strip():
                flags.add(line.strip())
        path_str = kv.get("worktree", "")
        if not path_str:
            continue
        head = kv.get("HEAD", "")[:12]
        branch_ref = kv.get("branch", "")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else ""
        is_main = len(worktrees) == 0
        is_prunable = "prunable" in flags
        is_locked = "locked" in flags
        worktrees.append(ParsedWorktree(
            path=Path(path_str).resolve(),
            head=head,
            branch=branch,
            is_main=is_main,
            is_prunable=is_prunable,
            is_locked=is_locked,
        ))
    return worktrees


# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------

def is_dirty(wt_path: Path) -> bool:
    """Return True if the worktree has uncommitted or untracked changes."""
    r = _git(["status", "--porcelain"], cwd=wt_path)
    if r.returncode != 0:
        # If git can't run there, treat as dirty/unknown to be safe.
        return True
    return bool(r.stdout.strip())


def has_submodules(wt_path: Path) -> bool:
    """Return True if the worktree contains any (nested) submodules."""
    r = _git(["submodule", "status", "--recursive"], cwd=wt_path)
    if r.returncode != 0:
        return False
    return bool(r.stdout.strip())


# ---------------------------------------------------------------------------
# Destination resolution
# ---------------------------------------------------------------------------

def _dest_for(
    basename: str,
    worktrees_dir: Path,
    *,
    rename_conflicts: bool,
) -> tuple[Path, str | None]:
    """Return ``(dest_path, suffix_used | None)``.

    Raises ``ValueError`` if the destination already exists and
    ``rename_conflicts`` is ``False``.
    """
    candidate = worktrees_dir / basename
    if not candidate.exists():
        return candidate, None
    if not rename_conflicts:
        raise ValueError(f"Destination already exists: {candidate}")
    # Suffix with -2, -3, …
    for n in range(2, 100):
        candidate = worktrees_dir / f"{basename}-{n}"
        if not candidate.exists():
            return candidate, f"-{n}"
    raise ValueError(
        f"Could not find a free destination name for {basename} after 99 attempts"
    )


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_moved_event(
    worker: str, old_path: Path, new_path: Path, branch: str, head: str
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "ts": _now_iso(),
        "worker": worker,
        "type": "worktree_moved",
        "old_path": str(old_path),
        "new_path": str(new_path),
        "branch": branch,
        "head": head,
    }


def _make_blocked_event(
    worker: str, old_path: Path, reason: str, branch: str, head: str
) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "ts": _now_iso(),
        "worker": worker,
        "type": "worktree_move_blocked",
        "old_path": str(old_path),
        "reason": reason,
        "branch": branch,
        "head": head,
    }


def _append_event(event_log: Path, event: dict) -> None:
    event_log.parent.mkdir(parents=True, exist_ok=True)
    with event_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def evaluate_candidates(
    worktrees: list[ParsedWorktree],
    main_path: Path,
    worktrees_dir: Path,
    *,
    include_locked: bool,
    allow_dirty: bool,
    allow_submodules: bool,
    rename_conflicts: bool,
) -> list[CandidateDecision]:
    """Evaluate each worktree and assign: move | blocked | skip."""
    parent_dir = main_path.parent
    decisions: list[CandidateDecision] = []

    for wt in worktrees:
        dec = CandidateDecision(worktree=wt)

        # 1. Skip the main worktree.
        if wt.is_main:
            dec.action = "skip"
            dec.reason = "main worktree"
            decisions.append(dec)
            continue

        # 2. Check if worktree is under .rig/worktrees/.
        try:
            rel_path = wt.path.relative_to(worktrees_dir)
            # This worktree is under .rig/worktrees/, check for legacy naming
            basename = wt.path.name
            
            # Check if it's a known legacy name
            if _is_legacy_worktree_name(basename):
                dec.action = "rename"
                dec.legacy_name = True
                dec.reason = f"legacy name: '{basename}'"
                # Propose canonical name
                proposed = _propose_canonical_name(basename, wt.branch)
                if proposed:
                    dec.canonical_proposal = proposed
                    try:
                        dest, suffix = _dest_for(proposed, worktrees_dir, rename_conflicts=rename_conflicts)
                        dec.dest = dest
                    except ValueError as e:
                        dec.action = "blocked"
                        dec.reason = f"legacy name with no clear canonical mapping: {e}"
                        dec.canonical_proposal = proposed
                else:
                    dec.canonical_proposal = f"needs-adr-mapping-{basename}"
                    try:
                        dest, suffix = _dest_for(dec.canonical_proposal, worktrees_dir, rename_conflicts=rename_conflicts)
                        dec.dest = dest
                    except ValueError:
                        dec.action = "blocked"
                        dec.reason = f"legacy name with no clear canonical mapping"
                        dec.canonical_proposal = None
                decisions.append(dec)
                continue
            
            # Check if it's a reserved name (allowed for integration worktrees)
            if _is_reserved_worktree_name(basename):
                dec.action = "skip"
                dec.reason = "reserved integration worktree"
                decisions.append(dec)
                continue
            
            # Valid canonical name - skip
            dec.action = "skip"
            dec.reason = "already under .rig/worktrees/ with valid name"
            decisions.append(dec)
            continue
            
        except ValueError:
            # Not under .rig/worktrees/, continue with sibling check
            pass

        # 3. Only consider direct siblings of the main repo's parent directory.
        #    This is the critical gate that prevents touching arbitrary directories.
        if wt.path.parent != parent_dir:
            dec.action = "skip"
            dec.reason = (
                f"not a sibling of {parent_dir} (parent is {wt.path.parent})"
            )
            decisions.append(dec)
            continue

        # 4. Locked check.
        if wt.is_locked and not include_locked:
            dec.action = "blocked"
            dec.reason = "worktree is locked (pass --include-locked to override)"
            decisions.append(dec)
            continue

        # 5. Dirty check.
        try:
            dirty = is_dirty(wt.path)
        except Exception as exc:
            dirty = True
            dec.reason = f"could not check dirty status: {exc}"
        dec.dirty = dirty
        if dirty and not allow_dirty:
            dec.action = "blocked"
            dec.reason = (
                dec.reason
                or "worktree has uncommitted changes or untracked files "
                   "(pass --allow-dirty to override)"
            )
            decisions.append(dec)
            continue

        # 6. Submodule check.
        try:
            subs = has_submodules(wt.path)
        except Exception:
            subs = False
        dec.has_submodules = subs
        if subs and not allow_submodules:
            dec.action = "blocked"
            dec.reason = (
                "worktree contains submodules "
                "(pass --allow-submodules to override)"
            )
            decisions.append(dec)
            continue

        # 7. Destination conflict check.
        basename = wt.path.name
        try:
            dest, _suffix = _dest_for(
                basename, worktrees_dir, rename_conflicts=rename_conflicts
            )
        except ValueError as exc:
            dec.action = "blocked"
            dec.reason = str(exc)
            decisions.append(dec)
            continue

        dec.dest = dest
        dec.action = "move"
        decisions.append(dec)

    return decisions


def execute_move(dec: CandidateDecision, root: Path) -> tuple[bool, str]:
    """Run ``git worktree move`` then ``git worktree repair``.

    Returns ``(success, message)``.  On failure, message is the error.
    On success, message is empty or a non-fatal repair warning.
    """
    assert dec.dest is not None
    dest = dec.dest
    wt_path = dec.worktree.path

    # Ensure destination parent exists.
    dest.parent.mkdir(parents=True, exist_ok=True)

    # git worktree move <old> <new>
    r = _git(["worktree", "move", str(wt_path), str(dest)], cwd=root)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "git worktree move failed").strip()
        return False, f"git worktree move failed: {msg}"

    # git worktree repair <new>  — non-fatal if it fails
    r2 = _git(["worktree", "repair", str(dest)], cwd=root)
    if r2.returncode != 0:
        msg = (r2.stderr or r2.stdout or "git worktree repair returned non-zero").strip()
        return True, f"[repair warning] {msg}"

    return True, ""


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_COL_WIDTHS = (50, 10, 10, 10, 40)


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def print_summary_table(decisions: list[CandidateDecision], *, apply: bool) -> None:
    header = ("worktree path", "branch", "head", "action", "dest / reason")
    sep = "  ".join("-" * w for w in _COL_WIDTHS)
    row_fmt = "  ".join(f"{{:<{w}}}" for w in _COL_WIDTHS)
    print()
    print("Worktree Normalization Summary")
    print("=" * (sum(_COL_WIDTHS) + 2 * (len(_COL_WIDTHS) - 1)))
    print(row_fmt.format(*(_trunc(h, w) for h, w in zip(header, _COL_WIDTHS))))
    print(sep)
    for dec in decisions:
        path_str = _trunc(str(dec.worktree.path), _COL_WIDTHS[0])
        branch = _trunc(dec.worktree.branch or "(detached)", _COL_WIDTHS[1])
        head = _trunc(dec.worktree.head, _COL_WIDTHS[2])
        if dec.action == "move":
            action_label = "MOVE" if apply else "WOULD MOVE"
            dest_reason = _trunc(str(dec.dest or ""), _COL_WIDTHS[4])
        elif dec.action == "rename":
            action_label = "RENAME" if apply else "WOULD RENAME"
            if dec.canonical_proposal:
                dest_reason = _trunc(f"to {dec.canonical_proposal}", _COL_WIDTHS[4])
            else:
                dest_reason = _trunc(dec.reason, _COL_WIDTHS[4])
        elif dec.action == "blocked":
            action_label = "BLOCKED"
            dest_reason = _trunc(dec.reason, _COL_WIDTHS[4])
        else:
            action_label = "skip"
            dest_reason = _trunc(dec.reason, _COL_WIDTHS[4])
        print(row_fmt.format(path_str, branch, head, action_label, dest_reason))
    print(sep)
    moved = sum(1 for d in decisions if d.action == "move")
    renamed = sum(1 for d in decisions if d.action == "rename")
    blocked = sum(1 for d in decisions if d.action == "blocked")
    skipped = sum(1 for d in decisions if d.action == "skip")
    mode_label = "--apply" if apply else "--dry-run"
    
    # Count legacy names
    legacy_count = sum(1 for d in decisions if d.legacy_name)
    
    print(
        f"\nMode: {mode_label}  |  Would move: {moved}"
        f"  |  Would rename: {renamed}"
        f"  |  Blocked: {blocked}  |  Skipped: {skipped}"
    )
    if legacy_count > 0:
        print(f"  |  Legacy worktrees detected: {legacy_count}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="worktree_normalize.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="(default) Show what would move; mutate nothing; append no events.",
    )
    mode.add_argument(
        "--apply",
        dest="dry_run",
        action="store_false",
        help="Actually move eligible worktrees and append events.",
    )
    p.add_argument(
        "--worker",
        required=True,
        metavar="NAME",
        help="Name/slug of the agent or user running this script (recorded in events).",
    )
    p.add_argument(
        "--include-locked",
        action="store_true",
        default=False,
        help="Include locked worktrees (default: blocked).",
    )
    p.add_argument(
        "--allow-dirty",
        action="store_true",
        default=False,
        help="Move worktrees with uncommitted changes or untracked files.",
    )
    p.add_argument(
        "--allow-submodules",
        action="store_true",
        default=False,
        help="Move worktrees that contain submodules (git worktree move may fail).",
    )
    p.add_argument(
        "--rename-conflicts",
        action="store_true",
        default=False,
        help="Suffix dest basename with -2, -3, … on name collision instead of refusing.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dry_run: bool = args.dry_run

    # Resolve paths.
    try:
        root = repo_root()
    except RuntimeError as exc:
        print(f"ERROR: Could not resolve git repo root: {exc}", file=sys.stderr)
        return 1

    worktrees_dir = root / ".rig" / "worktrees"
    event_log = root / ".rig" / "work" / "events" / "worktree-normalize.jsonl"

    # Gather worktrees — candidate set comes ONLY from git.
    r = _git(["worktree", "list", "--porcelain"], cwd=root)
    if r.returncode != 0:
        print(
            f"ERROR: git worktree list failed: {(r.stderr or r.stdout).strip()}",
            file=sys.stderr,
        )
        return 1

    worktrees = parse_worktree_list(r.stdout)
    if not worktrees:
        print("No worktrees found.", file=sys.stderr)
        return 0

    main_wt = next((w for w in worktrees if w.is_main), None)
    if main_wt is None:
        print("ERROR: Could not identify main worktree.", file=sys.stderr)
        return 1

    # Evaluate each worktree.
    decisions = evaluate_candidates(
        worktrees,
        main_path=main_wt.path,
        worktrees_dir=worktrees_dir,
        include_locked=args.include_locked,
        allow_dirty=args.allow_dirty,
        allow_submodules=args.allow_submodules,
        rename_conflicts=args.rename_conflicts,
    )

    if not dry_run:
        # Ensure .rig/worktrees/ exists before any moves.
        worktrees_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 0

    for dec in decisions:
        if dec.action != "move":
            # Append blocked events only in apply mode.
            if dec.action == "blocked" and not dry_run:
                event = _make_blocked_event(
                    args.worker,
                    dec.worktree.path,
                    dec.reason,
                    dec.worktree.branch,
                    dec.worktree.head,
                )
                _append_event(event_log, event)
            continue

        if dry_run:
            # Dry-run: nothing to execute; table will show WOULD MOVE.
            continue

        # Apply mode: execute the move.
        ok, msg = execute_move(dec, root)
        if ok:
            event = _make_moved_event(
                args.worker,
                dec.worktree.path,
                dec.dest,  # type: ignore[arg-type]
                dec.worktree.branch,
                dec.worktree.head,
            )
            _append_event(event_log, event)
            if msg:
                print(f"[warn] {dec.worktree.path.name}: {msg}")
        else:
            # Move failed: record as blocked, set non-zero exit.
            print(f"[error] {dec.worktree.path.name}: {msg}", file=sys.stderr)
            event = _make_blocked_event(
                args.worker,
                dec.worktree.path,
                msg,
                dec.worktree.branch,
                dec.worktree.head,
            )
            _append_event(event_log, event)
            dec.action = "blocked"
            dec.reason = msg
            exit_code = 1

    # Print summary table.
    print_summary_table(decisions, apply=not dry_run)

    # Re-run git worktree list --porcelain as post-run evidence.
    print("--- git worktree list --porcelain (post-run) ---")
    r2 = _git(["worktree", "list", "--porcelain"], cwd=root)
    print(r2.stdout if r2.returncode == 0 else f"(error: {r2.stderr.strip()})")
    print("---")

    if dry_run:
        print("Dry-run complete. No worktrees were moved. No events were appended.")
        print("Review the table above, then re-run with --apply to execute.")
    else:
        moved = sum(1 for d in decisions if d.action == "move")
        blocked_count = sum(1 for d in decisions if d.action == "blocked")
        print(f"Apply complete. Moved: {moved}  Blocked/failed: {blocked_count}")
        if event_log.exists():
            print(f"Events appended to: {event_log}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
