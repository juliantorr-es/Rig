"""
I/O Utilities for rig_tools

Provides atomic file operations and high-performance serialization.
Uses orjson for JSON when available (much faster than stdlib json).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TextIO

# Try to use orjson for speed, fall back to stdlib
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import tomli
    import tomli_w
    HAS_TOML = True
except ImportError:
    try:
        import tomllib
        HAS_TOML = True
    except ImportError:
        HAS_TOML = False


# =============================================================================
# Text I/O
# =============================================================================

def read_text(path: Path, encoding: str = "utf-8") -> str:
    """Read text from a file."""
    return path.read_text(encoding=encoding)


def write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write text to a file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding)


# =============================================================================
# JSON I/O
# =============================================================================

def load_json(text: str) -> dict[str, Any]:
    """Load JSON from a string. Uses orjson if available."""
    if HAS_ORJSON:
        return orjson.loads(text)
    return json.loads(text)


def dump_json(data: dict[str, Any], *, indent: int | None = 2, sort_keys: bool = True) -> str:
    """Dump JSON to a string. Uses orjson if available."""
    if HAS_ORJSON:
        if indent is not None:
            return orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS).decode()
        return orjson.dumps(data, option=orjson.OPT_SORT_KEYS if sort_keys else 0).decode()
    return json.dumps(data, indent=indent, sort_keys=sort_keys)


def read_json(path: Path) -> dict[str, Any]:
    """Read and parse JSON from a file."""
    return load_json(read_text(path))


def write_json(path: Path, data: dict[str, Any], *, indent: int | None = 2, sort_keys: bool = True) -> None:
    """Write JSON to a file atomically. Creates parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to temp file first, then rename for atomicity
    temp_path = path.with_suffix(path.suffix + ".tmp")
    write_text(temp_path, dump_json(data, indent=indent, sort_keys=sort_keys))
    temp_path.replace(path)


# =============================================================================
# YAML I/O
# =============================================================================

def read_yaml(path: Path) -> dict[str, Any] | list[Any]:
    """Read and parse YAML from a file."""
    if not HAS_YAML:
        raise ImportError("PyYAML is required for YAML support. Install with: pip install pyyaml")
    return yaml.safe_load(read_text(path))


def write_yaml(path: Path, data: dict[str, Any] | list[Any]) -> None:
    """Write YAML to a file. Creates parent directories."""
    if not HAS_YAML:
        raise ImportError("PyYAML is required for YAML support. Install with: pip install pyyaml")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
    temp_path.rename(path)


# =============================================================================
# TOML I/O
# =============================================================================

def read_toml(path: Path) -> dict[str, Any]:
    """Read and parse TOML from a file."""
    if not HAS_TOML:
        raise ImportError("tomli or tomllib is required for TOML support. Install with: pip install tomli")
    content = read_text(path)
    if HAS_ORJSON:
        # orjson can parse TOML-like structures but we'll use tomli
        pass
    if "tomllib" in globals():
        import tomllib
        return tomllib.loads(content.encode())
    else:
        import tomli
        return tomli.loads(content)


def write_toml(path: Path, data: dict[str, Any]) -> None:
    """Write TOML to a file. Creates parent directories."""
    if not HAS_TOML:
        raise ImportError("tomli_w is required for TOML writing. Install with: pip install tomli-w")
    import tomli_w
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "wb") as f:
        tomli_w.dump(data, f)
    temp_path.rename(path)
