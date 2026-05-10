---
name: rig-grill-with-adrs
description: Challenge a plan against Rig authorities before implementation.
category: governance
use_when:
  - A plan needs validation before code changes.
  - The work may cross ADR, sprint, mission, or forge boundaries.
do_not_use_when:
  - The task is already fully specified and gated.
  - You need execution, not review.
inputs:
  - User goal or draft plan
  - Relevant ADR, schema, and workflow docs
outputs:
  - Resolved questions
  - Recommended answers
  - ADR, sprint, or mission implications
required_context:
  - AGENTS.md
  - docs/workflow/adr-sprint-mission-evidence.md
  - docs/adr/*.md and *.json when present
required_gates:
  - Compare against source-of-truth docs
  - Surface authority boundary conflicts
workflow_stage: discovery
authority_boundaries:
  - No code changes
  - No scope expansion into implementation
handoff_requirements:
  - Return the decision points and recommended direction
---

# Rig Grill With ADRs

Use when a plan needs pressure-testing against `AGENTS.md`, ADR Markdown/JSON, schemas, workflow docs, and current code.

## Do

- Resolve open questions.
- Compare the plan with authority boundaries.
- Call out missing gates, missing contracts, and unsafe assumptions.
- Return recommended answers and the downstream ADR/sprint/mission implications.

## Do not

- Change code.
- Draft implementation files.
- Expand scope into execution.
