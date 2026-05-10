---
name: rig-handoff
description: Produce a Rig-format final handoff with evidence, gates, and scope notes.
category: governance
use_when:
  - Work is ready to close out.
  - A mission or sprint needs a governed summary.
do_not_use_when:
  - Implementation is still in flight.
  - Evidence is incomplete.
inputs:
  - Dirty state
  - Tests and validation results
  - Scope notes
outputs:
  - Final handoff summary
  - Evidence checklist
required_context:
  - Dirty-before state
  - Change list
  - Validation results
required_gates:
  - Separate pre-existing dirt from task work
  - Include forge gates and reviewability
workflow_stage: handoff
authority_boundaries:
  - No hiding blockers
  - No merging unrelated follow-up work
handoff_requirements:
  - Include out-of-current-scope findings
---

# Rig Handoff

Use when a task is ready to close out.

## Do

- Summarize dirty-before state, changed files, created files, deleted files, tests, blockers, forge gates, reviewability, and out-of-current-scope findings.
- Separate task-owned work from pre-existing dirt.
- State whether runtime behavior changed.

## Do not

- Hide blockers.
- Merge unrelated follow-up work into the handoff.
