# 07 — YouTube Devlog Outline

This is the public-facing version of the chronicle. The tone can be technical, frustrated, funny, and grounded. The hook is not “watch me code.” The hook is “watch me build the safety harness for AI agents before they burn my repo down.”

## Series title ideas

- Frustrated Developer Chronicles
- Building the Adult Supervision Layer for AI Agents
- My Repo Is Haunted, So I Built Rig
- Receipts, Not Vibes
- Governed Chaos: Building Rig
- The AI Agent Control Plane Diaries

## Episode 1 — The Tooling Became the Product

### Hook

“I started building scripts to keep my real project organized. Then I realized the scripts were the product.”

### Story beats

- Anigma was the original pressure cooker.
- AI agents could help but also created trust problems.
- Markdown, JSON, validators, and receipts became operational infrastructure.
- Rig emerged as its own standalone thing.

### Demo idea

Show the difference between a normal messy agent run and a governed Rig workspace with receipts.

### Ending line

“I thought I was organizing a project. Turns out I was building a control plane.”

## Episode 2 — The Agent Lost My Work

### Hook

“An AI agent reverted work it should not have touched. So now I am building the system that makes that harder to happen again.”

### Story beats

- Explain dirty files and user-owned changes.
- Explain why broad git checkout behavior is dangerous.
- Explain recovery reports and why evidence matters.
- Show how Rig treats file ownership and receipts.

### Demo idea

Use a safe toy repo to show protected dirty files and refused destructive operations.

### Ending line

“If an agent can lose the work, the system needs enough memory to rebuild it.”

## Episode 3 — Receipts Are Evidence, Not Decoration

### Hook

“Every AI coding tool wants to tell you what it did. I want proof.”

### Story beats

- Difference between summary and receipt.
- Why “done” is not enough.
- Validators, known limitations, branch status, and handoff packets.
- Why receipts are useful to both humans and future agents.

### Demo idea

Show a task before and after receipt generation.

### Ending line

“Trust me bro is not an audit trail.”

## Episode 4 — The Frontend Is Not Allowed to Lie

### Hook

“The UI can show state, but it does not get to invent state.”

### Story beats

- Projection authority.
- Widget renderer drift.
- Runtime.js swelling into a monolith.
- Browser debug logs as product surface.

### Demo idea

Show backend projection data driving frontend widgets.

### Ending line

“If the UI becomes a second backend, congratulations, you now have two bugs and a religion.”

## Episode 5 — I Do Not Want Better Agents. I Want Replaceable Agents.

### Hook

“Claude, Gemini, Vibe, OpenCode — they all have different flavors of chaos. Rig should not care which one is having a day.”

### Story beats

- Agent-specific quirks.
- Prompt contracts.
- Semantic tool calls.
- Sandbox/intercept/normalize idea.
- Rig as stable layer underneath unstable agents.

### Demo idea

Show two agents producing proposals that Rig normalizes into the same review surface.

### Ending line

“The agent proposes. Rig disposes.”

## Episode 6 — The Pseudo-Compiler for Agent Intent

### Hook

“What if instead of trusting the model to call tools perfectly, we treated its output like code that needs compiling?”

### Story beats

- Tool calls are brittle.
- Smaller models may be useful if the system does the deterministic work.
- Decode intent, validate scope, repair obvious issues, refuse unsafe changes.
- Receipts as compile artifacts.

### Demo idea

Show a fuzzy intent turning into a validated plan.

### Ending line

“LLMs do not need to be perfect operators if the operating environment has standards.”

## Episode 7 — Can Someone Install This in Ten Minutes?

### Hook

“A project is not a product if only the author can install it.”

### Story beats

- Standalone repo migration.
- Package path breakage.
- Local check scripts.
- Install docs and first-run flow.
- Doctor command, system benchmark, model downloader.

### Demo idea

Fresh install from zero to first governed workspace.

### Ending line

“Working on my machine is not a business model.”

## Episode 8 — The Chronicle Problem

### Hook

“How is it a chronicle if it only has one entry?”

### Story beats

- Receipts versus narrative.
- Why project history matters.
- Turning struggles into public-facing devlogs.
- Making technical work legible enough for support, grants, and sponsors.

### Demo idea

Show the generated chronicle archive and how it maps to project artifacts.

### Ending line

“The repo has receipts. The channel gets the story.”

## Recurring visual motifs

- Haunted working tree.
- Agent with root access.
- Receipts as courtroom evidence.
- UI as a window, not a judge.
- The control plane as adult supervision.
- Dirty files as crime scene tape.

## Reusable intro narration

“I am building Rig, a local-first control plane for AI coding agents. The goal is simple: let agents help without letting them own the truth. Every episode is one boss fight in turning agent chaos into governed software work.”
