# Visual Priority Hierarchy

Rig does not give equal visual weight to all telemetry. The interface must reserve the strongest emphasis for states that affect trust, supervision, or replay correctness.

## Priority Levels

### Low

- chunk throughput
- routine transitions
- stable execution

### Medium

- runtime routing changes
- capability transitions
- replay reconstruction

### High

- integrity divergence
- supervision failure
- replay inconsistency

## Visual Emphasis Rules

- Low-priority state should be quiet, compact, and mostly static.
- Medium-priority state may change geometry, but it should not dominate the screen.
- High-priority state may interrupt other signals, but it must remain bounded and explicit.

## Hierarchy by Channel

- Color: reserved for priority and status, not decoration
- Motion: reserved for meaningful transitions
- Density: reserved for critical summaries, not ornamental fill
- Interruption: reserved for trust and correctness issues

## Semantic Escalation

- Escalation should move from summary to detail, not from calm to spectacle.
- Critical state should surface quickly and then stabilize.
- Repeated critical events should aggregate into a stable fault summary rather than blinking independently.

## Readability Guarantee

The operator should always be able to identify what matters first, what matters second, and what can wait.
