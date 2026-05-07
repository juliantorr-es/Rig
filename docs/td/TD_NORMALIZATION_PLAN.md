# TD Normalization Plan

This is a proposal-only normalization pass for docs-as-code and TD discipline. It does not convert every note into a task, and it does not relaunch deferred legacy work.

## Current problem

Rig has useful documentation, but the source of truth is split across:
- roadmap notes
- proof/evidence notes
- migration/planning notes
- task-shaped implementation notes
- architecture/context packs
- ad hoc stabilization reports

That mix makes it too easy for a future capability, proof, or advisory note to be mistaken for an active task.

## Desired structure

Proposed tree only:
- `docs/td/ready/`
- `docs/td/in_progress/`
- `docs/td/blocked/`
- `docs/td/in_review/`
- `docs/td/done/`
- `docs/td/archived/`
- `docs/td/followups/`

## TD normalization rules

- A roadmap item is not an active task.
- A future capability is not an implementation task.
- A proof or receipt records evidence; it does not define current work.
- Active tasks must include status, goal, source of truth, non-goals, scope, acceptance criteria, validation, and evidence/proof requirement.
- Follow-ups should be parked, not implemented immediately.
- Deprecated or legacy areas should be explicitly archived or deferred, not silently deleted.

## Conversion guidance

### Keep as-is
- Architecture explanations.
- How-to guides.
- Reference docs.
- Decision records.
- Proof/receipt artifacts.

### Convert to TD
- Task-shaped docs that still describe actionable work.
- Migration notes that are still being executed.
- Queue/harness/setup notes that imply pending implementation.

### Convert to roadmap
- Future capabilities that are not active work.
- Deferred capability descriptions that belong in strategic planning.

### Convert to proof
- Stabilization notes.
- Validation/hardening summaries.
- Completed milestone notes that are evidence, not tasks.

### Convert to decision record
- Documents that primarily capture a settled policy or architecture choice.

### Archive
- Legacy TUI notes.
- Deprecated surfaces that should no longer be treated as current work.

## Proposed initial triage buckets

### `docs/td/ready/`
- None yet. Only create entries after the inventory is used to separate active work from evidence.

### `docs/td/in_progress/`
- Only for work with an explicit owner and a live validation path.

### `docs/td/blocked/`
- Use for tasks blocked by external dependencies or unresolved prerequisites.

### `docs/td/in_review/`
- Use for TD items awaiting validation or human sign-off.

### `docs/td/done/`
- Use only when the task has proof attached and no further implementation is expected.

### `docs/td/archived/`
- Use for legacy or superseded implementation notes.

### `docs/td/followups/`
- Use for parked ideas and post-stabilization notes that should not enter the active queue.

## Recommended first-wave moves

1. Convert task-shaped `docs/dev/rig/*.md` notes into TD entries only if they are still actionable.
2. Convert stabilization/hardening notes into proof artifacts when they only record completed work.
3. Archive legacy TUI notes instead of leaving them in ambiguous active-looking folders.
4. Add a small TD index once the first conversions exist.
5. Keep roadmap pages narrowly future-facing.

## Validation expectations

- TD entries stay explicit about scope and evidence.
- Proofs remain evidence-only.
- Roadmaps remain future-facing.
- No runtime code changes are required for this pass.

## Open questions

- Which task-shaped docs are still live vs already superseded?
- Which ad hoc notes should be promoted to proofs vs archived?
- Should there be a single `docs/td/index.md` once conversion begins?
