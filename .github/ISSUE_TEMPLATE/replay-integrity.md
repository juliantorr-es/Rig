---
name: Replay/Integrity Issue
about: Report issues with receipt replay, continuity validation, or audit trail integrity
title: "[REPLAY] "
labels: bug, replay, needs-triage
assignees: ''
---

> **Critical:** Replay/integrity issues may indicate governance bypass. Please provide complete receipt chain information.

## Issue Type

- [ ] Receipt chain breakage
- [ ] Replay determinism failure
- [ ] Continuity validation error
- [ ] Authority escalation concern
- [ ] Missing receipts
- [ ] Orphaned audit events
- [ ] Receipt forgery suspicion
- [ ] Validation bypass suspicion
- [ ] Other (describe below)

## Summary

<!-- Describe the replay/integrity issue in detail -->

## Receipt Chain Information

<!-- Provide the receipt chain for investigation -->
```bash
# Full replay timeline (REQUIRED)
python -m rig replay timeline --json
```

## Specific Receipt Details

<!-- If a specific receipt is problematic, provide its details -->
- Receipt ID:
- Receipt Type:
- Created At:
- Actor:
- Subject:
- Decision:

## Environment

- **Python version:** `python --version`
- **Rig version:** `python -m rig --version` or commit hash
- **Workspace ID:** (if applicable)

## Doctor Output

<!-- Run these validation commands -->
```bash
# Full integrity check
python -m rig doctor all

# Projection contract validation
python -m rig doctor projections
```

## Steps to Reproduce

1. Start from clean state (if possible):
2. Run these commands:
3. Observe the issue:

## Expected vs Actual

| Aspect | Expected | Actual |
|--------|----------|--------|
| Receipt continuity | Unbroken chain | [Describe breakage] |
| Authority flags | Preserved | [Describe change] |
| Hash validation | Pass | [Describe failure] |
| Replay determinism | Identical | [Describe difference] |

## Impact Assessment

- [ ] Breaks replay entirely
- [ ] Produces incorrect state
- [ ] Allows authority escalation
- [ ] Corrupts audit trail
- [ ] Data loss possible
- [ ] Other: _______

## Urgency

- [ ] Critical — Governance may be bypassed
- [ ] High — Replay broken, data may be lost
- [ ] Medium — Replay works but with warnings
- [ ] Low — Cosmetic or minor issue

## Additional Context

- Related receipts:
- Screenshots (if applicable):
- Workaround (if any):

## Validation Checklist

- [ ] I have run `python -m rig replay timeline --json` and included output
- [ ] I have run `python -m rig doctor all` and included output
- [ ] This is a replay/integrity-specific issue, not a general bug
- [ ] The receipt chain is complete or I've identified which receipts are missing
- [ ] I have checked that this isn't a known issue in the changelog
