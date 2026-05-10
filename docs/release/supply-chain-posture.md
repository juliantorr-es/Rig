# Supply Chain Posture

> **Rig's dependency trust philosophy: Minimal, auditable, reproducible.**

This document describes Rig's supply chain security posture, dependency philosophy, and trust boundaries. It is intended for contributors, users, and security auditors who need to understand what Rig depends on and why.

## Executive Summary

| Aspect | Status |
|--------|--------|
| **Core governance** | Zero external SaaS dependencies |
| **Dependency count** | 6 base + optional extras |
| **License policy** | Permissive only (MIT, BSD, Apache 2.0) |
| ** dependency sources** | PyPI only |
| **Network requirements** | None for core governance |
| **Reproducibility** | Deterministic builds from source |

**Core claim:** Rig's governance engine requires zero network access and zero SaaS dependencies to function. All trust derives from local receipts and cryptographic validation.

---

## Dependency Philosophy

### Core Principles

1. **Minimal Dependencies**
   - Only include what is absolutely necessary for core functionality
   - Each dependency must justify its existence
   - Prefer fewer, well-maintained packages over many specialized ones

2. **Trust But Verify**
   - All dependencies are auditable
   - All dependencies are scanned for known vulnerabilities
   - All dependencies use pinned minimum versions for reproducibility

3. **No SaaS in Core Governance**
   - Core governance (receipts, replay, validation, projections) has ZERO cloud dependencies
   - Optional features (UI, ML) may have external dependencies, but governance is isolated
   - The `rig` CLI works without any network access

4. **Reproducible Builds**
   - Same source + same dependencies = same artifacts
   - No dynamic code generation
   - No runtime code fetching

### Dependency Categories

| Category | Purpose | Trust Level | Update Cadence |
|----------|---------|-------------|----------------|
| **Base** | Core governance functionality | Highest | Security only (during alpha) |
| **UI** | Windowed user interface | High | Security only |
| **Dev** | Development tooling | Medium | As needed |
| **Docs** | Documentation generation | Low | As needed |
| **ML** | Machine learning integrations | Low | As needed |
| **Legacy TUI** | Deprecated textual interface | Low | Minimal |

### Third-Party Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│                        TRUST BOUNDARY                           │
│              Rig Core Governance (Zero External)               │
│              ├── Receipts (local, cryptographic)                │
│              ├── Audit Events (local, immutable)               │
│              ├── Replay Engine (deterministic, offline)         │
│              ├── Projections (derived, never authoritative)     │
│              └── Governance Engine (deny-by-default)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   OPTIONAL EXTERNAL BOUNDARY                   │
│              (User-initiated, explicitly allowed)                │
│              ├── UI Web Server (aiohttp, optional)             │
│              ├── Native Window (pywebview, optional)           │
│              └── ML Providers (user-initiated only)            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                      NETWORK ACCESS (User-Directed)
```

**Invariant:** Core governance NEVER initiates network requests. All network access must be explicitly user-initiated and goes through governance gates.

## Dependency Inventory

### Base Dependencies (Always Installed)

These are required for Rig to function at all. They are included in every installation.

| Package | Version | Purpose | License | Source | Security Notes |
|---------|---------|---------|---------|--------|----------------|
| `jsonschema` | >=4.23 | JSON schema validation for receipts | MIT | PyPI | Critical for receipt validation |
| `duckdb` | >=1.0.0 | Embedded analytical database for audit events | MIT | PyPI | Embedded, zero network |
| `PyYAML` | >=6.0 | YAML parsing for configuration | MIT | PyPI | Well-maintained, widely used |
| `rich` | >=13.7 | Rich terminal output | MIT | PyPI | Terminal-only, no network |
| `psutil` | >=5.9 | Process and system monitoring | BSD | PyPI | Read-only system access |
| `tomli-w` | >=1.0.0 | TOML parsing (Python 3.11+ compatible) | MIT | PyPI | Pure Python, minimal surface |

**Base dependency trust summary:** All base dependencies are:
- Referenced from PyPI (Python Package Index)
- Licensed under permissive licenses (MIT, BSD)
- Zero network dependencies in their core functionality
- Widely used and actively maintained
- Scanned for known vulnerabilities

### UI Dependencies (Optional)

Required only for the windowed UI (`rig ui` command). Core governance works without these.

| Package | Version | Purpose | License | Source | Security Notes |
|---------|---------|---------|---------|--------|----------------|
| `aiohttp` | >=3.9 | Async HTTP for WebSocket server | Apache 2.0 | PyPI | Optional, user-initiated only |
| `pywebview` | >=5.3 | Native window for web UI | BSD | PyPI | Optional, local-only |

**UI dependency trust summary:**
- Both are optional and only loaded when UI functionality is used
- The WebSocket server is local-only (binds to localhost)
- No automatic network requests

### Development Dependencies (Optional)

Required only for development and testing. Not needed for runtime.

| Package | Version | Purpose | License | Source | Security Notes |
|---------|---------|---------|---------|--------|----------------|
| `pytest` | >=8.0 | Test framework | MIT | PyPI | Runtime test execution |
| `pytest-asyncio` | >=0.23 | Async test support | Apache 2.0 | PyPI | Test support only |
| `build` | >=1.2 | Package building | MIT | PyPI | Build-time only |
| `pyright` | >=1.1 | Static type checking | MIT | PyPI | Build-time only |
| `ruff` | >=0.6 | Linting | MIT | PyPI | Build-time only |

**Development dependency trust summary:**
- Only used during development and CI
- Not included in runtime dependencies
- Run in isolated CI environments

### Documentation Dependencies (Optional)

Required only for building documentation.

| Package | Version | Purpose | License | Source |
|---------|---------|---------|---------|--------|
| `mkdocs` | >=1.6 | Documentation site generator | BSD | PyPI |
| `mkdocs-material` | >=9.5 | Material theme for mkdocs | MIT | PyPI |

### ML Dependencies (Optional, Platform-Specific)

Required only for ML features. macOS-only with platform markers.

| Package | Version | Purpose | License | Source | Platform |
|---------|---------|---------|---------|--------|----------|
| `mlx` | >=0.20 | Apple ML framework | MIT | PyPI | macOS ARM64 only |
| `llama-cpp-python` | >=0.3.0 | LLM inference | MIT | PyPI | macOS + others |

**ML dependency trust summary:**
- Only installed on supported platforms
- Never loaded for core governance
- Treated as untrusted (model output goes through governance)

### Legacy TUI Dependencies (Optional, Deprecated)

Required only for the deprecated Textual TUI (use `rig ui` instead).

| Package | Version | Purpose | License | Source | Status |
|---------|---------|---------|---------|--------|--------|
| `textual` | >=0.76 | Rich TUI framework | MIT | PyPI | Deprecated |
| `textual-serve` | >=1.1.0 | Web server for Textual | MIT | PyPI | Deprecated |

**Legacy TUI trust summary:**
- Deprecated in favor of `rig ui`
- Will be removed in a future version
- Not recommended for new development

## Package Integrity Philosophy

### What We Guarantee

1. **Deterministic Installs**
   - Same `pyproject.toml` + same Python version = reproducible environment
   - No lock files by design (version specifiers provide reproducibility)
   - All dependencies use `>=` version pins for minimum compatibility

2. **Immutable Artifacts**
   - Source distributions include exact source at build time
   - Built wheels are reproducible from source
   - No code is downloaded at runtime

3. **No Hidden Code**
   - No `eval()`, `exec()`, `__import__()` in Rig codebase
   - No dynamic code loading from strings
   - All imports are explicit and static

### What We Do NOT Guarantee

1. **Dependency Security**
   - We rely on PyPI's security for package distribution
   - We scan for known vulnerabilities but cannot prevent zero-days
   - We review dependencies but cannot audit all transitive dependencies

2. **Upstream Integrity**
   - We cannot guarantee that PyPI packages have not been compromised
   - We cannot guarantee that upstream maintainers have not been compromised
   - We monitor but cannot prevent supply chain attacks

3. **Platform Compatibility**
   - We primarily test on macOS (Apple Silicon)
   - Other platforms may have different dependency behavior
   - Platform-specific issues may occur

## Dependency Audit Process

### Manual Auditing

To audit Rig's dependencies manually:

```bash
# List all installed packages
python -m pip list

# List with versions (freeze format)
python -m pip freeze

# Audit for known vulnerabilities (requires pip-audit)
python -m pip install pip-audit
pip-audit --vulnerability-service-uri https://api.osv.dev/v1/query

# Check dependency tree
python -m pipdeptree
```

### Automated Scanning in CI

Rig's CI automatically:
1. Scans Python dependencies using `pip-audit` (weekly on main)
2. Scans GitHub Actions for vulnerabilities (weekly on main)
3. Uses Dependabot for automated security updates

See [.github/dependabot.yml](../.github/dependabot.yml) for configuration.

### Dependabot Configuration

| Package Ecosystem | Update Type | Frequency | Review |
|-------------------|-------------|-----------|--------|
| GitHub Actions | Security + Version | Weekly | Required |
| pip (production) | Security only | Daily | Required |
| pip (development) | Security only | Weekly | Required |

**Why security-only during alpha?**
- Version updates may introduce breaking changes
- We manually control when to upgrade dependencies
- Security updates are critical and should be applied promptly

### Pre-Merge Validation

Before merging any dependency update, maintainers must verify:

```bash
# Run full validation
bash scripts/check.sh

# Run core test suites
python -m pytest tests/test_replay.py -v
python -m pytest tests/test_integrity.py -v
python -m pytest tests/test_projection_contracts.py -v
python -m pytest tests/test_ui_frontend_logic.py -v

# Verify governance integrity
python -m rig doctor all
python -m rig replay timeline --json

# Verify install still works
python -m pip install -e ".[ui,dev]" --force-reinstall
```

## Action Pinning Expectations

### GitHub Actions

All GitHub Actions in Rig workflows are pinned to specific versions:

| Action | Current Version | Pinning Type | Rationale |
|--------|-----------------|--------------|-----------|
| `actions/checkout` | v4 | Major version | Stable, widely used |
| `actions/setup-python` | v5 | Major version | Stable, widely used |

**Pinning philosophy:**
- Use major version pins (`@v4`, `@v5`) for stability
- Avoid floating tags (`@main`, `@master`)
- Update pins when security issues are found
- Test pin updates before merging

### Python Package Pinning

**Production dependencies:**
- Use `>=` minimum version pins
- Specify exact minimum versions that are known to work
- Update only for security or compatibility

**Development dependencies:**
- Same approach as production
- Can be more flexible during active development

## Explicit Dependency Trust Notes

### What Rig Trusts

| Component | Trust Level | Rationale |
|-----------|-------------|-----------|
| Python standard library | High | Built into Python, widely audited |
| PyPI (pypi.org) | Medium-High | Official Python package repository |
| GitHub Actions | Medium | Microsoft-operated, widely used |
| GitHub (source) | Medium-High | Microsoft-operated, widely used |

### What Rig Does NOT Trust

| Component | Trust Level | Rationale |
|-----------|-------------|-----------|
| External AI providers | Low | Untrusted output, requires validation |
| Network responses | None | Never used in core governance |
| User input | None | Always validated, never executed directly |
| Model output | None | Always treated as untrusted |

### Trust Hierarchy

```
Trust Level 0 (Highest): Canonical Evidence
├── Git history (local, immutable)
├── Receipt chains (cryptographically signed)
└── Audit events (append-only, hash-linked)

Trust Level 1: Derived State
├── Replay results (deterministic from Level 0)
├── Workspace state (derived from receipts)
└── Validation results (computed from state)

Trust Level 2: Projections
├── UI display data (from Level 1)
├── Control authorizations (from governance)
└── Widget state (derived, never authoritative)

Trust Level 3 (Lowest): User Interface
└── Frontend rendering (dumb, from Level 2)

External/Network: NEVER TRUSTED
└── All network input treated as malicious
```

## Update Cadence

| Dependency Type | Update Frequency | Process |
|----------------|------------------|---------|
| Security patches | Immediate | Automated via Dependabot + manual review |
| Bug fixes | As needed | Manual review + validation |
| Feature updates | Infrequent | Manual review + extensive validation |
| Major versions | Rare | Requires compatibility testing |

**Alpha phase (0.1.0a1):** Minimal updates to reduce disruption while maintaining security.

## Supply Chain Limitations

### Known Gaps

| Gap | Impact | Mitigation |
|-----|--------|------------|
| No SBOM generation | Cannot automatically verify all transitive dependencies | Manual review of direct deps |
| No code signing | Cannot cryptographically verify Rig releases | Rely on GitHub's release verification |
| No hardware tokens | Cannot use HSM for key management | Software-only keys with workspace isolation |
| CI not on multiple platforms | Platform-specific issues may not be caught | Test on macOS primary, others secondary |

### Future Enhancements (Not Implemented)

These are **not currently implemented** but may be added in the future:

| Enhancement | Status | Priority | Blocked By |
|------------|--------|----------|-----------|
| SBOM generation | Paused | Low | Not critical for current use case |
| Code signing (GPG) | Paused | Low | Requires key management infrastructure |
| Multiple CI platforms | Paused | Medium | Resource constraints |
| Dependency lock files | Paused | Low | Philosophy: use version pins instead |
| Reproducible build verification | Paused | Medium | Requires build environment standardization |

## Local Authority Boundaries

Rig's security model is **local-first**:

### What Stays Local

- All receipts and audit events
- All workspace state
- All Git history
- All file contents
- All governance decisions

### What May Be Shared (User-Controlled)

- Debug bundles (explicitly created, redacted)
- Replay exports (explicit `--json` flag)
- Documentation (read-only, no sensitive data)

### What Is Never Shared

- Tokens, API keys, credentials
- Prompt content
- Model responses (raw)
- System information (hostname, IP, etc.)

## Verification Commands

### Verify Current Dependencies

```bash
# List all dependencies
python -m pip list

# Audit for vulnerabilities
python -m pip install pip-audit
pip-audit

# Build and verify artifacts
bash scripts/verify_release_artifacts.sh

# Fresh clone verification
bash scripts/verify_fresh_clone.sh --fast
```

### Verify Reproducibility

```bash
# Build source distribution
python -m build --sdist

# Build wheel
python -m build --wheel

# Install from built artifacts
python -m pip install dist/rig-*.tar.gz

# Verify it works
python -m rig doctor all
```

## Summary

Rig maintains a **strong supply chain posture** by:

1. ✅ **Minimal dependencies** - Only 6 base packages for core governance
2. ✅ **Zero SaaS in core** - Governance works without any cloud services
3. ✅ **Permissive licenses only** - MIT, BSD, Apache 2.0
4. ✅ **No dynamic code** - No eval, exec, or runtime imports
5. ✅ **Automated vulnerability scanning** - pip-audit + Dependabot
6. ✅ **Reproducible builds** - Deterministic from source
7. ✅ **Action pinning** - Pinned GitHub Actions versions
8. ✅ **Local-first** - All trust derives from local evidence

**Remaining gaps:** SBOM, code signing, multi-platform CI - these are acknowledged but not critical for Rig's current threat model.

**Bottom line:** Rig's governance engine requires zero network access and zero external trust. All authority derives from local receipts that are cryptographically verifiable.

---

*Document version: 1.0*
*Last updated: May 2025*
*Status: Active (aligned with Rig 0.1.0a1)*
