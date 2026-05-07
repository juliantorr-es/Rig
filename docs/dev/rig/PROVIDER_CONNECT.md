# Provider Connect

Rig treats providers as proposal sources.

## Connect modes

- API key setup for providers like OpenAI, Anthropic, Google, DeepSeek, Z.ai, and OpenAI-compatible endpoints.
- OAuth/PKCE only where the provider actually supports it, such as OpenRouter.

## Storage

- API keys are stored in macOS Keychain when available.
- Raw secrets do not appear in logs, receipts, or review bundles.

## Commands

- `rig provider list`
- `rig provider inspect <provider_id>`
- `rig provider connect <provider_id>`
- `rig provider disconnect <provider_id>`
- `rig provider test <provider_id>`
- `rig provider models <provider_id>`
