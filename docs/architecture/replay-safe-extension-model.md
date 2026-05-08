# Replay-Safe Extension Model

Rig extension points must remain replay-safe. If an extension cannot be reconstructed from canonical projection and replay data, it does not belong in the visualization substrate.

## Core Doctrine

- Deterministic event ordering is mandatory.
- Visualization must be sequence-derived.
- Replay reconstruction must be stable.
- Temporal consistency must survive rehydration.
- Replay memory must stay bounded.

## Canonical Rules

- No wall-clock-derived geometry.
- No random animation timing.
- No nondeterministic node placement.
- No hidden local state that changes replay output.

## Historical Visualization Semantics

- Historical rendering should show the state at the selected sequence, not the state at render time.
- Replay overlays may highlight a history path, but they may not infer unobserved events.
- Reconstructed state must match the same projection inputs on every pass.

## Bounded Replay Memory

- Replay extensions must cap retained frames and overlays.
- Older data should be evicted deterministically.
- The oldest non-critical detail is removed first.

## Extension Replay Lifecycle

1. Receive a sequence or replay frame
1. Reconstruct the required geometry from projection data
1. Register primitives in deterministic order
1. Render with replay-safe state only
1. Cleanup deterministically when the replay window moves

## Forbidden Behaviors

- wall-clock timers as state sources
- random or time-based animation delays
- hidden mutable caches that alter geometry
- replay-local state that cannot be reconstructed

## Guarantee

The same input history must produce the same extension visualization every time.
