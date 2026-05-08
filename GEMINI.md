# Gemini Agent Instructions

**Read and follow AGENTS.md. It is the canonical project agent policy for Rig.**

This file exists only as a pointer. All agent instructions are in `AGENTS.md`.

## Most Critical Safety Rules

**NEVER run these Git commands:**
- `git reset --hard`
- `git clean`
- `git checkout <commit-hash>`
- `git stash` / `git stash pop`
- `git restore` / `git restore .`
- `git checkout -- .`
- `rm -rf`

**Always check workspace state first:**
```bash
git status --short --branch
git branch --show-current
git rev-parse --short HEAD
```


**Patch forward through modified files:**
- Treat files that were already dirty at task start as user-owned.
- Do not restore, reset, checkout, stash, overwrite, or recreate a dirty file to get a clean base.
- If a dirty file must be edited, inspect its diff, preserve unrelated hunks, and apply only the minimal task-owned patch.
- If task hunks cannot be separated from pre-existing hunks, stop and report the conflict instead of rewriting the file.


**Commit rule summary:**
- Agents may commit on approved non-main task branches only.
- Agents must never commit to `main`.
- Agents must never push, merge, rebase, reset, clean, stash, or delete branches unless explicitly allowed by the user and policy.

**Canonical policy:** [AGENTS.md](./AGENTS.md)
