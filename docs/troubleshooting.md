# Troubleshooting

If `rig` is not found, use editable install or verify the active interpreter.

If Python is below 3.14, upgrade the interpreter. Rig will refuse to start cleanly on older versions.

If `rig init` is cancelled, rerun with `--yes` to skip the confirmation prompt.

If a command fails, inspect the logs first:

```bash
rig log list
rig log show <run_id>
```

If a governed run stops at a human gate, use the printed next command rather than forcing apply.

If `rig doctor queue` reports malformed jobs, repair them deliberately with `rig doctor repair --queue`.

If legacy queue state is detected, migrate it explicitly with `rig doctor repair --migrate-legacy-queue`.

If provider connect fails, confirm the provider is supported and then retry with the correct key or OAuth flow.

If the TUI looks unstyled or the footer bindings are missing, verify you are running the Gridline Interface path from `rig tui` and that Textual is installed in the active Python 3.14 environment.

If you need to share a report, use `rig debug bundle --dry-run` first to confirm which secrets and weights are excluded by default.

Before a tag or release candidate, run `rig release check` and fix any blocking findings first.
