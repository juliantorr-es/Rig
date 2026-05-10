# Operational Design Lineage

## Summary

The visual architecture of Rig is not an aesthetic afterthought, nor does it participate in the trendy "AI aesthetic" of blurred gradients and shimmering borders. 

Rig’s frontend derives its visual semantics from a strict lineage of industrial, operational, and systems-oriented design. This lineage is architectural. It exists to solve the precise problem Rig faces: rendering complex, high-stakes, temporally sensitive mechanical state into a truthful, human-readable format without obscuring the underlying machine.

This document outlines the philosophical and historical roots of Rig's visual execution doctrine.

---

## The Lineage

The design language of Rig is heavily informed by the following historical disciplines:

### 1. Bauhaus Geometry & Braun Industrial Design
- **Core Principle:** Form follows function.
- **Architectural Value:** Bauhaus and the later work of Dieter Rams at Braun prioritized extreme functional clarity. In Rig, this translates to strict geometric layouts. Rectangles, hard lines, and precise radii are used exclusively to define structural boundaries (e.g., separating a capability sandbox from a proposal lane). There is zero decorative geometry. If a shape exists, it represents a bounded state.

### 2. IBM Systems Manuals & Console Interfaces
- **Core Principle:** High-density, structured mechanical truth.
- **Architectural Value:** Mid-century IBM hardware manuals and mainframe console interfaces (like the System/360) were designed for operators to understand massive, opaque processing systems. Rig adopts this typographic and spatial rigor. Information must be structurally hierarchical, utilizing monospaced alignment and tabular layouts to render telemetry, execution traces, and logs predictably.

### 3. Terminal-Era Instrumentation
- **Core Principle:** Text as a deterministic interface.
- **Architectural Value:** The terminal is the original governed execution environment. Rig borrows the terminal's linear, append-only history and its absolute rejection of hidden state. While Rig uses SVG for topology, it treats text logs and streams with terminal-level severity—they are immutable receipts of execution, not fluid conversational elements.

### 4. Flight Recorder Interfaces & Systems Observability
- **Core Principle:** Absolute temporal awareness and forensic reconstruction.
- **Architectural Value:** A flight data recorder interface cannot lie, nor can it prioritize aesthetics over accuracy. Because Rig is a replay-first architecture, its UI must act as a forensic tool. The frontend must clearly delineate *when* an event happened, the *exact sequence* of states, and the *lineage* of an execution decision.

---

## Architectural Semantics derived from Lineage

These historical roots manifest in strict, actionable UI design principles for the Rig frontend.

### Information Density
Rig rejects the modern web trend of aggressively sparse, low-density UIs designed for casual consumption. Operational systems require high information density. Operators must be able to scan multiple telemetry streams, execution logs, and routing topologies simultaneously on a single screen without endless scrolling or hidden drawer menus.

### Operational Hierarchy
Visual weight directly maps to operational consequence.
- A critical failure or governance block commands the highest visual weight.
- Active execution streams command secondary weight.
- Historical replay logs and passive telemetry reside in structurally separated, lower-weight visual lanes.

### Geometric Semantics
Geometry is used as a mechanical vocabulary.
- **Hard right angles** denote immutable constraints (e.g., an isolated sandbox).
- **Lines** represent explicit routing paths for context or execution capability.
- **Dashed lines** represent advisory or proposed actions that have not yet mutated state.

### Instrumentation Clarity
There must be no ambiguity between a system that is actively computing, a system waiting on network IO, and a system stalled waiting for human approval. The lineage of analog instrumentation (dials, distinct toggle switches, indicator lamps) demands that states are binary and explicitly rendered, rather than blended or obscured.

### Temporal Awareness
Rig is temporally fluid due to deterministic replay. The design lineage of video editing timelines and forensic tools dictates that the UI must always ground the operator in time. The interface must explicitly indicate if the operator is viewing the *Live* stream or a *Reconstructed Replay* state.

### Constrained Palettes
Color is reserved strictly for semantic state indicators, drawing from industrial control room palettes.
- **Red:** Execution blocked, integrity failure, or hard error.
- **Yellow/Amber:** Human intervention required, or advisory warning.
- **Green/Blue:** Successful capability execution or verified integrity.
- **Monochrome/Grayscale:** Standard operational state, logs, and base geometry.
Decorative or brand-driven color application is forbidden.

### Restrained Motion
As dictated in the *Truthful Animation Doctrine*, motion is only permitted when mechanically driven by backend state. The lineage of physical instrumentation guarantees that dials only move when pressure changes. In Rig, pixels only move when execution state or telemetry changes.