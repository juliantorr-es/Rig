# Runtime Visualization Semantics

## Summary

In Rig’s execution control plane, visual primitives are not stylistic choices—they are a vocabulary. Every line weight, color shift, and pulse rate maps directly and deterministically to an underlying runtime or governance state.

This document canonicalizes the mapping between backend runtime mechanics and frontend visual geometry.

---

## State Mapping Doctrine

The frontend visualization is a direct function of the projection contract:
`f(RuntimeState) = VisualGeometry`

If a state does not exist in the runtime, it cannot be rendered in the visual geometry.

### 1. Execution Lanes and Sandboxing
Execution occurs within bounded authority. The UI must render these bounds.

- **Solid, Thick Borders (2px-3px):** Denotes a hard sandbox or isolated execution environment (e.g., an untrusted worktree executing a bash script).
- **Dashed Borders:** Denotes an advisory or planning context where state cannot be directly mutated.
- **Nested Boxes:** Maps exactly to sub-process supervision trees or delegated agent lanes.

### 2. Routing Paths and Context Delivery
Context and capability handoffs are explicitly visualized as topological paths.

- **Solid Connecting Lines:** A continuous, verified stream of context or execution handover.
- **Fractured/Broken Lines:** An interrupted stream, typically denoting network latency or a stalled subprocess.
- **Line Density/Thickness:** Corresponds to the volume or priority of the context payload.

### 3. Motion and Cadence
Motion maps to system throughput and state transitions.

- **Pulse Cadence:** Bound to telemetry. A fast, steady pulse denotes high data throughput (e.g., active websocket chunking). A slow pulse denotes idle polling (e.g., waiting for inference).
- **Geometric Transitions:** The physical movement of a UI block from one lane to another maps exactly to the backend state machine transitioning an Intent to a Proposal, or a Proposal to an Execution.
- **Throughput Modulation:** Animation speed (e.g., log scrolling or SVG path drawing) is mathematically linked to the `bytes/sec` or `tokens/sec` projected by the runtime.

---

## Semantic Domains

### Runtime Planning Semantics
When an agent or planner is formulating an approach:
- **Visual State:** Dashed geometry, low visual weight.
- **Motion:** Discrete updates mapping to tree-search node evaluations or logit probability distributions. No "smooth" spinning.
- **Meaning:** The system is computing, but authority has not been invoked and state has not been mutated.

### Proposal Semantics
When a model outputs an intent that requires governance approval:
- **Visual State:** A distinctly framed "Proposal Card" sitting on a boundary line between the agent lane and the execution lane.
- **Color:** Neutral or Amber (awaiting review).
- **Meaning:** The execution router has intercepted an action. The system is paused pending mechanical gate validation or human approval.

### Supervision and Stalled-Runtime Semantics
When a subprocess is running under supervision:
- **Visual State (Active):** Solid green or monochrome execution lane with active log tailing.
- **Visual State (Stalled/Blocked):** If the supervisor detects a stall (e.g., waiting for `stdin`), the execution lane border flashes or turns Amber, and a specific "Stall Reason" projection is rendered. The UI fractures the active execution path.
- **Meaning:** The runtime is blocked and requires intervention.

### Integrity Semantics
Integrity validation runs continuously in the background.
- **Visual State (Valid):** Thin, unobtrusive solid green checkmarks or borders.
- **Visual State (Divergence/Failure):** Snaps instantly to heavy Red geometry. The execution path is visibly severed.
- **Meaning:** The system's mechanical state has violated a governance rule (e.g., a file was mutated outside the worktree).

### Replay Semantics
When the user scrubs the temporal trace:
- **Visual State:** The entire UI shifts to a distinct "Replay Mode" palette (often desaturated or sepia-toned) to prevent confusion with live execution.
- **Replay Sweeps:** A vertical or horizontal "scrub line" or timecode overlay dominates the UI.
- **Motion:** Snap-to-state. When the timeline jumps, all widgets immediately render the projected state for that exact historical tick. Tweening is forbidden.