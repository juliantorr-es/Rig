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

**Canonical policy:** [AGENTS.md](./AGENTS.md)
