import os
from pathlib import Path

def repo_root() -> Path:
    """Returns the absolute path to the Rig repository root."""
    # Assumes rig/paths.py is at src/rig/paths.py
    return Path(__file__).resolve().parent.parent.parent

def docs_dir() -> Path:
    return repo_root() / "docs"

def schemas_dir() -> Path:
    return docs_dir() / "schemas"

def tests_dir() -> Path:
    return repo_root() / "tests"

def resolve_repo_path(*parts) -> Path:
    return repo_root().joinpath(*parts)
