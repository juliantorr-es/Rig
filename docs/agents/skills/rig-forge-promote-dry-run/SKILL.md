---
name: rig-forge-promote-dry-run
description: Check Rig forge readiness without mutating git or remote state.
category: forge
use_when:
  - A promotion candidate needs readiness checks.
  - Protected branch movement is being considered.
do_not_use_when:
  - The task is unrelated to promotion.
  - Mutation is already approved elsewhere.
inputs:
  - Candidate branch
  - Forge budget and gate state
outputs:
  - Dry-run readiness result
  - Blockers and budget status
required_context:
  - rig forge doctor
  - rig forge promote --dry-run
required_gates:
  - Run doctor
  - Run dry-run promote
  - Block over-budget candidates
workflow_stage: promotion
authority_boundaries:
  - No git mutations
  - No direct protected-branch pushes
handoff_requirements:
  - Include promotion blockers and reviewability budget
---

# Rig Forge Promote Dry Run

Use when promotion readiness must be checked before a protected branch move.

## Do

- Run `rig forge doctor`.
- Run `rig forge promote --dry-run`.
- Block over-budget promotion candidates.
- Report blockers and reviewability budget clearly.

## Do not

- Mutate Git state.
- Push or merge protected branches directly.
