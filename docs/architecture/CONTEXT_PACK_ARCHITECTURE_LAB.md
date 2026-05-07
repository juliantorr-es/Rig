# Context Pack: Architecture Lab (Provider Arena)

## Concept
Rig Architecture Lab is a **Governance-First Decision Subsystem**. It treats architectural planning as an evidence-based process: Proposers (LLMs) submit designs; Evaluators (Deterministic + Heuristics + LLM Judge) score them; and Synthesizers produce ADRs and Implementation Plans.

## Workflow Phases

1.  **Architecture Session**: Define the user goal, constraints, and non-goals.
2.  **Provider Arena**: Distribute the session state (context packets) to N model providers simultaneously.
3.  **Cross-Review/Critique**: Use specialized rubrics (Security, Portability, Complexity, UX, Governance) to critique proposals.
4.  **Synthesis**: Generate the "Final Brief" including:
    *   Architecture Brief
    *   Options Considered
    *   Recommended Option
    *   Risk Assessment
    *   Draft ADR
    *   Implementation Prompt
5.  **Evidence/Receipt Logging**: Persist every run as a signed receipt with scores, latencies, and metadata.

## Scoring Stack

- **Deterministic**: Checks for schema validity, citation of required context packs, mention of forbidden non-goals, and code-block completeness.
- **Heuristic**: Analysis of overbuild risk, risk coverage, and actionable step count.
- **LLM Judge**: Qualitative analysis of architectural depth, doctrine fit, and tradeoff reasoning.

## Cockpit UI Surface

- **Evidence Rail**: Links to raw provider outputs, critiques, and scorecards.
- **Provider Scoreboard**: Dynamic tables showing model performance on specific metrics (Reasoning, Schema, Doctrine, Risk, Speed).
- **Session Stream**: Real-time narration of the session progress.

## Architecture Rule
**Providers Propose; Rig Governs.**
Models never mutate the repository. They propose plans. The system logs these as persistent receipts. The User (or automated policy) selects the winning proposal, which is then converted into a governed Intent for implementation.

## Agent Checklist
- [ ] Is the goal clearly defined with constraints and non-goals?
- [ ] Are context packs bundled appropriately for the session?
- [ ] Are evaluations based on structured rubrics rather than qualitative "vibes"?
- [ ] Is the result documented in an ADR format?
- [ ] Does every session produce an auditable receipt?
