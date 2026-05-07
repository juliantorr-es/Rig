# TUI Queue Projection

The TUI reads the job store as a tolerant, read-only projection.

## Behavior

- Uses snapshot reads from `.build/rig/jobs/`.
- Ignores `.tmp`, `.lock`, and `.bad`.
- Never quarantines or deletes files during render.
- Surfaces malformed-file warnings instead of mutating state.
- Polls lightly and can refresh faster while jobs are active.
