# ADR: Rig-Native Benchmarking Architecture

## Status
Proposed

## Context
Rig requires high-confidence model providers for autonomous code generation and governance tasks. Standard benchmarks (e.g., HumanEval, CodeNeedle) focus on general capabilities or narrow retrieval, but fail to measure "Governance Fit"—a model's ability to remain silent, respect patch envelopes, and operate within the constraints of our `IntentDispatcher`.

We will implement a Rig-native benchmarking suite inspired by [CodeNeedle](https://github.com/alexziskind1/codeneedle), adapting its positional recall and extraction strategies into a governed testing harness.

## Architecture
Rig’s benchmarking will be composed of three distinct testing layers, integrated directly into the `rig_tools` and `src/rig/domain` logic:

### 1. Recall (Positional Fidelity)
*   **Source**: Inspired by CodeNeedle.
*   **Goal**: Ensure a model can read deeply into the repository and reproduce source code verbatim, avoiding context loss.
*   **Metric**: Line-matching accuracy at specific depths within the repo.

### 2. Discipline (Operational Safety)
*   **Source**: Rig-Native.
*   **Goal**: Measure a model's strict adherence to output envelopes (e.g., "The Patch Envelope") and its tendency to hallucinate extra text or commentary.
*   **Metric**: False-positive/negative rate on constrained output formats, stop-token reliability, and hallucination rate.

### 3. Governance Fit (Authority Calibration)
*   **Source**: Rig-Native (Governance Engine).
*   **Goal**: Determine the model's "Authority Lane."
*   **Metric**: Ability to reject forbidden intents, respect validator results, and refuse unauthorized operations.

## Integration Strategy
1. **Extraction**: Use Python AST-based extraction (modeled after CodeNeedle) to aggregate project source code.
2. **Scoring**: Implement a Rig-specific scorer that tracks:
    - **Recall/Fidelity**: Line-matching precision (LCS).
    - **Noise/Hallucination**: Off-envelope token emission.
3. **Evidence**: Every benchmarking run persists a signed `Receipt` including the prompt, model params, latency, and evaluator results.

## Lane Classification
Models will be classified into lanes based on their scorecard:
- **`Proposal`**: Reviewer role, generates ideas, cannot mutate code.
- **`Reviewer`**: Summarizes code, inspects receipts.
- **`Patch`**: Trusted with deterministic patch application via Rig's `ExecutionLease`.

## Decision Log
- We will *not* add CodeNeedle as a direct dependency to maintain minimal package surface. We will vendor the core extraction/scoring logic as Rig-native utilities.
