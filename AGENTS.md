# AGENTS.md — Canonical Rig Agent Policy

> **If a task instruction conflicts with AGENTS.md, follow the stricter safety rule and report the conflict.**

---

## 1. Project Summary

**Rig is a governed local AI coding control plane.**

- Models propose; Rig disposes.
- Safety, receipts, worktrees, validation, and explicit user intent matter more than agent speed.
- Do not make model output authoritative.
- Rig is the final authority on what changes are applied.

---

## 2. Python/Runtime Setup

- **Required Python**: 3.14
- **Create venv**:
  ```bash
  python3.14 -m venv .venv
  source .venv/bin/activate
  ```
- **Install dev + UI**:
  ```bash
  python -m pip install -e ".[ui,dev]"
  ```
- **UI package note**: package name is `pywebview`, runtime import is `import webview`.

---

## 3. Correct Validation Commands

### Active checks (normal gate):
- `python -m compileall -q src tests`
- `python -m pyright --project pyrightconfig.json`
- Targeted `ruff check` on touched files only
- Narrowly scoped tests relevant to the task

### Smoke commands:
- `python -m rig doctor`
- `python -m rig ui --help`
- `python -m rig tui`
- `python -m rig window open --dry-run`
- `python -m rig --debug ui --browser` (when UI browser path is touched)

### Gate scope rules:
- Do **not** report unscoped pyright as the active gate unless the task explicitly asks for repo-wide type debt.
- Do **not** run full pytest as a success criterion if legacy tests are known deferred, unless the task asks for full test triage.

---

## 4. Git Discipline Protocol

**STRICT: Read this entire section before editing any file.**

### Before editing files, agents MUST run and report:
```bash
git status --short --branch
git branch --show-current
git rev-parse --short HEAD
```

### Classify the workspace:
- **clean** — no tracked changes, no untracked files
- **dirty with pre-existing tracked changes** — user has uncommitted work
- **dirty with untracked files** — new files not yet tracked
- **dirty with both** — mixed state

### If workspace is dirty:
- Treat pre-existing changes as **user-owned** — you do not own them.
- Record the initial dirty file list immediately.
- Do **not** assume ownership of pre-existing changes.
- Do **not** run broad formatters or autofix on pre-existing dirty files.

### User-Owned Dirt / Modified File Discipline

Pre-existing dirty files are protected work. Agents must patch forward from the current working tree, not restore backward to `HEAD` and rebuild their preferred version.

For automation or scripted inspection, prefer the stable porcelain format:
```bash
git status --porcelain=v1 --branch
```

#### Hard rule
If a file is already modified when the task begins, agents must **not** restore it, reset it, check it out from `HEAD`, overwrite it wholesale, or recreate it from scratch just to get a clean base.

Do **not** use any of these to clear user-owned dirt:
```bash
git restore path/to/file
git checkout -- path/to/file
git reset --hard
git clean -fd
git stash
```

#### Required behavior when a dirty file must be edited
If the current task requires editing a file that was already dirty at task start:

1. Inspect the existing diff first.
2. Identify which hunks are pre-existing user or other-agent work.
3. Apply the smallest forward patch needed for the current task.
4. Preserve unrelated existing hunks exactly.
5. Do not normalize, reformat, reorder, or rewrite unrelated sections.
6. Stage only task-owned hunks when staging is explicitly authorized.
7. Report that the file had pre-existing modifications.

Use patch-forward workflows such as:
```bash
git diff -- path/to/file
git add -p path/to/file
```
Only use `git add -p` when staging is allowed by the current task and policy.

#### Forbidden "two steps back, one step forward" behavior
Agents must not revert a dirty file to `HEAD` and then re-apply their own changes. That destroys or obscures user work and makes review unreliable.

Correct behavior:
```text
existing dirty file
→ inspect existing hunks
→ preserve unrelated hunks
→ apply minimal new hunks
→ stage only task-owned hunks if authorized
→ report remaining user-owned dirt
```

Incorrect behavior:
```text
existing dirty file
→ restore/reset/checkout/stash
→ re-add agent changes
→ accidentally drop or rewrite user/other-agent work
```

#### Stop condition
If task hunks cannot be cleanly separated from pre-existing dirty hunks, agents must stop and report:

- the affected file
- the pre-existing hunks
- the needed task hunks
- why they cannot be safely separated
- the safest proposed next step

Do not restore the file. Do not overwrite the file. Do not keep editing through the conflict.

### Final report MUST separate:
- Files dirty **before** the task
- Files **changed** by the agent
- Files **created** by the agent
- Files **deleted** by the agent

### Commit Authority
- Agents may create commits only on non-main agent/sprint/feature branches when explicitly assigned to that worktree or lane.
- Approved branch patterns: `agent/<task>/<agent>`, `sprint/<task>`, `feature/<task>`.
- Agents must never commit to `main`.
- Agents must never push unless the user explicitly asks for push in the current message.
- Agents must never merge into `main`.
- Agents must never rebase, reset, clean, stash, or use Git as an undo mechanism.
- Commits must stay inside the intended assigned worktree and include only files changed for the current task.
- Messy checkpoint commits are acceptable on approved non-main branches.
- Main history stays clean through review, squash, or merge policy.

### FORBIDDEN Git Commands (unless user explicitly requests the **exact** operation in the current message):

| Command | Forbidden | Exception |
|---|---|---|
| `git add` | ✓ | User explicitly says "run git add <paths>" |
| `git commit` | ✓ | User explicitly says "run git commit -m '<message>'" |
| `git push` | ✓ | User explicitly says "run git push" |
| `git reset --hard` | ✓ | **NEVER** — even if user asks, refuse and report |
| `git clean` | ✓ | **NEVER** — even if user asks, refuse and report |
| `git checkout <commit>` | ✓ | **NEVER** — use only `git switch` to branches |
| `git checkout -- .` | ✓ | **NEVER** |
| `git restore` | ✓ | **NEVER** |
| `git restore .` | ✓ | **NEVER** |
| `git stash` | ✓ | **NEVER** |
| `git stash pop` | ✓ | **NEVER** |
| `git rebase` | ✓ | **NEVER** |
| `git merge` | ✓ | **NEVER** |
| `git branch -D` | ✓ | **NEVER** |
| `rm -rf` | ✓ | **NEVER** |

> **NEVER** use Git as an undo button.
> **NEVER** use destructive Git commands to inspect diffs.
> **NEVER** move HEAD to "check something."
> **NEVER** stash to "clean up" without explicit permission.

### Even when the user asks to commit:
1. First show `git status --short`
2. Summarize **exactly** what will be included
3. If tool/system rules still forbid committing, provide exact user-run commands instead
4. Never claim the user did not ask if they did ask

### Git Guard for Agent Sessions

- Agent shells should place the Rig Git guard first in `PATH` so destructive commands are blocked before they reach the real Git binary.
- If the guard blocks a command, stop immediately and report the blocked command and reason.
- Do not bypass the guard by calling absolute Git paths directly.
- The guard enforces the patch-forward policy for dirty files.

---

## 5. Recovery Protocol

**If an agent accidentally runs a destructive Git command:**

1. **STOP IMMEDIATELY** — do not edit any more files.
2. **ADMIT** the exact command that was run.
3. Run only these diagnostic commands:
   ```bash
   git status --short --branch
   git reflog --date=iso -10
   git log --oneline --decorate -8
   ```
4. **DO NOT** attempt recovery unless explicitly instructed by the user.
5. **DO NOT** keep editing files.

---

## 6. Retired/Legacy Surfaces

- **Do NOT revive** the Textual/Gridline TUI.
- `rig tui` **must remain** a deprecation shim unless the user explicitly asks otherwise.
- Legacy tests should **not** be deleted casually.
- If a legacy test is retained for proof/reference reasons, mark it skipped with an explicit retirement reason rather than deleting it silently.
- **Do NOT** remove failing tests to make the suite green.

---

## 7. UI Rules

- **Active UI**: `rig ui`
- **Correct debug command**: `python -m rig --debug ui`
- **Browser mode**: `python -m rig --debug ui --browser`
- **Dependency check**: `pywebview` is the package, but verify with `import webview` at runtime.
- **Token redaction**: Preserve token redaction in all UI output and logs.
- **Disabled controls**: Do not bypass disabled UI controls by faking success.
- **Manual repo path fallback**: May validate/submit intent, but must **not** imply workspace switching succeeded unless backend state actually changed.
- **Disabled state**: Controls must expose clear `disabled_reason` from backend.

---

## 8. Scope and Change Discipline

- Make the **smallest coherent change** to satisfy the task.
- **No broad rewrites.**
- **No broad formatting.**
- **No broad** `ruff --fix`.
- **No broad** `ruff format`.
- Do **not** weaken `pyrightconfig.json`.
- Do **not** add broad ignores.
- Prefer targeted ruff/pyright on touched files plus the configured active gate.
- **Runtime behavior changes must be explicitly reported.**

---

## 9. Documentation/TD Discipline

- A **roadmap item is NOT an active task**.
- **Future capability is NOT implementation.**
- **Proof/receipt records evidence**; it does not define current work.
- Active tasks need: goal, non-goals, scope, acceptance, validation, and evidence.
- **Park shiny ideas as follow-ups**; do not opportunistically implement them.

---

## 10. Final Report Format

**Every coding task final report must include:**

```
Changed:
- <file>: <what changed>

Created:
- <file>

Deleted:
- <file>

Runtime behavior changed: yes/no

Tests/Validation run:
- <command>: <result>

Failures remaining:
- <list failures>

Failure ownership:
- caused by this task: yes/no
- pre-existing: yes/no

Suggested commit message:
<message>

Safe to commit: yes/no
```

Also include:
- Current branch and HEAD
- Files dirty before the task
- Files intentionally left unstaged
- Whether any pre-existing dirty files were touched
- Whether partial staging was used

---

## Quick Reference

| Item | Value |
|---|---|
| Python version | 3.14 |
| Venv setup | `python3.14 -m venv .venv` |
| Install | `python -m pip install -e ".[ui,dev]"` |
| UI package | `pywebview` (import as `webview`) |
| Debug UI | `python -m rig --debug ui` |
| Browser mode | `python -m rig --debug ui --browser` |
| Type check | `python -m pyright --project pyrightconfig.json` |
| Syntax check | `python -m compileall -q src tests` |
| Lint | `ruff check` (targeted on touched files) |
| Smoke | `python -m rig doctor`, `python -m rig ui --help` |

---

## Agent skills

### Issue tracker

GitHub Issues at https://github.com/juliantorr-es/Rig via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at root, ADRs in `docs/adr/`. See `docs/agents/domain.md`.
