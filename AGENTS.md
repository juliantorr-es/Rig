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

### Commit Message Attribution Policy

**Suggested commit messages must describe the change, not advertise the model or agent.**

- Do **not** include "Generated by …" lines in suggested commit messages.
- Do **not** include "Co-Authored-By" lines unless the human explicitly asks for them.
- Do **not** mention the model vendor name, agent name, or tool name in commit messages, PR titles, PR bodies, commits, changelogs, or release notes.
- Final reports may state which tool performed the work only if operationally relevant, but suggested Git metadata must stay clean.
- Suggested commit messages should be concise, conventional, and project-focused.

**Examples:**

| Bad | Good |
|---|---|
| `Generated by Mistral Vibe.` | `Implement governed public intake funding spine` |
| `Co-Authored-By: Mistral Vibe <vibe@mistral.ai>` | `Fix race condition in workspace status substrate` |
| `Mistral Vibe: Update AGENTS.md` | `Add Git discipline rules for commit attribution` |
| `Created by Claude Code` | `Refactor TUI to use new console projection` |

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
| `git merge` | ✓ | **NEVER** — agents must use `scripts/work_promote.py` for preproduction promotion |
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
- Use `scripts/rig_vibe` to launch Vibe with the guard active.
- Use `scripts/rig_gemini` to launch Gemini with the guard active.
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
- **Canonical workflow**: Agents follow ADR → Sprint → **Sprint Research** → Mission → **Patch Batch** → Evidence → Review/Promotion. See `docs/workflow/adr-sprint-mission-evidence.md` for the authoritative workflow narrative.
- **Sprint Research is mandatory** before any implementation. Research is read-only and must produce research artifacts.
- **Patch batches are preferred** over repeated fine-grained edits. Always precheck patches with `git apply --check`.

---

## 10. Work Status Tracking

### Worktree placement

- Rig-owned linked worktrees must live under `.rig/worktrees/`.
- Do **not** create new sibling worktrees next to the main repo.
- Use `git worktree add .rig/worktrees/<name> <branch>` for new tracked work.
- If sibling worktrees already exist, normalize them with:
  ```bash
  python scripts/worktree_normalize.py --dry-run --worker <name>
  python scripts/worktree_normalize.py --apply --worker <name>
  ```
- **Never raw-move worktrees with `mv`.** Use `git worktree move` or the normalization script.
- If a worktree was moved manually and Git metadata is broken, run `git worktree repair` from the main worktree and report it.

### Worktree normalization script

Canonical script: `scripts/worktree_normalize.py` (tracked)
Local wrapper: `.rig/work/scripts/worktree_normalize.py` (gitignored, delegates to canonical)

| Flag | Effect |
|---|---|
| `--dry-run` | **(default)** Show candidates; mutate nothing; append no events. |
| `--apply` | Actually move eligible worktrees; append events. |
| `--worker NAME` | Required. Name/slug of the calling agent. |
| `--include-locked` | Include locked worktrees (default: blocked). |
| `--allow-dirty` | Move worktrees with uncommitted changes (default: refused). |
| `--allow-submodules` | Move worktrees containing submodules (default: refused). |
| `--rename-conflicts` | Suffix basename with `-2`, `-3`, … on name collision. |

Candidate set is determined **solely** by `git worktree list --porcelain`. The script never touches arbitrary sibling directories.

### Work-stream events

Events are appended to `.rig/work/events/worktree-normalize.jsonl` and validated against `docs/schemas/work-stream-event.schema.json`.

| Event type | When emitted |
|---|---|
| `worktree_moved` | After a successful `git worktree move`. |
| `worktree_move_blocked` | When a candidate is skipped or refused (apply mode only). |

### Acceptance checks

Run these to verify the script is functional before using `--apply`:

```bash
python scripts/worktree_normalize.py --dry-run --worker smoke
git worktree list --porcelain
```

### ADR work state

- ADR work state lives under `.rig/work/adr/<adr-id>/`.
- Each ADR has `task.json`, `progress.jsonl`, `projection.json`, and `notes/out-of-scope-findings.md`.
- Each sprint has `.rig/work/adr/<adr-id>/sprints/<sprint-id>/` with research artifacts and patch batches.
- `progress.jsonl` is **append-only**. Never delete or edit existing lines.
- `projection.json` and `notes/out-of-scope-findings.md` are **generated**. Do not hand-edit them.

### Sprint Research (MANDATORY)

- Sprint Research is **mandatory** before any implementation.
- Research is **read-only** — no file edits except writing artifacts under `.rig/work/adr/<adr-id>/sprints/<sprint-id>/`.
- Research must use installed Python tooling (pathlib, json, ast, difflib, subprocess, tokenize) and CLI tools (rg, fd, git diff, git status --porcelain=v1).
- Research must produce: research_summary, repo_inventory, relevant_files, current_state, risk_notes, mission_plan, patch_batches, validation_plan, out_of_scope_findings.
- Research must **identify expected files** before mutation begins.
- Research must **define validation commands** before mutation begins.
- Sprint Research must **record out-of-current-scope findings** instead of ignoring them.

### Mission and Patch Batch Execution

- Agents should **claim missions**, not tiny slices or subtasks.
- Agents should **derive their own internal checklist** from mission `intent` and `completion_criteria`.
- Agents should **execute missions using patch batches** where practical (`scripts/work_patch_batch.py`).
- Agents should **heartbeat** during long work (`scripts/work_heartbeat.py`).
- Agents must **precheck patches** with `git apply --check` before applying unified diffs.
- **Patch batches require merge-friendliness preflight before apply** (`scripts/work_merge_friendly.py`).
- **Agents must not apply patches blindly while other worktrees are active**.
- Agents must **check merge-friendliness** before applying any patch batch.
- Agents must **validate after each patch batch** is applied.
- Agents must **stop** if actual changed files exceed planned files, protected paths are touched, or unexpected dirty files appear.
- **Do not use** `git reset`/`restore`/`stash`/`checkout`/`clean` for rollback. Report and await direction.
- **Merge-friendliness rules**: Dirty same-file overlap in another worktree blocks by default. Same-directory overlap warns. Merge simulation is advisory/preflight only and does not mutate worktrees.

### Evidence Rules

- Out-of-scope findings **do not expand** the current mission or sprint. They are observations only.
- Agents must include **out-of-scope findings at the end of handoff/final reports**, even if the list is empty.
- Do **not** create nested subtasks, recursive missions, workstreams, or slices. Missions are flat.
- Slices are **implementation phases only** (see ADR 0009), not workflow hierarchy.
- Use `scripts/work_doctor.py` before any commit. `work_doctor.py` will warn or fail if a sprint has missions but no completed research.

#### ADR work scripts (all tracked under `scripts/`)

| Script | Purpose |
|---|---|
| `work_research.py <task_id> --sprint <id> --worker <name> --action start\|complete` | Start/complete sprint research, write research artifacts |
| `work_patch_batch.py <task_id> --action plan\|precheck\|merge-friendly\|apply\|validate --batch <id> ...` | Manage patch batch planning, precheck, merge-friendliness check, apply, validation |
| `work_merge_friendly.py <task_id> --batch <id> --patch-file <path> [--mission <id>] [--sprint <id>]` | Check patch merge-friendliness against active worktrees. Run before apply. |
| `work_export_dataset.py <task_id> [--output-dir <path>] [--force]` | Export ledger data as CSV/Parquet for analysis. Generates events.csv, missions.csv, patch_batches.csv, validations.csv, findings.csv, dataset_card.md, schema.json |
| `work_status.py <task_id>` | Regenerate projection + print status summary (includes sprint research, patch batch, and merge-friendliness status) |
| `work_claim.py <task_id> --mission <id> --worker <name> --paths <glob>` | Claim a mission |
| `work_heartbeat.py <task_id> --mission <id> --worker <name>` | Record heartbeat |
| `work_note.py <task_id> --worker <name> --note "text"` | Append a note |
| `work_note.py <task_id> --worker <name> --out-of-scope --note "text"` | Record out-of-scope finding |
| `work_blocked.py <task_id> --worker <name> --note "reason"` | Record blocked event |
| `work_handoff.py <task_id> --worker <name> --status ready_for_review ...` | Record handoff (includes patch batches applied and out-of-scope findings) |
| `work_doctor.py <task_id>` | Validate task + ledger; required before committing. **Warns/fails if sprint has missions but no completed research. Fails commit readiness if patch batch evidence or merge-friendliness check is missing.** |
| `work_commit.py <task_id> --worker <name> --message "..."` | Governed commit plan |
| `work_promote.py <task_id> --mission <id> --target preproduction --worker <name> [--sprint <id>] [--dry-run]` | Governed promotion to preproduction via Rite of Deterministic Passage. **Agents must NOT merge directly.** |

---

### Preproduction Promotion Rules (Rite of Deterministic Passage)

- **Agents MUST NOT run `git merge` directly.** Direct git merge is forbidden under all circumstances.
- **Agents MAY ONLY promote through `scripts/work_promote.py`** — this is the sole authorized path for preproduction promotion.
- **Target is restricted to `preproduction` only** — main/production are human-governed and out of scope.
- **All 13 deterministic gates must pass** before promotion executes:
  1. Sprint research completed
  2. Mission handoff completed
  3. Patch batches prechecked
  4. Patch batches applied and validated
  5. Merge-friendliness pass completed
  6. work_doctor.py passed
  7. Required tests/checks passed or explicitly justified
  8. Out-of-current-scope findings recorded (even if empty)
  9. Candidate source branch is clean
  10. Candidate source branch HEAD is recorded
  11. Preproduction branch exists locally
  12. Merge simulation against preproduction passes
  13. Preproduction working tree is clean before merge
- **Failed gates append `preproduction_promotion_blocked` event** to the ledger and **must not mutate branches**.
- **Promotion is fully auditable** through ADR-local progress ledger events.
- **Merge simulation uses `git merge-tree`** for non-mutating preflight check.
- **`--dry-run` mode** shows gate results without executing promotion.
- **Preproduction is integration/local only** — production/main remains human-governed and out of scope.

---

## 11. Final Report Format

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
