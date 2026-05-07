# Local Runtime Benchmarks

Rig can inspect local runtime capabilities without downloading model weights.

## What it checks

- Apple Silicon / CPU / RAM
- `mlx`
- `llama_cpp`
- `psutil`
- Textual and window dependencies

## Outputs

- `.build/rig/benchmarks/latest.json`
- `.build/rig/benchmarks/latest.md`

## Safety rules

- No model weight downloads
- No repo mutation beyond the benchmark artifact
- No runtime install actions
