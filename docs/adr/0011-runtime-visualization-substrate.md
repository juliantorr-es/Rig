# Runtime Visualization Substrate

**ADR 0011 — Canonical**

This ADR defines the architectural transition of Rig's UI from a stateless, imperative redraw model to a **Retained Render Graph** with incremental patching. This transition is informed by the successful **UI-R1 exploratory sprint**, which demonstrated that the primary performance bottleneck in Rig's visualization was **DOM lifecycle churn** (constant teardown and rebuild), not the choice of rendering backend (SVG).

**Status**: proposed

**Related ADRs**:
- [0002 Projection Domain Consolidation](0002-projection-domain-consolidation.md) — visualization remains a subordinate projection of authoritative state.
- [0004 Runtime Streaming Consolidation](0004-runtime-streaming-consolidation.md) — visualization consumes the canonical event stream for real-time telemetry.
- [0009 Agentic Workflow Refinement](0009-agentic-workflow-refinement.md) — visualization must represent governed agent intent truthfully.

---

## 1. Architectural Discovery: The UI-R1 Pivot

The UI-R1 exploratory sprint established the following empirical baseline:

### 1.1. Churn vs. Throughput
The bottleneck in the previous `DtgSvgRenderer` was not the total element count, but the **frequency of `createElement` and `removeChild` operations**. By clearing the entire SVG tree on every update, we forced the browser to re-evaluate style, layout, and paint for the entire branch, even when 95% of the topology remained stable.

### 1.2. Semantic Persistence
Imperative redraws destroyed visual state (selections, animations, hover states) and broke accessibility continuity. A retained model preserves the **identity** of visual elements, aligning them with the persistent identity of the underlying projection nodes.

### 1.3. SVG Viability
SVG remains the preferred substrate for Rig because it provides:
- Native accessibility semantics (`aria-hidden`, `role`).
- CSS-driven styling and theming (ADR 0005).
- Direct DOM-based inspectability for debugging.
- Sufficient performance for topologies up to ~1,000 nodes once redraw churn is removed.

---

## 2. Normative Architectural Constraints

> These constraints define the boundary between "fast rendering" and "governed visualization."

### 2.1. Projection Authority
**Visualization is subordinate to the Projection.** The render graph is a non-authoritative projection of the state. It must never "invent" visual state that does not have a corresponding origin in the deterministic projection.

### 2.2. Identity Determinism (Replay Fidelity)
Visual element IDs must be derived deterministically from **Projection Node IDs**. In a replay session, the same node must result in the same DOM element identity. This ensures that "scrubbing" a timeline results in stable visual patching rather than flickering.

### 2.3. Accessibility Integrity
The render graph must preserve a semantic tree.
- Decorative elements must be explicitly hidden (`aria-hidden="true"`).
- Interactive nodes must maintain focusable boundaries.
- The DOM structure should reflect the logical topology where possible.

### 2.4. Retention Boundaries
- **Stable Nodes**: Capability nodes, executors, and lanes are retained across the entire stream lifecycle.
- **Volatile Overlays**: Transitory stream density lines and connectors are garbage-collected when their sequence context expires.

---

## 3. The Render Graph Model

The visualization substrate is composed of three primary seams:

### 3.1. The `RenderNode` Interface
Every visual primitive (lane, node, edge, path) must implement the `RenderNode` contract:
- `render(parent)`: Initial DOM creation and mounting.
- `patch(element)`: Incremental update of an existing DOM element with new state.
- `id`: Deterministic identifier bound to the projection node.

### 3.2. The `SceneGraphManager`
Responsible for managing the lifecycle of `RenderNodes`:
- **Retention**: Maintains a registry of active `RenderNode` instances and their associated DOM elements.
- **Patching**: Orchestrates the `patch()` cycle, ensuring only mutated attributes are sent to the DOM.
- **Garbage Collection**: Prunes elements that were not visited during the current render pass.

### 3.3. The `BackendAdapter` (Future-Proofing)
While SVG is the current canonical backend, the `RenderNode` abstraction provides a seam for future expansion:
- **SVG Adapter**: (Current) Direct DOM manipulation.
- **Canvas Adapter**: (Optional) For high-density telemetry overlays.
- **WebGPU Adapter**: (Optional) For massive execution graph visualizations.

---

## 4. Implementation Strategy

### 4.1. Refactor Phase: Module Extraction
Move the prototype logic into a stable core module:
`src/rig_tools/static/js/core/render-graph.js`

### 4.2. Incremental Widget Migration
Migrate existing widgets to the `RenderNode` pattern in order of complexity:
1. **Topology Panel** (Completed in UI-R1 prototype).
2. **Execution Timeline**.
3. **Audit/Evidence Inspector**.
4. **Agent Proposal Overlays**.

### 4.3. Invalidation Doctrine
Implement targeted invalidation to avoid patching sub-trees that haven't changed.
- Use **Sequence Numbers** to skip patching of stable history.
- Use **State Hashes** for complex topology nodes.

---

## 5. Consequences

### 5.1. Leverage
- **Performance**: 90-100% reduction in DOM lifecycle operations for stable views.
- **Maintainability**: Clear separation between "what to draw" (Projection) and "how to patch it" (Render Graph).

### 5.2. Locality
Visual logic is encapsulated within specific `RenderNode` classes rather than scattered across procedural re-rendering loops in the widgets.

### 5.3. Risk
- **State Desync**: Risk of the DOM "ghosting" if the `patch()` logic doesn't perfectly match the `render()` logic. Mitigated by strict testing and shared styling tokens.
- **Memory Growth**: The retained graph must be rigorously garbage-collected. Mitigated by the `SceneGraphManager.garbageCollect` pass.

---

## 6. Summary

ADR 0011 transforms Rig's UI from a reactive display into a **persistent visual runtime**. By embracing retention semantics over imperative redraws, we preserve semantic identity and accessibility while achieving the performance levels required for professional agent orchestration tooling. Rig remains committed to **truthful visualization**, where every pixel on the screen is a deterministic projection of the governed execution state.
