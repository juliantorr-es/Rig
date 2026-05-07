# ADR: CandidateDecoder Architecture

## Status
Proposed

## Context
Rig's current interaction with LLMs relies on parsing potentially noisy output. To maintain security and governance, Rig must transition from "cleaning" input to "decoding" candidates through a deterministic, auditable pipeline. This ensures we never trust an LLM, we only extract valid candidates from its output.

## Core Doctrine
1. **Normalize Syntax**: Transform model output into machine-readable shapes.
2. **Validate Semantics**: Evaluate normalized candidates against business logic and validators.
3. **Never Hallucinate Intent**: If a required field or intent is missing, reject the output.

## Architecture: The CandidateDecoder Pipeline

The pipeline processes `RawEmission` through a series of stages, each producing an audit log (Receipt):

### 1. EmissionSegmenter & EnvelopeExtractor
- Isolates trusted "envelopes" (e.g., `RIG_PATCH`, `RIG_INTENT`).
- **Rejected Content**: Everything outside the envelope is marked as `rejected_segments` in the audit log (preambles, explanations).

### 2. CandidateDecoder
- Transforms normalized syntax into typed Rig domain objects.
- Handles "sloppy-but-obvious" structure (e.g., string -> list) explicitly.

### 3. SchemaCanonicalizer
- Performs type coercion (e.g., "low risk" -> "low") based on strictly defined mappings.

### 4. CandidateValidator
- Performs "Rig-Native" checks:
    - `repo_boundary_valid`: Are file paths allowed?
    - `patch_applies`: Can the patch be applied to the target worktree?
    - `validator_check`: Do the resulting changes pass existing system tests?

## Evidence Logging (The Receipt)
Every decoding stage produces a `Receipt` in the `ReceiptStore`:

```json
{
  "raw_sha256": "...",
  "normalized_sha256": "...",
  "normalizers_applied": ["strip_markdown_fence", "extract_envelope"],
  "rejected_segments": ["assistant_preamble", "trailing_explanation"],
  "candidate_type": "patch_proposal",
  "schema_valid": true,
  "repo_boundary_valid": true,
  "patch_applies": true
}
```

## Implementation Strategy
- **Layering**: Build these as independent functions in `src/rig/domain/decoding/` that accept a raw string and return a `Result` type containing the candidate and the audit logs.
- **Fail-Fast**: If `EmissionSegmenter` finds no envelope, terminate immediately and provide the `disabled_reason` to the UI via the standard `UIProjection`.
- **Stateless**: The `CandidateDecoder` should be purely functional; all state persists in the `ReceiptStore`.
