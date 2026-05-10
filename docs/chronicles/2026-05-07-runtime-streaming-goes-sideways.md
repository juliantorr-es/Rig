Historical narrative. Not current workflow authority.

# 2026-05-07 — Runtime Streaming Goes Sideways

## Situation
Agents were generating increasingly complex data, and we needed a better way to observe their progress. We moved to formalize how execution was monitored through ADR 0004 runtime streaming consolidation.

## The Pain
Observing agent output through unstructured, messy logs was no longer sufficient. Logs were easily polluted, hard to parse, and didn't provide a deterministic view of agent progress. The compatibility fallout of trying to standardize logs was causing massive friction.

## False Starts
The "observe output" approach—trying to read raw agent stdout or basic logs—was a dead end. We tried standardizing simple text logs, but the lack of structured states made it impossible to build reliable observability or governance on top.

## Decision
We introduced runtime streaming consolidation (ADR 0004), shifting to structured runtime evidence. This involved stream chunks, projections, and a dedicated runtime supervisor. This approach provided a clear, trackable, and testable view of agent execution.

## Evidence
- ADR 0004
- `src/rig/domain/runtime_supervisor.py`
- `tests/test_runtime_stream.py`

## Lesson
Unstructured logs are worthless for agent governance; you need structured, deterministic streams and projections to actually know what an agent is doing.

## Channel Hook
Why Basic Logging Failed Us, and How We Fixed It with Structured Projections.
