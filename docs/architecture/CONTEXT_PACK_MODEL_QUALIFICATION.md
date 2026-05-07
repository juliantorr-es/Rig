# Context Pack: Model Qualification & Benchmark

## Goal
Establish a codebase-local "Rig Model Bench" to qualify LLM providers (Gemini, DeepSeek, Local Llama/MLX) not by "vibes," but by deterministic behavior against Rig's governance and implementation standards.

## Behavioral Benchmarking Rubric
Models are scored on these dimensions:
- **Patch Discipline**: Does the model emit only the allowed patch envelope? Does it strip markdown/conversational filler?
- **Governance Fit**: Does it reject forbidden actions (e.g., `intent.apply_patch` without auth) rather than hallucinating success?
- **Evidence Integrity**: Does it correctly cite receipt IDs when summarizing validator results?
- **Stopping Rules**: Does it stop immediately after the required output, or does it ramble/hallucinate?
- **Depth Handling**: Can it parse a function at deep nesting levels without losing context?

## Implementation Strategy
1. **Runner Module (`rig.domain.bench`)**:
    - Executes identical context packets against providers (OpenAI-compatible endpoints).
    - Records receipts including latency, cost, and raw output.
2. **Deterministic Evaluator**:
    - JSON schema validation.
    - Patch envelope format check (regex).
    - Forbidden pattern detection (e.g., "I will run this command").
3. **Provider Scorecard**:
    - Persist stats to `ReceiptStore`.
    - UI widget `ProviderScoreboard` renders the "Stats Card" based on historical performance.

## Tooling Integration
- **`llama-cpp-python[server]`**: Use as the foundation for local `OpenAI`-compatible inference.
- **`MLX` / `mlx-lm`**: Prefer on Apple Silicon for faster inference/quantization support.
- **`pytest`**: Use for orchestrating benchmark runs as standard test cases.

## Workflow
1. `rig qualify model --model qwen3-coder-35b`
2. Rig runs standard suite: Needle recall, Patch proposal, Validator repair.
3. System logs `Receipt` for each run.
4. UI displays Scorecard: "Recommend: Guarded Patch Lane".

## Architectural Rule
**Models Propose; Rig Governs.**
The benchmark does not "trust" a high-scoring model. A model scoring 99% is still parsed through Rig's deterministic `IntentDispatcher`. Qualification only determines *which lane* (Review/Proposal/Patch) a model is trusted to operate in.
