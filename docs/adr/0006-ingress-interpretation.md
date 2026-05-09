# ADR 0006: Ingress Interpretation & Evidence Continuity

## Context
Rig’s intake logic (Google Forms, GitHub) currently has routing and persistence seams scattered across the CLI and partially extracted into domain helpers. To maintain operational coherence, this logic must converge into a dedicated, deep domain module that separates acquisition from interpretation.

## Decision
1. **Deterministic Evidence Interpreter**: The `IntakeModule` is a network-pure layer that interprets raw ingress artifacts into canonical `PublicIntakePacket` objects.
2. **Fetch/Interpret Split**: Acquisition (IO/Auth/Network) remains in the operational shell (CLI). Interpretation (Normalization/Validation) moves to the module.
3. **Evidence Topology Sovereignty**: The module preserves the existing filesystem topology (`.build/rig/public_intake/`) and evidence schemas. Implementation-era module boundaries must not leak into the Replay Engine; replay reads the evidence directly.
4. **Private Inventory**: Connector routing is a static internal detail of the module. We explicitly reject runtime registration or plugin architectures to preserve cognitive locality and determinism.
5. **Manager-over-Path**: The `IntakeStore` acts as a steward of the evidence path, not a creator of a new persistence format.

## Consequences
- **Positive**: Replay remains forensic, offline-capable, and decoupled from module refactors.
- **Positive**: CLI becomes thinner and focused strictly on the "Acquisition" (IO) shell.
- **Negative**: Adding new connectors requires modifying the internal module inventory (intentional constraint to prevent "discovery theater").
- **Neutral**: The filesystem becomes the stable "Level 0" interface between interpretation and reconstruction.
