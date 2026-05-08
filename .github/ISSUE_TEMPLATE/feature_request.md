---
name: Feature Request
about: Propose a Rig improvement or new capability
title: "[FEAT] "
labels: enhancement, needs-triage
assignees: ''
---

> **Note:** Rig has strict scope boundaries. Please review [CONTEXT.md](../CONTEXT.md) and [ROADMAP.md](../docs/roadmap/README.md) before submitting.

## Problem Statement

<!-- What problem does this feature solve? -->
<!-- Why is the current behavior insufficient? -->

## Proposed Solution

<!-- Describe the feature you'd like to see -->

## Why It Matters

<!-- 
- Why is this important for Rig's mission?
- How does it improve governance, replay, or projections?
- Who benefits from this feature?
-->

## Scope Assessment

**Rig's Core Doctrine:**
- Models propose; Rig disposes
- Local-first, offline-capable governance
- No auto-apply, no auto-accept
- Replayable from receipts alone
- Projection-only UI

**Please confirm this proposal aligns with Rig's doctrine:**

- [ ] This feature does NOT add new AI capabilities
- [ ] This feature does NOT add new governance systems
- [ ] This feature does NOT add new replay systems
- [ ] This feature does NOT require hosted/SaaS components
- [ ] This feature does NOT add OAuth or authentication
- [ ] This feature does NOT add database dependencies
- [ ] This feature maintains local-first operation
- [ ] This feature maintains replay determinism
- [ ] This feature maintains projection contracts

## Implementation Considerations

### Impact on Receipt Schema

- [ ] No changes to existing receipt types
- [ ] Adds new receipt type(s): _______
- [ ] Modifies existing receipt type(s): _______

### Impact on Projection Contracts

- [ ] No changes to existing projections
- [ ] Adds new projection(s): _______
- [ ] Modifies existing projection(s): _______

### Impact on Governance Engine

- [ ] No changes to existing gates
- [ ] Adds new gate(s): _______
- [ ] Modifies existing gate(s): _______

### Dependencies

- [ ] No new dependencies
- [ ] New dependency(ies): _______
- [ ] New optional dependency group: _______

### Breaking Changes

- [ ] No breaking changes
- [ ] Breaking changes to: _______
- [ ] Migration path: _______

## Example Usage

<!-- How would users interact with this feature? -->
```bash
# CLI examples
python -m rig ...
```

## Alternatives Considered

<!-- What other approaches did you consider? Why was this one chosen? -->

## Related Documentation

<!-- Links to relevant docs, ADRs, or issues -->
- [ ] CONTEXT.md defines terms used
- [ ] Architecture docs explain relevant components
- [ ] Related issues: #______

## Validation Plan

<!-- How would this feature be tested? -->
- [ ] Unit tests for new functionality
- [ ] Integration tests for new workflows
- [ ] Replay tests for new receipt types
- [ ] Projection contract tests for new projections
- [ ] Manual validation of end-to-end flow

## Acceptance Criteria

<!-- What must be true for this feature to be considered complete? -->
- [ ] Documentation updated
- [ ] Tests added and passing
- [ ] `bash scripts/check.sh` passes
- [ ] Replay determinism maintained
- [ ] Projection contracts maintained
- [ ] Backwards compatibility maintained

## Additional Context

- Blocked by:
- Blocks:
- Related proposals:
