# 06 — Productization and Readiness

Rig’s productization problem is simple to state and hard to satisfy:

> Can someone install it, understand it, and get useful value in less than ten minutes?

That question changed the project.

## From internal tool to product

An internal tool can assume context. A product cannot.

An internal tool can require the author’s memory. A product needs onboarding.

An internal tool can expose rough edges. A product needs known limitations, safe defaults, and a path to recovery.

Rig started crossing that boundary when it became a standalone repo with its own scaffolding, checks, workflows, migration notes, compatibility wrappers, and package fixes.

## What readiness means

Readiness does not mean every feature is done.

Readiness means a new user can answer four questions quickly:

1. What is this?
2. Why should I trust it?
3. How do I start?
4. What will it refuse to do?

Rig’s first serious product surface should make those answers obvious.

## The ten-minute path

The ideal first-run experience:

- install Rig,
- run a doctor/check command,
- initialize a workspace,
- see a governed task surface,
- run a read-only audit,
- receive a structured proposal,
- inspect receipts,
- understand what is blocked and why.

That is a product demo.

Not a pile of scripts. Not a vague agent wrapper. A governed loop.

## Bootstrap for non-technical users

A major idea was that Rig should help someone initialize a project even if the folder does not already contain a mature repository.

That means a bootstrap walkthrough could ask plain questions:

- What are you trying to build?
- Is this code, writing, research, or mixed work?
- Do you want agents to edit files or only propose changes?
- What files are source of truth?
- What should never be touched without permission?
- What counts as proof?

This matters because Rig should not only serve expert developers. It should help people externalize project shape before agents start generating chaos.

## System benchmarking and model downloader

Rig’s product path also needs system awareness.

A local-first AI workflow should know what hardware it is running on, what models can fit, what performance is plausible, and what tradeoffs the user is making.

System benchmarking and model downloading are not side quests. They are part of making local AI workflows understandable.

The user should not have to guess whether a model is too large, too slow, or inappropriate for a task. Rig can measure, recommend, and remember.

## Funding readiness

Once a project asks for support money, the bar changes again.

People need to understand what they are supporting. That requires:

- a clear public explanation,
- a working alpha,
- an install path,
- a roadmap,
- visible progress,
- honest limitations,
- and a way to sponsor or contribute.

The chronicle matters here. It gives the project a human-readable story.

A good devlog can become trust infrastructure.

## Product thesis

Rig should not be sold as “another AI coding tool.”

It should be framed as:

> A governed control plane for AI-assisted software work, built for people who want help from agents without handing them the keys to the house.

That is the product.
