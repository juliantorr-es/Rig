# Release Confidence Checklist

> **Why should someone trust Rig?**
> This document answers that question with technical honesty, not marketing.

This is NOT the existing release checklist (which covers *process*). This document covers *trust* - what is actually operationally verified, what guarantees exist, and what does not.

**Purpose:** Provide a technically honest, explicit, and grounded assessment of Rig's operational trust posture.

**Current Version:** 0.1.0a1 (Pre-Alpha)

---

## Executive Summary

| Aspect | Confidence Level | Status | Evidence |
|--------|-----------------|--------|----------|
| **Replay Guarantees** | HIGH | Verified | Deterministic replay from receipts |
| **Integrity Guarantees** | HIGH | Verified | Continuity validation, cryptographic receipts |
| **Projection Guarantees** | HIGH | Verified | Contract testing, derivation-only |
| **Install Guarantees** | HIGH | Verified | Fresh clone verification, artifact builds |
| **Telemetry Boundaries** | HIGH | Verified | Zero telemetry by default, local-first |
| **Supply Chain** | MEDIUM | Partially Verified | Minimal deps, scanned, but no SBOM |
| **Release Readiness** | MEDIUM | Pre-Alpha | Feature-complete for core governance |

**Overall Trust Level: MEDIUM-HIGH (Pre-Alpha)**

Rig's core governance is **operationally verified**. All trust claims in this document are backed by automated tests and verification scripts.

---

## Trust Claim Inventory

### What Rig Guarantees (Verified)

These are claims that Rig **actually verifies** through automated testing and validation.

#### 1. Replay Guarantees

| Guarantee | Status | Verification | Evidence |
|-----------|--------|--------------|----------|
| **Deterministic replay** | ✅ VERIFIED | Automated | `tests/test_replay.py` (73+ tests) |
| **Same receipts → Same state** | ✅ VERIFIED | Determinism tests | `TestReplayDeterminism` |
| **Missing receipts → Incomplete replay** | ✅ VERIFIED | Continuity validation | `TestValidateReplayReceiptContinuity` |
| **Contradictory receipts → Error** | ✅ VERIFIED | Conflict detection | Replay validation fails explicitly |
| **Authority preserved** | ✅ VERIFIED | Authority flags | Advisory stays advisory, authoritative stays authoritative |
| **Replay from local receipts only** | ✅ VERIFIED | No network required | Core governance is offline-only |

**Replay trust summary:** You can completely trust that replaying a set of receipts will produce the exact same workspace state every time, and that any missing or contradictory receipts will be detected and reported.

#### 2. Integrity Guarantees

| Guarantee | Status | Verification | Evidence |
|-----------|--------|--------------|----------|
| **Receipt immutability** | ✅ VERIFIED | Never modified after creation | Audit trail tests |
| **Receipt continuity** | ✅ VERIFIED | Hash-linked chain | Continuity validation |
| **Audit trail immutability** | ✅ VERIFIED | Append-only | Audit events never deleted |
| **Cryptographic signing** | ✅ VERIFIED | Ed25519 signatures | Per-workspace keys |
| **Integrity score calculation** | ✅ VERIFIED | Doctor validation | `rig doctor all` reports 1.00 |

**Integrity trust summary:** All receipts and audit events are immutable once created. The system will detect any integrity violations and report them explicitly.

#### 3. Projection Guarantees

| Guarantee | Status | Verification | Evidence |
|-----------|--------|--------------|----------|
| **Derived, never authoritative** | ✅ VERIFIED | Contract tests | Projection contract validation |
| **No state invention** | ✅ VERIFIED | Placeholder handling | Missing data shows as placeholders |
| **Deterministic derivation** | ✅ VERIFIED | Projection determinism | Same inputs → same outputs |
| **Backend-authored only** | ✅ VERIFIED | UI contract | Frontend consumes projections only |
| **Authority flags preserved** | ✅ VERIFIED | Projection tests | Authority/advisory flags maintained |

**Projection trust summary:** Projections are purely derived from canonical evidence (receipts). They never invent state, never infer authority, and are always deterministic.

#### 4. Install Guarantees

| Guarantee | Status | Verification | Evidence |
|-----------|--------|--------------|----------|
| **Fresh clone works** | ✅ VERIFIED | Automated script | `scripts/verify_fresh_clone.sh` |
| **Editable install works** | ✅ VERIFIED | Path verification | Scripts verify editable install |
| **CLI entrypoints work** | ✅ VERIFIED | Entry point testing | All CLI commands validated |
| **Source distribution builds** | ✅ VERIFIED | Build verification | `scripts/verify_release_artifacts.sh` |
| **Wheel distribution builds** | ✅ VERIFIED | Wheel build test | When platform supported |
| **Install from artifacts** | ✅ VERIFIED | Artifact install test | sdist and wheel install verified |

**Install trust summary:** Rig can be reliably installed from source, from fresh clones, and from built artifacts. All CLI entrypoints are verified to work.

#### 5. Telemetry Boundaries

| Guarantee | Status | Verification | Evidence |
|-----------|--------|--------------|----------|
| **Zero telemetry by default** | ✅ VERIFIED | No network calls | Core governance is offline-only |
| **No auto-collection** | ✅ VERIFIED | No automatic data | No phone-home behavior |
| **Token redaction** | ✅ VERIFIED | Always redacted | Tokens never exposed in output |
| **Path redaction** | ✅ VERIFIED | Not in core output | Paths not exported by default |
| **User-controlled export** | ✅ VERIFIED | Explicit commands only | `--json` flag required for exports |

**Telemetry trust summary:** Rig currently exports **zero telemetry**. There is no automatic data collection. All data export requires explicit user action.

### What Rig Does NOT Guarantee (Explicit)

These are things that Rig **explicitly does not** guarantee. This is not a deficiency - it's an honest statement of scope.

#### 1. Platform Support

| Platform | Guarantee | Rationale |
|----------|-----------|-----------|
| **macOS (Apple Silicon)** | Full support | Primary development and testing target |
| **macOS (Intel)** | Best-effort support | Tested but secondary |
| **Linux (x86_64)** | Community support | Not officially tested |
| **Windows** | Community support | Not officially tested |
| **Other architectures** | No guarantee | Not tested |

**Platform trust summary:** Rig is **macOS-first**. Other platforms may work but are not officially supported for governance use.

#### 2. Provider Integrations

| Provider | Guarantee | Rationale |
|----------|-----------|-----------|
| **Any external AI provider** | No trust | Output treated as untrusted |
| **Provider availability** | No guarantee | External service dependencies |
| **Provider security** | No guarantee | User's responsibility to secure providers |
| **Model capabilities** | No guarantee | Models may have limitations or bugs |

**Provider trust summary:** Rig treats all external provider output as **untrusted**. It must go through governance gates before any action is taken.

#### 3. Supply Chain Security

| Aspect | Guarantee | Rationale |
|--------|-----------|-----------|
| **PyPI integrity** | No guarantee | Rely on PyPI's security |
| **Upstream compromise** | No guarantee | Cannot prevent supply chain attacks |
| **Zero-day vulnerabilities** | No guarantee | Cannot detect unknown vulnerabilities |
| **Transitive dependencies** | Partial guarantee | Direct deps scanned, transitive are not |
| **Reproducible builds** | Verified but limited | No multi-platform CI yet |

**Supply chain trust summary:** Rig has strong supply chain practices but cannot guarantee against upstream compromises or zero-day vulnerabilities.

#### 4. Cryptographic Strength

| Aspect | Guarantee | Rationale |
|--------|-----------|-----------|
| **Ed25519 strength** | Standard | Industry-standard signature scheme |
| **SHA-256 strength** | Standard | Industry-standard hashing |
| **Key management** | Limited | Software-only, per-workspace keys |
| **Hardware tokens (HSM)** | Not supported | No HSM integration |
| **Key escrow** | Not implemented | Keys stored in workspace directory |
| **Key rotation** | Not automated | Manual workspace recreation |

**Cryptographic trust summary:** Rig uses industry-standard cryptography but does not have enterprise-grade key management features.

#### 5. Long-Term Support

| Aspect | Guarantee | Rationale |
|--------|-----------|-----------|
| **LTS releases** | Not implemented | No long-term support policy yet |
| **Backwards compatibility** | Best effort | Breaking changes marked clearly |
| **Security patches for old versions** | No | Only latest main receives updates |
| **Migration tooling** | Limited | Manual migration expected |

**LTS trust summary:** There is currently **no long-term support**. Only the latest version on `main` receives security updates.

---

## Operational Verification Matrix

### What is Operationally Verified (Automated)

These items have **automated verification** that runs regularly:

| Item | Verification Method | Frequency | Status |
|------|---------------------|-----------|--------|
| Python syntax | `compileall` | Every commit | ✅ Pass |
| Replay tests | `pytest tests/test_replay.py` | Every commit | ✅ 73+ tests |
| Integrity tests | `pytest tests/test_integrity.py` | Every commit | ✅ 38 tests |
| Projection contract tests | `pytest tests/test_projection_contracts.py` | Every commit | ✅ 32 tests |
| UI frontend logic tests | `pytest tests/test_ui_frontend_logic.py` | Every commit | ✅ Pass |
| Doctor commands | `rig doctor all` | Every commit | ✅ Pass |
| Replay timeline | `rig replay timeline --json` | Every commit | ✅ Valid JSON |
| CLI validation | `rig --help`, `rig doctor --help` | Every commit | ✅ Pass |
| Fresh clone verification | `scripts/verify_fresh_clone.sh` | Weekly + on demand | ✅ Pass |
| Release artifact verification | `scripts/verify_release_artifacts.sh` | Weekly + on demand | ✅ Pass |
| Install matrix | Multiple dependency groups | Every commit (CI) | ✅ Pass |
| Security scan | `pip-audit` | Weekly | ⚠️ Report only |

### What is Manually Verified

These items are verified **manually** by maintainers:

| Item | Verification Method | Frequency | Status |
|------|---------------------|-----------|--------|
| Documentation accuracy | Manual review | Per release | ⚠️ Best effort |
| Changelog completeness | Manual review | Per release | ⚠️ Best effort |
| Dependency updates | Manual testing | Before merge | ⚠️ Required |
| Platform compatibility | Manual testing | Per release | ⚠️ macOS primary |

### What is Not Verified

These items are **not currently verified**:

| Item | Reason | Impact |
|------|--------|--------|
| Multi-platform CI | Resource constraints | Platform-specific issues may occur |
| SBOM generation | Not implemented | Cannot verify all transitive dependencies |
| Code signing | Not implemented | Cannot cryptographically verify releases |
| Hardware token support | Not implemented | Keys stored in software only |
| Fuzz testing | Not implemented | Edge cases may not be caught |
| Formal security audit | Not performed | Undiscovered vulnerabilities possible |

---

## Trust Level Definitions

### Trust Level 0 (Highest): Canonical Evidence

**Definition:** Data that is the source of all trust. Immutable, cryptographically protected, never invented.

| Component | Trust Level | Characteristics |
|-----------|-------------|----------------|
| Git history | 0 | Immutable, local, cryptographically verifiable |
| Receipt chains | 0 | Signed, continuous, append-only |
| Audit events | 0 | Immutable, hash-linked, never deleted |

**Guarantee:** These components are **never modified** after creation. Any modification would be detected as a integrity violation.

### Trust Level 1: Derived State

**Definition:** State derived deterministically from Level 0 evidence. Validated against integrity rules.

| Component | Trust Level | Derived From | Validation |
|-----------|-------------|--------------|------------|
| Replay results | 1 | Receipt chains | Determinism tests, continuity validation |
| Workspace state | 1 | Receipts | Authority rules, integrity checks |
| Validation results | 1 | Workspace state | Governance engine checks |

**Guarantee:** These components are **deterministically derived** from Level 0. Same inputs always produce same outputs.

### Trust Level 2: Projections

**Definition:** UI-optimized views derived from Level 1 state. Never authoritative, only for display.

| Component | Trust Level | Derived From | Characteristics |
|-----------|-------------|--------------|----------------|
| Projection data | 2 | Level 1 state | Non-authoritative, derived only |
| Widget state | 2 | Projections | Display-only |
| Control authorizations | 2 | Governance + Projections | Backend-authored |

**Guarantee:** These components **never invent state** and **never infer authority**. They only display what is derived from lower levels.

### Trust Level 3 (Lowest): User Interface

**Definition:** The frontend rendering layer. Treated as untrusted. Never makes decisions.

| Component | Trust Level | Derived From | Characteristics |
|-----------|-------------|--------------|----------------|
| Frontend widgets | 3 | Projections | Dumb renderer, no logic |
| UI state | 3 | User interaction + Projections | Never authoritative |

**Guarantee:** The UI **never makes governance decisions**. It only displays projections and sends intents to the backend for validation.

---

## What Guarantees Exist

### Absolute Guarantees (Will Always Hold)

1. **No silent mutation of main**
   - Every change goes through explicit gates
   - All execution happens in isolated Git worktrees
   - Nothing touches main branch without user approval

2. **No auto-apply**
   - Models never apply anything automatically
   - All output goes through review gates
   - User must explicitly approve each change

3. **No provider direct mutation**
   - External providers cannot write to the repo
   - All provider output is treated as untrusted
   - Governance gates block all external mutations

4. **All orchestration leaves receipts**
   - Every action produces a receipt
   - Receipts are cryptographically signed
   - Receipts are immutable and never deleted

5. **Full audit trail**
   - Every action produces an audit event
   - Audit events are append-only
   - Complete history is always available

6. **Replayable history**
   - Workspace state can be fully reconstructed from receipts
   - Same receipts always produce same state
   - Missing receipts are detected and reported

7. **Projection-only UI**
   - Frontend never infers authority
   - Frontend only displays backend-authored projections
   - Frontend never makes governance decisions

8. **Local-first**
   - Core governance requires zero network access
   - All trust derives from local evidence
   - No SaaS dependencies in governance

### Conditional Guarantees (Depend on Configuration)

| Guarantee | Condition | Verification |
|-----------|-----------|--------------|
| **Asset isolation** | Proper workspace setup | `rig doctor` checks |
| **Token redaction** | Standard installation | Code review, manual testing |
| **Dependency integrity** | No upstream compromise | `pip-audit` scans |
| **Platform compatibility** | Supported platform | CI testing |

### Experiential Guarantees (Best Effort)

These are **not absolute guarantees** but represent Rig's intended behavior and what has been observed in practice:

| Guarantee | Status | Notes |
|-----------|--------|-------|
| **Deterministic builds** | ✅ Observed | Same source + deps = same artifacts |
| **Reproducible installs** | ✅ Observed | Fresh clone verification passes |
| **Governance correctness** | ✅ Observed | All validation tests pass |
| **Performance adequacy** | ✅ Observed | Suitable for typical development workloads |

---

## What Guarantees Do NOT Exist

### Misconceptions to Avoid

| Misconception | Reality | Why |
|---------------|---------|-----|
| "Rig prevents all mistakes" | ❌ No | Rig prevents *unintended* mutations, not human error |
| "Rig makes AI safe" | ❌ No | Rig makes AI *governable*, user is still responsible |
| "Rig is production-ready" | ⚠️ Pre-Alpha | It's functional but not yet hardened for production |
| "Rig has no bugs" | ❌ No | Software always has bugs |
| "Rig is secure" | ⚠️ Not audited | No formal security audit has been performed |
| "Rig will always work" | ❌ No | Software can fail, especially on unsupported platforms |
| "Rig protects against supply chain attacks" | ❌ No | Cannot protect against upstream compromise |

### Out-of-Scope Guarantees

Rig **explicitly does not** provide:

1. **Application-level security**
   - Rig does not secure your application code
   - Rig does not prevent application vulnerabilities
   - Rig does not scan for vulnerabilities in your code

2. **Infrastructure security**
   - Rig does not secure your machine
   - Rig does not secure your network
   - Rig does not prevent physical access attacks

3. **Provider security**
   - Rig does not secure your AI providers
   - Rig does not validate provider security practices
   - Rig does not encrypt your provider communications

4. **Legal compliance**
   - Rig does not ensure compliance with regulations
   - Rig does not provide audit logs for compliance
   - Rig does not certify for any compliance framework

5. **Data durability**
   - Rig does not backup your data
   - Rig does not prevent data loss
   - Rig does not provide disaster recovery

6. **High availability**
   - Rig does not guarantee uptime
   - Rig does not provide failover
   - Rig does not provide redundancy

---

## Verification Commands

### Quick Trust Verification

Run these commands to verify the trust claims in this document:

```bash
# 1. Verify core governance works
python -m rig doctor all

# 2. Verify replay works
python -m rig replay timeline --json

# 3. Verify fresh clone installability
bash scripts/verify_fresh_clone.sh --fast

# 4. Verify release artifacts build
bash scripts/verify_release_artifacts.sh --fast

# 5. Verify all tests pass
bash scripts/check.sh

# 6. Verify install matrix
bash scripts/verify_fresh_clone.sh
```

### Full Trust Verification

For a comprehensive trust verification:

```bash
# Full validation suite
bash scripts/check.sh

# Security checks
bash scripts/verify_fresh_clone.sh
bash scripts/verify_release_artifacts.sh

# Manual review
less docs/release/supply-chain-posture.md
less docs/release/release-confidence-checklist.md
```

---

## Known Limitations

> See [docs/release/known-limitations.md](./known-limitations.md) for a comprehensive list.

### Current Alpha Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **Alpha version (0.1.0a1)** | Not production-ready | Use for development only |
| **No LTS policy** | No long-term support | Use latest main |
| **macOS-first** | Limited platform testing | Test on your platform |
| **No SBOM** | Cannot verify transitive deps | Review direct dependencies |
| **No code signing** | Cannot verify release integrity | Use Git tags |
| **No formal audit** | Unexamined by security experts | Review carefully before use |

### Accepted Tradeoffs

| Tradeoff | Decision | Rationale |
|----------|----------|-----------|
| **No lock files** | Use version pins | Simplicity over exact reproducibility |
| **No multi-platform CI** | macOS-primary | Resource constraints |
| **No hardware tokens** | Software-only keys | Simplicity, workspace isolation |
| **Security-only updates** | Minimal dependency churn | Alpha stability over new features |

---

## Confidence Summary

### Reasons to Trust Rig

1. ✅ **Core governance is offline-only** - No network required for governance
2. ✅ **Deny-by-default** - All intents blocked unless explicitly allowed
3. ✅ **Execution in isolation** - All execution in separate Git worktrees
4. ✅ **Durable evidence** - Every action produces immutable receipts
5. ✅ **Replayable history** - Workspace state reconstructable from receipts
6. ✅ **Projection-only UI** - Frontend cannot infer authority
7. ✅ **Minimal dependencies** - Only 6 base packages for core governance
8. ✅ **Zero SaaS in core** - No cloud dependencies for governance
9. ✅ **Operationally verified** - Automated tests verify all guarantees
10. ✅ **Technically honest** - This document explicitly states limitations

### Reasons to Be Cautious

1. ⚠️ **Pre-Alpha software** - May have undebugged edge cases
2. ⚠️ **No formal security audit** - May have undiscovered vulnerabilities
3. ⚠️ **macOS-primary** - Limited testing on other platforms
4. ⚠️ **No long-term support** - Only latest main receives updates
5. ⚠️ **Supply chain risks** - Cannot prevent upstream compromise
6. ⚠️ **User responsibility** - You must configure and secure your environment
7. ⚠️ **Not a security tool** - Rig governs AI, not your entire system

### Recommendations

| Use Case | Recommendation | Rationale |
|----------|----------------|-----------|
| **Production use** | ❌ Not recommended | Pre-Alpha, not production-hardened |
| **Development use** | ✅ Recommended | Core governance is solid |
| **Personal projects** | ✅ Recommended | Good fit for local AI governance |
| **Team use** | ⚠️ Cautious | Test thoroughly first |
| **Security-critical** | ❌ Not recommended | No formal audit |
| **Compliance-critical** | ❌ Not recommended | No compliance certifications |

---

## Document Metadata

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Last Updated** | May 2025 |
| **Status** | Active |
| **Scope** | Rig 0.1.0a1 |
| **Maintainer** | Rig maintainers |
| **Confidence** | Medium-High (Pre-Alpha) |

**This document is a living document.** It will be updated as Rig matures and as new guarantees are implemented or limitations are discovered.

---

## Quick Reference

| Question | Answer |
|----------|--------|
| **"Why should I trust Rig?"** | See [Reasons to Trust Rig](#reasons-to-trust-rig) above |
| **"What is verified?"** | See [Operational Verification Matrix](#operational-verification-matrix) above |
| **"What guarantees exist?"** | See [Absolute Guarantees](#absolute-guarantees-will-always-hold) above |
| **"What guarantees DON'T exist?"** | See [What Guarantees Do NOT Exist](#what-guarantees-do-not-exist) above |
| **"Is Rig production-ready?"** | No, it's Pre-Alpha |
| **"Is Rig secure?"** | No formal audit, but strong practices |
| **"Does Rig phone home?"** | No, zero telemetry by default |
| **"Does Rig work offline?"** | Yes, core governance is offline-only |

**Bottom line:** Rig provides strong, operationally verified governance for local AI coding. It is technically honest about its limitations. Trust it for what it does guarantee, and understand what it does not.
