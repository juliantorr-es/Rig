Historical narrative. Not current workflow authority.

# 2026-05-08 — Worktrees and Sandboxing

## Situation
With agents producing structured output and proposing changes, we needed a place for those changes to happen safely.

## The Pain
Agents mutating the main repository directly was a disaster waiting to happen. It was too easy to accidentally commit broken code to the main branch or lose track of what the agent was actually doing amidst human-authored changes. We couldn't afford to let agents work in the same space as the developer.

## False Starts
Trying to have agents work directly on branches in the main working tree. We also saw scattered, arbitrary sibling worktrees popping up, making a mess of the project structure.

## Decision
We introduced strict worktree isolation. Sibling worktrees were moved into a dedicated `.rig/worktrees/` directory. Agents were sandboxed away from the main worktree, forcing them into isolated, tracked worktrees where their actions could be evaluated safely. Git worktrees became the practical substrate for agent execution.

## Evidence
- `.rig/worktrees/`
- `scripts/worktree_normalize.py`
- `docs/architecture/workspace-authority-auditability.md` (now removed)

## Lesson
Never let agents mutate the main working tree; always sandbox them in dedicated Git worktrees.

## Channel Hook
Sandboxing AI Agents: Why Git Worktrees Saved Our Codebase.
