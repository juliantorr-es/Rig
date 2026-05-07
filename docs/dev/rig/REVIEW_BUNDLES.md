# Review Bundles

`rig workspace review <workspace_id>` writes `.build/rig/reviews/<workspace_id>/`.

Files:

- `review.json`
- `summary.md`
- `diff.patch`
- `validation.json`

Purpose:

- Capture current workspace state.
- Freeze changed-file and diff evidence.
- Bind review output to execution receipt and validation results.

