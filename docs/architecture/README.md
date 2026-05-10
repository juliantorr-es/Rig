# Rig Architecture Navigation Map

> **This is a navigation map, not a manifesto.**
> Goal: A contributor should understand the system topology in under 15 minutes.

## System Overview

Rig is a **cryptographically governed control plane** for local AI coding. The system is built around **immutable evidence** (receipts, audit events) and **deterministic replay** of workspace state.

### Core Philosophy

1. **Models propose; Rig disposes** — AI models generate output, Rig governs what happens to it
2. **Local-first** — No SaaS, no cloud dependencies for core governance
3. **Git-native** — Uses Git worktrees for isolation
4. **Deny by default** — All actions blocked unless explicitly allowed
5. **Everything leaves a receipt** — Immutable, cryptographic proof of every action

### Trust Boundary Model

```
┌─────────────────────────────────────────────────────────────┐
│              TRUST LEVEL 0 - Canonical Evidence               │
│         Receipts + Audit Events + Workspace Records           │
│            (Source of Truth - Never Invented)                 │
├─────────────────────────────────────────────────────────────┤
│              TRUST LEVEL 1 - Replay Results                  │
│            Derived from Level 0 via replay functions         │
├─────────────────────────────────────────────────────────────┤
│              TRUST LEVEL 2 - Projections                      │
│         UI-optimized views derived from Level 1             │
├─────────────────────────────────────────────────────────────┤
## Trust Level 3 - Frontend Rendering
│            Dumb widgets consuming Level 2 projections        │
└─────────────────────────────────────────────────────────────┘

Invariant: Trust NEVER increases when moving down levels.
```

## Canonical Reading Paths

Use these paths to navigate the documentation based on your role or interest.

### 🐣 New Contributor (Onboarding)
1. [README.md](../../README.md) — High-level project overview
2. [AGENTS.md](../AGENTS.md) — Agent policy and Git discipline
3. [CONTEXT.md](../CONTEXT.md) — Domain terminology and concepts
4. [quickstart.md](../quickstart.md) — Getting started locally

### 🎨 Frontend Contributor (Visualization & UX)
1. [visual-execution-doctrine.md](visual-execution-doctrine.md) — The core philosophy
2. [visual-language.md](visual-language.md) — Design tokens and semantics
3. [svg-instrumentation.md](svg-instrumentation.md) — Vector rendering architecture
4. [truthful-animation.md](truthful-animation.md) — Motion semantics
5. [topology-density-convergence.md](topology-density-convergence.md) — Scaling and readability
6. [frontend-systems-architecture.md](frontend-systems-architecture.md) — Widget and stream architecture

### ⚙️ Runtime Contributor (Execution & Replay)
1. [workspace-control-plane.md](workspace-control-plane.md) — Workspace architecture
2. [governance-replay.md](governance-replay.md) — Replay system mechanics
3. [replay-determinism.md](replay-determinism.md) — Determinism guarantees
4. [runtime-streaming.md](runtime-streaming.md) — Streaming architecture
5. [execution-sandbox.md](execution-sandbox.md) — Isolation and execution

### 🛡️ CI & Governance Contributor (Operational Trust)
1. [governance-engine.md](governance-engine.md) — Action legality rules
2. [integrity-validation.md](integrity-validation.md) — Validation and integrity checks
3. [preproduction-governance.md](preproduction-governance.md) — CI/CD gates
4. [protected-branch-governance.md](protected-branch-governance.md) — Branch protection policy
5. [review-governance.md](review-governance.md) — Review and approval flow

### 🧭 Operational Substrate Canonicalization
1. [operational-substrate.md](operational-substrate.md) — Rig layered above Git/GitHub
2. [workspace-as-substrate.md](workspace-as-substrate.md) — Workspace as governed environment
3. [agent-operational-model.md](agent-operational-model.md) — Rig-native agent flow
4. [operational-event-substrate.md](operational-event-substrate.md) — Stream-oriented runtime contracts
5. [execution-substrate-pluralism.md](execution-substrate-pluralism.md) — Backend pluralism and routing
6. [native-operational-shell.md](native-operational-shell.md) — Native macOS supervision
7. [operational-governance-principles.md](operational-governance-principles.md) — Canonical operating principles

### 🧪 Research Contributor (Doctrine & Future)
1. [operational-coherence.md](operational-coherence.md) — The Project Vision
2. [visual-execution-doctrine.md](visual-execution-doctrine.md) — Foundational philosophy
3. [governance-replay.md](governance-replay.md) — Replay theory
3. [public-ops.md](public-ops.md) — Future public operations
4. [experiential-runtime-learning.md](experiential-runtime-learning.md) — Research on runtime learning

## Architecture Topology


```
┌─────────────────────────────────────────────────────────────────┐
│                           RIG ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Workspace  │────▶│   Receipt    │────▶│    Audit     │    │
│  │    Control   │     │  Envelope    │     │   Event      │    │
│  │    Plane     │◀────┴──────────────┘     │    Trail     │    │
│  └──────────────┘          │                 └──────────────┘    │
│                            │                                      │
│                            ▼                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │  Validation  │◀────┤  Governance  │◀───▶│  Integrity   │    │
│  │    Gates     │     │    Engine     │     │   Engine     │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│            │               │                    │                 │
│            └───────────────┼────────────────────┘                 │
│                                │                                      │
│                                ▼                                      │
│                      ┌──────────────────┐                          │
│                      │    REPLAY        │                          │
│                      │   (Phase 5)      │                          │
│                      └────────┬─────────┘                          │
│                               │                                   │
│          ┌────────────────────┼────────────────────┐              │
│          ▼                    ▼                    ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  CLI Commands │    │   UI         │    │   Doctor     │       │
│  │               │    │  Projections │    │  Commands    │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Component Guide

### 📁 Core Domain Components

| Component | File | Purpose | Trust Level |
|-----------|------|---------|-------------|
| Workspace | `src/rig/domain/workspace.py` | Project authority boundary | 0 |
| ReceiptEnvelope | `src/rig/domain/receipt_envelope.py` | Cryptographic proof container | 0 |
| AuditEvent | `src/rig/domain/workspace_audit.py` | Immutable audit trail | 0 |
| Governance Engine | `src/rig/domain/governance.py` | Action legality checks | 1 |
| Integrity Engine | `src/rig/domain/integrity.py` | Validation and finding generation | 1 |
| Replay | `src/rig/domain/replay.py` | Deterministic state reconstruction | 1 |
| Projection | `src/rig/domain/projection.py` | UI-optimized state views | 2 |

### 🎯 Workspace Lifecycle

```
                    ┌─────────────┐
                    │   planned    │
                    └──────┬──────┘
                           │ create workspace
                           ▼
                    ┌─────────────┐
               ┌────▶│   active    │◀────┐
               │     └──────┬──────┘     │
               │            │            │
               │    run job │            │ propose
               │     or     │            │
               │  execute   │            │
               ▼            ▼            ▼
        ┌─────────────┐ ┌───────────┐ ┌─────────────────┐
        │  executed   │ │  blocked  │ │ review_ready    │
        └──────┬──────┘ └───────────┘ └─────────┬────────┘
               │                                 │
               │ validate                       │ apply
               ▼                                 ▼
        ┌─────────────┐                  ┌──────────────────┐
        │  validated   │─────────────────▶│     applied      │
        └─────────────┘                  │   (terminal)     │
                                       └──────────────────┘
                                        ┌──────────────────┐
                                        │    blocked        │
                                        │   (terminal)      │
                                        └──────────────────┘
```

**Terminal states:** `blocked`, `applied` — No transitions allowed from terminal states.

**Every transition produces a receipt.** Missing receipts = incomplete replay.

### 📜 Receipt Chain

All actions in Rig produce signed receipts:

| Action | Receipt Type | Authority | Purpose |
|--------|--------------|-----------|---------|
| Workspace creation | `workspace_create` | Authoritative | Establish workspace |
| Job run | `exec_receipt` | Authoritative | Record execution |
| Validation | `validator_receipt` | Authoritative | Validate outputs |
| Review bundle | `review_bundle` | Advisory | Package for review |
| Apply | `apply_receipt` | Authoritative | Apply to main |
| Gate decision | `gate_decision` | Authoritative | Allow/block intent |
| Public sync | `public_sync_receipt` | Advisory | External sync |

**Chain integrity:** Receipts form a linked chain. Each receipt references related receipts via `related_receipt_ids`.

### 🎭 Projection Contract

Projections are **derived, never authoritative** views of domain state:

```
Domain State (Trust Level 0-1)
    │
    ▼
Projection Builder ←── Contract Definition
    │
    ▼
Projection Output (Trust Level 2)
    │
    ▼
Frontend Widgets (Trust Level 3)
```

**Rules:**
1. Projections derive ONLY from canonical evidence (receipts + audit events)
2. No state is invented during projection
3. Missing data shows as placeholders, not fabricated data
4. All projection data is traceable back to source events
5. Projections are deterministic (same inputs → same outputs)

### 🔄 Replay System (Phase 5 - Complete)

The replay system provides **deterministic reconstruction** of workspace state from receipts alone.

**Key capabilities:**
- Reconstruct workspace state from receipts + audit events
- Handle incomplete history gracefully
- Produce explicit findings for integrity issues
- Never auto-repair corrupted state
- Preserve authority/advisory distinctions

**Replay entry points:**
- `replay_workspace_from_fs()` — Replay from filesystem
- `replay_workspace_lifecycle()` — Replay from record + receipts + audit events
- `load_replay_events_from_fs()` — Load events from .build/rig/

**Validation:**
- `validate_replay_determinism()` — Two replays of same inputs produce identical results
- `validate_replay_consistency()` — Replay matches workspace record
- `validate_replay_projection_consistency()` — Projection matches replay
- `validate_replay_receipt_continuity()` — Receipt chain has no gaps

### 🏗️ Frontend Widget Architecture

Frontend widgets are **dumb renderers** that consume projections:

```
┌─────────────────────────────────────────┐
│           Widget Rules                  │
├─────────────────────────────────────────┤
│ ✓ Consume projections only              │
│ ✓ No authority inference                │
│ ✓ No side effects                       │
│ ✓ No I/O operations                     │
│ ✓ Use textContent (no innerHTML)         │
│ ✓ Handle missing data gracefully        │
│ ✓ Registered in widget registry          │
└─────────────────────────────────────────┘
```

**Widget location:** `src/rig_tools/static/js/widgets/`

**Example widgets:**
- `replay-timeline-card.js` — Replay timeline visualization
- Various workspace status widgets
- Integrity finding display widgets

### Visualization Extensibility

Runtime visualization is now treated as a governed composition surface:

- `docs/architecture/visualization-composition.md` — how panels, overlays, and primitives compose
- `docs/architecture/instrumentation-extension-api.md` — how contributors add instrumentation safely
- `docs/architecture/replay-safe-extension-model.md` — replay constraints for extensions
- `docs/architecture/visualization-lifecycle.md` — mount, update, replay, and cleanup lifecycle rules
- `src/rig_tools/static/js/svg-primitive-registry.js` — deterministic primitive registration substrate
- `src/rig_tools/static/js/topology-plugin-model.js` — bounded topology extension hooks

### 🩺 Doctor Commands

Doctor commands provide **runtime integrity checking**:

| Command | Purpose | Output |
|---------|---------|--------|
| `rig doctor all` | Full integrity check | Score, findings |
| `rig doctor projections` | Projection contract validation | Contract status |
| `rig doctor workspace <id>` | Workspace-specific check | Workspace status |

**Guarantees:**
- No mutation during doctor checks
- Read-only operations only
- Explicit findings for all issues

## Navigation by Task

### "I want to understand the Visual Execution Doctrine"

→ Read these in order:
1. [visual-execution-doctrine.md](visual-execution-doctrine.md) — The core frontend philosophy
2. [truthful-animation.md](truthful-animation.md) — Motion semantics
3. [svg-instrumentation.md](svg-instrumentation.md) — Rendering architecture
4. [design-lineage.md](design-lineage.md) — Historical and geometric roots
5. [visual-language.md](visual-language.md) — Design tokens and color semantics
6. [runtime-visualization-semantics.md](runtime-visualization-semantics.md) — Mapping backend state to frontend geometry

### "I want to understand Frontend Systems Architecture"

→ Read these in order:
1. [frontend-systems-architecture.md](frontend-systems-architecture.md) — Projection-backed rendering
2. [replayable-visualization.md](replayable-visualization.md) — Deterministic reconstruction
3. [frontend-anti-patterns.md](frontend-anti-patterns.md) — Forbidden UI mechanics
4. [ui-projections.md](ui-projections.md) — UI projection schema

### "I want to understand Runtime Visualization Convergence"

→ Read these in order (Phase 8: Visual Systems Convergence):
1. [visual-execution-doctrine.md](visual-execution-doctrine.md) — Core philosophy
2. [telemetry-scaling-semantics.md](telemetry-scaling-semantics.md) — Telemetry → visual mapping formulas
3. [visual-semantic-normalization.md](visual-semantic-normalization.md) — Unified visual language
4. [topology-density-convergence.md](topology-density-convergence.md) — High-density readability
5. [motion-cadence-convergence.md](motion-cadence-convergence.md) — Deterministic motion timing
6. [frontend-memory-governance.md](frontend-memory-governance.md) — Memory and DOM management

### "I want to understand how workspaces work"

→ Read these in order:
1. [CONTEXT.md](../CONTEXT.md) — Domain terminology
2. [workspace-control-plane.md](workspace-control-plane.md) — Workspace architecture
3. [workspace-authority-auditability.md](workspace-authority-auditability.md) — Authority model
4. [workspace-integrity-rules.md](workspace-integrity-rules.md) — Integrity constraints

### "I want to understand governance"

→ Read these in order:
1. [governance-engine.md](governance-engine.md) — Core governance
2. [governance-replay.md](governance-replay.md) — Replay system
3. [replay-determinism.md](replay-determinism.md) — Determinism guarantees
4. [integrity-validation.md](integrity-validation.md) — Validation layer

### "I want to understand receipts"

→ Read these in order:
1. [receipt-formalization.md](receipt-formalization.md) — Receipt design
2. [workspace-authority-auditability.md](workspace-authority-auditability.md) — How receipts establish authority
3. [governance-replay.md](governance-replay.md) — How receipts enable replay

### "I want to understand projections"

→ Read these in order:
1. [workspace-ui-projection-contract.md](workspace-ui-projection-contract.md) — Contract definition
2. [projection-contract-lockdown.md](projection-contract-lockdown.md) — Contract enforcement
3. [projection-renderer-frontend.md](projection-renderer-frontend.md) — Frontend rendering

### "I want to understand the UI"

→ Read these in order:
1. [UI_DOCTRINE.md](UI_DOCTRINE.md) — UI philosophy
2. [ui-projections.md](ui-projections.md) — UI projection design
3. [workspace-ui-projection-contract.md](workspace-ui-projection-contract.md) — Contract
4. Source: `src/rig_tools/static/js/widgets/`

## Deep Dive Documents

### Architecture
- [governance-engine.md](governance-engine.md) — The authority decision engine
- [workspace-control-plane.md](workspace-control-plane.md) — Workspace management
- [governance-replay.md](governance-replay.md) — Time-travel and replay
- [projection-contract-lockdown.md](projection-contract-lockdown.md) — Projection safety guarantees

### Domain
- [CONTEXT.md](../CONTEXT.md) — Core concepts and terminology
- [receipt-formalization.md](receipt-formalization.md) — Receipt system design
- [workspace-authority-auditability.md](workspace-authority-auditability.md) — Authority and audit
- [workspace-integrity-rules.md](workspace-integrity-rules.md) — Integrity constraints
- [proposal-lifecycle.md](proposal-lifecycle.md) — Proposal flow

### Validation & Integrity
- [integrity-validation.md](integrity-validation.md) — Validation engine
- [replay-determinism.md](replay-determinism.md) — Determinism proof

### Visual Execution Doctrine
- [visual-execution-doctrine.md](visual-execution-doctrine.md) — Core frontend philosophy
- [truthful-animation.md](truthful-animation.md) — Driven motion semantics
- [svg-instrumentation.md](svg-instrumentation.md) — Vector topology architecture
- [design-lineage.md](design-lineage.md) — Industrial design roots
- [runtime-visualization-semantics.md](runtime-visualization-semantics.md) — Mechanical state mapping
- [replayable-visualization.md](replayable-visualization.md) — Deterministic trace reconstruction
- [frontend-systems-architecture.md](frontend-systems-architecture.md) — Widget and stream architecture
- [frontend-anti-patterns.md](frontend-anti-patterns.md) — Harmful UI mechanics
- [visual-language.md](visual-language.md) — Geometry and color tokens

### Runtime Visualization Convergence (Phase 8)
- [telemetry-scaling-semantics.md](telemetry-scaling-semantics.md) — Canonical telemetry → visual formulas
- [frontend-memory-governance.md](frontend-memory-governance.md) — DOM lifecycle and bounded buffers
- [visual-semantic-normalization.md](visual-semantic-normalization.md) — Unified color, stroke, spacing, and shape semantics
- [topology-density-convergence.md](topology-density-convergence.md) — High-density readability preservation
- [motion-cadence-convergence.md](motion-cadence-convergence.md) — Deterministic timing and animation

### Public Ops
- [public-ops.md](public-ops.md) — Public operation governance
- [publicops-governance.md](publicops-governance.md) — Extended public ops

## Data Flow Diagram

```
User Intent
     │
     ▼
┌─────────────────────┐
│   Governance Engine  │ ◄─── Decision: ALLOWED / BLOCKED
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Workspace Record   │ ◄─── State: planned, active, executed,...
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Receipt Chain      │ ◄─── Immutable evidence of all actions
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Audit Event Trail  │ ◄─── Immutable audit log
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│      REPLAY          │ ◄─── Reconstruct state from receipts
└────────┬────────────┘
         │
         ├──▶ PROJECTIONS ◄─── UI-optimized views (Trust Level 2)
         │        │
         │        ▼
         │   FRONTEND WIDGETS ◄─── Dumb renderers (Trust Level 3)
         │
         ▼
   DOCTOR COMMANDS ◄─── Integrity validation
```

## Quick Reference

### Import Conventions

```python
# Domain layer imports (authoritative)
from rig.domain.workspace import Workspace, WorkspaceRecord
from rig.domain.receipt_envelope import ReceiptEnvelope, ReceiptDecision
from rig.domain.workspace_audit import AuditEvent, AuditAction
from rig.domain.governance import GovernanceResult, GateDecision

# Projection layer imports (derived)
from rig.domain.projection import build_workspace_projection
from rig.domain.replay import build_replay_projection, replay_workspace_from_fs

# Validation layer imports
from rig.domain.integrity import validate_workspace, IntegrityFinding
```

### File Locations

```
┌─────────────────────────────────────────────────────────────┐
│  Directory             │ Purpose                                │
├─────────────────────────────────────────────────────────────┤
│  src/rig/domain/       │ Core domain types and logic            │
│  src/rig/commands/     │ CLI command implementations             │
│  src/rig/cli/          │ CLI entry points                       │
│  src/rig_tools/        │ Tools, orchestration, frontend assets   │
│  src/rig_tools/static/ │ Frontend static assets (JS, CSS)        │
│  tests/                │ Test suites                            │
│  docs/                 │ Documentation                          │
│  docs/architecture/    │ Architecture documents                 │
│  scripts/              │ Utility scripts                        │
│  .github/workflows/    │ GitHub Actions CI workflows            │
└─────────────────────────────────────────────────────────────┘
```

## Testing Strategy

| Test Type | Location | Purpose |
|-----------|----------|---------|
| Replay tests | `tests/test_replay.py` | Replay functionality, determinism |
| Integrity tests | `tests/test_integrity.py` | Validation layer |
| Projection tests | `tests/test_projection_contracts.py` | Projection contracts |
| UI logic tests | `tests/test_ui_frontend_logic.py` | Frontend behavior |

**Test doctrine:**
- All tests must be deterministic
- No external dependencies
- No I/O (except golden fixtures)
- No network calls
- Fast execution (< 1 minute total)

## Validation Strategy

### Before Opening a PR

```bash
# Single command validation
bash scripts/check.sh

# Or manually:
python3.14 -m compileall -q src tests
python -m pytest tests/test_replay.py -v
python -m pytest tests/test_integrity.py -v
python -m pytest tests/test_projection_contracts.py -v
python -m pytest tests/test_ui_frontend_logic.py -v
python -m rig doctor all
python -m rig doctor projections
python -m rig replay timeline --json
python -m rig ui --help
python -m rig window open --dry-run
```

### CI Validation

See [.github/workflows/ci.yml](../../.github/workflows/ci.yml) for the CI pipeline.

## Common Patterns

### Creating a Receipt

```python
from rig.domain.receipt_envelope import (
    ReceiptEnvelope, ReceiptActor, ReceiptSubject, ReceiptDecision
)

actor = ReceiptActor.cli()
subject = ReceiptSubject.workspace("my-workspace")
decision = ReceiptDecision.allowed("decision-id", "Allowed for reason")

envelope = ReceiptEnvelope(
    schema_version="rig.receipt_envelope.v1",
    receipt_id="unique-id",
    receipt_type="workspace_create",
    authority_level="authoritative",
    advisory_only=False,
    created_at=utc_now(),
    actor=actor,
    subject=subject,
    decision=decision,
    inputs=[],
    outputs=[],
    evidence=[],
    related_receipt_ids=[],
    related_audit_event_ids=[],
    summary="Human-readable summary",
)
```

### Replaying Workspace State

```python
from rig.domain.replay import replay_workspace_from_fs, load_replay_events_from_fs
from pathlib import Path

# Load and replay
repo_root = Path(".")
replay_result = replay_workspace_from_fs(repo_root, "workspace-id")

# Check results
assert replay_result.is_complete
assert not replay_result.has_conflicts
assert not replay_result.has_findings
```

### Building a Projection

```python
from rig.domain.replay import build_replay_projection

# Get projection from replay result
projection = build_replay_projection(replay_result, frame_index=None)

# Use projection in UI - SAFE because it's derived, not authoritative
print(f"Status: {projection['workspace_status']}")
```

## Summary

This architecture navigation map provides a **quick orientation** to Rig's system topology. For detailed understanding of any component, follow the navigation paths above to the relevant deep-dive documents.

**Remember:**
- **Rig is the authority** — Not models, not users
- **Deny by default** — All intents must be explicitly allowed
- **Everything leaves a receipt** — Immutable evidence is mandatory
- **Projections are derived** — UI never infers authority
- **Replay is deterministic** — Same inputs always produce same outputs
- **Trust never increases** — When moving from receipts → replay → projections → UI
