# Rig Productization Phase 8B Gridline Interface Proof

Files created:
- `src/rig_tools/tui_theme.py`
- `src/rig_tools/tui_layout.py`
- `src/rig_tools/tui_grid.py`
- `docs/dev/rig/GRIDLINE_INTERFACE.md`
- `tests/test_phase8b_gridline_interface.py`

Files modified:
- `src/rig/commands_tui.py`
- `src/rig_tools/tui_app.py`
- `docs/cli.md`
- `docs/quickstart.md`
- `docs/troubleshooting.md`

Behavior:
- Gridline Interface tokens and CSS live in `tui_theme.py`.
- Semantic layout primitives live in `tui_layout.py`.
- Dashboard skeleton lives in `tui_grid.py`.
- `rig tui --window` and `rig tui --dry-run` remain canonical.
- Product TUI/window paths avoid `scripts/rig.py`.
- Native Textual `Footer` remains in use.

Validation:
- `find src scripts tests -name "*.py" -print0 | xargs -0 python -m py_compile`
- `.build/venv/bin/python -m pytest -q`

Remaining risk:
- The legacy TUI app is still large and has not been fully replaced by the new grid shell yet.
