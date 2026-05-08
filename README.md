# Rig

**Models propose; Rig disposes.**

Rig is a cryptographically governed control plane for local AI coding. It forces AI work through isolated Git worktrees, validation gates, and explicit review before anything touches your main branch.

## Why Rig Exists

Most AI coding tools mutate your code blindly. Rig ensures:
- **No silent mutation of main** — Every change goes through explicit gates
- **No auto-apply** — You decide what gets applied, when
- **No provider direct mutation** — Models never write directly to your repo
- **All orchestration leaves receipts and logs** — Full audit trail of every action

## Quickstart

```bash
# 1. Clone and install (Python 3.14+ required)
git clone <repo-url>
cd Rig
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[ui,dev]"

# 2. Verify installation
python -m rig doctor all

# 3. Run the windowed UI
python -m rig ui

# 4. Or use CLI commands
python -m rig --help
```

## Platform Assumptions

- **macOS-first** — Primary development and testing target
- **Python 3.14+** — Required runtime
- **Local-first** — No SaaS, no networking, no cloud dependencies for core governance
- **Git-native** — Uses Git worktrees for isolation

## Core Architecture

| Component | Purpose | Key File |
|-----------|---------|----------|
| **Workspaces** | Project authority boundary | `src/rig/domain/workspace.py` |
| **Receipts** | Cryptographic proof of events | `src/rig/domain/receipt_envelope.py` |
| **Audit Events** | Immutable audit trail | `src/rig/domain/workspace_audit.py` |
| **Governance Engine** | Action legality checks | `src/rig/domain/governance.py` |
| **Replay** | Deterministic state reconstruction | `src/rig/domain/replay.py` |
| **Projections** | UI-optimized state views | `src/rig/domain/projection.py` |

## First Successful Commands

```bash
# Validate your environment
python -m rig doctor all

# Check projections
python -m rig doctor projections

# View timeline (replay from receipts)
python -m rig replay timeline --json

# Run all replay tests
python -m pytest tests/test_replay.py -v

# Run all integrity tests
python -m pytest tests/test_integrity.py -v

# Run all projection contract tests
python -m pytest tests/test_projection_contracts.py -v

# Full validation
bash scripts/check.sh
```

## Validation Workflow

Before contributing or opening a PR:

```bash
# Syntax check
python3.14 -m compileall -q src tests

# Core test suites
python -m pytest tests/test_replay.py tests/test_integrity.py tests/test_projection_contracts.py tests/test_ui_frontend_logic.py

# Doctor commands
python -m rig doctor all
python -m rig doctor projections

# Replay validation
python -m rig replay timeline --json

# UI dry-run
python -m rig window open --dry-run
```

### Operational Trust Verification

For comprehensive operational trust validation:

```bash
# Full validation entrypoint
bash scripts/check.sh

# Fresh clone verification (proves installability)
bash scripts/verify_fresh_clone.sh --fast

# Release artifact verification (proves buildability)
bash scripts/verify_release_artifacts.sh --fast
```

These scripts run deterministic, isolated verification of:
- ✅ Fresh clone install and validation
- ✅ Editable install path verification  
- ✅ CLI entrypoint functionality
- ✅ Source distribution builds
- ✅ Wheel distribution builds (when supported)
- ✅ Installability from built artifacts
- ✅ Package metadata integrity

## Architecture Overview

### Workspace Lifecycle

```
planned → active → executed → validated → review_ready → applied
                     ↓
                  blocked (terminal)
```

- Each transition requires **explicit receipts**
- Each receipt is **cryptographically signed**
- All state is **replayable from receipts alone**
- **No hidden mutation** — Authority state is never invented

### Receipt Chain

Every action produces a receipt:
- Workspace creation → `workspace_create` receipt
- Command execution → `exec_receipt` 
- Validation pass → `validator_receipt`
- Review approval → `review_bundle`
- Apply → `apply_receipt`

Receipts form an immutable chain. Lost receipts = incomplete replay.

### Projection Contract

- **Projections are derived, never authoritative**
- **Frontend widgets consume projections only**
- **No state invention** — Missing data shows as placeholders
- **Deterministic** — Same inputs always produce same outputs

## User Interfaces

| Interface | Command | Purpose |
|-----------|---------|---------|
| **CLI** | `python -m rig <command>` | Scriptable, deterministic workflows |
| **Windowed UI** | `python -m rig ui` | Rich interactive control plane |
| **Browser mode** | `python -m rig --debug ui --browser` | Web-based UI for development |

## Governance Doctrine

1. **Rig is the authority** — Not the model, not the user, not external systems
2. **Deny by default** — All intents are blocked unless explicitly allowed
3. **Execution in isolation** — Every execution happens in a separate Git worktree
4. **Durable evidence** — Every action produces a receipt; receipts are never deleted
5. **Replayable history** — Workspace state can be fully reconstructed from receipts
6. **Projection-only UI** — Frontend never infers authority, only displays projections

## Trust Boundaries

```
┌─────────────────────────────────────────────────────────┐
│                    TRUST LEVEL 0 (Highest)                │
│              Canonical receipts and audit events           │
├─────────────────────────────────────────────────────────┤
│                    TRUST LEVEL 1                           │
│              Replay results derived from Level 0          │
├─────────────────────────────────────────────────────────┤
│                    TRUST LEVEL 2                           │
│              Projections derived from Level 1            │
├─────────────────────────────────────────────────────────┤
│                    TRUST LEVEL 3 (Lowest)                  │
│              Frontend rendering from Level 2             │
└─────────────────────────────────────────────────────────┘

Invariant: Trust never increases when moving down levels.
```

## Key Commands Reference

### Setup & Inspection
```bash
rig init                  # Initialize Rig in current directory
rig config inspect        # Show current configuration
rig runtime list          # List available runtimes
rig model list            # List configured models
rig provider list         # List configured providers
rig system inspect        # System-level inspection
```

### Workspace Management
```bash
rig workspace status              # Show workspace status
rig workspace lanes               # List workspace lanes
rig workspace projection          # Show workspace projection
rig workspace receipts           # List workspace receipts
rig workspace create <name>       # Create new workspace
rig workspace review              # Review pending changes
rig workspace apply               # Apply approved changes
```

### Job Management
```bash
rig job create    # Create new job
rig job run      # Run job
rig run --task <task-id> --provider <provider>  # Shortcut for task execution
```

### Governance & Audit
```bash
rig log list      # List log entries
rig log show <id> # Show specific log entry
rig debug bundle  # Create debug bundle
```

### Doctor & Replay
```bash
rig doctor all                    # Full integrity check
rig doctor projections             # Check projection contracts
rig replay timeline --json        # Show replay timeline
rig replay workspace <id> --json  # Replay specific workspace
```

## Testing

```bash
# Install dev dependencies
python -m pip install -e ".[dev]"

# Run all tests
python -m pytest tests/ -v

# Run specific test suites
python -m pytest tests/test_replay.py        # 73 replay tests
python -m pytest tests/test_integrity.py      # 38 integrity tests
python -m pytest tests/test_projection_contracts.py  # 32 projection tests
python -m pytest tests/test_ui_frontend_logic.py   # UI logic tests

# Validation entrypoint
bash scripts/check.sh
```

## Documentation

| Document | Purpose |
|----------|---------|
| [CONTEXT.md](./CONTEXT.md) | Domain terminology and core concepts |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Contribution guidelines and workflow |
| [CHANGELOG.md](./CHANGELOG.md) | Release history and changes |
| [docs/architecture/README.md](./docs/architecture/README.md) | Architecture navigation map |
| [docs/quickstart.md](./docs/quickstart.md) | Detailed getting started guide |
| [docs/troubleshooting.md](./docs/troubleshooting.md) | Debugging and failure ergonomics |

### Architecture Deep Dives

- [Workspace Control Plane](docs/architecture/workspace-control-plane.md)
- [Governance Engine](docs/architecture/governance-engine.md)
- [Receipt Formalization](docs/architecture/receipt-formalization.md)
- [Workspace Integrity Rules](docs/architecture/workspace-integrity-rules.md)
- [Governance Replay](docs/architecture/governance-replay.md)
- [Replay Determinism](docs/architecture/replay-determinism.md)
- [Projection Contracts](docs/architecture/projection-contract-lockdown.md)
- [Audit & Integrity](docs/architecture/integrity-validation.md)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for:
- Git discipline and branch expectations
- Validation workflow before opening PRs
- How to add widgets, projections, receipts, audit events
- Testing expectations and code review guidelines

## License

AGPL-3.0-or-later — See LICENSE file for details.
