# Governed Agent Lane Management Proof

Status: drafted and documented

What changed:

- Added the formal spec for governed agent lane management.
- Updated `AGENTS.md` commit policy to match the real non-main lane workflow.
- Updated receipts guidance for lane receipts.
- Linked the new spec from the docs index.

Validation:

- `python3.14 -m compileall -q scripts tests`
- `python3.14 -m pytest tests/test_rig_agent_worktree.py -v`

Runtime behavior changed: no

CLI behavior changed: no

Notes:

- The helper/runtime behavior was not changed in this docs task.
- The Gemini cockpit lane remains separate and untouched by this documentation update.
