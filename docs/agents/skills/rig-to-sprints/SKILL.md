---
name: rig-to-sprints
description: Break one ADR into substantial Rig implementation sprints.
category: workflow
use_when:
  - An ADR needs one or more implementation campaigns.
  - Scope is large enough to justify separate sprints.
do_not_use_when:
  - The work is already at mission granularity.
  - The ADR still needs clarification.
inputs:
  - ADR Markdown or JSON
  - Relevant codebase context
outputs:
  - Sprint proposals
  - Sprint boundaries and goals
required_context:
  - ADR Markdown and JSON
  - docs/workflow/adr-sprint-mission-evidence.md
required_gates:
  - Keep sprints substantial
  - Avoid recursive decomposition
workflow_stage: sprint
authority_boundaries:
  - No task slicing into tiny tickets
  - No implementation edits
handoff_requirements:
  - Include sprint goals and why each exists
---

# Rig To Sprints

Use when one ADR needs implementation campaigns.

## Do

- Split the ADR into a few substantial sprints.
- Keep each sprint coherent and reviewable.
- Tie each sprint back to the ADR authority.

## Do not

- Create nested subtasks.
- Slice work into tiny tickets.
