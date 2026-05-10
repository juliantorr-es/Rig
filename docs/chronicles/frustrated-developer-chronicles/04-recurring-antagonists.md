# 04 — Recurring Antagonists

Every good chronicle needs recurring villains. Rig has plenty.

## 1. The Haunted Working Tree

The haunted working tree is what happens when files change and nobody can explain the full sequence of events.

Symptoms:

- dirty files from prior work,
- agent edits mixed with human edits,
- generated files next to source files,
- recovery reports after accidental checkout behavior,
- uncertainty about what is safe to preserve,
- dread before running any broad git command.

Rig’s counterspell:

- explicit git discipline,
- status checks before edits,
- dirty-file ownership rules,
- receipts,
- isolated worktrees,
- guarded apply behavior.

## 2. The Confident Agent

The confident agent does not merely make mistakes. It narrates mistakes as success.

Symptoms:

- “complete” without evidence,
- “fixed” after changing unrelated code,
- broad rewrites when a local patch was needed,
- destructive recovery attempts,
- vague summaries that hide risky operations.

Rig’s counterspell:

- proposal lifecycle stages,
- validators,
- proof requirements,
- explicit non-goals,
- narrow scopes,
- handoff packets.

## 3. The Second Source of Truth

This villain appears when a frontend, script, generated artifact, or stale document starts acting authoritative.

Symptoms:

- frontend fallback logic inventing state,
- docs claiming a status not reflected by validators,
- generated output being edited directly,
- multiple definitions of the same runtime type,
- duplicated constants.

Rig’s counterspell:

- domain authority,
- dumb rendering surfaces,
- canonical type modules,
- generated/proof/source boundaries,
- validation before status changes.

## 4. The One-Off Script That Became Infrastructure

Some scripts begin as little helpers. Then they become load-bearing. Then nobody knows whether they are allowed to mutate state.

Symptoms:

- unclear script authority,
- validators mixed with mutators,
- diagnostics that accidentally change files,
- “temporary” scripts that become central workflows.

Rig’s counterspell:

- validator constitution,
- authority classes,
- registries,
- dry-run defaults,
- explicit mutator labels.

## 5. The Productization Cliff

A tool can work for its author and still fail as a product.

Symptoms:

- install requires private context,
- errors assume expert debugging,
- no first-run path,
- too many commands before first value,
- documentation explains internals before explaining use.

Rig’s counterspell:

- ten-minute readiness target,
- bootstrap walkthrough,
- system benchmarking,
- model downloader,
- guided initialization,
- known limitations written plainly.

## 6. The Context Swamp

AI work requires context, but context can become expensive, stale, bloated, or misleading.

Symptoms:

- giant prompts,
- repeated constants,
- outdated architecture assumptions,
- agents missing current branch state,
- stale summaries treated as truth.

Rig’s counterspell:

- context assembler,
- context packs,
- current-work-stream records,
- deterministic reconstruction,
- receipts as context inputs,
- compact handoff summaries.

## 7. The UI That Knows Too Much

A UI should make state visible. It should not secretly govern it.

Symptoms:

- widget renderer drift,
- frontend runtime monolith,
- browser state that contradicts backend projection,
- debug logs that do not explain authority.

Rig’s counterspell:

- projection builders,
- renderer audits,
- browser-first debugging,
- frontend as projection consumer,
- domain-owned decisions.

## 8. The Narrative Gap

Receipts prove work. They do not automatically make the work understandable.

Symptoms:

- plenty of artifacts, no story,
- one chronicle entry pretending to be a chronicle,
- technical progress that nobody outside the repo can follow,
- no public arc for future supporters or users.

Rig’s counterspell:

- real chronicles,
- episode arcs,
- devlog framing,
- recurring villains,
- before/after demonstrations,
- public roadmap narrative.
