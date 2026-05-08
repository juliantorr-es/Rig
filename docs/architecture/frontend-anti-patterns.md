# Frontend Visual Anti-Patterns

## Summary

Rig is an operational execution environment. Because the frontend serves as a forensic lens and a literal representation of backend state, certain visual patterns common in modern web design and consumer "AI apps" are structurally harmful.

This document explicitly defines forbidden frontend patterns and explains why they violate Rig’s architecture.

---

## 1. Synthetic "AI" Motion

### Fake AI Typing Bubbles
**Description:** Three bouncing dots used to indicate an LLM is "thinking" or processing.
**Why it is harmful:** It masks the actual mechanical state. The backend is either waiting for a network byte, processing a context window, or blocked by a governance gate. A generic bouncing bubble obscures the exact operational phase from the user, destroying observability.

### Arbitrary Shimmer and Particle Effects
**Description:** Sweeping light gradients or floating particles over active UI components.
**Why it is harmful:** It breaks the *Visual Truthfulness Doctrine*. Motion must represent throughput, state transition, or specific routing logic. Arbitrary shimmer implies activity without providing verifiable telemetry, reducing the UI to decoration.

### Meaningless Gradients
**Description:** Colorful gradient backgrounds or borders that do not map to telemetry.
**Why it is harmful:** It consumes semantic bandwidth. In Rig, color gradients are reserved for literal data mapping (e.g., inference entropy gradients or topology heatmaps). Decorative gradients dilute the operational vocabulary.

---

## 2. Dishonest Operational State

### Fake Progress Bars
**Description:** A progress bar that artificially "eases" forward on a generic timer without receiving discrete progress chunks from the backend.
**Why it is harmful:** When an execution stalls at 90%, a fake progress bar will confidently animate to 99% and hang. This lies to the user about when and where the execution actually failed, corrupting the replay trace.

### Synthetic Activity Loops
**Description:** Infinite looping animations (like spinning rings) that continue spinning even if the backend websocket connection is severed or paused.
**Why it is harmful:** The frontend must never animate a state of "working" if the backend stream has fractured. If the system is stalled, the UI must immediately render a fractured or static state.

---

## 3. Structural and Systemic Violations

### Frontend Authority Inference
**Description:** The frontend inspecting a user token or capability payload and independently deciding to hide or show an execution lane based on presumed permissions.
**Why it is harmful:** The frontend possesses zero authority. By inferring authority, the frontend creates a risk of state desynchronization. The backend governance engine must calculate visibility and project an explicit `isVisible: true/false` flag. The UI obeys the projection blindly.

### Hidden Execution State
**Description:** Truncating or hiding specific `stdout` lines or intermediate reasoning steps to make the UI look "cleaner" or more consumer-friendly.
**Why it is harmful:** Rig is an execution control plane. If an agent executes a command, the operator must be able to see the literal receipt of that command. Hiding execution state breaks the forensic auditability of the tool.

### Direct Subprocess Rendering
**Description:** Opening a direct terminal or WebRTC channel from the frontend directly to an executing bash sandbox, bypassing the projection engine.
**Why it is harmful:** It bypasses the websocket normalization and recording layer. The execution state is rendered to the user but not captured in the canonical trace, permanently fracturing the replayability of the session.

### Runtime State Hidden from Projections
**Description:** Implementing a complex UI feature that calculates its own intermediate states (e.g., a multi-step wizard) without those states being round-tripped and saved as formal backend projections.
**Why it is harmful:** When the session is replayed, the intermediate wizard states will be lost because they were never recorded in the governance trace. All visual states must be projection-backed.