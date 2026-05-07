# Batteries-Included Install Recipes

Rig ships dependency recipes, not dependency cargo.

## pip

```bash
python3.14 -m pip install git+https://github.com/juliantorr-es/Rig
```

## pipx

```bash
pipx install git+https://github.com/juliantorr-es/Rig
```

## uv

```bash
uv tool install git+https://github.com/juliantorr-es/Rig
```

## Homebrew draft

See `packaging/homebrew/rig.rb`.

## npm shim

See `packaging/npm/README.md`.

## Notes

- Rig does not bundle model weights.
- Rig does not vendor third-party source trees.
- MLX is preferred on Apple Silicon when available.
