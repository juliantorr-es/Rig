# Debug Bundle Contract

Debug bundles are redacted support archives for public issue reporting.

## Included by default

- Rig version and commit when available
- Python executable and version
- platform metadata
- doctor output
- doctor queue output
- doctor deps output
- redacted config inspection
- job manifests
- queue health
- bounded recent logs
- TUI snapshot
- provider manifests with credential refs redacted

## Excluded by default

- raw API keys
- model weights
- venvs
- full repository source
- unbounded logs
- arbitrary home directory files
- raw provider responses unless explicitly included and redacted

## Redaction rules

- Secret-like strings are redacted.
- Bundle manifest must not contain raw secrets.
- Dry-run lists the bundle contents without writing the archive.

## Manifest

- Schema: `rig.debug_bundle_manifest.v1`
- Output: `.build/rig/debug/rig-debug-bundle-<timestamp>.zip`

