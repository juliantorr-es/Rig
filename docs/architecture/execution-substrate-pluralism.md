# Execution Substrate Pluralism

Rig orchestrates execution substrates. It is not itself a monolithic inference engine. Different backends are selected by capability, locality, and governance constraints.

## Substrate Roles

| Runtime | Role |
|---|---|
| oMLX | Apple Silicon optimized execution |
| MLX | Native local inference substrate |
| llama.cpp | Portable local execution |
| OpenAI / Anthropic | Remote cognition and hosted reasoning |
| Future runtimes | Governed executors that fit Rig contracts |

## Operating Principle

Portable by contract, native by executor.

Rig should define a stable operational contract for telemetry, routing, and governance while allowing the executor to vary.

## Required Capabilities

- Structured telemetry ingestion.
- Backend-aware execution routing.
- Memory, batching, and load visibility.
- Runtime-specific constraints surfaced through governance.

## Boundary Rules

- Rig does not rewrite the backend execution engine during this pass.
- Execution backends remain plural.
- Backend specialization is acceptable when the contract remains stable.

