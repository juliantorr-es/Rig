# 01 — Origin Story: The Tooling Became the Product

Rig did not start as a grand standalone product. It emerged from pressure.

Anigma had already created the conditions: a serious codebase, a lot of architecture doctrine, zero-copy ambitions, native Apple Silicon constraints, validators, governance documents, evidence artifacts, and enough moving pieces that ordinary “just ask an AI to code it” workflows started looking reckless.

At first, the supporting structure looked like project hygiene. Structured folders. JSON manifests. Markdown task specs. Validators. Proof files. Context packs. Review gates.

Then the punchline arrived:

> The scaffolding was not just helping the project. The scaffolding was the product.

Rig became the name for that realization.

## The original pain

The pain was not that AI agents could not write code. They absolutely could.

The pain was that they could write code in ways that were hard to trust:

- They could touch too many files.
- They could lose previous work.
- They could claim completion without evidence.
- They could pass a narrow test while breaking architectural intent.
- They could overwrite user-owned dirty files.
- They could confuse “generated output” with “source of truth.”
- They could make the repo feel haunted.

The human cost was not abstract. Every bad agent run created cleanup labor. Every unclear handoff created decision fatigue. Every missing receipt forced a reconstruction of what happened.

Rig grew out of that frustration.

## The initial doctrine

The earliest doctrine was simple:

> Receipts are evidence, not decoration.

That one sentence explains most of the project.

A tool should not merely say it did something. It should leave behind enough structured evidence for the next human or agent to understand what changed, why it changed, and how to verify it.

That doctrine turned into workspace state, proposal lifecycles, apply gates, known limitations, context packs, release notes, validator outputs, and the habit of treating documentation as operational infrastructure instead of dead text.

## The split from Anigma

The moment Rig became its own repository mattered. It changed the mental model from “helper scripts inside Anigma” to “a governed system that can stand on its own.”

That split introduced its own struggle. Package paths broke. Compatibility wrappers were needed. Shared helpers and assets had to be repaired. The repo needed scaffolding, checks, migration notes, workflows, and a credible installation story.

But that pain was clarifying.

A product cannot remain a private nest of scripts forever. It needs shape. It needs installability. It needs a user path that does not require already understanding the author’s entire brain.

## The real thesis

Rig’s origin story is not about writing a CLI. It is about discovering that AI coding needs a control plane.

The model can propose. The system must govern.

The model can draft. The system must validate.

The model can act. The system must make action auditable.

That is the origin of Rig.
