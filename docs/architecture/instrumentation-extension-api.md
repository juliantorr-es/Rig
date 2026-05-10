# Instrumentation Extension API

Rig’s visualization substrate is extensible only through deterministic, replay-safe, projection-backed extensions. Contributors add new instrumentation by registering bounded primitives and declaring how those primitives participate in disclosure, motion, and density governance.

## Required Contracts

- Extensions must derive from projection state.
- Extensions must remain replay-safe.
- Extensions must be bounded in element count and lifecycle.
- Extensions must declare disclosure layer participation.
- Extensions must declare density priority.
- Extensions must declare collapse behavior.
- Extensions must declare reduced-motion behavior.

## Deterministic Ordering Rules

- Registration order must be explicit and stable.
- Primitive ordering within a registration bucket must sort by deterministic keys, typically projection sequence and semantic priority.
- Composition must not depend on wall-clock ordering.

## Replay Requirements

- Visual output must reconstruct from sequence-derived inputs.
- Replay overlays and visualizers must be able to rehydrate from historical projections.
- Hidden local state may not change replay output.

## Memory Requirements

- All extension-managed collections must be bounded.
- Cleanup must evict stale primitives deterministically.
- New primitives must not cause unbounded DOM growth.

## Motion Governance Participation

- Extensions must respect reduced-motion mode.
- Extensions must calm motion under overload.
- Extensions must not amplify stimulation when density rises.

## Disclosure Participation

- Extensions must declare the highest disclosure layer they may occupy.
- Lower layers may show summaries of extension state.
- Higher layers may reveal full detail when the operator expands the surface.

## Density Collapse Participation

- Extensions must define how they summarize under density pressure.
- Dense detail should collapse into stable abstraction.
- Collapse must preserve semantic meaning and anchor identity.

## Example Extension Lifecycle

1. Receive a projection
1. Map the projection to a bounded primitive set
1. Register primitives with explicit metadata
1. Render inside the declared disclosure layer
1. Suppress or collapse detail when density rises
1. Clean up primitives when the projection or panel changes

## Example Primitive Registration

```javascript
registry.register({
  id: 'runtime-throughput',
  kind: 'throughput-indicator',
  disclosureLayer: 2,
  densityPriority: 'medium',
  collapseBehavior: 'summarize',
  reducedMotionBehavior: 'static',
  sequence: projection.sequence,
  build: () => new SvgThroughputBar(...)
});
```

## Example Projection Mapping

- Use the projection sequence for deterministic placement.
- Use projection severity for priority and emphasis.
- Use projection kind for semantic routing.
- Use projection replay flags for historical overlays.

## Example Cleanup Semantics

- Remove orphaned primitives when their owning projection disappears.
- Trim older primitives when bounded capacity is exceeded.
- Preserve the latest stable owner for replay reconstruction.

## Contributor Rule of Thumb

If an extension cannot explain its replay behavior, disclosure layer, collapse behavior, and cleanup behavior up front, it is not ready to be added.
