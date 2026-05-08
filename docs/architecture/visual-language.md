# Design Tokens & Visual Language

## Summary

Rig’s visual language is constrained by design to prioritize operational readability and instrumentation density over decorative appeal. Every design token—color, line weight, spacing, and typography—carries absolute semantic weight.

This document canonicalizes the geometric and chromatic primitives used to construct Rig's frontend.

---

## Constrained Palette Doctrine

Rig employs a restrained color philosophy. The UI is predominantly monochrome to ensure high contrast for dense instrumentation. Color is exclusively used as an active state indicator. If a color exists, an event is happening or a state has changed.

### Restrained Color Philosophy
- **Base Palette:** Deep charcoal/black (backgrounds), stark white/light grey (text and primary lines), and mid-greys (inactive boundaries).
- **Prohibition:** UI elements must not use "brand colors" or pastel washes to look modern. The palette must mimic physical control rooms.

### Semantic Color Mapping
Colors map directly to runtime, integrity, and routing states.

| Token | Hex/Value | Semantic Mapping |
| :--- | :--- | :--- |
| `color-state-active` | Blue / Cyan | Active execution, healthy context routing, verifiable throughput. |
| `color-state-blocked` | Amber / Yellow | Paused for governance review, stalled subprocess, advisory warning. |
| `color-state-critical` | Red | Integrity divergence, strict sandbox violation, execution crash. |
| `color-state-success` | Green | Receipt validated, gate passed, completed deterministic execution. |
| `color-state-inactive` | Mid-Grey | Idle capability, historical replay context, inactive routing lane. |

---

## Geometric Primitives

Geometry in Rig is sharp, mechanical, and unambiguous.

### Line Weight Philosophy
Line thickness represents the rigidity of the boundary or the volume of the execution.
- `stroke-width: 1px` : Standard boundary, advisory execution, static topology.
- `stroke-width: 2px` : Active routing path, execution context flow.
- `stroke-width: 3px` : Hard sandbox boundary, strict governance isolation lane.

### Stroke Semantics
- `stroke-dasharray: none` : A verified, continuous execution or boundary.
- `stroke-dasharray: "4 4"` : A proposed, unverified, or advisory intent that has not mutated state.

### Geometric Examples (SVG)
```xml
<!-- Example: Active Hard Sandbox -->
<rect width="100%" height="200" fill="none" stroke="var(--color-state-active)" stroke-width="3px" />

<!-- Example: Proposed Advisory Route -->
<path d="M 0,50 L 200,50" stroke="var(--color-state-blocked)" stroke-width="1px" stroke-dasharray="4 4" />
```

---

## Typography Hierarchy

Typography is utilized purely for data transmission, structured heavily around fixed-width alignment.

### Operational Readability
- **Primary Typeface:** A highly legible monospaced font (e.g., JetBrains Mono, Fira Code, or IBM Plex Mono) is required for all telemetry, code snippets, logs, and sequence IDs to ensure horizontal alignment across data streams.
- **Secondary Typeface:** A clean sans-serif (e.g., Inter or Helvetica) is used *only* for high-level labels (e.g., "Execution Lane", "Proposal Review").

### Font Weights
- `font-weight: 400` : Standard logs and telemetry.
- `font-weight: 700` : Governance gates, critical errors, and active sequence identifiers.

---

## Spacing and Instrumentation Density

Rig prioritizes high instrumentation density. Information is tightly packed but meticulously structured to prevent visual sludge.

### Spacing Philosophy
- Space is used as a delimiter between execution lanes, not as "breathing room."
- Margins and padding are built on a strict `4px` grid (e.g., `4px`, `8px`, `16px`, `32px`).

### Layout Examples
- **Telemetry Clusters:** Grouped with `4px` gaps, surrounded by a `1px` geometric bounding box.
- **Execution Lanes:** Separated by heavy `32px` gaps to immediately signal to the operator that context does not leak between these boundaries.

```xml
<!-- Example: High-Density Telemetry Cluster -->
<g transform="translate(16, 16)">
  <rect width="200" height="64" stroke="var(--color-state-inactive)" stroke-width="1px" fill="none" />
  <text x="8" y="24" font-family="monospace" font-size="12px">CPU: 42%</text>
  <text x="8" y="44" font-family="monospace" font-size="12px">MEM: 1.2GB</text>
</g>
```

---

## Visual Hierarchy

Visual hierarchy dictates where the operator's eye must go during a live execution.

1. **Top Priority:** Integrity failures (Red, heavy line weights, stark geometric disruption).
2. **Second Priority:** Active execution streams (Blue/Green, moving deterministic paths, updating monospaced tails).
3. **Third Priority:** Pending proposals (Amber, dashed borders, paused routing paths).
4. **Base Priority:** Historical logs, passive telemetry, and inactive capabilities (Greys, 1px lines).