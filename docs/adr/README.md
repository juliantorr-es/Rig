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

| ADR | Status | Concept | Seam | Lines |
|---|---|---|---|---|
| [0001](0001-command-layer-consolidation.md) | proposed | Command Layer | CLI | 47 |
| [0002](0002-projection-domain-consolidation.md) | proposed | Projection Domain | UI | 85 |
| [0003](0003-governance-engine-deepening.md) | proposed | Governance Engine | Intent | 75 |
| [0004](0004-runtime-streaming-consolidation.md) | accepted | Runtime Streaming | Execution | 5,915 (Cluster 2) |
| [0005](0005-public-intake-connector-seam.md) | superseded by ADR-0006 | Public Intake | Connector | ~120 |
| [0006](0006-ingress-interpretation.md) | proposed | Ingress Interpretation | Ingress | 54 |
| [0007](0007-workspace-domain-authority.md) | proposed | Workspace Domain | Worktree | 82 |
| [0008](0008-receipt-evidence-unification.md) | proposed | Evidence Domain | Receipt | 101 |
| [0009](0009-agentic-workflow-refinement.md) | proposed | Agentic Workflow | Orchestration | ~280 |
| [0010](0010-repository-forge-bootstrap-and-promotion-abstraction.md) | proposed | Forge Abstraction | Promotion | ~700 |

## ADR Format: Markdown + JSON Contracts

**New ADRs must have both a Markdown file and a JSON companion.**

| File | Purpose | Authority |
|------|---------|-----------|
| `docs/adr/NNNN-title.md` | Human-readable narrative: context, decisions, rationale | **Rationale Authority** - Explains WHY |
| `docs/adr/NNNN-title.json` | Machine-readable contract: workflows, constraints, names | **Contract Authority** - Tells Rig WHAT |
| `docs/schemas/rig-adr.schema.json` | JSON Schema that validates ADR contracts | **Schema Authority** - Ensures consistency |

**Why both?**
- Markdown is for humans to understand the architectural reasoning.
- JSON is for Rig to parse, validate, and execute against.
- Tests must NOT depend on Markdown prose (except for existence checks).
- Tests SHOULD validate JSON contracts against the schema.

**Validation**: Each ADR JSON must validate against `docs/schemas/rig-adr.schema.json`.

**Example**: ADR 0009 has both `0009-agentic-workflow-refinement.md` (human) and `0009-agentic-workflow-refinement.json` (machine).

---

## Workflow Authority

**ADR 0009 (Agentic Workflow Refinement)** is the umbrella ADR for agent workflow refinement and serves as the canonical reference for the **ADR → Sprint → Mission → Evidence → Review/Promotion** narrative. See also the operational workflow reference at `docs/workflow/adr-sprint-mission-evidence.md`.

Each candidate follows the **improve-codebase-architecture** skill methodology:
- Applies the **deletion test** to identify shallow modules
- Targets **depth-as-leverage** (not lines-of-code ratio)
- Uses **seam** (not "boundary") and **adapter** (not "component") terminology
- Aims for **one adapter = hypothetical seam, two adapters = real seam**
