# Gemini Agent Instructions

**Read and follow AGENTS.md. It is the canonical project agent policy for Rig.**

## 1. Context Precision Protocol
Gemini agents must optimize for context window efficiency to maintain high reasoning quality.

- **Prefer Discovery over Reading**: Use `rg`, `fd`, and `anigma-mcp` to find specific code hunks. Do not read entire directories or large files (>1000 lines) unless architectural context is required.
- **Granular Retrieval**: When using `anigma-mcp`, prefer `read_file` with specific line ranges over broad searches.
- **Context Search**: Use the `context_search` tool to query the local Anigma SQLite database (`~/Library/Application Support/Anigma/contextum.sqlite`) for historical project context.

## 2. Multimodal Evidence
For UI-R* sprints and any visual work:
- **Visual Verification**: Use the `browser_subagent` to verify that UI changes (styles, layout, animations) match the Rig Design Language (RDL v1).
- **Evidence Collection**: Capture and record browser sessions for UI-related missions. Attach these recordings to the mission handoff.

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
