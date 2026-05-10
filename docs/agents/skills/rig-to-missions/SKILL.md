---
name: rig-to-missions
description: Break one Rig sprint into substantial missions.
category: workflow
use_when:
  - A sprint needs execution packets.
  - Work should be delegated as flat missions.
do_not_use_when:
  - The sprint is still underspecified.
  - The request is for direct implementation.
inputs:
  - Sprint scope
  - Relevant repo state
outputs:
  - Mission list
  - Mission boundaries
required_context:
  - Sprint plan
  - Allowed and protected path list
required_gates:
  - Keep missions substantial and flat
  - Include validation and out-of-scope findings
workflow_stage: mission
authority_boundaries:
  - No nested missions
  - No micro-slices
handoff_requirements:
  - Include completion criteria and validation
---

# Rig To Missions

Use when a sprint needs agent-sized execution packets.

## Do

- Define research, allowed paths, protected paths, completion criteria, validation, and out-of-scope findings.
- Keep missions flat and substantial.
- Prefer one coherent handoff per mission.

## Do not

- Create nested missions.
- Emit tiny slices that do not stand alone.
