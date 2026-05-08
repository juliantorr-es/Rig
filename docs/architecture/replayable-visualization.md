# Replayable Visualization Theory

## Summary

Rig is a replay-first architecture. The frontend must be capable of rendering reconstructed historical state identically to live execution state. This requires a profound shift in how UI is built: visualization cannot rely on ephemeral browser state or unbounded time loops. 

This document defines the theory and mechanical requirements for Replayable Visualization.

---

## Why Replayable Visualization Matters

In traditional web applications, if a user refreshes the page or disconnects, transient animation states and micro-interactions are lost. In Rig, an execution trace is an auditable, governed artifact.

If an operator is investigating why a capability sandbox was breached, they must be able to scrub the execution trace backward and forward. The UI must reconstruct exactly what happened, in the exact sequence it happened, without visual artifacting or "guessing" intermediate states. The frontend is a forensic lens.

---

## Temporal Reconstruction

To achieve deterministic reconstruction, the frontend must act as a pure function of historical time.

### Bounded Visual History
The UI does not store an infinite, mutating DOM tree. Instead, the backend projection contract guarantees a bounded window of state. When the frontend requests a specific historical tick, the backend projects the exact mechanical state of that tick. The UI wipes its current visual topology and renders the newly projected historical state instantly.

### Event Ordering Guarantees and Websocket Sequencing
Live visualization depends on strict event ordering.
- Every websocket payload carries an incrementing sequence ID and a discrete timestamp.
- The frontend buffer must process these chunks strictly in sequence.
- If a chunk is dropped or arrives out of order, the UI must halt rendering and request a sequence resync. Rendering out-of-order execution fragments violates visualization integrity.

---

## Replay-Safe Animation

As established in the *Truthful Animation Doctrine*, motion in a replayable environment is dangerous if unconstrained.

### Deterministic Motion Sequencing
Animations must be mathematically derivable from sequence IDs, not system clocks. 
- A progress bar moving from 10% to 50% must not use an unconstrained CSS `transition`. 
- Instead, the UI renders exactly what the sequence dictates. If played back at 10x speed, the visual updates 10x faster. The visual motion is a byproduct of the sequence velocity, not a frontend tweening engine.

### Visual Reconstruction Semantics
When scrubbing to a specific historical frame:
1. **Halt Motion:** All active animations are immediately killed.
2. **Snap to State:** DOM nodes update their attributes (coordinates, text, colors) to the exact projected values of the target frame.
3. **No Tweening:** The UI must not visually tween from the "current" scrub position to the "target" scrub position, as that would generate a synthetic visual reality that never existed in the actual trace.

---

## Visualization Integrity and Divergence

Replayable visualization requires explicit handling of divergence.

### Replay Divergence Visualization
When a backend integrity check detects that a deterministic replay has diverged from its original receipted trace (e.g., due to a non-deterministic external API call mutating state differently on replay), the frontend must explicitly visualize this fracture.

- **Visual State:** The timeline or topological graph fractures at the exact sequence ID where divergence occurred.
- **Semantics:** The UI renders a diverging branch. The original canonical trace is locked in a read-only visual state, while the diverged replay is rendered in an "Advisory" or "Unverified" geometric lane (dashed borders, amber styling).
- **Meaning:** The operator is visually informed that the execution being viewed is no longer cryptographically bound to the original receipt.