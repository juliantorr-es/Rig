---
name: rig-write-skill
description: Create new Rig-native skills that validate against the Rig skill schema.
category: writing
use_when:
  - A new Rig skill is needed.
  - An existing Rig skill needs a schema-backed update.
do_not_use_when:
  - The request is for unrelated docs.
  - The output should be an ADR or mission instead.
inputs:
  - Skill intent
  - Rig skill schema
outputs:
  - New SKILL.md
  - Validation result
required_context:
  - docs/schemas/rig-skill.schema.json
  - Existing Rig skill examples
required_gates:
  - Validate frontmatter against the schema
  - Keep the skill Rig-native
workflow_stage: adr
authority_boundaries:
  - No verbatim copying
  - No generic filler
handoff_requirements:
  - Report files created and validation status
---

# Rig Write Skill

Use when creating or updating Rig-native skills.

## Do

- Write short, Rig-specific skills.
- Validate every skill against `docs/schemas/rig-skill.schema.json`.
- Keep the skill aligned with Rig authorities and gates.

## Do not

- Copy another skill verbatim.
- Add general-purpose filler.
