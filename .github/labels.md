# Label Governance

Rig uses labels as governance signals, not as decoration.

## Canonical Labels

| Label | Meaning |
|---|---|
| `agent-generated` | Produced by an agent workflow |
| `needs-human-review` | Human approval required before merge |
| `replay-sensitive` | Change affects replay semantics or determinism |
| `frontend-contract` | Change affects frontend contracts or widget behavior |
| `topology-sensitive` | Change affects topology, routing, or workspace structure |
| `governance-sensitive` | Change affects runtime governance or protected-branch policy |
| `integration-risk` | Change needs soak testing or wider integration validation |

## Escalation Flow

1. The change is labeled by the submitter or triage maintainer.
2. Mechanical validation runs on the appropriate protected branch or PR target.
3. Human review is required whenever a governance-sensitive, replay-sensitive, topology-sensitive, or frontend-contract label is present.
4. Integration-risk work remains in preproduction until soak confidence is sufficient.

## Merge-Blocking Labels

The following labels should block merge until the associated concerns are resolved:

- `needs-human-review`
- `replay-sensitive` when replay validation has not passed
- `frontend-contract` when contract validation has not passed
- `topology-sensitive` when topology integrity review is incomplete
- `governance-sensitive` when branch or authority review is incomplete
- `integration-risk` when soak requirements are not satisfied

## Governance Rule

Labels must reflect actual risk.

Do not use labels to hide validation gaps, shortcut review, or waive human authority.
