# 05 — Agent Chaos and Governance

Rig is being built in the age of CLI agents. That means the project has to deal with Claude Code, Gemini, Vibe, OpenCode, and whatever new agent shows up next week with a logo and a dangerous amount of confidence.

The lesson so far is not that one agent should be trusted forever.

The lesson is that agents need to be treated as interchangeable workers behind a governing interface.

## The problem with direct tool trust

Letting an agent invoke tools directly creates a fragile dependency on the model’s ability to:

- understand the repository,
- respect dirty files,
- choose safe commands,
- format tool calls correctly,
- avoid destructive operations,
- summarize truthfully,
- and stop when it hits uncertainty.

That is too much trust.

Even strong models fail in weird ways. Smaller models fail more often. Cheaper models may still be useful, but not if the system requires them to be perfect operators.

## The better split

A stronger architecture is:

> Agent proposes intent. Rig validates, routes, executes, records, and explains.

The agent should not need to perfectly invoke every tool. It should be able to say, in a controlled format or even plain language, what it is trying to accomplish.

Rig can then infer the actual operation, check the policy surface, confirm the scope, run deterministic validation, and produce receipts.

This is the heart of the semantic tool-call idea.

## Semantic tool calls

Instead of making the model produce brittle tool syntax, Rig could accept descriptions such as:

> “Inspect the current workspace and identify files related to runtime streaming consolidation without modifying anything.”

Rig then maps that to a read-only plan:

- check branch and status,
- inspect workspace metadata,
- search relevant docs and source files,
- produce a structured finding,
- refuse mutation.

The model describes. Rig operationalizes.

## The sandboxing idea

A natural next step is running each CLI agent in a sandbox. Rig would intercept tool calls, normalize them, route them through its own implementation, and feed results back to the agent.

That would give Rig leverage over:

- filesystem access,
- command execution,
- network access,
- git operations,
- model-specific quirks,
- logging,
- receipts,
- and policy enforcement.

This would also make agent comparison more useful. Instead of comparing agents in uncontrolled conditions, Rig could compare them under the same governance surface.

## Why this matters for local agents

Local and smaller models may not be excellent at perfect tool use. But they may be good enough at intent generation, summarization, classification, and narrow reasoning if Rig handles the deterministic parts.

That suggests a powerful product direction:

> Make weaker models useful by making the environment smarter.

This could reduce cloud dependency, cost, and latency while preserving safety.

## Prompt discipline became product discipline

The repeated need for structured prompts taught Rig something important. Prompt discipline is not just communication style. It is a policy surface.

A good agent prompt needs:

- role,
- source of truth,
- goal,
- non-goals,
- approved shape,
- scope,
- implementation sequence,
- acceptance tests,
- evidence requirements,
- handoff instructions.

That structure is practically a contract.

Rig can turn those contracts into machine-checkable workflows.

## The end state

The goal is not to find the one perfect coding agent.

The goal is to make the agent replaceable.

Rig should become the stable layer underneath unstable agent behavior.
