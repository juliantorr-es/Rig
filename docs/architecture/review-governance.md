# Review Governance

## Purpose

Rig review authority is intentionally split.

The system allows advisory AI review, but only humans may approve protected-branch merges.

## Authority Model

| Reviewer Type | Authority |
|---|---|
| Agent | Proposal only |
| Advisory AI review | Advisory only |
| GitHub Actions | Mechanical validation |
| Human reviewer | Merge authority |

## Routing Expectations

- CODEOWNERS should route changes to the maintainers responsible for the touched surface.
- Labels should surface the review risk class.
- Protected branches should require human review before merge.
- Advisory review output must never be treated as a merge decision.

## Review Lanes

### Agent lane

- Used for proposal branches
- Must target `preproduction`
- Must not self-approve
- Must not bypass human review

### Human lane

- Required for protected branches
- Owns merge authority
- Resolves reviewer questions
- Approves promotion from `preproduction` to `main`

### Advisory lane

- AI tools may summarize risk, identify missing tests, or suggest follow-up validation
- Advisory output must be read as guidance only
- Advisory output cannot satisfy merge requirements

## Escalation

If a change touches replay, topology, frontend contracts, or governance policy, reviewers should expect explicit validation evidence and artifact links.

If review is blocked, the blocker should be documented in the PR and reflected in the label set.

## Merge Rule

No AI-only approval loop.

No merge occurs without human authority.
