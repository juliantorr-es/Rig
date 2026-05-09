# Architecture Decision Records

ADRs (Architecture Decision Records) for Rig live in this directory.

Each ADR documents a significant architectural decision, its context, and the consequences of the choice.

## Status Legend

- **proposed** — Decision documented, not yet implemented
- **accepted** — Decision implemented and active
- **deprecated** — Decision superseded or reversed
- **superseded by ADR-NNNN** — Replaced by another ADR

## Architectural Deepening Candidates

These ADRs propose **deepening opportunities** — refactors to turn shallow modules into deep ones, improving **locality**, **leverage**, and **testability** while maintaining **AI-navigability**.

| ADR | Status | Concept | Seam |
|---|---|---|---|
| [0001](0001-command-layer-consolidation.md) | proposed | Command Layer | CLI |
| [0002](0002-projection-domain-consolidation.md) | proposed | Projection Domain | UI |
| [0003](0003-governance-engine-deepening.md) | proposed | Governance Engine | Intent |
| [0004](0004-runtime-domain-consolidation.md) | proposed | Runtime Domain | Execution |
| [0005](0005-public-intake-connector-seam.md) | proposed | Public Intake | Connector |
| [0006](0006-workspace-domain-authority.md) | proposed | Workspace Domain | Worktree |
| [0007](0007-receipt-evidence-unification.md) | proposed | Evidence Domain | Receipt |

Each candidate follows the **improve-codebase-architecture** skill methodology:
- Applies the **deletion test** to identify shallow modules
- Targets **depth-as-leverage** (not lines-of-code ratio)
- Uses **seam** (not "boundary") and **adapter** (not "component") terminology
- Aims for **one adapter = hypothetical seam, two adapters = real seam**
