---
name: rig-to-adr
description: Turn resolved Rig context into an ADR Markdown and JSON pair.
category: writing
use_when:
  - The architectural decision is settled.
  - A new ADR needs both narrative and contract forms.
do_not_use_when:
  - The decision is still open.
  - The work belongs in a sprint or mission.
inputs:
  - Resolved context
  - Existing ADR conventions
outputs:
  - ADR Markdown file
  - ADR JSON companion
required_context:
  - docs/schemas/rig-adr.schema.json
  - docs/adr/README.md
  - docs/workflow/adr-sprint-mission-evidence.md
required_gates:
  - Validate JSON against rig-adr.schema.json
  - Keep Markdown and JSON aligned
workflow_stage: adr
authority_boundaries:
  - No bulk ADR rewrites
  - No implementation code
handoff_requirements:
  - Provide the paired ADR paths and validation result
---

# Rig To ADR

Use when the context is resolved enough to write a new ADR.

## Do

- Produce a Markdown ADR and a JSON companion.
- Validate the JSON against `docs/schemas/rig-adr.schema.json`.
- Keep the ADR narrow and decision-focused.

## Do not

- Convert every ADR at once.
- Invent implementation details that belong in sprints or missions.
