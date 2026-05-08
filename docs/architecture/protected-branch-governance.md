# Protected Branch Governance

## Purpose

This document canonicalizes protected-branch behavior for Rig.

Protected branches exist to preserve deterministic replay guarantees, frontend contract integrity, and human merge authority.

## Branch Policy

### `main`

`main` is the stable trusted runtime branch.

Requirements:

- No direct pushes
- No force pushes
- Required status checks
- Required human review
- No bypass of governance gates
- No merge without validation evidence

### `preproduction`

`preproduction` is the governed integration branch.

Requirements:

- Protected against direct bypass
- Requires mandatory validation
- Requires replay validation for replay-sensitive work
- Requires frontend contract validation for UI-impacting work
- Requires human approval before promotion to `main`

## Required Review Model

Rig uses a split authority model:

- Agent: proposal only
- Advisory AI review: guidance only
- GitHub Actions: mechanical validation
- Human reviewer: merge authority

Advisory AI output must never be treated as sufficient approval for protected branches.

## Required Checks

Protected branches should require the relevant deterministic validation gates for the work being merged, including:

- Syntax integrity
- Type integrity
- Replay determinism
- Projection contract integrity
- Frontend contract integrity
- Runtime doctor checks
- Browser boot smoke checks when UI surfaces are affected

## Merge Restrictions

- No autonomous merge into `main`
- No AI-only merge approval loop
- No direct push to protected branches
- No force-push workflow
- No destructive Git operations as remediation
- No bypass of replay or frontend validation

## CODEOWNER Expectations

CODEOWNERS should be used as a routing mechanism, not as a replacement for protected branch rules.

Expectation:

- files in governed surfaces route to maintainers
- review responsibility remains human
- approval does not override required checks

## Ruleset Recommendations

Recommended branch protection posture:

- Require pull requests
- Require at least one human review
- Require passing status checks
- Dismiss stale approvals after new commits
- Restrict who can push
- Block force pushes
- Block branch deletion for protected branches
- Require conversation resolution where appropriate

## Operational Principle

Branch protection is a governance control, not a convenience setting.

If a branch can change replay behavior, topology, or frontend contracts, then protection must remain stricter than convenience workflows.
