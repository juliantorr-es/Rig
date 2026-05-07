# Context Pack: Rig Prompt Lab

## Concept
Rig Prompt Lab is a **Governance-First Provider Arena**. It evaluates prompts/models by running identical context packets through multiple providers, validating outputs against deterministic contracts, scoring them with evaluator suites, and recording results as persistent receipts.

## Workflow
1. **Context Packet Build**: Rig compiles task state (workspace + policy + validators) into a single deterministic packet.
2. **Provider Arena**: Packet is executed against N providers (DeepSeek, Gemini, Local Llama).
3. **Validator/Contract Pass**: Output is checked against deterministic contracts (JSON schema, forbidden patterns, patch-apply status).
4. **Scoring**: Metrics are calculated (Scorecard) for reasoning, doctrine fit, and risk.
5. **Receipt Logging**: Every run produces a signed `Receipt` linked to the input packet, raw response, score, and latency.

## Provider Scoreboard (UI Projection)
- **Rankings**: Based on overall score across benchmarks.
- **Stat Cards**: Visual breakdown (Reasoning, Schema, Doctrine, Risk, Speed, Cost).
- **Actions**: "Promote Provider" (set as Rig default), "Inspect Run" (opens receipt).

## Evaluation Framework
- **Deterministic Checks**: Schema validity, forbidden actions, patch-apply success, test-run exit codes.
- **Heuristic Checks**: Missing non-goals, vagueness, required citation.
- **LLM Judge**: Quality, clarity, architectural fit (run only after deterministic checks pass).

## Threat Model (Red Teaming)
- Use `promptfoo` patterns to detect:
    - Authority leaks (models trying to bypass Governance Engine).
    - Destructive intent (model proposing file system mutations outside Worktree).
    - Prompt injection (jailbreak strategies).
    - Data exfiltration (model leaking context pack contents).

## Agent Implementation Checklist
- [ ] Record prompt/context-pack hashes in every receipt.
- [ ] Use `promptfoo` YAML config to define red teaming plugins.
- [ ] Implement `ProviderScoreboard` projection widget.
- [ ] Ensure all prompt runs are stored as `receipts` in Rig's native format.
- [ ] Separate model judgment from deterministic evaluation.

## Architecture Rule
**Providers are not trusted.** Every model output is treated as untrusted data until it passes the deterministic contracts defined by the Governance Engine.
