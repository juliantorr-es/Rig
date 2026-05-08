# Frontend Systems Architecture

## Summary

Rig’s frontend is a strict, projection-backed visualization layer. It is not an autonomous application that manages its own business logic or infers state. The frontend exists exclusively to consume normalized websocket streams and render deterministic geometry.

This document canonicalizes the mechanical architecture of the frontend.

---

## Projection-Backed Architecture

The core tenet of the frontend is that **widgets remain dumb renderers**. They possess no independent cognitive capacity.

### Why Widgets Remain Dumb
If a widget decides to fetch its own data, infer the state of an execution, or mutate a local variable that the backend is unaware of, the system fractures. The frontend would display a visual reality that does not exist in the governed backend trace, rendering replay and forensic auditing impossible.

### Strict Constraints
To maintain a forensic visualization layer, the frontend adheres to absolute constraints:
1. **No Hidden Fetching:** Widgets are forbidden from making out-of-band HTTP requests or secondary API calls. Every piece of data rendered must arrive via the centralized websocket projection stream.
2. **No Authority Inference:** The frontend must never guess if a user or agent has permission to execute an action. Authority boundaries (e.g., capability gating) are calculated entirely by the backend governance engine and projected to the frontend as explicit Boolean/Enum states.
3. **No Hidden State Mutation:** Frontend state management (e.g., Redux, local component state) is heavily restricted. The frontend may maintain ephemeral UI state (e.g., "is this dropdown open"), but it must never maintain derived execution state. 
4. **Projection-Only Rendering:** Visual geometry is a pure function of the incoming projection contract.

---

## The Runtime Instrumentation Pipeline

The pipeline connecting the mechanical execution environment to the visual interface is unidirectional and highly normalized.

### 1. Websocket Normalization
The backend translates complex, heterogeneous runtime events (subprocess `stdout` emission, token generation, governance gate checks) into a strictly typed, normalized schema. This schema is transmitted over a single websocket connection. This ensures that the frontend only ever parses a consistent, versioned contract.

### 2. Bounded Frontend State
The frontend buffer that receives the websocket sequence is mechanically bounded. It retains only the state necessary to render the current projection and reconstruct the immediate context. It relies on the backend to manage the full, heavy history of the trace. When the buffer fills or when the UI requests a different historical frame, the backend sends a fresh projection payload, and the frontend aggressively garbage-collects the old state.

### 3. Frontend Replay Integration
Because the frontend state is bounded and normalized, integrating replay is trivial. The frontend does not care if the websocket payload represents a live execution occurring in real-time or a historical trace being streamed from a database. The rendering logic is identical. The only distinction is a specific `ReplayContext` flag in the projection that shifts the visual palette to indicate historical mode.

---

## Visualization Lifecycles

### Runtime Visualization Lifecycle
1. **Instantiation:** The backend spins up a runtime (e.g., a Bash sandbox). It projects a `RuntimeStarted` event. The frontend renders the sandbox geometry.
2. **Execution:** The runtime executes. The backend projects `RuntimeTelemetry` (CPU, memory, entropy). The frontend dynamically scales its geometric indicators (e.g., line thickness, pulse rate) based on the data.
3. **Termination:** The runtime halts. The backend projects a `RuntimeExited` event with a deterministic status code. The frontend locks the sandbox geometry, changing its state to "Complete" or "Failed."

### Stream Visualization Lifecycle
1. **Chunk Arrival:** A raw token or byte chunk arrives via websocket.
2. **Append:** The frontend appends the chunk to the targeted widget’s bounded buffer.
3. **Flush:** If the chunk completes a logical boundary (e.g., a newline in a terminal stream or a complete JSON object in a structured tool call), the widget flushes the buffer to the DOM deterministically.
4. **Fracture Handling:** If a sequence ID is missed or the websocket drops, the UI instantly renders a "Fractured Stream" geometric overlay, pausing all animation until the backend re-syncs the stream.