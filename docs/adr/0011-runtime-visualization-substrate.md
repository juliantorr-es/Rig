# Runtime Visualization Substrate

**ADR 0011 — Canonical**

This ADR defines the architectural transition of Rig's UI from a stateless, imperative redraw model to a **Retained Render Graph** with incremental patching. This transition is informed by the successful **UI-R1 exploratory sprint**, which demonstrated that the primary performance bottleneck in Rig's visualization was **DOM lifecycle churn** (constant teardown and rebuild), not the choice of rendering backend (SVG).

**Status**: accepted

**Related ADRs**:
- [0002 Projection Domain Consolidation](0002-projection-domain-consolidation.md) — visualization remains a subordinate projection of authoritative state.
- [0004 Runtime Streaming Consolidation](0004-runtime-streaming-consolidation.md) — visualization consumes the canonical event stream for real-time telemetry.
- [0009 Agentic Workflow Refinement](0009-agentic-workflow-refinement.md) — visualization must represent governed agent intent truthfully.

---

## 1. Architectural Discovery & Research Foundation

The transition defined in this ADR is informed by both the empirical results of the **UI-R1 exploratory sprint** and a rigorous review of HCI and visualization literature.

### 1.1. External Cognition
Following Scaife and Rogers (1996), Rig's interface is treated as an **external cognitive artifact**. Graphical representations are designed to offload memory, restructure search, and make complex system relationships available "at a glance."

### 1.2. Stable Geography vs. Flexible Geometry
Research on spatial memory (e.g., Robertson et al.'s *Data Mountain*) indicates that **stable spatial arrangement** provides statistically significant advantages in orientation and retrieval. Rig explicitly avoids flexible or "auto-layout" geometry that breaks a user's cognitive map, opting instead for a persistent geographic reference frame.

### 1.3. Churn vs. Throughput (Empirical)
The UI-R1 sprint confirmed that the primary performance bottleneck was the **frequency of `createElement` and `removeChild` operations**. By clearing the entire SVG tree on every update, we forced the browser to re-evaluate style, layout, and paint for the entire branch, even when 95% of the topology remained stable.

### 1.4. Semantic Persistence
Retaining DOM elements preserves the **identity** of visual elements (Object Constancy), aligning them with the persistent identity of the underlying projection nodes.

### 1.5. SVG Viability
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

## 3. Non-Goals

- ADR 0011 does **not** make the renderer authoritative; state remains in the projection.
- ADR 0011 does **not** introduce Canvas or WebGPU as required backends for demo stability.
- ADR 0011 does **not** make educational narration a substitute for objective evidence.
- ADR 0011 does **not** allow demo choreography to fabricate or simulate runtime state.
- ADR 0011 does **not** optimize for visual spectacle over causal clarity.

---

## 4. The Render Graph Model

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

## 5. Implementation Strategy

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

## 6. Cognitive Runtime Experience (UI-R3)

The substrate has evolved beyond rendering into a **Cognitive Infrastructure** that manages information density through progressive disclosure, spatial orientation, and semantic motion.

### 6.1. Progressive Cognitive Disclosure (Layers 1-4)
Advanced systems become unusable if all telemetry is equally visible. Rig implements a visibility governance system that layers information density:
- **Layer 1 (Health)**: Primary intent, current progress, and system health.
- **Layer 2 (Topology)**: Execution lanes and runtime graph structures.
- **Layer 3 (Trace)**: Governance logs, streaming audits, and trace projections.
- **Layer 4 (Debug)**: Internal telemetry, replay timelines, and renderer metrics.

### 6.2. Meaningful Motion Doctrine (Visual Momentum)
Following Heer and Robertson (2007), motion in Rig is used to support **Object Constancy** and help users understand how one system state became another. Animations must preserve visual momentum and reinforce the deterministic flow of execution:
- **Causal Staging**: Animations are staged and staggered (Thompson et al., 2021) to indicate propagation paths through the graph without creating "temporal chart junk."
- **Governance Shakes**: Visually resisting invalid or blocked proposals to provide immediate causal feedback.
- **Identity Preservation**: Maintaining persistent identity across re-projections to reduce the cognitive cost of re-orientation.

### 6.3. Spatial Cognition & Landmarks
The runtime environment is organized into five **Districts** (Lynch, 1960) to build user muscle memory and persistent orientation (Vinson, 1999). We use simple, asymmetrical landmarks to ensure the geography is legible across all zoom levels:
*   **North (Intent)**: The administrative district for workspace status and intent dispatch.
*   **West (Execution)**: The path for live streaming telemetry and execution logs.
*   **Center (Causality)**: The core node-link topology and causality map.
*   **East (Governance)**: The boundary for validation receipts and audit trails.
*   **South (History)**: The temporal district for replay timelines and navigation.

### 6.4. Educational Narration Layer (Signaling Effect)
Visualization is subordinate to **Causality**. Following Mayer and Moreno (2003), the `ExplainerNode` substrate uses **Signaling** to guide attention to relevant parts of a causal process:
- **Segmented Bursting**: Educational narration appears as small, well-timed, controllable bursts to reduce cognitive load.
- **Contextual Anchoring**: Explanations are anchored to specific landmarks (Vinson, 1999) to preserve the spatial frame.
- **Neutral Phrasing**: To avoid author bias (Hearst, 2020), annotations use neutral, evidence-based language that supports exploratory reasoning rather than replacing it.

## 7. Operational Doctrine & Guardrails

To prevent the cognitive infrastructure from becoming "decorative mythology," Rig enforces strict operational rules, thresholds, and failure modes.

### 7.1. Evaluation Metrics
ADR 0011 features must be evaluated against the following deterministic metrics:
- **Time to Orient**: How quickly a user can identify Intent (North), Execution (West), Governance (East), and History (South).
- **Reorientation Cost**: The cognitive effort required after a layer change, replay scrub, or reconnect.
- **Explanation Usefulness**: Whether annotations improve causal understanding without replacing user reasoning.
- **Churn Budget**: Total create/remove counts, patch counts, skipped patches, and layout invalidations per second.
- **Disclosure Safety**: Ensuring critical errors (Layer 1) remain visible even when high-density layers (Layer 2-4) are hidden.
- **Replay Fidelity**: Ensuring the same projection sequence produces stable visual identities across sessions.

### 7.2. User Control Over Explanation
Following the segmentation effect (Moreno, 2003), educational narration must be user-controllable:
- **Dismissal**: Users can dismiss current explainers immediately.
- **Replay**: Users can request a replay of the explainer for the current state.
- **Suppression**: Users can disable narration for the current session.
- **Density Control**: Users can reduce explainer frequency by raising trigger thresholds or selecting a lower narration density.
- **Provenance**: Every explainer must optionally show its **Research Provenance** (which design principle informed it) and its **Runtime Provenance** (which specific projection field or event triggered it).

### 7.3. Explainer Governance & Neutrality
Every `ExplainerNode` must map to an observable runtime event or projection field. Explainers must not infer user intent or emotional state.
**Required Attribution Fields**:
- Triggering Projection Field
- Triggering Runtime Event
- Affected Render Node ID
- **Research Provenance**: Design principle or research citation reference.
- **Runtime Provenance**: Originating projection field or event ID.
- **Dismissal State**: Whether the explainer was dismissed or timed out.

### 7.4. Stable Geography Rules
- **District Stability**: Districts (North/West/Center/East/South) must not reorder during a session.
- **Landmark Persistence**: Primary visual anchors must remain visible across cognitive layers.
- **Layout Constraint**: Auto-layout must not move stable concepts unless topology identity changes.
- **Orientation Continuity**: Zoom/pan operations must preserve orientation markers.
- **Demo Guard**: Demo mode must use a fixed geography to avoid re-orientation fatigue.

### 7.5. Motion Budget
Motion is a finite cognitive resource. We enforce a strict budget:
- **No Ambient Motion**: All movement must be tied to a specific runtime event (pulse, shake, transition).
- **Serialization**: No more than one primary causal animation may fire at a time.
- **Traceability**: All motion must correspond to a change in projection sequence or governance state.
- **Reduced Motion**: All animations must respect browser `prefers-reduced-motion` settings.
- **Streaming Degradation**: Long-running telemetry must degrade from active pulses to subtle state indicators to avoid visual fatigue.

### 7.6. Accessibility Requirements
- **Keyboard Reachability**: All cognitive layers and explainers must be reachable via keyboard navigation.
- **Text Alternatives**: Explainers must be accessible as ARIA-compliant text, not just spatial bubbles.
- **Contrast & Hierarchy**: Governance states must be distinguishable by shape or icon, not just color.

### 7.7. Demo Mode Boundary
Demo mode may choreograph disclosure sequences, but it **must not fabricate projection state**. The "Truthful Replay" doctrine is non-negotiable; theater is permitted in pacing, but forbidden in data.

### 7.8. Failure Modes
- **Geography Collapse**: Zones move/resize unpredictably, breaking spatial memory.
- **Annotation Spam**: Explainers compete for attention, causing cognitive overload.
- **False Causality**: Motion suggests a relationship not present in the projection.
- **Hidden Criticality**: Progressive disclosure hides a safety issue or blocked state.
- **Replay Ghosting**: Retained DOM state survives after projection state changes.
- **Debug Leakage**: Internal Layer 4 telemetry appears during beginner/demo flows.
- **Landmark Overdecoration**: Visual anchors become noise instead of orientation aids.

---

## 8. Evidence Notes
Research citations (Scaife, Rogers, Robertson, et al.) inform the design constraints but do not prove Rig's implementation is effective. Final effectiveness must be validated through:
- **Local Usability Rehearsals**: Can a user orient themselves in <3 seconds?
- **Renderer Metrics**: Monitoring the Churn Budget in the Rig Debug Panel.
- **Replay Audit**: Verifying visual identity stability across multiple scrub cycles.

---

## 9. Implementation Progress

### 9.1. UI-R1: Retained Prototype
Explored incremental graph patching and established the SVG backend seam. (Completed)

### 9.2. UI-R2: Substrate Expansion
Migrated heterogeneous widgets (Timeline, Audit Trail) to `RenderNode` and implemented global renderer observability. (Completed)

### 9.3. UI-R3: Cognitive Experience
Established Rig Design Language v1 and implemented the Progressive Disclosure system and Meaningful Motion primitives. (Completed)

### 9.4. UI-R5: Research-Aligned Validation (Next Mission)
**Goal**: Transition ADR 0011 from doctrine to a testable product experience.
- Implement `prefers-reduced-motion` handling.
- Implement Explainer Density Controls.
- Implement Demo-Mode Boundary Enforcement.
- Add Critical-Error Visibility Escalation tests.
- Add DOM Churn Regression and Replay Ghosting tests.
- Add Annotation Provenance Metadata (Research vs. Runtime) to the `ExplainerNode`.

**Acceptance Criteria**:
- `UI-R5` is accepted only when:
  - `prefers-reduced-motion` mode successfully disables all non-essential causal animations.
  - Explainers expose both Research and Runtime provenance metadata.
  - Critical Layer 1 errors successfully trigger visibility escalation, overriding active disclosure filters.
  - Demo mode code is audited to ensure zero fabrication of projection state.
  - DOM churn regression tests fail if unexpected clear/rebuild patterns are detected.
  - Replay ghosting test proves that retained DOM nodes are correctly pruned when their projection source is removed.

---

## 10. Architectural Consequences

### 10.1. Leverage
- **Performance**: 90-100% reduction in DOM lifecycle operations for stable views.
- **Cognition**: Users can manage system complexity by unfolding layers at their own pace.
- **Muscle Memory**: Users develop geographic intuition for where **Evidence/Governance** (East) vs **Execution** (West) lives.

### 10.2. Locality
Visual logic is encapsulated within specific `RenderNode` classes, while visibility governance is managed by the `CognitiveDisclosure` controller.

### 10.3. Risk
- **Information Hiding**: Risk of critical errors being hidden in Layer 3/4. Mitigated by "Health" layer alerts that trigger visibility escalation.

---

## 11. Summary

ADR 0011 transforms Rig's UI from a reactive display into a **persistent cognitive runtime**. By embracing retention semantics, progressive disclosure, and governed narration, we provide a visual language for systems thinking. Rig remains committed to **truthful visualization**, where every pixel on the screen is a deterministic projection of the governed execution state, audited against the strict operational doctrine of the Rig-Governed Workflow.
