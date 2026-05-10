---
name: rig-architecture-deepening
description: Find authority-boundary opportunities and emit Rig ADR proposals.
category: governance
use_when:
  - The code suggests an authority boundary is missing.
  - A deep module should become explicit.
do_not_use_when:
  - The work is already bounded and tactical.
  - The task needs immediate implementation.
inputs:
  - Codebase area under review
  - Authority or contract pressure points
outputs:
  - ADR proposals
  - Sprint and mission proposals
required_context:
  - Current code
  - Relevant ADRs and workflow docs
required_gates:
  - Name the boundary
  - Propose follow-up work
workflow_stage: discovery
authority_boundaries:
  - No sprawling refactors
  - No direct implementation plan as the final output
handoff_requirements:
  - Describe the proposed boundary and next steps
---

# Rig Architecture Deepening

Use when the code suggests a deeper authority boundary or contract should exist.

## Do

- Identify the boundary.
- Propose ADR, sprint, and mission follow-ups.
- Keep output as proposals, not sprawling implementation.

## Do not

- Jump straight into refactors without a decision record.
