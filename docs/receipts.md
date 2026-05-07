# Receipts

Receipts are JSON evidence for execution, validation, and apply.

## Lane Receipts

The governed agent lane workflow uses receipts as evidence for lane creation, attachment, prompting, checkpoint planning, checkpoint commits, validation, and removal decisions.

Lane receipt kinds include:

- `lane_start`
- `lane_attach`
- `lane_prompt_generated`
- `lane_checkpoint_dry_run`
- `lane_checkpoint_commit`
- `lane_validation`
- `lane_remove_refused`
- `lane_remove`
- `lane_promote` future
- `lane_recommendation` future

Lane receipts should record repo root, worktree path, branch, before/after HEAD, detected dirty files, selected files, excluded files, command summary, result, timestamp, and warnings.

Reference schema:

- [`docs/schemas/rig.checkpoint.v1.json`](/Users/user/Developer/GitHub/Rig/docs/schemas/rig.checkpoint.v1.json)
- [`docs/schemas/runtime-receipt.schema.json`](/Users/user/Developer/GitHub/Rig/docs/schemas/runtime-receipt.schema.json)
