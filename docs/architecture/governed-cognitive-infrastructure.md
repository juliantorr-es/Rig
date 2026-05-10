# Governed Cognitive Infrastructure

## Summary

Rig is evolving toward a governed cognitive infrastructure model rather than a traditional AI assistant architecture. This document defines the core doctrine of how cognition, context, and execution are structurally governed within the system.

Core doctrine:

- Models propose
- Rig governs
- Execution is advisory
- Authority is explicit
- Replay is canonical
- Integrity is continuously validated
- Context is routed intentionally
- Execution is routed intentionally
- Inference observability drives runtime supervision

The system is designed around explicit governance boundaries and mechanical feedback loops rather than unconstrained, opaque agent autonomy.

---

## Architectural Layers

### 1. Governed Inference Observability

Inference is not treated as a black box that merely returns text. Rig taps into the statistical exhaust of the inference engine to establish mechanical governance gates. This is a foundational shift from trusting text to supervising statistical mechanics.

**Observability vs. Neural Introspection:**
- **Neural Introspection (Anti-Pattern):** Rig does not attempt to dump raw attention matrices, residual streams, or intermediate tensor activations. These are heavy, research-oriented, and operationally useless for a control plane.
- **Inference Observability (Rig Pattern):** Rig extracts targeted, lightweight statistical metrics—such as token logits, probability distributions, entropy, and sparse expert routing—to feed into governance gates.

#### The Logit/Probability Surface
By ingesting logit distributions and token probabilities, Rig mechanically measures inference confidence and detects collapse.
- **Uncertainty Gates:** If token entropy spikes during a critical decision (e.g., formulating a bash command or deciding to mutate a file), the runtime halts execution. It mechanically demands a different routing path, broadened context, or human intervention.
- **Proposal Confidence Scoring:** Proposals in Rig are not merely text payloads. They are backed by statistical confidence scores derived from the underlying logits, establishing an empirical baseline for the proposal's reliability.

#### Sparse Expert Routing (MoE) Tracing
For architectures utilizing Mixture of Experts (MoE), tracking which experts activate per token provides a mechanism for cognitive profiling.
- **Capability Tracing:** If the runtime detects that reasoning experts are dormant while conversational experts are saturated during a coding task, the execution router flags the output as low-value or potentially hallucinated.
- **Benchmarking:** Expert activation profiles are recorded in telemetry to baseline normal behavior for specific capability invocations.

#### Adaptive Execution Feedback Loops
Inference observability enables a self-correcting cognitive runtime. 
1. **Monitor:** The runtime continuously ingests entropy, repetition, and divergence metrics.
2. **Detect:** The runtime mechanically detects "proposal collapse" (e.g., repeating loops, plummeting entropy, flatlined divergence).
3. **Act:** The execution router shifts policy autonomously. It may widen diversity (increase temperature), dynamically restrict the capability set, or swap to a heavier model.
4. **Record:** The exact state of the collapse, the metrics that triggered the policy shift, and the new routing policy are written immutably to the Replay Trace as authoritative evidence.

---

### 2. Governed Context Routing

Governed Context Routing determines:

- who sees what
- when context is admissible
- which receipts are visible
- which replay evidence is admissible
- which capability metadata is exposed
- which integrity findings are relevant
- which projections are visible

This avoids:
- giant undifferentiated prompt contexts
- recursive context sludge
- uncontrolled memory growth
- authority leakage
- replay divergence

#### Context Types

- **Authority Context:** The explicit permissions and constraints for the current execution.
- **Workspace Context:** The bounded state of the current working directory.
- **Proposal Context:** The history of what the agent has previously suggested.
- **Replay Context:** Reconstructed deterministic history for resumption.
- **Integrity Context:** Results from recent validation gates.
- **Projection Context:** UI-derived state optimized for minimal representation.
- **Telemetry Context:** Execution metadata and observability baselines.
- **Tool Invocation Context:** Strict schemas governing how external capabilities are called.

#### Doctrine
The runtime should never automatically receive unrestricted repository access, unbound replay history, or full raw telemetry. Context is mechanically compressed, explicitly bounded, and intentionally routed based on the current execution phase.

---

### 3. Governed Execution Routing

Governed Execution Routing determines:

- which runtime executes
- which capability set is admissible
- which sandbox is allowed
- which timeout policy applies
- which review gates apply
- which execution receipts are required

Execution is treated as a policy problem, not merely a tool-calling problem.

#### Example Routing Flows

- **Documentation fetch:** → lightweight network-capable runtime.
- **Patch proposal:** → isolated patch runtime.
- **Dangerous shell proposal:** → elevated runtime with mandatory human review gates.
- **Large architectural reasoning:** → high-context planner runtime.
- **Formatting pass:** → small deterministic local runtime.

Execution routing dynamically adapts based on the Inference Observability layer. A drop in confidence shifts execution routing from an autonomous sandbox to an explicit review gate.

---

### 4. Runtime Governance

Runtimes are strictly advisory execution providers.

Runtimes:
- do not mutate authority directly
- do not apply patches directly
- do not bypass review gates
- do not bypass capability registries

All runtime actions must produce:
- receipts
- replay evidence
- integrity-compatible metadata
- projection-compatible summaries
- inference observability metrics (entropy, confidence bounds)

---

### 5. Replay & Integrity

Replay is not a debugging afterthought; it is the canonical source of truth for execution lineage.

Replay provides:
- deterministic reconstruction
- execution lineage
- proposal history
- capability history
- governance evidence
- integrity validation
- inference-policy adaptation records

Integrity continuously validates:
- impossible authority states
- capability mismatches
- replay divergence
- stale references
- advisory escalation leaks
- receipt chain validity

---

### 6. Projection Doctrine

The frontend consumes projections, not raw execution state.

UI streaming must remain:
- deterministic
- replay-safe
- projection-backed
- authority-safe

Widgets remain dumb renderers. They are strictly projection-only, meaning they contain no hidden fetching logic and make no authority inferences.

---

## Long-Term Direction

Rig is converging toward a **Governed AI Execution Kernel** defined by:
- inference observability loops
- governed context routing
- governed execution routing
- replayable execution
- policy-aware capability control
- deterministic receipts
- integrity validation
- inspectable telemetry
- bounded authority

---

## Comparative Industry Direction

Related industry architectures include:
- governed memory systems (e.g., Decision Trace Graphs)
- policy-aware orchestration (e.g., AI Control Towers)
- replayable execution (e.g., Temporal State Compression)
- cognitive kernels (e.g., Mechanical Stability Gates)
- context governance (e.g., Enterprise Context Layers with ACLs)
- capability-gated runtimes (e.g., Scoped Delegation)

Rig differentiates itself by:
- emphasizing deterministic replay and continuous integrity validation
- rejecting neural introspection in favor of actionable inference observability
- treating UI projections as strictly governed, authoritative surfaces
- enforcing proposal-only execution where models can never act unilaterally
- integrating governance mechanics directly into the runtime architecture, rather than wrapping it as a secondary compliance layer.