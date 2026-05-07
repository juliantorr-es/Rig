# Context Pack: CandidateDecoder Implementation Guide

## Implementation Strategy
To avoid a monolithic "everything" parser, Rig will implement a pipeline using lightweight Python tools.

### 1. Structure Enforcement (`outlines`)
When Rig manages the generation:
- Use `outlines` to constrain LLM token emission to valid JSON Schema or Pydantic models.
- This prevents the "malformed JSON" problem at the source.

### 2. Post-Generation Pipeline (The CandidateDecoder)
When Rig receives raw output from a model it doesn't control (or as a safety fallback):
- **Stage 1: Envelope Extraction**
  - Use regex-based `EnvelopeExtractor` to isolate `RIG_...` blocks.
  - Audit log: capture `rejected_segments` (all text outside the envelope).
- **Stage 2: Schema Decoding**
  - Use `Pydantic` as the `CandidateDecoder`. 
  - Define `RigCandidate` models (e.g., `PatchProposal`, `GovernanceIntent`).
  - Validation: `RigCandidate.model_validate_json(decoded_string)`.
- **Stage 3: Logic Validation**
  - Path canonicalization: verify file paths are within `RepoRoot` using `pathlib.Path.resolve()`.
  - Deterministic check: Use `git apply --check` for patch candidates.

### 3. Error Handling & Recovery
- **No-op Recovery**: If a candidate fails validation, do *not* attempt to "fix" it by guessing.
- **Feedback Loop**: Reject the candidate, attach the `Pydantic` validation error to the `Receipt`, and signal a "Repair" intent to the model provider.
- **Authority**: The UI projection reflects the `disabled_reason` from the pipeline, ensuring users understand why an intent is unavailable.

### 4. Implementation Checklist
- [ ] Vendor or implement a lightweight `FenceStripper` (no extra dependencies).
- [ ] Define `pydantic` models for core Rig intents (`PatchProposal`, `GovernanceIntent`).
- [ ] Implement `CandidateDecoder` class that chains Segmenter -> Stripper -> Pydantic Decoder -> Validator.
- [ ] Ensure every pipeline step generates a `Receipt` in the `ReceiptStore`.
- [ ] Hook `CandidateDecoder` into the existing `IntentDispatcher`.
