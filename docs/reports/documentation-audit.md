# Documentation Audit Report

Audit scope: repository docs, roadmap notes, proofs, ad hoc stabilization notes, and schema/reference artifacts.

## Summary

- Documents inventoried: 197
- Docs by class:
- active_task: 7
- architecture_explanation: 5
- decision_record: 7
- future_capability: 2
- how_to: 20
- legacy_or_archival: 5
- proof_or_receipt: 16
- reference: 127
- report: 7
- roadmap: 1

## Recommended actions

- archive: 5
- convert_to_proof: 4
- convert_to_roadmap: 1
- convert_to_td: 7
- keep_as_is: 180

## Findings

- Roadmap material and proof material overlap in a few places; the roadmap should stay future-facing, while proofs stay evidence-only.
- Several `docs/dev/rig/*.md` files are task-shaped notes without TD structure; those are the main normalization candidates.
- Legacy Textual/TUI notes are present and should be archived or clearly deferred, not revived.
- Schema/reference files are numerous and should remain source-of-truth adjacent, but they need a clearer index layer rather than individual promotion to tasks.

## Normalization approach

- Keep roadmap pages future-facing and separate from implementation task tracking.
- Convert only task-shaped docs that still imply active work into TD entries.
- Preserve proof/report artifacts as evidence unless they are clearly duplicate roadmaps.
- Archive legacy UI/TUI notes so they stop acting like active work.
- Add a small TD tree proposal, not a large bureaucracy.

## Proposed TD structure

- `docs/td/ready/`
- `docs/td/in_progress/`
- `docs/td/blocked/`
- `docs/td/in_review/`
- `docs/td/done/`
- `docs/td/archived/`
- `docs/td/followups/`

## Highest-priority normalization targets

1. Task-shaped `docs/dev/rig/*.md` notes that still read like active work.
2. Evidence/roadmap duplicates, especially the not-compiler pair.
3. Legacy TUI notes and proofs that should be explicitly archived.
4. Missing docs index layer for schemas/reference artifacts.
5. Ad hoc stabilization notes outside the docs/proofs convention.

## Deferred cleanup

- Full rewrite of architecture/context-pack docs.
- Broad schema-to-docs indexing work.
- Moving files until the index and classification settle.
