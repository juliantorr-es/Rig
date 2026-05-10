---
name: Bug Report
about: Report a reproducible Rig failure
title: "[BUG] "
labels: bug, needs-triage
assignees: ''
---

> **Before filing:** Please run `bash scripts/check.sh` to ensure this isn't a validation issue.

## Summary

<!-- Clear, concise description of the issue -->

## Steps to Reproduce

<!-- Exact commands to reproduce the issue. Be specific. -->
```bash
# Example:
# 1. python -m rig workspace create test
# 2. python -m rig run --task implement-feature-x --provider custom-command
# 3. python -m rig workspace apply
```

## Expected Behavior

<!-- What should happen -->

## Actual Behavior

<!-- What actually happens -->

## Environment

- **Python version:** `python --version`
- **Rig version:** `python -m rig --version` or commit hash
- **OS:** macOS/Linux/Windows, version
- **Install method:** editable/dev/regular
- **Dependencies:** `python -m pip freeze` (if relevant)

## Receipts and Audit Trail

<!-- Run these commands and paste the output -->
```bash
# Show recent receipts
python -m rig replay timeline --json

# Show doctor output
python -m rig doctor all

# Show projections validation
python -m rig doctor projections
```

## Additional Context

<!-- Any other relevant information -->
- Related issues:
- Screenshots (if UI issue):
- Log output:

## Validation Checklist

- [ ] I have run `bash scripts/check.sh` and it passes (or fails with this specific issue)
- [ ] This is a bug in Rig itself, not a usage question
- [ ] I have checked existing issues for duplicates
- [ ] The issue is reproducible with the steps above
