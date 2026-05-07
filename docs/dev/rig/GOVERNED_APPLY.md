# Governed Apply

`rig workspace apply <workspace_id>` is the only apply path.

Gates:

- Main worktree clean.
- Workspace exists.
- Workspace has isolated worktree.
- Successful execution receipt exists.
- Receipt schema validates.
- Receipt workspace id matches.
- Receipt hash matches current isolated worktree state.
- Workspace branch exists.
- Workspace branch has changes.
- Review bundle exists or is generated.
- Validators pass.
- User invoked apply explicitly.

Apply method:

- `git merge --no-ff <workspace_branch>`
- On merge failure, run `git merge --abort` and mark workspace blocked.

