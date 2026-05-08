# Rig Git Guard

## Why It Exists

Agent sessions must patch forward from dirty files. They must not use Git as an undo button, and they must not restore, reset, checkout, stash, clean, rebase, or merge away user-owned work.

The Rig Git guard enforces that policy for agent shells before a destructive Git command can run.

## What It Blocks

The guard blocks destructive or history-shifting Git usage, including:

- `git restore`
- `git clean`
- `git stash`
- `git rebase`
- `git merge`
- `git checkout -- ...`
- `git checkout <commitish>`
- `git reset --hard`
- `git reset --merge`
- `git reset --keep`
- `git branch -D ...`

## What It Allows

Inspection commands remain allowed, including:

- `git status --short --branch`
- `git status --porcelain=v1 --branch`
- `git diff`
- `git diff --staged`
- `git log`
- `git rev-parse`
- `git branch --show-current`

## How To Enable It

Put the repo `scripts/` directory first in `PATH` before launching an agent session:

```zsh
PATH="/Users/user/Developer/GitHub/Rig/scripts:$PATH" command vibe "$@"
```

Generic form:

```zsh
agent_command() {
  PATH="/Users/user/Developer/GitHub/Rig/scripts:$PATH" command agent_command "$@"
}
```

The guard can also be called directly:

```bash
python3.14 /Users/user/Developer/GitHub/Rig/scripts/rig_git_guard.py status --short --branch
```

## Test Commands

These should work:

```bash
git status --short --branch
git status --porcelain=v1 --branch
git diff
git diff --staged
git log --oneline -5
git rev-parse --short HEAD
git branch --show-current
```

These should be blocked:

```bash
git restore AGENTS.md
git stash
git clean -fd
git rebase main
git merge main
git reset --hard
```

## Limitation

The wrapper only guards commands that pass through the wrapper process. It cannot intercept a caller that bypasses PATH and invokes an absolute Git binary directly. Agents must still obey AGENTS.md and must not bypass the guard with absolute Git paths.

