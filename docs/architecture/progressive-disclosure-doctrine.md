# Progressive Disclosure Doctrine

Rig uses progressive disclosure to keep runtime instrumentation calm, legible, and operational under pressure. The UI must reveal only the detail required for the current task and expand further only when the user intentionally asks for it or when a higher-severity runtime condition requires it.

## Core Doctrine

Progressive disclosure is a governance mechanism, not a visual preference. It exists to prevent telemetry overload, preserve spatial stability, and keep the runtime surface inspectable during long sessions, replay-heavy sessions, and high-density execution.

### Layer 1: Calm Operational Overview

This layer is the default surface.

- low stimulation
- minimal motion
- stable topology
- runtime health summary
- high-level execution state
- integrity summary

### Layer 2: Active Instrumentation

This layer is visible when the operator needs live runtime detail.

- routing visibility
- throughput visibility
- replay progression
- runtime transitions
- supervision visibility

### Layer 3: Deep Runtime Inspection

This layer is deferred until the operator expands a runtime surface intentionally.

- DTGs
- execution lineage
- replay lineage
- capability escalation paths
- integrity chains
- routing internals

### Layer 4: Forensics / Replay Analysis

This layer is reserved for historical reconstruction and incident analysis.

- full replay reconstruction
- event sequencing
- temporal scrubbing
- topology replay
- divergence analysis

## Disclosure Transition Rules

- Layers must expand explicitly, not implicitly.
- Higher layers never replace lower layers; they refine them.
- The default path must remain readable when deeper layers are hidden.
- Severe integrity or supervision conditions may surface higher layers, but only to the minimum level needed for the operator to respond.
- Replay mode can reveal deeper temporal detail, but it must not destabilize the live operational layout.

## Density Escalation Policy

- Density increases by abstraction first, not by adding more primitives.
- When telemetry rises, the system should aggregate, summarize, and collapse before it introduces additional visual channels.
- If a surface exceeds its comfortable cognitive threshold, labels shorten, repeated structures merge, and secondary details defer.
- Under overload, the operator sees fewer moving parts, not more.

## User-Controlled Expansion

- Operators control disclosure expansion.
- Expansion must be local to the selected runtime surface.
- No global expansion should reflow unrelated layout.
- Once expanded, a surface must remain stable unless runtime state or explicit user action changes it.

## Operational Readability Guarantees

- Stable geometry is preserved across disclosure levels.
- Critical state remains visible at every layer.
- Motion never becomes the primary carrier of meaning.
- Secondary detail is always optional.
- The default view must remain calm enough for long-session monitoring.
