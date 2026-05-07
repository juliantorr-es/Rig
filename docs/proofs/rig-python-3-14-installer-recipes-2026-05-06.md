# Rig Python 3.14 Installer Recipes Proof

## Policy

- `pyproject.toml` requires Python `>=3.14`
- Public entrypoints fail cleanly below 3.14 with interpreter details

## Dependencies

- Default install now includes runtime/TUI/window dependencies where feasible
- No vendored wheelhouse or source tree was added
- No model weights were bundled

## Recipes

- pip
- pipx
- uv
- Homebrew draft formula
- npm shim

## Validation

- `python -m rig --help`
- `python -m rig tui --help`
- `python -m rig window status`
- `python -m rig window open --dry-run`
- `python -m rig doctor`
- `python -m rig doctor deps`
- `python -m rig system inspect`
- `python -m rig runtime list`
- `python -m rig runtime inspect mlx`
- `python -m rig runtime inspect llama-cpp`
- `python -m rig benchmark run --dry-run`
- `python -m rig model recommend --dry-run`

## Remaining risks

- The current environment may not have Python 3.14 available for full end-to-end execution.
- `mlx` and `pywebview` remain platform-dependent.
- Phase 8 scheduler/daemon/autonomy work was not started.
