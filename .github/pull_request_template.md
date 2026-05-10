# Pull Request

> **Before submitting:** Ensure all validation commands pass. See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Summary

<!-- Clear, concise description of what this PR changes -->

## Motivation

<!-- Why is this change needed? Link to issues, discussions, or roadmap items -->
- Closes #______
- Related to #______
- Part of: [roadmap item](../docs/roadmap/)

## Changes

### Code Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `src/rig/...` | Added/Modified/Removed | What changed and why |
| `tests/...` | Added/Modified | Test coverage for changes |

### Documentation Changes

- [ ] No documentation changes needed
- [ ] docs/... updated
- [ ] README.md updated
- [ ] Other: _______

## Validation

**Required:** All checks must pass before review.

### Canonical Validation

```bash
# Run this before requesting review
bash scripts/check.sh
```

### Individual Checks

- [ ] `python3.14 -m compileall -q src tests` — Syntax check
- [ ] `python -m pytest tests/test_replay.py -v` — Replay tests (73+) 
- [ ] `python -m pytest tests/test_integrity.py -v` — Integrity tests (38)
- [ ] `python -m pytest tests/test_projection_contracts.py -v` — Projection tests (32)
- [ ] `python -m pytest tests/test_ui_frontend_logic.py -v` — UI logic tests
- [ ] `python -m rig doctor all` — Full integrity check
- [ ] `python -m rig doctor projections` — Projection contract validation
- [ ] `python -m rig replay timeline --json` — Replay timeline
- [ ] `python -m rig ui --help` — UI help command
- [ ] `python -m rig window open --dry-run` — UI dry-run

### Targeted Validation

<!-- Run these if your changes affect specific areas -->
- [ ] Replay-specific tests
- [ ] Projection contract tests  
- [ ] UI frontend logic tests
- [ ] Doctor command tests
- [ ] Other: _______

## Impact Assessment

### Replay/Integrity Impact

- [ ] No impact on replay or integrity
- [ ] Modifies replay behavior (describe):
- [ ] Affects receipt schema (describe):
- [ ] Changes replay determinism (describe):
- [ ] Breaks existing replay tests (fix required):

**Replay validation:**
```bash
# Run before and after to verify determinism
python -m rig replay timeline --json > before.json
# ... make changes ...
python -m rig replay timeline --json > after.json
# Compare: diff before.json after.json
```

### Projection Contract Impact

- [ ] No impact on projection contracts
- [ ] Adds new projection(s):
- [ ] Modifies existing projection(s):
- [ ] Breaks projection contract tests:

### Governance Impact

- [ ] No impact on governance
- [ ] Adds new gate(s):
- [ ] Modifies existing gate(s):
- [ ] Changes authority behavior:
- [ ] Affects deny-by-default posture:

### CLI Impact

- [ ] No CLI changes
- [ ] New command(s):
- [ ] Modified command(s):
- [ ] Changed flags/arguments:
- [ ] Breaking CLI changes:

### UI Impact (if applicable)

- [ ] No UI changes
- [ ] New widget(s):
- [ ] Modified widget(s):
- [ ] Requires `disabled_reason` from backend:
- [ ] Screenshots attached:

## Screenshots/Logs

<!-- Attach screenshots for UI changes, logs for debugging -->

## Risk Assessment

### Breaking Changes

- [ ] No breaking changes
- [ ] Breaking changes to:
  - [ ] Receipt schema
  - [ ] Projection contracts
  - [ ] CLI interface
  - [ ] API contracts
  - [ ] Other: _______

### Backwards Compatibility

- [ ] Fully backwards compatible
- [ ] Requires migration (document steps):
- [ ] Breaks existing workspaces:

### Security Considerations

- [ ] No security implications
- [ ] Fixes security vulnerability:
- [ ] Introduces new attack surface (describe mitigation):
- [ ] Security review needed:

## Testing

### Test Coverage

- [ ] New tests added for new functionality
- [ ] Existing tests modified for changed behavior
- [ ] All existing tests pass
- [ ] Test count: __ new tests, __ modified tests

### Manual Testing

<!-- Describe manual testing performed -->

## Documentation

- [ ] Code comments updated
- [ ] Docstrings updated
- [ ] docs/ updated
- [ ] README.md updated (if needed)
- [ ] CHANGELOG.md updated (if releasing)

## Checklist

### Before Requesting Review

- [ ] Code follows existing patterns (see AGENTS.md)
- [ ] No destructive Git commands used (see CONTRIBUTING.md)
- [ ] Changes are minimal and focused
- [ ] All validation commands pass (see above)
- [ ] No broad formatters run (ruff format, etc.)
- [ ] No pre-existing dirty files were modified unintentionally
- [ ] Git history is clean (no unnecessary commits)

### Before Merging

- [ ] All CI checks pass
- [ ] PR has been reviewed by at least one maintainer
- [ ] All reviewers' concerns have been addressed
- [ ] Documentation is complete
- [ ] CHANGELOG.md updated (if applicable)

## Notes

<!-- Any additional information for reviewers -->

### Follow-up Required

- [ ] None
- [ ] Issues to be created:
- [ ] Documentation to be added:
- [ ] Cleanup needed:

## Review Guidance

**Reviewers, please focus on:**
1. **Replay determinism** — Does this break existing replay behavior?
2. **Projection contracts** — Are projections still derived correctly?
3. **Governance doctrine** — Does this maintain deny-by-default?
4. **Trust boundaries** — Are trust levels preserved?
5. **Backwards compatibility** — Does this break existing workflows?
6. **Test coverage** — Is new functionality properly tested?

See [Architecture Docs](../docs/architecture/README.md) for component details.
