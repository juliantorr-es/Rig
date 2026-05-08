# Versioning Policy

> **Stable contracts, predictable changes, governance-first.**

This document defines Rig's versioning policy, compatibility guarantees, and release expectations. It is intended for users, contributors, and maintainers.

## Version Format

Rig uses **Semantic Versioning 2.0.0** with alpha/beta pre-release identifiers.

```
<MAJOR>.<MINOR>.<PATCH>[-<PRERELEASE>][+<BUILDMETA>]

Examples:
  0.1.0a1    - Alpha 1 of version 0.1.0
  0.1.0b2    - Beta 2 of version 0.1.0
  0.2.0      - Stable release 0.2.0
  1.0.0      - Major release 1.0.0
```

### Current Version

The current version is defined in `pyproject.toml`:

```toml
[project]
version = "0.1.0a1"
```

## Version Types

| Version | Format | Meaning | Stability |
|---------|--------|---------|------------|
| Alpha | `0.Y.Z-aN` | Early development | Unstable, breaking changes expected |
| Beta | `0.Y.0-bN` | Feature complete | Mostly stable, API close to final |
| Stable | `X.Y.0` | Production ready | Stable, breaking changes only in MAJOR |

### Current State: Alpha

Rig is currently in **Alpha** (`0.1.0a1`). This means:

- **Unstable API** — Breaking changes may occur between releases
- **Experimental features** — Not all features are finalized
- **Not production ready** — Use at your own risk
- **Feedback welcome** — Active development, contributions encouraged

## Compatibility Guarantees

Rig provides different levels of compatibility guarantees depending on the component:

### Receipt Schema (HIGHEST PRIORITY)

**Guarantee:** **No breaking changes without MAJOR version bump.**

| Change Type | Allowed In | Notes |
|-------------|------------|-------|
| Add optional field | PATCH | New field with default value |
| Add required field | MAJOR | Breaking change |
| Remove field | MAJOR | Breaking change |
| Change field type | MAJOR | Breaking change |
| Change field meaning | MAJOR | Breaking change |

**Rationale:** Receipts are the foundation of Rig's trust model. Breaking receipt schema changes would:
- Prevent replay of existing receipts
- Break integrity validation
- Violate the "replayable from receipts alone" guarantee

### Projection Contracts (HIGH PRIORITY)

**Guarantee:** **No breaking changes without MAJOR version bump.**

| Change Type | Allowed In | Notes |
|-------------|------------|-------|
| Add optional field | PATCH | New field with default/null |
| Add required field | MAJOR | Breaking change |
| Remove field | MAJOR | Breaking change |
| Change field type | MAJOR | Breaking change |
| Change derivation logic | MAJOR | May change outputs |

**Rationale:** Projections are the contract between backend and frontend. Breaking changes would:
- Break existing UI widgets
- Violate projection contract expectations
- Require coordinated frontend/backend updates

### CLI Interface (MEDIUM PRIORITY)

**Guarantee:** **No breaking changes without MINOR version bump (for now).**

| Change Type | Allowed In | Notes |
|-------------|------------|-------|
| Add command | PATCH | New subcommand |
| Add flag | PATCH | New optional flag |
| Add required argument | MINOR | Breaking change |
| Remove command | MINOR | Breaking change |
| Remove flag | MINOR | Breaking change |
| Change flag meaning | MINOR | Breaking change |
| Change output format | MINOR | Breaking change |

**Note:** During Alpha, CLI stability is lower. Breaking changes may occur in MINOR releases.

### Python API (LOW PRIORITY)

**Guarantee:** **No stability guarantees during Alpha.**

Rig's Python API (importing `rig` modules directly) is **not considered stable** during Alpha. Changes may occur in any release.

To use Rig programmatically:
- Use the CLI (`python -m rig`)
- Parse JSON output (`--json` flag)
- Do not import `rig` modules directly (unless you accept instability risk)

### Governance Behavior (HIGHEST PRIORITY)

**Guarantee:** **Core governance behavior is immutable.**

| Aspect | Guarantee | Notes |
|--------|-----------|-------|
| Deny-by-default | Never changes | Core doctrine |
| No auto-apply | Never changes | Core doctrine |
| Execution in isolation | Never changes | Core doctrine |
| Durable evidence | Never changes | Core doctrine |
| Replayable history | Never changes | Core doctrine |
| Projection-only UI | Never changes | Core doctrine |

**Rationale:** These are Rig's **immutable** core principles. Changing them would fundamentally alter what Rig is.

## Release Types

### Alpha Releases (`0.Y.Z-aN`)

**Purpose:** Early development, experimental features, rapid iteration.

**Expectations:**
- Breaking changes may occur between releases
- API is not stable
- New features may be added or removed
- Bugs are expected
- Not recommended for production use

**Example:** `0.1.0a1`, `0.1.0a2`, `0.2.0a1`

**When to use:**
- Evaluating Rig
- Contributing to Rig
- Testing new features
- Providing feedback

### Beta Releases (`0.Y.0-bN`)

**Purpose:** Feature complete, API freeze, testing before stable release.

**Expectations:**
- No new features (only bug fixes)
- API is frozen (no breaking changes)
- Fewer bugs than Alpha
- Suitable for testing before production

**Example:** `0.1.0b1`, `0.1.0b2`

**When to use:**
- Testing before production deployment
- Validating compatibility
- Final integration testing

### Stable Releases (`X.Y.0`)

**Purpose:** Production ready, long-term support.

**Expectations:**
- Production ready
- Long-term support
- Breaking changes only in MAJOR releases
- Security updates for all supported versions

**Example:** `0.1.0`, `0.2.0`, `1.0.0`

**When to use:**
- Production deployment
- Long-term projects
- When stability is required

## Stability Classifications

Each component has a stability classification:

| Component | Classification | Stability | Breaking Changes |
|-----------|---------------|-----------|------------------|
| Receipt Schema | Immutable | Highest | MAJOR only |
| Projection Contracts | Stable | High | MAJOR only |
| Governance Engine | Stable | High | MAJOR only |
| Replay System | Stable | High | MAJOR only |
| Audit System | Stable | High | MAJOR only |
| Workspace Management | Evolving | Medium | MINOR only |
| CLI Interface | Evolving | Medium | MINOR only |
| Python API | Experimental | Low | Any release |
| ML Integration | Experimental | Low | Any release |
| UI | Experimental | Low | Any release |

## Supported Platforms

### Officially Supported

| Platform | Architecture | Python | Support Level |
|----------|--------------|--------|---------------|
| macOS | Apple Silicon (ARM64) | 3.14+ | Full |
| macOS | Intel (x86_64) | 3.14+ | Full |

### Community Supported

| Platform | Architecture | Python | Support Level |
|----------|--------------|--------|---------------|
| Linux | x86_64 | 3.14+ | Best effort |
| Linux | ARM64 | 3.14+ | Best effort |
| Windows | x86_64 | 3.14+ | Best effort |

**Note:** Core governance is platform-independent. Only UI and some ML features may have platform limitations.

### Unsupported

- Python < 3.14
- 32-bit architectures
- Non-Git version control systems

## Supported Workflows

### Fully Supported

| Workflow | Support Level | Notes |
|----------|---------------|-------|
| Local development | Full | Primary use case |
| Git worktree isolation | Full | Core feature |
| Receipt-based orchestration | Full | Core feature |
| CLI usage | Full | Primary interface |
| JSON output (`--json`) | Full | For automation |
| Single repository | Full | One Rig per repo |

### Community Supported

| Workflow | Support Level | Notes |
|----------|---------------|-------|
| Multiple workspaces | Best effort | Per task |
| CI/CD integration | Best effort | Via CLI |
| Containerized usage | Best effort | Docker, etc. |
| Windows usage | Best effort | May have limitations |

### Explicitly Unsupported

| Workflow | Status | Reason |
|----------|--------|--------|
| Auto-apply without review | ❌ Unsupported | Violates governance |
| Direct main branch mutation | ❌ Unsupported | Violates governance |
| Cloud-only usage | ❌ Unsupported | Local-first only |
| SaaS usage without source availability | ❌ Unsupported | AGPL violation |
| Real-time collaboration | ❌ Unsupported | Not a design goal |
| Shared worktrees | ❌ Unsupported | Isolation required |

## Release Cadence

### Current (Alpha Phase)

| Release Type | Frequency | Process |
|--------------|-----------|---------|
| Alpha | As needed | Feature development |
| Beta | Before stable | Feature freeze, testing |
| Stable | When ready | Full validation |

### Planned (Post-Alpha)

| Release Type | Frequency | Process |
|--------------|-----------|---------|
| Patch | As needed | Bug fixes only |
| Minor | ~Monthly | New features, improvements |
| Major | ~6 months | Breaking changes, major features |

**Note:** These are targets, not guarantees. Releases will be made when ready, not on a schedule.

## Compatibility Matrix

### Python Version Compatibility

| Rig Version | Min Python | Max Python | Notes |
|-------------|------------|------------|-------|
| 0.1.0a1 | 3.14.0 | 3.14.x | First Alpha |
| 0.1.0 | 3.14.0 | 3.15.x | Stable |
| Future | 3.14+ | Latest | TBD |

### Dependency Version Compatibility

Rig uses **minimum version specifiers** (`>=`) for dependencies. This means:

- **Newer patch versions** are supported (e.g., `jsonschema>=4.23` supports 4.23.1, 4.23.2, etc.)
- **Newer minor versions** are supported (e.g., `rich>=13.7` supports 13.8, 13.9, etc.)
- **Breaking changes** in dependencies may break Rig (but this is rare for our chosen dependencies)

For exact reproducibility, pin your dependencies:

```bash
# Create requirements.txt with exact versions
python -m pip freeze > requirements.txt

# Install from exact versions
python -m pip install -r requirements.txt
```

## Migration Policy

### Breaking Changes

When breaking changes are introduced:

1. **Announced in advance** — Breaking changes are documented in release notes
2. **Migration guide provided** — Step-by-step migration instructions
3. **Grace period** — Old behavior may be deprecated but not removed immediately
4. **Validation required** — All migration paths are tested

### Deprecation Policy

1. **Warning period** — Deprecated features emit warnings for at least one MINOR release
2. **Documentation** — Deprecation notices in docs and changelog
3. **Removal** — Deprecated features removed in next MAJOR release
4. **Exception** — Security issues may require immediate removal

### End-of-Life

When a feature reaches EOL:

1. **Announcement** — 30-day notice before removal
2. **Documentation** — Migration guidance provided
3. **Final release** — Last release with the feature
4. **Removal** — Feature removed in next release

## Receipt/Projection Stability

### Receipt Schema Stability

| Version | Schema Version | Notes |
|---------|----------------|-------|
| 0.1.0a1 | v1.0 | Initial schema |

**Current schema version:** v1.0

**Future changes:**
- Schema version will be bumped for any breaking change
- Old schema versions will be supported for replay
- Migration tools will be provided if needed

### Projection Contract Stability

| Contract | Version | Notes |
|----------|---------|-------|
| workspace_status | v1.0 | Initial |
| receipt_timeline | v1.0 | Initial |
| intent_status | v1.0 | Initial |
| validation_findings | v1.0 | Initial |
| audit_trail | v1.0 | Initial |

**Current contract versions:** v1.0 for all

**Future changes:**
- Contract version will be bumped for any breaking change
- Old contract versions will be supported for backwards compatibility
- New projections may be added without breaking existing ones

## Telemetry Stability

**Current state:** No telemetry is implemented.

**Future:** If telemetry is added:
- Will be opt-in only
- Will be documented in [SECURITY.md](../../SECURITY.md)
- Will follow [telemetry transparency principles](../../docs/telemetry.md)
- Will not affect core governance

## Local Inference Limitations

Rig's ML integration (via `rig run --provider ml`) has the following limitations:

### Supported Models

- **mlx** (macOS ARM64 only): Apple's ML framework
- **llama-cpp-python**: LLM inference library

### Platform Limitations

| Platform | ML Support | Notes |
|----------|------------|-------|
| macOS ARM64 | Full | Native support |
| macOS x86_64 | Partial | May work, not tested |
| Linux x86_64 | Partial | May work, not tested |
| Linux ARM64 | Partial | May work, not tested |
| Windows | None | Not supported |

### Model Limitations

- **Model loading** — Rig does not bundle models; you must provide your own
- **Memory usage** — Large models may exceed available memory
- **Inference speed** — Depends on hardware and model size
- **Model compatibility** — Not all models are supported by all backends

### Provider Limitations

- **External providers** — You must configure your own provider connections
- **API keys** — You must provide your own API keys
- **Rate limits** — Subject to provider rate limits
- **Data privacy** — Subject to provider privacy policies

**Note:** Core governance does **not** depend on ML. The `--provider` flag is optional, and Rig works perfectly without ML providers.

## Roadmap Boundaries

Rig has explicit **non-goals** that will not be implemented:

| Feature | Status | Reason |
|---------|--------|--------|
| Hosted SaaS version | ❌ Won't implement | Local-first only |
| OAuth integration | ❌ Won't implement | Local-first only |
| Real-time collaboration | ❌ Won't implement | Not a design goal |
| Database storage | ❌ Won't implement | Local files only |
| Web-based UI (hosted) | ❌ Won't implement | Windowed UI only |
| Cloud sync | ❌ Won't implement | Local-first only |
| Multi-user | ❌ Won't implement | Single-user only |

### Future Capabilities (Maybe)

These are **not roadmap commitments**, but potential future directions:

| Feature | Status | Notes |
|---------|--------|-------|
| pip installable packages | ⏸️ Paused | PyPI publishing |
| CBCC integration | ⏸️ Paused | GitHub integration |
| Outgate telemetry | ⏸️ Paused | Opt-in, inspectable |
| Documentation fetching | ⏸️ Paused | Cached, opt-in |
| Local model serving | ⏸️ Paused | Optional, local-only |

## Version Number Meaning

| Position | Meaning | Example |
|----------|---------|---------|
| MAJOR | Breaking changes to receipt schema, governance, or projections | 1.0.0 |
| MINOR | Backwards-compatible new features | 0.2.0 |
| PATCH | Bug fixes, documentation, non-breaking changes | 0.1.1 |
| Pre-release | Alpha/Beta identifier | 0.1.0a1, 0.1.0b1 |

## Summary

| Aspect | Guarantee |
|--------|-----------|
| **Receipt schema** | No breaking changes without MAJOR |
| **Projection contracts** | No breaking changes without MAJOR |
| **Governance behavior** | Immutable (never changes) |
| **CLI interface** | No breaking changes without MINOR (alpha) |
| **Python API** | No stability guarantees (alpha) |
| **Platform support** | macOS first, others best effort |
| **Workflow support** | Local development fully supported |

**Rig's compatibility promise:**
> "Receipts created today will replay correctly on any future Rig version with the same MAJOR version number."

**Rig's stability promise:**
> "Core governance behavior (deny-by-default, no auto-apply, execution in isolation, durable evidence, replayable history, projection-only UI) will never change."

---

**Document Version:** 1.0
**Last Updated:** May 2025
**Current Rig Version:** 0.1.0a1
