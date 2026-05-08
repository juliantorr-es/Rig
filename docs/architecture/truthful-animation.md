# Truthful Animation Doctrine

## Summary

Rig's frontend is an operational instrument, not a conversational simulation. Therefore, all visual motion—animation, transitions, and state indicators—must derive strictly from real runtime state. Fake "AI thinking" motion is architecturally dishonest and explicitly forbidden.

This document defines the structural rules for motion within Rig's projection-backed frontend.

---

## The Prohibition of Synthetic Motion

Synthetic motion exists to placate human impatience by simulating a continuous thought process. In a governed execution environment, this is fundamentally dishonest. It obscures the mechanical reality of the system, making genuine failures, stalls, and latencies indistinguishable from normal operation.

**Explicitly Forbidden Patterns:**
- **Fake "Thinking" Indicators:** Bouncing dots, pulsing brains, or infinite spinners that are disconnected from actual network or compute IO.
- **Fake Typing Indicators:** Artificially delaying or tweening text rendering to simulate a human typing on a keyboard.
- **Decorative Shimmer:** Sweeping light effects across UI elements that do not map to a specific execution sweep or data throughput rate.
- **Meaningless Gradient Motion:** Gradients that animate infinitely without binding their stops or rotation to a live telemetry variable (e.g., inference entropy or CPU load).

---

## Driven Motion Semantics

All animation in Rig must be derived directly from the backend projection contract. If the backend state is static, the frontend must be static. Motion is a visual receipt of execution.

### 1. Runtime-Derived Motion
Motion driven by the discrete mechanical steps of the execution engine.
- **Example:** When a subprocess is spawned, a deterministic geometric block slides into the "Active" execution lane. The motion duration is bounded by the backend projection's state transition, not an arbitrary CSS transition.

### 2. Throughput-Derived Motion
Motion driven by the volume or velocity of data traversing the system.
- **Example:** A network IO indicator pulses. The frequency of the pulse is mathematically bound to the bytes-per-second transferred. If the network stalls, the pulse stops immediately. It does not gracefully ease-out.

### 3. Capability-Routing-Derived Motion
Motion driven by the governed handover of context from one capability or agent lane to another.
- **Example:** When an execution requires elevated authority, the visual connection line representing the context route draws itself incrementally, mapping to the backend authorization handshake.

### 4. Integrity-Derived Motion
Motion driven by continuous background validation.
- **Example:** A slow, continuous SVG dash-offset animation surrounding an execution sandbox. This motion is bound to the background integrity polling tick. If the poll fails or divergence is detected, the line snaps solid red—the motion ceases instantly.

### 5. Replay-Derived Motion
Motion driven by scrubbing through the temporal execution trace.
- **Example:** When a user scrubs backward in history, UI elements do not "animate out" gracefully. They immediately snap to their deterministically reconstructed state for that specific timestamp. Motion only occurs if the user "plays" the trace forward at a defined multiplier of the original sequence.

### 6. Projection-Derived Motion
The overarching principle: the frontend listens to the websocket stream. Every animation frame or state transition is a direct reaction to a newly received projection chunk.

---

## Truthful vs. Fake Motion: Examples

| Context | Fake (Forbidden) | Truthful (Mandatory) |
| :--- | :--- | :--- |
| **Awaiting LLM response** | Three bouncing dots looping infinitely. | A static "Awaiting First Byte" indicator. |
| **Receiving LLM stream** | Text fades in character-by-character. | Chunks render instantly in blocks as they arrive via websocket. |
| **Executing long bash script** | A generic, uncalibrated progress bar filling up. | A raw terminal output tail updating strictly upon `stdout` emission. |
| **Agent reasoning phase** | A glowing, pulsing gradient border. | A step-by-step rendering of the decision trace graph nodes as they are evaluated. |

---

## Determinism and Replay-Safe Animation

Rig's architecture guarantees that an execution session can be replayed identically. Consequently, frontend animations must be replay-safe.

1. **No Unbounded Clocks:** Animations must not rely on the client browser's `requestAnimationFrame` loop iterating independently of backend state.
2. **State-Driven Easing:** CSS transitions or SVG morphs are permissible *only* if they interpolate between two explicit states provided by the projection stream. The end-state must always accurately reflect the final projected data.
3. **Temporal Snapping:** If the projection stream dictates a jump in time (e.g., during replay scrubbing), all in-flight animations must instantly snap to their final state. Tweening across a discontinuous time jump is forbidden, as it creates a visual reality that never existed in the runtime.

By enforcing these constraints, Rig's frontend remains a trustworthy operational instrument, ensuring that what the user sees is exactly what the cognitive infrastructure did.