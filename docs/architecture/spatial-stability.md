# Spatial Stability Doctrine

Rig keeps runtime geometry stable so the operator can track change without losing orientation. Persistent topology keeps state changes inside anchored structures, not by reflowing the whole interface.

## Core Doctrine

- Persistent topology is preferred over transient layout.
- Lane positions should remain stable across updates.
- Geometry must be deterministic and replay-safe.
- Movement must be bounded and purposeful.
- Condensation must preserve anchors.

## Stable SVG Anchor Policy

- Each lane, node, and routing surface needs a deterministic anchor.
- Anchors should be derived from projection state, not from incidental render order.
- Re-rendering must reuse the same anchor positions whenever the underlying topology identity is unchanged.

## Lane Persistence Semantics

- Lanes keep their identity even when content changes.
- Added or removed content must not force unrelated lanes to move.
- Lane collapse should preserve lane order and priority semantics.
- When a lane is summarized, its placeholder must occupy the same spatial role.

## Topology Stabilization Rules

- New state should appear inside existing stable containers where possible.
- Routing updates should bend or summarize before they trigger layout shifts.
- Supervision and integrity changes may emphasize a lane, but they must not force wholesale restructuring.
- The view should resist oscillation when the backend emits rapid updates.

## Deterministic Condensation Anchoring

- Dense clusters should collapse toward the same anchors every time.
- Aggregated summaries should inherit the spatial identity of the group they represent.
- Replay must reconstruct the same condensed structure for the same state history.

## Readability Guarantee

The operator should never need to re-learn where a lane lives because the system is under load.
