# Context Pack: Packaged Application Support

## Goal
Enable Rig to launch as a standalone application (`Rig.app`) where the current working directory is not the target repository, and enforce clean separation between app resources and governed user workspaces.

## Conceptual Path Model
- **`AppRoot` (Resource Root)**: Where the code and static assets live.
    - Source mode: `Path(__file__).parent`.
    - Packaged mode: `sys._MEIPASS` (for PyInstaller/briefcase).
- **`RepoRoot` (Workspace Root)**: The user-selected project folder.
    - CLI mode default: `Path.cwd()`.
    - Packaged app launch: Initially `None` (user must open or select).

## Architectural Rules
1. **No Implicit CWD**: All path lookups (receipts, logs, state files) must be relative to `RepoRoot`, never `cwd`.
2. **Resource Locality**: Static UI assets (HTML/CSS/JS) must always be resolved via `AppRoot` helpers.
3. **Lazy Initialization**: If `RepoRoot` is `None` (app launch), the backend must enter an `uninitialized` state and push a `Projection` with an `intent.open_repository`.
4. **Frozen Mode Awareness**: The backend must detect `sys.frozen` to resolve internal assets without relying on standard Python import paths.

## Implementation Plan
1. **`rig_tools.core.paths`**: Centralize path resolution logic.
    - `get_app_root()`: Returns absolute path to app binaries/resources.
    - `get_repo_root(override: Path | None)`: Logic for selecting/defaulting workspace.
2. **`UIServer` Initialization**:
    - Allow launching with `repo_root=None`.
    - `ProjectionBuilder` must handle `repo_root is None` by returning a `workspace_unselected` projection.
3. **Intent-Driven Repo Selection**:
    - Define `intent.open_repository` to trigger a native folder picker or path prompt.
    - UI state should reflect "No workspace selected" until the user acts.
4. **Packaging Hygiene**:
    - Rig must never write to `AppRoot`. All persistent state (build artifacts, receipts) must be scoped to `RepoRoot`.

## Testing Plan
- [ ] Mock `sys.frozen` to verify resource resolution.
- [ ] Verify `ProjectionBuilder` renders an "Open Repository" state when `repo_root` is `None`.
- [ ] Ensure `rig ui --repo <path>` correctly sets the repository root regardless of current shell directory.
- [ ] Verify `rig ui` defaults correctly to `cwd` only when no flag is provided in CLI mode.

## Checklist for Future Agents
- [ ] Is `RepoRoot` used for all file I/O?
- [ ] Are assets loaded via `AppRoot`?
- [ ] Is `RepoRoot=None` handled safely in the projection builder?
- [ ] Is the app mode (CLI vs Packaged) explicitly detected?
