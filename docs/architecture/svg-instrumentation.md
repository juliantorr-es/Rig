# SVG-First Instrumentation Architecture

## Summary

Rig's frontend is an operational instrument that relies on deterministic, replay-safe visualization. To achieve this, the architecture mandates an **SVG-first** rendering philosophy. 

This document explains why SVG is the canonical primitive for runtime instrumentation, how projection data maps to geometry, and why opaque rendering layers like Canvas and WebGL are explicitly avoided for core visualization.

---

## Why SVG is the Canonical Primitive

Rig visualizes complex, governed cognitive infrastructure: execution routing, capability lanes, telemetry bounds, and replay topology. SVG provides specific architectural guarantees that align with Rig's doctrine.

### 1. Deterministic Rendering
SVG is mathematically deterministic. A defined coordinate space maps perfectly to strict projection data. Given the same backend projection payload, the SVG geometry will render identically across sessions and replays, leaving no room for unconstrained rendering variability.

### 2. DOM-Addressable Geometry
Unlike Canvas, where state is drawn into an opaque raster bitmap, SVG nodes exist as discrete elements in the DOM. This ensures that every line, stroke, and polygon can be individually addressed, inspected, styled via CSS, and bound directly to websocket projection streams without needing complex intermediate state managers.

### 3. Inspectability
Rig is an execution control plane. Transparency is paramount. SVG allows operators (and developers) to open the browser inspector and literally read the structural geometry of the execution topology in plaintext markup.

### 4. Vector Instrumentation
Operational visualization demands infinite precision at any scale. Vector graphics ensure that whether the user is viewing a macro-level capability routing graph or a micro-level token throughput timeline, the instrumentation remains geometrically pristine.

---

## The Avoidance of Canvas and WebGL

Rig explicitly avoids Canvas and WebGL-heavy architectures for core visualization. 

**Why?**
1. **Opaqueness:** Canvas acts as a black box. The rendered state cannot be easily inspected or diffed via standard DOM tools, violating Rig's transparency doctrine.
2. **Replay Complexity:** Reconstructing exact temporal states on a Canvas requires building a bespoke, heavy rendering engine to manage the delta between frames. SVG allows the browser to handle the DOM reconciliation deterministically based on projection data.
3. **Overhead:** WebGL is designed for high-framerate, complex 3D scenes. Rig's operational geometry—lines, boxes, graphs, and structured text—does not require GPU pipeline overhead; it requires structural rigidity.

---

## Core Instrumentation Rendering

SVG is utilized to render the fundamental mechanical realities of the Rig runtime:

- **Topology Rendering:** Visualizing the relationship between agents, tools, and the workspace.
- **Execution Routing Visualization:** Drawing the explicit paths context takes as it is handed off from a planner to an isolated execution sandbox.
- **Capability Lane Visualization:** Rendering the bounding boxes and access limits of specific toolsets (e.g., separating a network-fetch lane from a bash-execution lane).
- **Runtime Graph Rendering:** Plotting decision trace graphs, inference entropy sparklines, and bounded stream buffers.

---

## SVG State Binding Patterns

The frontend projection contract dictates how backend state becomes visual geometry. Widgets must adhere to these mapping patterns:

### Projection → Geometry Mapping
State variables from the backend map directly to SVG attributes.
- Example: A subprocess execution progress projection maps directly to an `<rect width="[projected_value]">` or an `<line stroke-dashoffset="[projected_value]">`.

### Vector Topology Semantics
- **Coordinate Space:** SVG `viewBox` coordinates must be treated as absolute truth. The coordinate system must not float or dynamically scale without an explicit backend projection commanding it to do so.
- **Grouping:** Related operational scopes must be grouped logically in `<g>` tags, matching the hierarchical tree of the backend execution structure.

### Stroke and Fill Semantics
- **Stroke Weight:** Maps to authority or trust levels. A 3px solid stroke denotes a hard sandbox boundary; a 1px dashed stroke denotes an advisory capability link.
- **Color/Fill:** Strictly maps to runtime state (e.g., active, stalled, failed, successful). Gradients are only permitted if they map directly to a telemetry variance (e.g., mapping confidence gradients across a temporal axis).

### Motion and Transform Semantics
SVG `<animate>` or CSS `transform` attributes are heavily constrained (see *Truthful Animation Doctrine*). 
- Transforms (translate, scale, rotate) must bind to specific, projected target values.
- If a replay scrub occurs, the `transform` value must snap to the exact historical projected coordinate instantly. Unbounded SVG SMIL animations that lack a discrete end-state mapped to projection data are forbidden.