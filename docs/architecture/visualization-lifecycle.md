# Visualization Lifecycle

Rig visualizations are governed by a bounded lifecycle so contributors can extend the system without creating orphaned DOM, unstable geometry, or replay drift.

## Lifecycle Stages

### Mount

- Bind the visualization to a projection owner.
- Register bounded primitives.
- Attach disclosure metadata, density metadata, and motion metadata.

### Update

- Recompute geometry from projection changes only.
- Preserve anchors where possible.
- Update visible detail without changing ownership boundaries.

### Replay

- Reconstruct historical state from replay data.
- Keep replay overlays bounded and deterministic.
- Use sequence order as the visual authority.

### Cleanup

- Evict stale primitives.
- Remove detached overlay nodes.
- Clear orphaned DOM elements deterministically.

This cleanup lifecycle must be bounded and deterministic.

### Disclosure

- Reveal or hide layers according to explicit disclosure state.
- Never let disclosure cause unrelated layout shifts.

### Density Collapse

- Summarize dense content before adding more primitives.
- Preserve critical anchors and priority information.

### Reduced Motion

- Reduce or suppress motion when the low-stimulation mode is active.
- Motion should simplify, not intensify, under overload.

## Stale Node Cleanup

- Stale nodes are removed when their owning projection is no longer active.
- Removal order must be deterministic.

## Topology Eviction

- Topology eviction preserves high-priority nodes first.
- Collapsed nodes should preserve enough metadata for replay reconstruction.

## Replay Truncation

- Replay truncation must be explicit and bounded.
- Truncated replay must keep a stable summary of the omitted region.

## Primitive Reuse

- Reuse is allowed only when the primitive identity remains stable.
- Reuse may not cross ownership boundaries.

## DOM Recycling

- DOM recycling must preserve deterministic IDs and semantic ownership.
- Recycled DOM must not leak stale disclosure or replay state.

## Bounded SVG Ownership

- Each owner may hold only a bounded number of primitives.
- Ownership changes must be explicit and cleanup-aware.
