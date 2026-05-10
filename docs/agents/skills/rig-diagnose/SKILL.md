---
name: rig-diagnose
description: Reproduce, minimize, instrument, fix, and regression-test a Rig defect.
category: maintenance
use_when:
  - Something fails or behaves unexpectedly.
  - A bug must be isolated before fixing.
do_not_use_when:
  - The change is clearly mechanical.
  - No reproduction is needed.
inputs:
  - Failure report
  - Relevant logs or traces
outputs:
  - Root cause hypothesis
  - Fix
  - Regression test
required_context:
  - Reproduction steps
  - Current failure output
required_gates:
  - Reproduce
  - Minimize
  - Instrument
  - Fix
  - Regression-test
workflow_stage: validation
authority_boundaries:
  - No broad rewrite first
  - No hiding out-of-scope findings
handoff_requirements:
  - Classify out-of-current-scope findings
---

# Rig Diagnose

Use for bugs, regressions, and unexpected behavior.

## Do

- Reproduce the failure.
- Minimize the case.
- Instrument only what helps explain the fault.
- Fix the smallest safe cause.
- Regression-test the path that broke.
- Classify anything outside current scope.

## Do not

- Start with a broad rewrite.
- Hide unrelated findings.
