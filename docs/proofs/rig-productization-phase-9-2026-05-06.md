# Rig Productization Phase 9 Release Candidate Infrastructure Proof

Files created:
- `src/rig/commands_release.py`
- `scripts/release/smoke_install.py`
- `scripts/release/check_public_commands.py`
- `scripts/release/check_readme_commands.py`
- `scripts/release/check_release.py`
- `docs/dev/rig/PUBLIC_COMMAND_CONTRACT.md`
- `docs/dev/rig/public_command_contract.json`
- `docs/dev/rig/SCAFFOLDING_INVENTORY.md`
- `docs/dev/rig/DEBUG_BUNDLE_CONTRACT.md`
- `docs/release/RELEASE_CHECKLIST.md`
- `docs/release/PUBLIC_ALPHA_CRITERIA.md`
- `docs/release/KNOWN_LIMITATIONS.md`
- `CHANGELOG.md`
- `SECURITY.md`
- `SUPPORT.md`
- `CONTRIBUTING.md`
- `examples/tiny-python-project/README.md`
- `.github/workflows/test.yml`
- `.github/workflows/release-check.yml`
- `.github/workflows/docs.yml`
- `.github/workflows/publish.yml.disabled`

Files modified:
- `src/rig/cli/main.py`
- `docs/cli.md`
- `docs/quickstart.md`
- `docs/troubleshooting.md`

Runtime behavior changed:
- `rig release check` now exists as the public release gate.
- `rig release check --json` emits machine-readable output.
- Installer smoke and public-command check scripts exist.
- Release documentation and public command contract are now explicit.

Validation:
- `find src scripts tests -name "*.py" -print0 | xargs -0 python -m py_compile`
- `.build/venv/bin/python -m pytest -q tests/test_phase9_release_scaffolding.py`
- `.build/venv/bin/python -m pytest -q`

Remaining risks:
- The release gate still runs within the Python 3.13 container here, so the 3.14-path validation must be exercised in a 3.14 environment.
- Some command groups remain preview or internal by design while the product matures.
