# 03 — Chronicle of Struggles

## Prologue: the repo was not the problem

At several points, the obvious temptation was to say: “The codebase is getting too big.”

But that was not really it. Rig was not enormous. Compared with Anigma, it was manageable. The problem was that Rig had to encode discipline.

A normal project can tolerate some mess if a human understands the unwritten rules. Rig could not. The unwritten rules had to become machinery.

That meant the project kept turning vague instincts into hard surfaces:

- “Do not touch user-owned dirty files” became guard behavior.
- “Show your work” became receipts.
- “Do not claim completion without proof” became validation gates.
- “Do not let the frontend invent state” became projection authority.
- “Do not let agents freestyle repository surgery” became workspaces and isolated worktrees.

The struggle was translation: turning hard-earned paranoia into product design.

## Chapter 1: structured folders went too far, then became the point

At first, structured folders, JSON, and Markdown looked like project organization. Then they started carrying the operational load.

The files were not just notes. They became state boundaries, task surfaces, audit material, and handoff packets. The system started to treat documentation as something closer to a database with human-readable affordances.

That was both powerful and absurd.

Powerful because it made the work inspectable.

Absurd because the project kept proving that a disciplined pile of Markdown and JSON could outgrow a lot of supposedly more sophisticated tooling.

The recurring realization was:

> This should not work this well, but it does.

That realization is part of Rig’s DNA.

## Chapter 2: the agent did the thing, then lost the thing

One of the defining wounds was the lost lifecycle enrichment work.

The work existed. Then it got reverted. The details matter less than the category of failure: an agent touched files it should not have touched, and prior progress had to be reconstructed from scratch.

That kind of failure is not just annoying. It attacks trust.

It forced a sharper view of what Rig needs to prevent:

- no casual destructive checkout behavior,
- no treating dirty files as disposable,
- no assuming the agent understands ownership,
- no hiding behind “oops,”
- no action without recoverable evidence.

The recovery work was not wasted. It hardened the doctrine.

The slogan could be:

> If an agent can lose the work, the system must remember enough to rebuild it.

## Chapter 3: proposal lifecycle became a philosophy

The proposal lifecycle console was not just UI polish. It represented a deeper boundary.

A recommendation is not a proposal.

A proposal is not validation.

Validation is not proof of safe application.

Application is not completion.

Completion is not the same as evidence.

That sequence became important because AI tools collapse distinctions constantly. They present “I think this is done” as though it were equivalent to “the repo is safe, the tests pass, the architecture holds, and the human has accepted the change.”

Rig had to make those stages visible.

That is why stage-aware summaries, placeholder states like `unknown`, `unavailable`, `not_created`, `not_run`, and `not_proof`, and blocked apply notes mattered. They were not cosmetic. They were the interface saying:

> We do not lie about the state of the work just because a model wants closure.

## Chapter 4: browser UI made the invisible mess visible

The UI work introduced another class of struggle.

A browser-first debug mode sounded simple: run the UI, inspect logs, see what happened.

Then pywebview surfaced an unexpected keyword argument error. JavaScript threw duplicate constant declarations. Frontend runtime responsibilities had swollen into a monolith. Runtime state, WebSocket behavior, intent dispatch, projections, logs, render loops, stream chunks, and widget registries were tangled together.

This was not glamorous work. It was plumbing.

But the plumbing mattered because Rig needs to make agent behavior observable. A control plane without usable diagnostics is just a nicer-looking failure generator.

The lesson was blunt:

> Debuggability is product surface.

If a user cannot see what the system thinks is happening, they cannot trust the system when something goes sideways.

## Chapter 5: the frontend was not allowed to become a second backend

The backend/frontend wiring audits exposed a subtle problem. Projection builders created widget types. Frontend renderers had to match them. Some things were wired. Some things were missing or ambiguous.

The easy mistake would have been to make the frontend smarter.

Rig’s architecture pushed the opposite direction: the frontend should be dumb. It should render projection data. It should not become an authority engine.

This struggle matters because every “tiny little fallback” in the UI can become a second source of truth. Once that happens, debugging becomes theological. Which truth is true? The backend state? The frontend interpretation? The widget fallback? The stale browser runtime?

Rig’s answer was:

> Authority belongs in the domain layer. The UI renders state; it does not govern it.

## Chapter 6: runtime streaming became a consolidation battle

The runtime streaming work became another example of authority consolidation.

Types and constants had to become canonical. Imports had to stop drifting across modules. Tests had to prove type authority. Streaming state had to be less haunted.

This kind of work is tedious because it often does not produce an obvious new feature. But it reduces conceptual duplication. It prevents the codebase from becoming a set of nearly identical definitions that disagree in tiny fatal ways.

The chronicle version is simple:

> Half of building Rig was teaching the codebase to stop arguing with itself.

## Chapter 7: installation readiness became a product question

A tool is not a product if only its author can install it.

The migration to a standalone repo forced that uncomfortable truth. Rig needed repo scaffolding, checks, workflows, migration notes, package repair, compatibility wrappers, and eventually an install story where someone could get ready in under ten minutes.

This became one of the most important productization thresholds.

The project had to move from:

> “I can make this work on my machine.”

To:

> “A stranger can install this, understand the shape, and reach first value before they give up.”

That is a completely different standard.

## Chapter 8: every AI agent had a different flavor of chaos

Claude Code, Gemini, Vibe, OpenCode, and other CLI agents all suggested the same larger need: Rig should not depend on any one agent behaving perfectly.

The insight was not that one model is good and another is bad. The insight was that agents are inconsistent interfaces to capability.

Some are better at tool calls. Some are better at edits. Some are cheaper. Some are more verbose. Some are reckless. Some need stronger prompts. Some need guardrails so explicit they feel like legal contracts.

Rig’s opportunity is to normalize the chaos.

Instead of trusting every agent to invoke every command perfectly, Rig can make agents propose intent and let deterministic machinery validate, route, and apply changes.

That idea is a major product seam:

> The agent should describe what needs to happen. Rig should decide what is allowed to happen.

## Chapter 9: the pseudo-compiler instinct

The “pseudo compiler” idea emerged from frustration with funky codebase states.

The dream was not just linting. It was a deterministic layer that could decode a model’s proposed change, check it against repository rules, repair obvious issues, and refuse unsafe transformations.

That connects to a larger theme: smaller or cheaper models might become far more useful if the system around them absorbs more of the hard deterministic work.

Rather than requiring perfect tool-calling syntax from the model, Rig can accept structured or semi-structured intent, infer the real operation, validate it, and produce receipts.

The model becomes less of a wizard and more of a proposal generator.

The system becomes the adult in the room.

## Chapter 10: local models, dense context, and token paranoia

Another recurring struggle was context cost.

If Rig is going to orchestrate local agents, cloud models, context assemblers, receipts, and project history, then context cannot be treated as an infinite free buffet.

This led to questions about dense semantic representation, deterministic reconstruction, language compression, and whether constants in repeated prompts could be abstracted before transmission and reconstructed afterward.

The deeper concern was not merely saving tokens. It was control.

A serious control plane needs to know what context was sent, why it was sent, how it was compressed, and whether the result can be audited.

Even token optimization becomes governance once the context itself is evidence.

## Chapter 11: funding anxiety entered the architecture room

Rig was never just a technical exercise. There was also the practical question: how does this become something people can support?

Cash App, Apple Cash, Zelle, GitHub Sponsors, grants, and support channels entered the conversation because productization is not just code. It is survival infrastructure.

That pressure matters. It changes what “ready” means.

A project that might accept support money needs a credible story, a working alpha, a public roadmap, clear installability, a support mechanism, and enough narrative for people to understand why the work matters.

The chronicle is not separate from funding. The chronicle is part of making the project legible.

## Chapter 12: the chronicle problem

At one point the system had only one chronicle entry, which raised the obvious objection:

> How is it a chronicle if it has only one entry?

That question was correct.

A chronicle needs sequence. It needs tension. It needs incidents. It needs recurring villains and visible evolution. It needs enough narrative that someone could follow the transformation from “I am fighting my tools” to “I built a tool to govern the fight.”

Receipts tell what happened.

A chronicle tells what it felt like to survive it.

Rig needs both.

## Epilogue: the actual product promise

Rig’s promise is not that AI agents will stop being weird.

They will remain weird.

Rig’s promise is that their weirdness can be contained, inspected, normalized, and governed.

That is the product.
