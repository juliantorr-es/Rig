# 02 — The Shape of the Monster

Rig is trying to become a local-first, governed control plane for AI-assisted software work.

That sounds clean. The actual work was not clean.

The project had to define its own shape while being built by the very class of tools it is trying to supervise. That is the monster: using AI agents to build the harness that keeps AI agents from causing damage.

## Core nouns

Rig’s world is built around a few blunt concepts.

### Workspaces

A workspace is a governed unit of work. It gives the agent a contained problem, a status boundary, and a place to attach evidence.

### Isolated worktrees

Agents should not be allowed to thrash the main working tree. Isolation is not aesthetic. It is blast-radius control.

### Receipts

A receipt is proof that something happened. Logs, validator outputs, diffs, known limitations, and handoff packets all belong to this world.

### Proposals

A proposal is not an applied change. It is advisory until accepted. This distinction matters because AI agents love acting like “I suggested it” and “I safely changed it” are the same thing. They are not.

### Gates

Review and apply gates protect the main branch. They are the difference between a useful assistant and a very confident vandal.

### Projections

The UI should render state. It should not invent authority. This is why projection data, frontend widgets, and backend domain authority kept becoming major architectural themes.

## What made it hard

The codebase was not huge. That was almost the insulting part.

The difficulty came from the shape of the problem, not raw size. Even a modest codebase becomes tricky when it needs:

- deterministic validators,
- agent-safe workflows,
- dirty-file protection,
- reproducible handoffs,
- multiple CLI agents,
- browser and terminal surfaces,
- UI projection consistency,
- strict governance semantics,
- and a product path understandable by non-experts.

In other words, the hard part was not scale by lines of code. The hard part was trust.

## The hidden product

The hidden product is not “AI writes code.” Everyone is chasing that.

The hidden product is:

> AI can propose work inside a governed environment where every meaningful action can be inspected, validated, replayed, refused, or applied safely.

That is a much more interesting product.

It also explains why so much of the work looks like “boring” infrastructure: Markdown, JSON, validators, sprints, context packs, known limitations, receipts, branch discipline, and CLI ergonomics.

Boring infrastructure is what makes the dangerous part usable.
