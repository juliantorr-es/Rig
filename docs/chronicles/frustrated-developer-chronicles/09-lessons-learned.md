# 09 — Lessons Learned

## 1. The hard part is not generation. The hard part is trust.

AI agents can generate code. That is no longer the interesting part. The interesting part is whether the generated work is scoped, reviewable, validated, reversible, and honest about uncertainty.

## 2. Documentation can be operational infrastructure.

Markdown and JSON are not automatically amateur. If structured well, they can carry task state, receipts, proofs, validators, known limitations, and handoff context.

The amateur version is random notes.

The serious version is docs-as-control-surface.

## 3. A proposal is not a change.

This distinction needs to be enforced everywhere. The system should make it visually and procedurally obvious when something is merely recommended, when it has been turned into a proposal, when it has been validated, and when it has actually been applied.

## 4. Agents need blast-radius limits.

A coding agent without isolation is a liability. Worktrees, sandboxes, guarded git behavior, and dirty-file protection are not optional polish. They are core safety infrastructure.

## 5. The UI must not become a hidden authority layer.

A frontend should render state from an authoritative projection. It should not create secret interpretations that drift from backend truth.

## 6. Receipts are reusable context.

Receipts are not just audit trails for humans. They are future context for agents. A good receipt lets the next worker understand what happened without reconstructing the entire session from vibes.

## 7. Productization starts when strangers enter the story.

The author can tolerate rough edges because the author has context. A user cannot. Installation, first-run flow, diagnostics, and plain-language known limitations are product features.

## 8. Smaller models may become useful if the system gets smarter.

A weaker model does not need perfect tool use if Rig can decode intent, validate scope, route operations, repair predictable issues, and refuse unsafe actions.

## 9. Narrative matters.

Receipts prove the work. Chronicles make the work legible. If Rig is going to attract users, contributors, grants, or sponsors, the story needs to be understandable outside the repo.

## 10. The thesis survived the frustration.

Every failure reinforced the same direction:

> AI agents need governance, not just better prompts.

That is Rig’s reason to exist.
