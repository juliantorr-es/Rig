# Governed Motion Doctrine

Rig treats motion as a governed signal. Motion must convey runtime meaning without overwhelming the operator, and it must become calmer when overload rises.

## Core Doctrine

- Motion is a projection of real runtime state.
- Motion rate is bounded.
- Motion must not intensify simply because telemetry grows.
- Motion MUST become calmer under overload.
- Overload collapse means calmer cadence, simpler transitions, and lower stimulation.
- Replay motion should pace understanding, not dramatize history.

## Cadence Priority Hierarchy

1. Integrity and supervision signals
1. Replay state transitions
1. Routing and throughput transitions
1. Routine execution progress
1. Background or low-priority state changes

Higher-priority motion may interrupt lower-priority motion, but it must still respect the overall stimulation ceiling.

## Motion Significance Hierarchy

- High significance: integrity divergence, supervision failure, replay inconsistency
- Medium significance: routing change, capability transition, replay progression
- Low significance: routine throughput shifts, stable execution, routine completion

Not all telemetry deserves animation. Some state should remain static and legible.

## Reduced-Motion Behavior

- Reduced-motion mode minimizes transition distance and duration.
- Low-stimulation mode favors snapping or short interpolation over sweeping movement.
- Motion should collapse to shorter, slower, or fully static representations when density rises.
- The system should never substitute flashing or pulsing for missing clarity.

## Overload Collapse Behavior

When complexity increases:

- motion becomes calmer
- cadence slows or stops
- topology stabilizes
- secondary animation defers
- high-frequency pulses are removed
- dense surfaces summarize instead of shimmer

This is a hard requirement. More input must never create more visual chaos.

## Interruption Semantics

- Integrity and supervision events may interrupt routine motion.
- Interruptions should be rare, explicit, and bounded.
- Repeated interruptions should aggregate into a stable summary rather than a flashing loop.

## Forbidden Motion

- strobing
- flashing alert spam
- RGB-style instrumentation
- high-frequency pulsing
- chaotic topology motion
- decorative gradients used as motion substitutes

## Replay Pacing

- Replay should be understandable at a glance.
- Temporal scrubbing must be deterministic and bounded.
- Replay speed should default to measured, not dramatic.
- Under replay overload, pacing should slow and summarize instead of accelerating.
