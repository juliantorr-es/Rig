# Context Pack: Python Dev-Check Pipeline

## Goal
Establish a fast, reliable CI-style local dev check that catches common Python errors (missing imports, type mismatches, formatting drift) before runtime.

## 1. Dependencies (`pyproject.toml`)
Add these to `[project.optional-dependencies] dev = [...]`.

```toml
[project.optional-dependencies]
dev = [
  "ruff>=0.4.0",
  "basedpyright>=1.15.0",
  "pytest>=8.0.0",
  "pytest-asyncio>=0.23.0"
]
```

## 2. Tool Configs (`pyproject.toml`)

### Ruff
```toml
[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I"] # F401 (unused imports), I (isort)
fixable = ["ALL"]
```

### Pyright
```toml
[tool.pyright]
include = ["src"]
reportMissingImports = "error"
reportMissingTypeStubs = false
pythonVersion = "3.10"
```

## 3. The `check.sh` Pipeline
```bash
#!/bin/bash
set -e
echo "Running static analysis..."
ruff check src/ tests/
ruff format --check src/ tests/
basedpyright src/
echo "Running tests..."
pytest tests/
```

## 4. Import Regression Test (`tests/test_imports.py`)
```python
import importlib

def test_commands_ui_exists():
    """Verify core UI commands are importable."""
    try:
        importlib.import_module("rig.commands_ui")
    except ImportError as e:
        pytest.fail(f"rig.commands_ui failed to import: {e}")
```

## 5. Migration Strategy
1. **Ruff first**: Add to `pyproject.toml`, run `ruff check` and `ruff format --fix` (non-destructive).
2. **Pyright last**: Run `basedpyright` and suppress top-level errors using `pyrightconfig.json` exclusions until you are ready to fix them. Do NOT fix the whole repo at once.
