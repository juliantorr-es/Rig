# Rig Release Checklist

> **Lightweight operational release discipline.**
> No enterprise process theater.

This checklist ensures Rig releases maintain governance integrity, replay compatibility, and projection stability.

---

## Pre-Release: Validation

### ✅ Code & Tests

- [ ] All validation commands pass
  ```bash
  bash scripts/check.sh
  ```
- [ ] All replay tests pass (73+ tests)
  ```bash
  python -m pytest tests/test_replay.py -v
  ```
- [ ] All integrity tests pass (38 tests)
  ```bash
  python -m pytest tests/test_integrity.py -v
  ```
- [ ] All projection contract tests pass (32 tests)
  ```bash
  python -m pytest tests/test_projection_contracts.py -v
  ```
- [ ] All UI frontend logic tests pass
  ```bash
  python -m pytest tests/test_ui_frontend_logic.py -v
  ```

### ✅ Doctor Commands

- [ ] Full integrity check passes
  ```bash
  python -m rig doctor all
  ```
- [ ] Projection contracts validated
  ```bash
  python -m rig doctor projections
  ```
- [ ] Integrity score is 1.00

### ✅ Replay validation

- [ ] Replay timeline produces valid JSON
  ```bash
  python -m rig replay timeline --json
  ```
- [ ] Replay determinism verified (run twice, compare outputs)
- [ ] No replay findings for known workspaces

### ✅ CLI Commands

- [ ] All CLI commands respond to `--help`
  ```bash
  python -m rig --help
  python -m rig ui --help
  python -m rig doctor --help
  python -m rig replay --help
  ```
- [ ] UI dry-run succeeds
  ```bash
  python -m rig window open --dry-run
  ```

---

## Pre-Release: Compatibility

### ✅ Python Version

- [ ] Python 3.14+ requirement enforced in `pyproject.toml`
- [ ] CI workflow uses Python 3.14
- [ ] All `requires-python` declarations are `>=3.14`

### ✅ Dependency Integrity

- [ ] No new external dependencies without justification
- [ ] No SaaS/cloud dependencies in core governance
- [ ] UI dependencies (aiohttp, pywebview) are optional extras
- [ ] Dev dependencies (pytest, pyright, ruff) are optional extras

### ✅ Backwards Compatibility

- [ ] **Receipt Schema:** No breaking changes to existing receipt types
  - No required fields added
  - No field types changed
  - No fields removed
- [ ] **Projection Contracts:** No breaking changes to existing projections
  - No required fields added to existing projections
  - No fields removed from existing projections
- [ ] **CLI Commands:** No breaking changes to command interfaces
  - No command names changed
  - No required arguments added
  - No argument semantics changed

---

## Pre-Release: Governance

### ✅ Receipt Chain Integrity

- [ ] All test workspaces have complete receipt chains
- [ ] No missing receipts in golden fixture tests
- [ ] Receipt continuity validation passes
  ```bash
  python -m pytest tests/test_replay.py::TestValidateReplayReceiptContinuity -v
  ```

### ✅ Replay Determinism

- [ ] Determinism tests pass
  ```bash
  python -m pytest tests/test_replay.py::TestReplayDeterminism -v
  ```
- [ ] Replay comparison produces identical results for same inputs

### ✅ Authority Safety

- [ ] No authority escalation in replay (advisory stays advisory)
- [ ] No authority demotion in replay (authoritative stays authoritative)
- [ ] Projections preserve authority/advisory flags

### ✅ Projection Safety

- [ ] Projections derive ONLY from canonical evidence
- [ ] No state invention in projections
- [ ] Missing data shows as placeholders
- [ ] Projection contract tests pass

---

## Pre-Release: Documentation

### ✅ Release Notes

- [ ] CHANGELOG.md updated with all changes since last release
- [ ] Breaking changes clearly marked
- [ ] Version numbers updated
- [ ] Release date added

### ✅ Architecture Docs

- [ ] docs/architecture/README.md is up to date
- [ ] New components documented
- [ ] Changed behavior documented

### ✅ Getting Started

- [ ] README.md has correct install instructions
- [ ] README.md has working quickstart commands
- [ ] First successful commands are documented and tested

---

## Pre-Release: Security

### ✅ Token & Secret Redaction

- [ ] No hardcoded tokens or secrets in source
- [ ] Debug bundles are redacted (test with `rig debug bundle`)
- [ ] UI output does not expose tokens in projections
- [ ] Log files do not contain sensitive data

### ✅ Input Validation

- [ ] All external inputs validated
- [ ] No SQL injection vectors (Rig uses DuckDB with parameterized queries)
- [ ] No XSS vectors in frontend (widgets use textContent only)

---

## Pre-Release: Packaging

### ✅ Package Metadata

- [ ] `pyproject.toml` version updated
- [ ] `pyproject.toml` dependencies are current
- [ ] Package builds cleanly
  ```bash
  python -m build
  ```

### ✅ Installer Smoke Tests

- [ ] Fresh install succeeds
  ```bash
  python3.14 -m venv /tmp/rig_test
  source /tmp/rig_test/bin/activate
  python -m pip install -e ".[ui,dev]"
  python -m rig --help
  ```
- [ ] All optional dependency groups installable
  ```bash
  python -m pip install -e ".[ui,dev,docs,ml,legacy_tui]"
  ```

---

## Release: Tagging & Publishing

### ✅ Version Tagging

- [ ] Version tag created with `v` prefix (e.g., `v0.1.0a1`)
- [ ] Tag message describes the release
- [ ] Tag points to correct commit

### ✅ GitHub Release

- [ ] Release created on GitHub with tag
- [ ] Release notes copied from CHANGELOG.md
- [ ] Assets attached if applicable (wheel, sdist)

### ✅ Post-Release Validation

- [ ] Release tag is protected
- [ ] Release artifacts are verified
- [ ] Release notification sent (if applicable)

---

## Post-Release

### ✅ Announcements

- [ ] Release announced to contributors (if applicable)
- [ ] Known issues documented
- [ ] Upgrade instructions provided (if needed)

### ✅ Monitoring

- [ ] CI passes for release tag
- [ ] No immediate regression reports
- [ ] Release metrics tracked

---

## Rollback |

> **Rollback is a governance action, not a technical failure.**

### Rollback Triggers

- [ ] Critical regression in governance (authority escalation possible)
- [ ] Receipt schema breakage
- [ ] Projection contract breakage causing UI failures
- [ ] Security vulnerability

### Rollback Procedure

1. Identify the faulty commit
2. Create a rollback commit that reverts the change
3. Tag a new patch release (e.g., `0.1.0a1-rollback-1`)
4. Document the rollback in CHANGELOG.md
5. Notify contributors

**Do NOT use `git revert` for complex changes** — Create explicit rollback commits that re-establish correct state.

---

## Release Types

### Alpha Releases (`0.Y.Z-aN`)

- Experimental features
- May have known issues
- Not recommended for production
- Feedback welcome

### Beta Releases (`0.Y.0-bN`)

- Feature complete for next minor version
- API close to final
- Recommended for testing

### Stable Releases (`0.Y.0`)

- Production ready
- Long-term support
- Breaking changes only in MAJOR version

---

## Version Numbering

| Version | Format | Meaning |
|---------|--------|---------|
| MAJOR | X.0.0 | Breaking changes to receipt schema, governance, or projections |
| MINOR | 0.Y.0 | Backwards-compatible new features |
| PATCH | 0.0.Z | Bug fixes, documentation, non-breaking changes |
| Pre-release | X.Y.Z-aN | Alpha N of X.Y.Z |
| Pre-release | X.Y.Z-bN | Beta N of X.Y.Z |

---

## Quick Validation Script

Run this before any release:

```bash
#!/usr/bin/env bash
set -e

echo "=== Pre-Release Validation ==="
echo ""

# Syntax
python3.14 -m compileall -q src tests

# Tests
python -m pytest tests/test_replay.py -v
python -m pytest tests/test_integrity.py -v
python -m pytest tests/test_projection_contracts.py -v
python -m pytest tests/test_ui_frontend_logic.py -v

# Doctor
python -m rig doctor all
python -m rig doctor projections

# Replay
python -m rig replay timeline --json

# CLI
python -m rig ui --help
python -m rig window open --dry-run

echo ""
echo "✓ All pre-release checks passed!"
```

---

## Summary

This checklist ensures every Rig release:
- ✅ Passes all validation tests
- ✅ Maintains backwards compatibility
- ✅ Preserves governance integrity
- ✅ Has complete documentation
- ✅ Is ready for contributors to use

**Time estimate:** 30-60 minutes for a trained maintainer.
