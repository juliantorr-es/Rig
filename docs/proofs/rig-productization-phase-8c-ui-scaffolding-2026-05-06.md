# Rig Productization Phase 8C UI Scaffolding Proof

Files created:
- `src/rig_tools/tui_layout.py`
- `src/rig_tools/tui_grid.py`
- `src/rig_tools/tui_command_registry.py`
- `src/rig_tools/debug_bundle.py`
- `src/rig/commands_debug.py`
- `docs/dev/rig/GRIDLINE_INTERFACE.md`
- `docs/schemas/rig.debug_bundle_manifest.v1.schema.json`
- `docs/proofs/rig-productization-phase-8c-ui-scaffolding-2026-05-06.md`

Files modified:
- `src/rig_tools/tui_theme.py`
- `src/rig_tools/tui_chat.py`
- `src/rig_tools/tui_chat_rendering.py`
- `src/rig/commands_tui.py`
- `src/rig/cli/main.py`
- `src/rig_tools/window_launcher.py`
- `README.md`
- `docs/cli.md`
- `docs/quickstart.md`
- `docs/troubleshooting.md`

Runtime behavior changed:
- `rig tui --gridline` now selects the Gridline shell.
- `rig tui --chat` enables the chat/slash console on the Gridline shell.
- `rig tui --dry-run` prints the canonical launch plan without writing state.
- `rig debug bundle` exports a redacted support archive.
- `rig debug bundle --dry-run` reports bundle contents without writing a zip.
- Window dry-runs no longer write session files.

Validation:
- `find src scripts tests -name "*.py" -print0 | xargs -0 python -m py_compile`
- `.build/venv/bin/python -m pytest -q`

Remaining risk:
- The legacy TUI screen still exists alongside Gridline while the shell transition completes.
