Historical narrative. Not current workflow authority.

# 2026-05-09 — Docs Purge

## Situation
Rig's documentation had ballooned out of control. We had accumulated a massive amount of architectural documents, test plans, and legacy instructions.

## The Pain
Stale docs were becoming hostile prompts. Agents were reading outdated documentation and treating it as canonical authority, trying to revive dead features or follow abandoned architectures. The noise ratio was drowning out the actual governance rules.

## False Starts
Keeping "CONTEXT_PACK" docs, complex visualization semantics, and overly specific UI documentation (like the Gridline Interface and Textual TUI) around for "reference." We thought they'd be useful history, but they actively confused the system.

## Decision
A massive docs purge. We abandoned the Gridline/Textual/TUI, removed all the CONTEXT_PACK docs, and cleared out the proof/audit clutter. We introduced this chronicle as the pressure valve—a place to put narrative history so the current docs authority stack (like `AGENTS.md`) could remain pristine and operational.

## Evidence
- Massive deletion of `docs/architecture/*` and `docs/proofs/*`
- `AGENTS.md` (the canonical authority)
- The establishment of the `docs/chronicles/` directory

## Lesson
Stale documentation is toxic to agentic workflows; delete it ruthlessly or move it to a clearly marked historical narrative.

## Channel Hook
The Great Docs Purge: Why Stale Documentation is a Hostile Prompt.
