# Contributing to Rig

> **Operational rigor is part of governance.**

This document covers how to contribute to Rig, including Git discipline, validation workflows, and architectural expectations.

## Before You Start

### Prerequisites

- **Python 3.14+** — Rig requires Python 3.14 or newer. No exceptions.
- **macOS-first** — Primary development and testing target. Other platforms may work but are not officially supported.
- **Git** — Standard Git tooling. Rig uses Git worktrees extensively.

### First Time Setup

```bash
# Clone the repository
git clone <repo-url>
cd Rig

# Create virtual environment
python3.14 -m venv .venv
source .venv/bin/activate

# Install with all dependencies (default for contributors)
python -m pip install -e ".[ui,dev]"

# Verify environment
python -m rig doctor all
```

## Git Discipline

> **STRICT: Never use destructive Git commands.**

This repository enforces strict Git discipline. Agents and contributors must follow these rules.

### Forbidden Commands (NEVER use)

```bash
# DELIBERATELY NOT ALLOWED - these destroy history/work
git reset --hard
git clean -fd
git restore .
git checkout -- .
git stash
git rebase
git merge
git branch -D
```

### Allowed Git Operations

```bash
# Safe operations
git status
git diff
git log
git branch -a
git switch <branch-name>  # Switch to existing branch
git checkout -b <branch-name>  # Create new branch

# Review operations
git add -p  # Interactive patch staging (review before staging)
git diff --cached  # Review staged changes
```

### Branch Strategy

| Branch Type | Pattern | Purpose |
|-------------|---------|---------|
| Main | `main` | Protected. No direct commits from agents. |
| Feature | `feature/<name>` | Feature development. PR to main. |
| Sprint | `sprint/<name>` | Sprint work. PR to main. |
| Agent | `agent/<task>/<name>` | Agent-owned work. PR to main. |

**Rule:** Agents may never commit directly to `main`. All changes must go through PR review.

### Patch-Forward Development

When modifying files that already have changes:

1. **Inspect first** — `git diff -- <file>` to see existing changes
2. **Preserve unrelated hunks** — Your changes must not overwrite other work
3. **Apply minimal patches** — Only change what's necessary for your task
4. **Never restore to HEAD** — Don't `git checkout HEAD -- file` to "start fresh"

If you cannot cleanly separate your changes from existing ones:
- **STOP** — Do not continue editing
- **REPORT** — Document the conflict to the user
- **WAIT** — For human resolution

## Validation Workflow

> **Before opening a PR, run these commands.**

### Single Command Validation

```bash
# Canonical validation entrypoint
bash scripts/check.sh
```

This runs all required checks in deterministic order.

### Manual Validation Commands

```bash
# 1. Syntax check (Must pass)
python3.14 -m compileall -q src tests

# 2. Core test suites (Must pass)
python -m pytest tests/test_replay.py -v           # 73 replay tests
python -m pytest tests/test_integrity.py -v         # 38 integrity tests
python -m pytest tests/test_projection_contracts.py -v  # 32 projection tests
python -m pytest tests/test_ui_frontend_logic.py -v   # UI logic tests

# 3. Doctor commands (Must pass)
python -m rig doctor all
python -m rig doctor projections

# 4. Replay validation (Must pass)
python -m rig replay timeline --json

# 5. UI validation (Must pass)
python -m rig ui --help
python -m rig window open --dry-run
```

### Validation Order

Checks are run in this deterministic order:
1. Syntax compilation → Fastest, catches parse errors early
2. Replay tests → Core governance functionality
3. Integrity tests → Validation layer
4. Projection contract tests → UI contract compliance
5. UI frontend logic tests → Frontend behavior
6. Doctor commands → Runtime integrity
7. Replay timeline → End-to-end replay
8. UI dry-run → Windowed UI readiness

### Fail-Fast Behavior

- **First failure stops the pipeline** — Don't run remaining checks if one fails
- **Explicit failure surfaces** — Each check reports its own failures clearly
- **No hidden mutation** — Validation checks are read-only

## Architecture Philosophy

### Core Doctrine

1. **Rig is the authority** — Not models, not users, not external systems
2. **Deny by default** — All intents blocked unless explicitly allowed
3. **Execution in isolation** — Every action in a separate Git worktree
4. **Durable evidence** — Every action produces immutable receipts
5. **Replayable history** — State reconstructable from receipts alone
6. **Projection-only UI** — Frontend never infers authority

### Trust Boundaries

```
TRUST LEVEL 0: Canonical receipts and audit events (Highest)
TRUST LEVEL 1: Replay results derived from Level 0
TRUST LEVEL 2: Projections derived from Level 1
TRUST LEVEL 3: Frontend rendering from Level 2 (Lowest)

Invariant: Trust NEVER increases when moving down levels.
```

## Adding New Components

### How to Add a Widget

1. **Location** — Place in `src/rig_tools/static/js/widgets/`
2. **Pattern** — Follow existing widget patterns (see `replay-timeline-card.js`)
3. **Contract** — Consume projections only, never fetch authority
4. **Registration** — Add to widget registry
5. **Testing** — Add UI frontend logic tests

**Rules:**
- No direct authority inference
- No side effects
- No state invention
- Use `textContent` only (no `innerHTML`) for XSS safety

### How to Add a Projection

1. **Location** — Domain layer (`src/rig/domain/`)
2. **Pattern** — Return frozen dataclass, implement `to_dict()`
3. **Safety** — Derive from canonical evidence only
4. **Determinism** — Same inputs must produce same outputs

**Example:**
```python
@dataclass(frozen=True, slots=True)
class MyProjection:
    value: str
    created_at: str
    
    def to_dict(self) -> dict:
        return asdict(self)
```

### How to Add a Receipt

1. **Standard** — Use `ReceiptEnvelope` as the container
2. **Required fields** — `schema_version`, `receipt_id`, `receipt_type`, `created_at`, `actor`, `subject`, `decision`
3. **Authority flags** — Set `authoritative` and `advisory_only` appropriately
4. **Immutability** — Receipts are never modified after creation

### How to Add an Audit Event

1. **Standard** — Use `AuditEvent` as the container
2. **Required fields** — `event_id`, `action`, `actor`, `subject`, `decision`, `timestamp`, `workspace_id`
3. **Receipt linkage** — Set `receipt_id` and `receipt_status` for traceability
4. **Immutability** — Audit events are never modified

### How to Add a Replay Fixture

1. **Location** — `tests/test_replay.py` in `TestGoldenReplayFixtures` class
2. **Pattern** — Use `_create_*` helper methods for test data
3. **Determinism** — Tests must produce consistent results
4. **Coverage** — Each fixture tests a specific scenario

**Example scenarios to cover:**
- Clean workspace lifecycle
- Advisory-only receipts
- Missing validation receipts
- Orphaned audit events
- Corrupted replay ordering
- Contradictory gate decisions
- Stale receipt references

## Testing Expectations

### Test Requirements

- **All tests must pass** before PR review
- **No skipped tests** without explicit justification
- **Deterministic** — Same inputs produce same results
- **Fast** — Tests should run in seconds, not minutes
- **Isolated** — Tests don't depend on external state

### Test Coverage

| Area | Test File | Count |
|------|-----------|-------|
| Replay | `tests/test_replay.py` | 73+ tests |
| Integrity | `tests/test_integrity.py` | 38 tests |
| Projections | `tests/test_projection_contracts.py` | 32 tests |
| UI Logic | `tests/test_ui_frontend_logic.py` | Varies |

### Writing Good Tests

1. **Test one thing** — Each test validates a single behavior
2. **Use fixtures** — Reuse test data with pytest fixtures
3. **Clear assertions** — Use descriptive assertion messages
4. **No I/O** — Tests should not read/write files (except golden fixtures)
5. **No network** — Tests must work offline

## Code Review Expectations

### Before Submitting a PR

- [ ] All validation commands pass (see above)
- [ ] Code follows existing patterns and conventions
- [ ] No destructive Git commands used
- [ ] No broad formatters run (`ruff format`, etc.)
- [ ] Changes are minimal and focused
- [ ] Documentation updated if needed

### What Reviewers Look For

1. **Git discipline** — No destructive commands, proper patch-forward
2. **Architecture compliance** — Follows Rig's governance patterns
3. **Test coverage** — New functionality has corresponding tests
4. **Projection safety** — UI changes don't infer authority
5. **Determinism** — Logic produces consistent results
6. **Error handling** — Graceful degradation, explicit findings

### Review Checklist

- [ ] `python3.14 -m compileall -q src tests` passes
- [ ] `python -m pytest tests/test_replay.py` passes
- [ ] `python -m pytest tests/test_integrity.py` passes
- [ ] `python -m pytest tests/test_projection_contracts.py` passes
- [ ] `python -m rig doctor all` passes
- [ ] `bash scripts/check.sh` passes
- [ ] No pre-existing dirty files were modified unintentionally
- [ ] Changes are described accurately in commit message

## Development Workflow

### Typical Session

```bash
# Start fresh
source .venv/bin/activate

# Make changes
# ... edit files ...

# Validate incrementally
python3.14 -m compileall -q src tests
python -m pytest tests/test_replay.py -v

# When ready for PR
bash scripts/check.sh

# Review your changes
git diff
git status

# Commit (if authorized)
git add -p  # Review each hunk
git commit -m "<clear message>"
```

### Deterministic Development

- **Always run the same validation commands**
- **Don't rely on caches** — Clean environment testing
- **Reproduce issues** — Include steps to reproduce in bug reports
- **Document assumptions** — If code assumes something, document it

## Reporting Issues

### What to Include

1. **Steps to reproduce** — Exact commands to trigger the issue
2. **Expected behavior** — What should happen
3. **Actual behavior** — What actually happens
4. **Environment** — Python version, OS, install method
5. **Relevant output** — Error messages, logs, tracebacks

### Debug Commands

Run these to gather diagnostic information:

```bash
# System info
python --version
uname -a

# Rig doctor
python -m rig doctor all --json > doctor.json
python -m rig doctor projections --json > projections.json

# Replay diagnostics
python -m rig replay timeline --json > timeline.json

# Test specific areas
python -m pytest tests/test_replay.py -v > replay_tests.log
```

## Resources

| Resource | Location |
|----------|----------|
| Architecture Navigation | [docs/architecture/README.md](docs/architecture/README.md) |
| Contributor Orientation | [docs/architecture/contributor-orientation.md](docs/architecture/contributor-orientation.md) |
| Terminology | [docs/architecture/terminology.md](docs/architecture/terminology.md) |
| Doctrine Map | [docs/architecture/doctrine-map.md](docs/architecture/doctrine-map.md) |
| Current vs. Future | [docs/architecture/current-vs-future.md](docs/architecture/current-vs-future.md) |
| Documentation Governance | [docs/architecture/documentation-governance.md](docs/architecture/documentation-governance.md) |
| Sprint Plans | `docs/sprints/` |
| ADRs | `docs/adr/` |
| Issue Templates | `.github/ISSUE_TEMPLATE/` |
| PR Template | `.github/pull_request_template.md` |
| Release Docs | `docs/release/` |

### Key Architecture Documents

- [Architecture Navigation](docs/architecture/README.md) — Start here
- [Workspace Control Plane](docs/architecture/workspace-control-plane.md)
- [Governance Engine](docs/architecture/governance-engine.md)
- [Governance Replay](docs/architecture/governance-replay.md)
- [Replay Determinism](docs/architecture/replay-determinism.md)
- [Projection Contracts](docs/architecture/projection-contract-lockdown.md)
- [Integrity Validation](docs/architecture/integrity-validation.md)

## Summary

- **Git discipline is mandatory** — No destructive commands, ever
- **Validation before PR** — Run `scripts/check.sh` always
- **Projection safety** — UI never infers authority
- **Determinism required** — Same inputs, same outputs
- **Replayable** — All state reconstructable from receipts
- **Documented** — Changes must include documentation updates
