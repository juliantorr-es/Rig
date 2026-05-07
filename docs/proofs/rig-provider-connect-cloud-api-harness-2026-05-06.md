# Rig Provider Connect & Cloud API Harness Proof

## Summary

- Provider registry added for cloud API, OpenAI-compatible, OAuth-capable, local, and custom providers.
- Governed context packets added under `.build/rig/context/`.
- Proposal generation now includes context packet id/hash references.
- Provider secrets are stored indirectly through Keychain references when available.

## Validation

- `python -m pytest -q tests/test_phase8b_provider_connect.py`

## Remaining risks

- Live OAuth and API-key connect flows are still intentionally conservative in this pass.
- Provider-specific request adapters are thin and meant to be hardened per provider docs.
- No scheduler/daemon/autonomous-loop work was started.
