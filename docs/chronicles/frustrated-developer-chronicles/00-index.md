# 00 — Index

## Reading order

1. `01-origin-story.md`
2. `02-the-shape-of-the-monster.md`
3. `03-chronicle-of-struggles.md`
4. `04-recurring-antagonists.md`
5. `05-agent-chaos-and-governance.md`
6. `06-productization-and-readiness.md`
7. `07-youtube-devlog-outline.md`
8. `08-quotes-and-one-liners.md`
9. `09-lessons-learned.md`

## The central arc

Rig began as tooling around a larger project, Anigma, but it became obvious that the tooling was not incidental. The tooling was the product. The hard part was not generating code. The hard part was keeping code generation bounded, inspectable, reversible, and governed.

The project kept surfacing the same question in different costumes:

> How do you let an AI agent act without letting it own the truth?

That question turned into a stack of practices: workspaces, isolated worktrees, receipts, validators, proposal lifecycles, review gates, known limitations, context packs, deterministic projections, and eventually the idea of Rig as a control plane for local AI coding.

## Main tensions

### Velocity versus safety

Fast agents can generate a lot of code. Fast agents can also delete or overwrite the wrong thing very confidently. Rig’s governance exists because “move fast and break things” is a terrible motto when the thing being broken is your working tree.

### Narrative versus receipts

A project can have a lot of evidence and still lack a readable story. Receipts prove what happened. Chronicles explain why it mattered.

### Product versus pile of scripts

Rig started as structured folders, JSON, Markdown, validators, and CLI glue. The tension became whether that was still amateur scaffolding or the beginning of a product-grade control plane.

### Local-first control versus cloud model power

The project repeatedly returned to a practical question: can cheap or local models be made useful if the surrounding system carries more of the determinism, validation, context assembly, and tool execution burden?

## Narrative through-line

The story is not “I built a CLI.”

The story is: “I got tired of AI agents acting like interns with root access, so I started building the adult supervision layer.”
