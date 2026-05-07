# Credential Storage

Rig stores provider secrets indirectly.

## macOS default

- Use Keychain.
- Store only credential references in manifests and config.

## Rules

- No raw secrets in logs.
- No raw secrets in receipts.
- No raw secrets in review bundles.
- No raw secrets in TUI snapshots.
