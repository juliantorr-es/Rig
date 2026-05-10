Historical narrative. Not current workflow authority.

# 2026-05-06 — Agent Control Plane Begins

## Situation
Rig was entering its early productization phase. We were starting to integrate local agents and raw prompts into the development workflow, testing the waters of an AI-assisted ecosystem.

## The Pain
There was deep governance anxiety. We were essentially throwing models at local repositories and hoping they didn't overwrite or destroy the state. Raw agent execution was too risky and unpredictable; models could easily cause catastrophic damage if given unconstrained write access.

## False Starts
Relying on raw agent execution without safety boundaries was the primary false start. Believing that agents could autonomously edit and merge code without supervision proved to be a liability.

## Decision
We established the "Proposal Lifecycle" and the core tenet: "Models propose, Rig disposes." Rig became the final authority on what changes are applied, shifting from a loose set of tools to an actual governance plane. Evidence and receipt thinking became foundational.

## Evidence
- `docs/dev/rig/AGENT_PROPOSALS.md` (now removed)
- `docs/architecture/CONTEXT_PACK_GOVERNANCE.md` (now removed)
- `docs/proofs/rig-productization-phase-1-2026-05-06.md`

## Lesson
Never give models unconstrained, authoritative write access. Safety, receipts, and explicit user intent matter more than agent speed.

## Channel Hook
Models Propose, Rig Disposes: Building a Paranoia-Driven Control Plane.
