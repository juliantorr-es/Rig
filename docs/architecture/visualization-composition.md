# Visualization Composition

Rig’s visualization layer is a governed composition system, not a free-form widget pile. Composition exists so contributors can add instrumentation without breaking replay determinism, disclosure hierarchy, motion governance, or bounded DOM behavior.

## Core Doctrine

- Instrumentation modules compose by projection ownership, not by incidental import order.
- Topology systems compose through stable lane and node ownership.
- SVG primitives compose through deterministic registration and bounded lifecycle rules.
- Replay overlays compose as attachments to existing state, never as independent authority.
- Runtime panels compose as projection-backed containers with explicit disclosure layers.

## Composition Boundaries

- A visualization module owns only the primitives it registers.
- A topology owner owns lane allocation and node placement within its lane scope.
- A replay overlay may attach to a panel, but it may not rewrite the panel’s topology.
- A disclosure layer may suppress or reveal detail, but it may not alter the underlying source of truth.

## Projection Ownership

- Projections remain the only input to visualization decisions.
- Composed primitives may transform projection data into geometry, but they may not invent state.
- A child visualization inherits semantic context from its parent projection and from the active disclosure layer.

## Visualization Lifecycle

1. Register primitives or overlays
1. Bind them to a projection-derived owner
1. Render within bounded DOM and SVG budgets
1. Update deterministically on projection change
1. Clean up stale primitives and orphaned DOM nodes

## Semantic Inheritance

- Parent panels establish the primary operational context.
- Child primitives inherit disclosure constraints, density limits, and motion limits.
- Overlays inherit replay semantics but do not inherit authority.

## Instrumentation Layering

- Layer 1: calm operational overview
- Layer 2: active instrumentation
- Layer 3: deep runtime inspection
- Layer 4: forensics and replay analysis

The layer assignment determines how much detail a component may surface, not whether it may exist.

## Parent/Child Relationships

- A runtime panel is the parent of its topology, stream, and status surfaces.
- A topology surface is the parent of its lanes, nodes, routes, and overlays.
- A replay overlay is a child attachment to an existing visualization surface.

## Topology Ownership Rules

- Each lane belongs to one topology owner.
- Nodes may move within a lane only when projection state changes.
- Cross-lane movement must be explicit and replay-safe.
- A topology owner may summarize dense content, but it may not relocate unrelated lanes.

## Runtime Lane Ownership

- The lane owner defines lane identity and stability.
- Lane summaries are still lane-owned primitives.
- Density collapse may compress content inside a lane, but the lane’s anchor remains fixed.

## Replay Overlay Attachment Rules

- Replay overlays attach to existing panel coordinates.
- Replay overlays may not force topology reflow.
- Replay attachments must be sequence-derived and bounded.
- Overlay cleanup must occur when the replay context exits.
