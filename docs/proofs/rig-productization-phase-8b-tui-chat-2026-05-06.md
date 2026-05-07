# Rig Productization Phase 8B TUI Chat Proof

## Summary

- CLI gained `rig status`.
- TUI command construction no longer depends on `scripts/rig.py`.
- TUI chat/slash helpers were added as governed intent boundaries.
- TUI snapshot loading remains read-only.

## Validation

- `python -m pytest -q tests/test_phase8b_tui_chat.py`

## Remaining risks

- The full Textual chat UI still needs integration polish.
- Compatibility aliases and older implementation-shaped commands remain in the tree.
- No scheduler/daemon/autonomous-loop work was started.
