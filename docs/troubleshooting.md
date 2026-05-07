# Troubleshooting

If `rig` is not found, use editable install or verify the active interpreter.

If `rig init` is cancelled, rerun with `--yes` to skip the confirmation prompt.

If a command fails, inspect the logs first:

```bash
rig log list
rig log show <run_id>
```

If a governed run stops at a human gate, use the printed next command rather than forcing apply.
