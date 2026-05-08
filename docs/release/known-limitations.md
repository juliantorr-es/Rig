# Known Limitations

> **Transparency about what Rig does and doesn't do.**

This document explicitly lists Rig's known limitations, unsupported workflows, and experimental surfaces. It is intended to set accurate expectations for users.

## Philosophy

Rig is designed with explicit boundaries. This document states what Rig **does not** do, so users can make informed decisions.

## Core Limitations

### Scope Limitations

Rig is a **governed local control plane**, not a general-purpose AI platform. It does **not** provide:

| Capability | Status | Reason |
|------------|--------|--------|
| **AI model hosting** | ❌ Not provided | Use external providers |
| **Model fine-tuning** | ❌ Not provided | Out of scope |
| **Prompt engineering tools** | ❌ Not provided | Out of scope |
| **Multi-user collaboration** | ❌ Not provided | Single-user only |
| **Real-time features** | ❌ Not provided | Not a design goal |
| **Cloud storage** | ❌ Not provided | Local-first only |
| **Web dashboard** | ❌ Not provided | CLI + windowed UI only |
| **Mobile support** | ❌ Not provided | Not a design goal |

### Governance Limitations

Rig's governance is **local-only**. It does not:

| Capability | Status | Workaround |
|------------|--------|------------|
| **Remote policy enforcement** | ❌ Not supported | Local policies only |
| **Team-based permissions** | ❌ Not supported | Single-user only |
| **Audit logging to external systems** | ❌ Not supported | Local audit trail only |
| **Compliance reporting** | ❌ Not supported | Manual export only |
| **Approval workflows** | ❌ Not supported | Single-user review only |

**What this means:** Rig enforces **your** local policies, not organizational policies. If you need team-based governance, Rig is not the right tool.

## Platform Limitations

### Officially Supported Platforms

| Platform | Architecture | Support | Notes |
|----------|--------------|---------|-------|
| macOS | Apple Silicon (ARM64) | ✅ Full | Primary target |
| macOS | Intel (x86_64) | ✅ Full | Tested |

### Community Supported Platforms

| Platform | Architecture | Support | Notes |
|----------|--------------|---------|-------|
| Linux | x86_64 | ⚠️ Best effort | May work, not officially tested |
| Linux | ARM64 | ⚠️ Best effort | May work, not officially tested |
| Windows | x86_64 | ⚠️ Best effort | May work, not officially tested |

**Note:** Core governance (receipts, replay, projections, doctor) is platform-independent. Only UI and ML features may have platform limitations.

### Known Platform Issues

#### Linux

| Issue | Status | Workaround |
|-------|--------|------------|
| **Git worktree permissions** | ⚠️ May differ | Check `git worktree` behavior |
| **File path handling** | ⚠️ May differ | Use relative paths when possible |
| **pywebview display** | ⚠️ May not work | Use `--browser` flag for web UI |

#### Windows

| Issue | Status | Workaround |
|-------|--------|------------|
| **Git worktree symlinks** | ⚠️ May not work | Avoid symlinks |
| **File path separators** | ⚠️ May differ | Use `/` not `\` for paths |
| **Virtual environment activation** | ⚠️ Different syntax | Use correct `activate` script |
| **pywebview display** | ⚠️ May not work | Use `--browser` flag for web UI |
| **ML inference (mlx)** | ❌ Not supported | Use llama-cpp-python or external |

## Dependency Limitations

### Core Dependencies

Rig's core dependencies are intentionally minimal:

| Dependency | Purpose | Version | Notes |
|------------|---------|---------|-------|
| `jsonschema` | JSON validation | >=4.23 | Schema validation for receipts |
| `duckdb` | Embedded DB | >=1.0.0 | Audit event storage |
| `PyYAML` | YAML parsing | >=6.0 | Configuration parsing |
| `rich` | Terminal output | >=13.7 | Rich terminal formatting |
| `psutil` | System monitoring | >=5.9 | Process monitoring |
| `tomli-w` | TOML parsing | >=1.0.0 | `pyproject.toml` parsing |

**Limitation:** These are **minimum versions**. Rig may work with newer versions, but:
- We cannot guarantee compatibility with all future versions
- Breaking changes in dependencies may break Rig
- You are responsible for dependency version compatibility

### Optional Dependencies

Optional dependencies have their own limitations:

| Group | Dependencies | Notes |
|-------|--------------|-------|
| `ui` | aiohttp, pywebview | Windowed UI requires native windowing |
| `ml` | mlx, llama-cpp-python | ML inference, platform-specific |
| `dev` | pytest, pyright, ruff | Development tools |
| `docs` | mkdocs, mkdocs-material | Documentation generation |
| `legacy_tui` | textual, textual-serve | Deprecated, use `rig ui` instead |

### Dependency Conflicts

| Issue | Status | Workaround |
|-------|--------|------------|
| **Version conflicts** | ⚠️ Possible | Use virtual environment |
| **Platform-specific wheels** | ⚠️ Possible | May need to build from source |
| **Python version incompatibility** | ❌ Not supported | Use Python 3.14+ |

## Feature Limitations

### Workspace Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Workspace count** | No hard limit | Disk space is the limit |
| **Workspace nesting** | ❌ Not supported | Flat structure only |
| **Workspace renaming** | ❌ Not supported | Create new, delete old |
| **Workspace sharing** | ❌ Not supported | Single-user only |
| **Workspace import/export** | ❌ Not supported | Local only |

### Receipt Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Receipt size** | No hard limit | Disk space is the limit |
| **Receipt count** | No hard limit | Disk space is the limit |
| **Receipt editing** | ❌ Not supported | Immutable by design |
| **Receipt deletion** | ❌ Not supported | Delegated to archive only |
| **Receipt encryption** | ❌ Not supported | Future capability |
| **Receipt signing (chain)** | ❌ Not implemented | Individual receipts only |

### Replay Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Replay speed** | Depends on receipt count | O(n) where n = receipt count |
| **Replay memory** | Depends on receipt size | Large receipts may use more memory |
| **Partial replay** | ❌ Not supported | All or nothing |
| **Selective replay** | ❌ Not supported | Full timeline only |
| **Replay to different state** | ❌ Not supported | Deterministic only |

### Projection Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Projection caching** | ❌ Not implemented | Derived on demand |
| **Projection subscriptions** | ❌ Not implemented | Poll-based only |
| **Projection versioning** | ✅ Implemented | Contract version in each projection |
| **Projection customization** | ❌ Not supported | Backend-authored only |

### UI Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **UI themes** | ❌ Not supported | Uses system/default theme |
| **UI customization** | ❌ Not supported | Backend-authored only |
| **UI plugins** | ❌ Not supported | Not extensible |
| **UI state persistence** | ❌ Not implemented | Derived on demand |
| **UI offline mode** | ⚠️ Partial | Core governance is offline |

### ML limitations

Rig's ML integration has significant limitations:

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Model loading** | ⚠️ Manual | You must provide models |
| **Model serving** | ❌ Not provided | Local inference only |
| **Model fine-tuning** | ❌ Not provided | Out of scope |
| **Model hosting** | ❌ Not provided | External only |
| **Multi-model** | ⚠️ Manual | Configure per-provider |
| **Model caching** | ❌ Not implemented | Load on demand |
| **GPU acceleration** | ⚠️ Depends on provider | mlx supports Metal, llama-cpp varies |

**Platform-specific ML limitations:**

| Platform | mlx | llama-cpp-python | Notes |
|----------|-----|-----------------|-------|
| macOS ARM64 | ✅ Full | ✅ Supported | Native Metal acceleration |
| macOS x86_64 | ❌ Not supported | ⚠️ May work | No Metal acceleration |
| Linux x86_64 | ❌ Not supported | ⚠️ May work | Check provider support |
| Linux ARM64 | ❌ Not supported | ⚠️ May work | Check provider support |
| Windows | ❌ Not supported | ⚠️ May work | No mlx, llama-cpp may work |

### Provider Limitations

External provider integration has limitations:

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Provider configuration** | ⚠️ Manual | You must configure providers |
| **Provider authentication** | ⚠️ Manual | You must provide API keys |
| **Provider rate limits** | ⚠️ Applies | Subject to provider limits |
| **Provider data retention** | ⚠️ Applies | Check provider policy |
| **Provider training** | ⚠️ May apply | Some providers use data for training |
| **Provider reliability** | ⚠️ Depends | Rig treats output as untrusted |

**Important:** Rig does **not** validate provider behavior. You are responsible for:
- Choosing trustworthy providers
- Understanding provider terms and privacy policies
- Managing provider API keys securely

## Performance Limitations

### Expected Performance

| Operation | Time Complexity | Notes |
|-----------|-----------------|-------|
| Workspace creation | O(1) | Fast |
| Intent execution | O(1) + command time | Depends on command |
| Receipt creation | O(1) | Fast |
| Receipt signing | O(1) | Ed25519 is fast |
| Audit event writing | O(1) | DuckDB is fast |
| Replay (n receipts) | O(n) | Linear in receipt count |
| Projection generation | O(n) | Depends on derived state |
| Doctor all | O(n) | Depends on workspace count |

### Known Performance Issues

| Issue | Status | Impact | Workaround |
|-------|--------|--------|------------|
| **First run slow** | ⚠️ Known | Initial imports | Use virtual environment |
| **Large receipt chains** | ⚠️ Slow replay | Replay time increases | Archive old workspaces |
| **Many workspaces** | ⚠️ Slow doctor | Doctor time increases | Limit workspace count |
| **DuckDB queries** | ⚠️ May vary | Query performance | Optimize queries |

### Memory Usage

| Component | Memory Usage | Notes |
|-----------|---------------|-------|
| Rig core | ~50-100 MB | Base process |
| DuckDB | ~10-50 MB per DB | Per workspace |
| pywebview | ~100-300 MB | Browser engine |
| ML models | Model size + | Can be GBs |

**Note:** ML model memory usage depends entirely on the model being used. Rig itself has minimal memory overhead beyond what the model requires.

## Security Limitations

### Cryptographic Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Key management** | ⚠️ Basic | Per-workspace keys, file-based |
| **Key backup** | ❌ Not implemented | Lose workspace = lose keys |
| **Key rotation** | ❌ Not implemented | Static keys per workspace |
| **Hardware security** | ❌ Not implemented | No HSM support |
| **Code signing** | ❌ Not implemented | No release signing |
| **SBOM generation** | ❌ Not implemented | No software bill of materials |

### Network Security

| Feature | Limitation | Notes |
|---------|------------|-------|
| **TLS verification** | ✅ Enabled | For provider connections |
| **Certificate pinning** | ❌ Not implemented | Standard TLS only |
| **Network isolation** | ⚠️ Partial | Core governance is offline |
| **Firewall rules** | ❌ Not configured | User responsibility |

### Data Security

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Encryption at rest** | ❌ Not implemented | Plaintext files |
| **Encryption in transit** | ⚠️ For providers only | Rig doesn't transmit data |
| **Data redaction** | ✅ Implemented | Debug bundles are redacted |
| **Secret scanning** | ❌ Not implemented | Don't commit secrets |
| **Memory sanitization** | ❌ Not implemented | Standard Python behavior |

## Stability Limitations

### Experimental Features

These features are **experimental** and may change or be removed:

| Feature | Status | Notes |
|---------|--------|-------|
| **ML integration** | 🟡 Experimental | May change significantly |
| **Legacy TUI** | 🟠 Deprecated | Will be removed |
| **Provider integrations** | 🟡 Experimental | API may change |
| **UI widgets** | 🟡 Experimental | May change |
| **Projection system** | 🟢 Stable | Contract locked |
| **Receipt system** | 🟢 Stable | Schema locked |
| **Replay system** | 🟢 Stable | Core feature |
| **Governance engine** | 🟢 Stable | Core feature |

### Unstable APIs

These APIs are **not stable** and may change in any release:

| API | Status | Notes |
|-----|--------|-------|
| Direct Python imports | 🟠 Unstable | Use CLI instead |
| Internal functions | 🟠 Unstable | Use public CLI only |
| CLI flags/arguments | 🟡 Mostly stable | May change in minor releases |
| JSON output schema | 🟢 Stable | Versioned, backwards compatible |
| Receipt schema | 🟢 Stable | Versioned, backwards compatible |
| Projection contracts | 🟢 Stable | Versioned, backwards compatible |

### Known Bugs

See the [issue tracker](https://github.com/juliantorr-es/Rig/issues) for known bugs.

## Error Handling Limitations

| Scenario | Limitation | Notes |
|----------|------------|-------|
| **Malformed receipts** | ⚠️ Partial handling | May fail validation |
| **Corrupted database** | ⚠️ Limited recovery | May need to recreate |
| **Missing dependencies** | ❌ Hard failure | Clear error messages |
| **Provider errors** | ⚠️ Pass-through | Provider errors Surface as-is |
| **Network failures** | ⚠️ Retry not automatic | User must retry |
| **Disk full** | ❌ Hard failure | Standard OS behavior |

## Internationalization Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Non-ASCII characters** | ✅ Supported | UTF-8 throughout |
| **Unicode normalization** | ⚠️ Not normalized | May cause comparison issues |
| **Locale support** | ⚠️ C locale | Numbers use `.` not `,` |
| **Time zones** | ✅ Supported | UTC recommended |
| **Right-to-left text** | ⚠️ Not tested | May have display issues |

## Accessibility Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **CLI color contrast** | ⚠️ May not meet WCAG | Uses rich library defaults |
| **Screen reader support** | ⚠️ Not tested | Terminal UI only |
| **Keyboard navigation** | ⚠️ Basic | Windowed UI has keyboard support |
| **High contrast mode** | ❌ Not supported | Uses system theme |
| **Font size adjustment** | ❌ Not supported | Uses system defaults |

## Compatibility Limitations

### Git Versions

| Git Version | Support | Notes |
|-------------|---------|-------|
| 2.30+ | ✅ Full | Recommended |
| 2.20-2.29 | ⚠️ May work | Not tested |
| < 2.20 | ❌ Not supported | Missing worktree support |

### Python Versions

| Python Version | Support | Notes |
|---------------|---------|-------|
| 3.14.x | ✅ Full | Primary target |
| 3.15.x | ✅ Full | Tested when available |
| 3.13.x | ❌ Not supported | Missing features |
| < 3.13 | ❌ Not supported | Requires 3.14+ |

## Configuration Limitations

| Feature | Limitation | Notes |
|---------|------------|-------|
| **Config file format** | TOML only | `pyproject.toml` |
| **Config file location** | Fixed | Project root only |
| **Environment variables** | Limited | See [Install Guide](../install.md#environment-variables) |
| **Config validation** | ✅ Implemented | Schema-validated |
| **Config hot-reload** | ❌ Not supported | Restart required |

## Summary Table

| Area | Status | Key Limitation |
|------|--------|----------------|
| **Core governance** | 🟢 Stable | None |
| **Receipt system** | 🟢 Stable | Immutable, deterministic |
| **Replay system** | 🟢 Stable | From receipts alone |
| **Projection system** | 🟢 Stable | Backend-authored |
| **Doctor system** | 🟢 Stable | Integrity validation |
| **CLI interface** | 🟡 Mostly stable | May change in minor |
| **Windowed UI** | 🟡 Experimental | May change |
| **ML integration** | 🟡 Experimental | Platform-specific |
| **Provider integration** | 🟡 Experimental | External dependencies |
| **Unicode support** | ✅ Good | UTF-8 throughout |
| **Performance** | 🟡 Acceptable | Linear scaling |
| **Security** | 🟡 Basic | No encryption at rest |
| **Accessibility** | ⚠️ Limited | Not fully accessible |
| **Platform support** | 🟡 MacOS-first | Others best effort |

## What Rig Does Well

| Capability | Strength |
|------------|----------|
| **Governance** | Deny-by-default, no auto-apply |
| **Isolation** | Git worktrees for each task |
| **Audit trail** | Immutable receipts for everything |
| **Replay** | Deterministic from receipts alone |
| **Replay validation** | Continuity and integrity checks |
| **Projections** | Backend-authored, never authoritative |
| **Trust boundaries** | Explicit, enforced |
| **Transparency** | All behavior inspectable |
| **Local-first** | No cloud dependencies for core |
| **Offline-capable** | Core governance needs no network |

## What Rig Doesn't Do

| Capability | Status | Alternative |
|------------|--------|------------|
| **Host models** | ❌ Not provided | Use external providers |
| **Fine-tune models** | ❌ Not provided | Use external tools |
| **Collaborate in real-time** | ❌ Not provided | Use external tools |
| **Store in cloud** | ❌ Not provided | Store locally only |
| **Sync across machines** | ❌ Not provided | Manual copy only |
| **Multi-user** | ❌ Not provided | Single-user only |
| **Team permissions** | ❌ Not provided | Local policies only |
| **Compliance reporting** | ❌ Not provided | Manual export only |

## Recommendations

### When to Use Rig

✅ **Use Rig when:**
- You want governed AI coding workflows
- You need audit trails for AI actions
- You want isolated execution environments
- You need to verify what an AI did
- You want to prevent silent code mutations
- You're working on a single machine
- You're okay with local-only storage

### When NOT to Use Rig

❌ **Don't use Rig when:**
- You need multi-user collaboration
- You need cloud storage
- You need real-time features
- You need hosted/SaaS solutions
- You need team-based permissions
- You need compliance reporting
- You need fine-grained audit controls

## Getting Help

If you encounter a limitation that blocks your workflow:

1. **Check this document** — Your limitation may be known
2. **Check the issue tracker** — Search for existing issues
3. **Create a feature request** — If it's a missing feature
4. **Create a bug report** — If it's a bug
5. **Ask in discussions** — For usage questions

**Note:** Not all limitations will be addressed. Rig has explicit scope boundaries.

---

**Document Version:** 1.0
**Last Updated:** May 2025
**Rig Version:** 0.1.0a1
