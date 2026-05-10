---
name: rig-tdd
description: Run Rig red/green/refactor work with required validation gates.
category: engineering
use_when:
  - Behavior must change safely.
  - Tests should lead the implementation.
do_not_use_when:
  - The task is documentation-only.
  - The work is pure analysis.
inputs:
  - Target behavior
  - Existing tests and compile state
outputs:
  - Failing test
  - Minimal fix
  - Regression coverage
required_context:
  - Current tests
  - scripts/check.sh expectations
required_gates:
  - Compile
  - Focused tests
  - Collection
  - check.sh where relevant
workflow_stage: implementation
authority_boundaries:
  - No skipping failed tests
  - No broad refactors before proof
handoff_requirements:
  - State the tests run and what changed
---

# Rig TDD

Use for Rig code changes that need test-first discipline.

## Do

- Write or update the narrowest failing test first.
- Run compile, focused tests, collection, and `scripts/check.sh` where relevant.
- Keep refactors separate from behavior changes when possible.

## Do not

- Skip failing tests to force green.
- Broaden the validation scope beyond the task without reason.
