# Visual Execution Doctrine

## Summary

Rig is NOT a chat UI. Rig is an execution instrumentation environment.

The frontend is an operational surface designed to visualize deterministic execution, replay bounds, and governed context routing. This document establishes the foundational Visual Execution Doctrine that dictates how frontend architecture is structured, rendered, and interpreted.

---

## The Role of the Frontend

The Rig frontend is systematically constrained. It does not possess authority, it does not infer state, and it does not invent transitions.

### 1. Instrumentation Surface
The frontend exists to display the mechanical reality of the backend. If a runtime pauses, the UI must display a pause. If a stream fractures, the UI must display the fracture. It is a dashboard for inspecting the governed cognitive infrastructure, not a conversational interface simulating a human.

### 2. Execution Observability Layer
Execution observability means the UI must explicitly render the capabilities being invoked, the context being routed, and the execution boundaries established by the control plane. The user must be able to observe exactly what is being executed, which runtime is acting, and under what authority.

### 3. Replay Surface
Rig is a replay-first architecture. The frontend must be capable of rendering reconstructed historical state identically to live state. The visual layer is designed to scrub temporally backward and forward through deterministic execution traces without visual artifacting or state corruption.

### 4. Governance Visibility Layer
Governance rules (capability gating, sandbox limits, context dropping) are mechanically enforced in the backend. The frontend makes these rules explicitly visible. If an execution is blocked by a governance gate, the UI must render the structural boundary that caused the failure, rather than presenting a generic error message.

### 5. Operational Telemetry
The UI acts as a telemetry console. It renders throughput, latency, inference confidence metrics, and connection topologies. It visualizes the pulse of the system via literal data mapping.

---

## The Rendering Pipeline

Visualization is strictly downstream of projection. The pipeline is immutable:

`Runtime State` → `Projection Contract` → `Websocket Sequence` → `Visual Instrumentation`

1. **Runtime State:** The actual mechanical state of the execution environment (dirty files, stream chunks, subprocess exits, inference logits).
2. **Projection Contract:** The backend normalizes runtime state into dumb, UI-consumable data structures (Projections).
3. **Websocket Sequence:** Projections are streamed to the frontend via deterministic, sequenced websocket events.
4. **Visual Instrumentation:** Dumb frontend widgets bind directly to projection fields to render geometry.

---

## Visual Truthfulness Doctrine

Visual truthfulness is an architectural requirement, not an aesthetic preference. The UI must never lie to the user about what the machine is doing.

- **No Fake "Thinking":** If the system is waiting on network IO, it renders a network IO wait state. It does not display a pulsing brain or typing dots.
- **No Smoothing:** If the runtime outputs chunked data, the UI renders the chunks. It does not artificially smooth, delay, or tween rendering to make the text appear more "human."
- **Literal Representation:** Visual components must represent an underlying variable. If a gradient exists, its stops and colors must map to real telemetry (e.g., mapping inference entropy to color density). Arbitrary decorative gradients are forbidden.

---

## Replay-Safe Visualization Doctrine

Because the frontend is a Replay Surface, animation and motion must be deterministic and replay-safe.

- **Time-Independent Motion:** Animations cannot rely on unbounded `requestAnimationFrame` loops or arbitrary browser clocks. Motion must be derivable from the progression of sequential events or bounded timestamps provided by the backend projection.
- **Historical Consistency:** When scrubbing to a past event, the visual state must reconstruct deterministically. State machines within widgets must be purely functional representations of the currently projected event.

---

## Operational Geometry Principles

The visual language of Rig relies on hard geometry, drawing from industrial design and systems consoles.

- **Line Weight:** Used to denote authority boundaries. Thick lines represent hard execution sandboxes; thin or dashed lines represent advisory capabilities.
- **Structural Framing:** Interfaces are built using clear, unambiguous bounding boxes to reinforce the separation of contexts (e.g., Planner context vs. Execution sandbox).
- **Whitespace as Cadence:** Spacing is mathematically rigid, utilized to group related operational metrics and visually separate disparate execution lanes, preventing information sludge.

---

## Related Documents

| Section | Link |
|---------|------|
| **Core Philosophy** | [visual-execution-doctrine.md](visual-execution-doctrine.md) |
| **Motion Semantics** | [truthful-animation.md](truthful-animation.md) |
| **Design Tokens** | [visual-language.md](visual-language.md) |
| **System Architecture** | [frontend-systems-architecture.md](frontend-systems-architecture.md) |
| **Replay Mechanics** | [replayable-visualization.md](replayable-visualization.md) |
| **SVG Architecture** | [svg-instrumentation.md](svg-instrumentation.md) |
| **Terminology** | [terminology.md](terminology.md) |
