# Changelog

> **Semantic versioning for Rig: MAJOR.MINOR.PATCH**
>
> - **MAJOR**: Breaking changes to receipt schema, governance contracts, or projection interfaces
> - **MINOR**: Backwards-compatible new functionality (new receipt types, commands)
> - **PATCH**: Bug fixes, documentation improvements, non-breaking changes
>
> **Pre-1.0**: Version format is `0.Y.Z` where Y increments for significant feature additions, Z for bug fixes.

All notable changes to this project are documented in this file.

---

## [Unreleased]

### Added
- **Operational Maturity Phase 1** — Complete operational foundations
  - Rewritten [README.md](./README.md) with quickstart, architecture overview, validation examples
  - Expanded [CONTRIBUTING.md](./CONTRIBUTING.md) with Git discipline, development workflow
  - Canonical validation entrypoint: `scripts/check.sh`
  - Updated CI workflow: `.github/workflows/ci.yml` with Python 3.14 and full validation
  - Architecture navigation map: [docs/architecture/README.md](./docs/architecture/README.md)

### Changed
- **Governance Replay Phase 5 Completion** — Closed all 6 identified gaps
  - GAP-001: AuditEvent reconstruction from filesystem in `replay_workspace_from_fs()`
  - GAP-002: Explicit ReplayIntegrityFinding for corrupted files instead of silent skips
  - GAP-003: Golden test for corrupted replay ordering
  - GAP-004: Golden test for contradictory gate decisions
  - GAP-005: Golden test for stale receipt references
  - GAP-006: Robust status extraction with multiple fallback strategies
  - Reclassified Phase 5 from C) partially implemented to A) complete and trustworthy

### Fixed
- Corrupted receipt/audit files now produce explicit findings instead of being silently skipped
- Status extraction handles multiple field name variations across different receipt types
- AuditEvent objects properly reconstructed from filesystem data during replay

---

## [0.1.0a1] - 2025-XX-XX

### Added
- First public alpha release candidate
- Governance Replay Phase 5 (85% complete at time of tagging, now 100%)
- Deterministic replay from receipts and audit events
- Replay integrity validation
- Projection contract enforcement
- Complete test coverage for replay (70+ tests)

### Known Issues
- None — All Phase 5 gaps closed before this release

---

## Version History

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| 0.1.0a2 | TBD | Planned | Operational Maturity Phase 1 complete |
| 0.1.0a1 | 2025-XX-XX | Released | First public alpha, Phase 5 complete |
| 0.1.0 | Planned | Future | First stable release |

---

## Release Process

See [docs/release/RELEASE_CHECKLIST.md](./docs/release/RELEASE_CHECKLIST.md) for the complete release checklist.

### Validation Before Release

Before any release, the following must pass:

```bash
# Canonical validation
bash scripts/check.sh

# Replay determinism validation
python -m pytest tests/test_replay.py -v

# Projection contract validation
python -m pytest tests/test_projection_contracts.py -v

# Integrity validation
python -m pytest tests/test_integrity.py -v

# Doctor commands
python -m rig doctor all
python -m rig doctor projections

# Replay validation
python -m rig replay timeline --json
```

### Receipt Schema Stability

Receipt schema changes are **breaking changes** and require MAJOR version bump:
- Adding required fields to receipts
- Changing field types in receipts
- Removing fields from receipts
- Changing receipt validation rules

### Projection Contract Stability

Projection contract changes that break existing widgets require MINOR version bump:
- Adding new required projection fields
- Removing projection fields
- Changing projection field semantics

Non-breaking additions (new optional fields) can be PATCH releases.

---

## Contributing

Changes to this changelog are accepted via PR following the same review process as code changes.

Format guidelines:
- Use past tense for completed work
- Group changes by category (Added, Changed, Fixed, Deprecated, Removed, Security)
- Include links to relevant documentation
- Note breaking changes explicitly
- Update release date when tagging
