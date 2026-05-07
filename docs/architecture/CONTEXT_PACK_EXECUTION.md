# Context Pack: Git Worktree Execution

## Overview

Git worktrees allow Rig to maintain multiple isolated workspaces (main branch + isolated execution environment) without polluting the main branch or requiring expensive environment setup.

## Workflow

1. **Acquisition (Lease)**:
   - Use `git worktree add <path> <commit-ish>` to create a new isolated environment.
   - Use `git worktree lock <path> --reason "Rig lease"` to ensure that the worktree remains stable during long-running tasks and cannot be pruned by background GC processes.

2. **Execution**:
   - Run commands (validators, tests, patches) inside the worktree via `subprocess` with specific environment variables and working directories.
   - Capture `stdout` and `stderr` streams as execution receipts.

3. **Release**:
   - Unlock the worktree via `git worktree unlock <path>`.
   - Remove the worktree via `git worktree remove <path>`.
   - Optionally run `git worktree prune` to clean up stale worktree administrative files if a cleanup fails.

## Operational Safety

- **Isolation**: Worktrees provide OS-level directory separation, preventing untrusted code from modifying the main working directory.
- **Fail-Safety**: Always wrap execution in a `try...finally` block that ensures the worktree is unlocked and removed even if the command fails or times out.
- **Evidence**: Treat every execution as a "transaction". Create a JSON receipt including command arguments, exit code, and captured output logs.

## Constraints & Limitations

- **Concurrency**: Git worktrees are linked to the base repository. They share the same `.git` directory; concurrently running operations that modify repository-global state (e.g., `git gc`) can lead to race conditions.
- **Cleanup Failure**: If a worktree is deleted improperly, `git worktree prune` is required to clean the Git administrative files.

## Rig Checklist for `WorktreeExecutor`

- [ ] Does the executor lock the worktree during task execution?
- [ ] Is cleanup (unlock/remove) guaranteed in a `finally` block?
- [ ] Are stdout/stderr captured into a durable JSON receipt?
- [ ] Is the worktree path unique per task or session?
- [ ] Are timeouts enforced on all subprocess calls?
