# Security Policy

> **Rig is local-first. Trust boundaries are explicit. Governance applies to security too.**

This document describes Rig's security posture, threat model, and vulnerability reporting process. It is intended for users, contributors, and security researchers.

## Threat Model

Rig is designed with the following threat assumptions:

### In-Scope Threats

These threats are actively mitigated by Rig's design:

| Threat | Mitigation | Effectiveness |
|--------|------------|---------------|
| **Malicious repository content** | Execution in isolated Git worktrees, receipt-based orchestration | High |
| **Untrusted model output** | Deny-by-default governance, explicit review gates, no auto-apply | High |
| **Compromised local client** | Cryptographic receipt chains, replay validation, immutable audit trail | High |
| **State corruption** | Durable receipts, deterministic replay, continuity validation | High |
| **Authority escalation** | Governance Engine deny-by-default, explicit gate checks | High |

### Out-of-Scope Threats

These threats are explicitly **not** addressed by Rig's design:

| Threat | Rationale |
|--------|-----------|
| **Physical access to machine** | Local-first philosophy: if an attacker has physical access, all bets are off |
| **OS-level compromise** | Rig runs as a user-space application; OS compromise is beyond its scope |
| **Supply chain attacks on PyPI** | We rely on PyPI's security; mitigations are at the package manager level |
| **Side-channel attacks** | Not addressed by application-level controls |
| **Denial of service** | Local resource exhaustion is a user responsibility |

### Trust Boundaries

Rig enforces explicit trust boundaries between components:

```
┌─────────────────────────────────────────────────────────────┐
│                    TRUST LEVEL 0 (Highest)                     │
│         Canonical receipts, audit events, Git history         │
│         Immutable, cryptographically linked, never deleted    │
├─────────────────────────────────────────────────────────────┤
│                    TRUST LEVEL 1                               │
│         Replay results derived deterministically from L0     │
│         Validated against continuity and integrity rules      │
├─────────────────────────────────────────────────────────────┤
│                    TRUST LEVEL 2                               │
│         Projections derived from L1, backend-authored        │
│         Contains only display data, no authority inference   │
├─────────────────────────────────────────────────────────────┤
│                    TRUST LEVEL 3 (Lowest)                      │
│         Frontend rendering from L2 projections               │
│         dumb renderer, no state invention                     │
└─────────────────────────────────────────────────────────────┘

Invariant: Trust NEVER increases when moving down levels.
```

**Core Principle:** Trust decreases as data moves from canonical evidence (Level 0) to user-facing UI (Level 3). The UI must never infer authority; it only displays backend-authored projections.

## Local-First Trust Philosophy

Rig is **local-first but online-aware**. This means:

### What Stays Local (Never Leaves the Machine)

| Category | Data Type | Guarantee |
|----------|-----------|-----------|
| **Receipts** | All receipt envelopes, audit events | Never exported |
| **Git history** | Repository content, commit messages | Never exported |
| **Workspace state** | Worktree contents, intent states | Never exported |
| **Validation results** | Test outputs, doctor findings | Never exported |
| **Configuration** | `pyproject.toml`, Rig config files | Never exported |
| **File contents** | Source code, documentation | Never exported |

### What May Be Inspected (Optional, User-Controlled)

| Category | Data Type | When | User Control |
|----------|-----------|------|--------------|
| **Debug bundles** | Redacted support archives | Explicit `rig debug bundle` command | User must explicitly run command |
| **Replay exports** | Replay timeline JSON | Explicit `--json` flag | User must explicitly request |
| **Telemetry** | Usage metrics (if enabled) | Future capability | Opt-in only, disabled by default |

### What is Explicitly Forbidden

| Category | Data Type | Status |
|----------|-----------|--------|
| **Tokens/Secrets** | API keys, credentials | NEVER exported, always redacted |
| **Prompt content** | User prompts to models | NEVER exported |
| **Model responses** | Raw model output | NEVER exported |
| **System information** | Hostname, IP addresses | Redacted in debug bundles |

## Telemetry and Data Export Philosophy

### Current State (v0.1.0a1)

**Rig currently exports NO telemetry by default.** There is no automatic data collection, no phone-home behavior, and no network calls made by core governance functionality.

### Future "Outgate" Philosophy

Rig may introduce **opt-in, inspectable outbound data** in the future. If implemented, it will follow these principles:

1. **Opt-in by default** — Telemetry disabled unless explicitly enabled
2. **Inspectable** — All outbound data visible to user before export
3. **Redacted by default** — Sensitive data (tokens, paths, content) always redacted
4. **Minimal** — Only what's necessary for the stated purpose
5. **User-controlled** — Can be disabled at any time
6. **Documented** — Full transparency about what's collected and why

### Outbound Data Categories

| Category | Status | Description |
|----------|--------|-------------|
| Usage metrics | Paused | Aggregate command usage, no content |
| Error reports | Paused | Stack traces, environment info (redacted) |
| Update checks | Paused | Version check against GitHub releases |
| Documentation fetch | Paused | Fetch docs from GitHub (cached locally) |

**Current reality:** None of these are implemented. Rig is currently offline-only for core governance.

## Network Behavior

### Core Governance (No Network Required)

These operations **never** make network requests:

- Workspace creation, execution, validation
- Receipt creation, signing, validation
- Replay (from local receipts)
- Doctor commands
- Projection generation
- Governance Engine checks
- All test suites

### Optional Network Operations

These operations **may** make network requests (user-initiated only):

| Operation | Trigger | Purpose | Data Sent |
|-----------|---------|---------|-----------|
| `rig init` (future) | Explicit command | Fetch templates | None (local cache) |
| `rig update` (future) | Explicit command | Check for updates | Version info only |
| doc fetching (future) | Explicit or cache miss | Fetch latest docs | None |

### Provider Integrations (External)

Rig can integrate with external AI providers (e.g., through `rig run --provider`). These integrations:

1. Are **explicitly user-initiated** — No automatic calls
2. Send **only what the user provides** — No additional context
3. Receive **untrusted output** — Treated as malicious until validated
4. **Never auto-apply** — All output goes through governance gates

**Provider communications are NOT Rig's telemetry.** They are user-directed requests to external services, and Rig treats all provider output as untrusted.

## Vulnerability Reporting

### Reporting a Security Issue

**DO NOT create a public GitHub issue for security vulnerabilities.** Instead:

1. **Email directly** to security contact (to be established)
2. **Or use GitHub Security Advisories** (private reporting)
3. **Include:**
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (Python version, OS, Rig version)
   - Impact assessment

### Vulnerability Response Process

| Phase | Timeframe | Description |
|-------|-----------|-------------|
| **Triage** | 24 hours | Acknowledge receipt, assess severity |
| **Verification** | 48 hours | Reproduce issue, confirm vulnerability |
| **Fix** | Depends on severity | Develop and test fix |
| **Disclosure** | Coordinated | Release fix, publish advisory |

### Severity Classification

| Severity | Criteria | Example |
|----------|----------|---------|
| **Critical** | Remote code execution, privilege escalation | Receipt forgery, governance bypass |
| **High** | Data exfiltration, unauthorized access | Token leakage in debug output |
| **Medium** | Denial of service, data corruption | Malformed receipt causing crash |
| **Low** | Information disclosure (non-sensitive) | Version info leakage |

## Supported Versions

| Version | Support Status | Security Updates |
|---------|----------------|------------------|
| 0.1.0a1 (main) | Active development | Yes |
| < 0.1.0a1 | Not supported | No |

**Policy:** Only the latest version on `main` receives security updates. There are no LTS (Long-Term Support) releases at this time.

### End-of-Life

There is currently no formal EOL policy. When established, it will include:

- 30-day notice for breaking changes
- Migration guidance
- Final release with security patches only

## Supply Chain Security

### Dependency Trust

Rig follows these supply chain principles:

1. **Minimal dependencies** — Only what's necessary
2. **Permissive licenses only** — MIT, BSD, Apache 2.0
3. **No SaaS in core** — Core governance has zero cloud dependencies
4. **Pinned minimum versions** — `>=` specifiers for reproducibility
5. **No dynamic code** — No `eval()`, no `__import__()`, no `exec()`

### Dependency Audit

All dependencies are automatically scanned:

```bash
# Install pip-audit
python -m pip install pip-audit

# Audit installed packages
pip-audit
```

### Dependency List

See [docs/install.md#supply-chain-transparency](docs/install.md#supply-chain-transparency) for the complete list of dependencies and their sources.

### Reproducible Builds

Rig supports reproducible builds:

```bash
# Build source distribution
python -m build --sdist

# Build wheel
python -m build --wheel

# Verify installation
python -m pip install dist/rig-*.tar.gz
```

## Receipt and Audit Trust Guarantees

### Receipt Chain Integrity

Rig's receipt system provides these guarantees:

1. **Immutability** — Receipts are never modified after creation
2. **Continuity** — Receipts form an unbroken chain
3. **Authenticity** — Receipts are cryptographically signed
4. **Deterministic replay** — Same receipts always produce same state
5. **Durability** — Receipts persist across restarts

### Audit Trail

Every action produces an audit event:

| Action | Audit Event | Contains |
|--------|--------------|----------|
| Workspace create | `workspace_create` | Workspace ID, timestamp, actor |
| Intent execution | `exec_receipt` | Intent ID, command, exit code |
| Validation pass | `validator_receipt` | Validator ID, findings |
| Review approval | `review_bundle` | Reviewer, decision, receipts |
| Apply | `apply_receipt` | Applied changes, timestamp |

**Audit events are immutable.** Once written, they cannot be modified or deleted.

### Replay Determinism

Rig guarantees that:

1. **Same receipts -> Same state** — Replaying the same set of receipts always produces the same workspace state
2. **Missing receipts -> Incomplete replay** — If receipts are missing, replay reports them as missing (never invents state)
3. **Contradictory receipts -> Error** — If receipts contradict each other, replay fails explicitly
4. **Authority preserved -> Never escalated** — Replay preserves authority/advisory flags exactly as in original receipts

## Cryptographic Posture

### Current State

- **Receipt signing:** Ed25519 signatures with per-workspace keys
- **Audit event hashing:** SHA-256 hashes for continuity validation
- **Intent hashing:** SHA-256 hashes of all inputs for intent IDs

### Future Enhancements (Not Implemented)

These are **not currently implemented** but may be added:

| Feature | Status | Description |
|---------|--------|-------------|
| Receipt chain signing | Paused | Sign entire receipt chain, not just individual receipts |
| External key management | Paused | Support for hardware security modules (HSMs) |
| Code signing | Paused | Sign Rig releases with GPG |
| SBOM generation | Paused | Software Bill of Materials for releases |

### Key Management

Currently:
- Each workspace generates its own Ed25519 key pair
- Private keys are stored in the workspace directory
- No central key authority

**Warning:** If you delete a workspace, you lose its keys. Receipts from that workspace cannot be verified without the key.

## Security Best Practices for Users

### Running Rig Safely

1. **Always use a virtual environment** — Never install to system Python
2. **Review before applying** — Never skip the review step
3. **Inspect receipts** — Use `rig replay timeline` to see what happened
4. **Validate regularly** — Run `rig doctor all` periodically
5. **Backup receipts** — Receipts are your audit trail; back them up
6. **Limit provider access** — Use providers with minimal permissions
7. **Monitor worktrees** — Check Git worktree state regularly

### Provider Security

When using external providers:

1. **Use API keys with minimal permissions** — Never use admin-level access
2. **Rotate keys regularly** — Change provider keys periodically
3. **Review model access** — Some models may have access to training data
4. **Audit provider output** — Treat all provider output as untrusted
5. **Use local models when possible** — Reduces exposure to external services

### Workspace Security

1. **One workspace per task** — Isolate different tasks in different workspaces
2. **Clean up old workspaces** — Delete workspaces you no longer need
3. **Review workspace contents** — Check what's in each worktree
4. **Limit workspace lifetime** — Don't keep workspaces open indefinitely

## Security Testing

### Automated Security Checks

Run these commands to verify security posture:

```bash
# Syntax check (catches potential injection vectors)
python3.14 -m compileall -q src tests

# Run all tests (validates governance integrity)
bash scripts/check.sh

# Doctor commands (check system integrity)
python -m rig doctor all

# Replay validation (verify receipt chain integrity)
python -m rig replay timeline --json

# Operational trust verification
bash scripts/verify_fresh_clone.sh --fast
bash scripts/verify_release_artifacts.sh --fast
```

### Manual Security Review

When contributing code:

1. **No dynamic code execution** — No `eval()`, `exec()`, `compile()`
2. **No shell injection** — Use `shlex.quote()` for shell arguments
3. **No path traversal** — Validate all file paths
4. **No SQL injection** — Rig uses DuckDB with parameterized queries
5. **No XSS** — Frontend widgets use `textContent` only (no `innerHTML`)
6. **No secret logging** — Never log tokens, API keys, or sensitive data
7. **No network by default** — All network operations must be explicit

### Fuzz Testing (Future)

Rig does not currently have fuzz testing. Future plans may include:

- Receipt parsing fuzzing
- Input validation fuzzing
- Replay determinism fuzzing

## Incident Response

### Security Incident Definition

A security incident is any event that:

- Compromises the confidentiality, integrity, or availability of Rig or user data
- Results in unauthorized access to systems or data
- Allows execution of arbitrary code
- Enables privilege escalation

### Incident Response Steps

1. **Detection** — Identify and confirm the incident
2. **Containment** — Limit the impact and prevent spread
3. **Eradication** — Remove the threat
4. **Recovery** — Restore normal operations
5. **Lessons learned** — Document and improve

### Communications

- **Internal:** Maintainers notified within 1 hour
- **Public:** Advisory published within 72 hours (or coordinated disclosure)
- **Users:** Guidance on mitigation and upgrades

## Legal and Compliance

### License

Rig is licensed under **AGPL-3.0-or-later**. This means:

- **Strong copyleft** — Derivative works must also be open source (AGPL)
- **Source availability** — If you distribute Rig (including SaaS), you must provide source
- **Patent grant** — Licensors grant patent rights to users

### Export Controls

Rig may be subject to export controls in some jurisdictions. Users are responsible for:

- Complying with local export control laws
- Obtaining necessary licenses for cryptographic functionality
- Ensuring use complies with sanctions and embargoes

### Privacy

Rig does not collect user data by default. If telemetry is enabled in the future:

- **Minimal data** — Only what's necessary
- **Redacted** — Sensitive data always removed
- **Inspectable** — Users can see exactly what's collected
- **Opt-in** — Disabled by default
- **Deletable** — Users can request data deletion

## Summary

| Aspect | Status |
|--------|--------|
| **Local-first** | Yes — Core governance is offline-only |
| **No auto-telemetry** | Yes — No data collected by default |
| **Deny-by-default** | Yes — All intents blocked unless allowed |
| **Immutable receipts** | Yes — Never modified after creation |
| **Deterministic replay** | Yes — Same inputs, same outputs |
| **No state invention** | Yes — Missing data shows as placeholders |
| **Token redaction** | Yes — Secrets never exposed |

**Rig's security model:** If it's not explicitly allowed by a receipt and validated through governance gates, it doesn't happen.

---

**Security Contact:** (To be established)

**Last Updated:** May 2025
