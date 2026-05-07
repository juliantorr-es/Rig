"""
File locking utilities for rig_tools.

DEPRECATED: This module is deprecated. Use rig_tools.core.filesystem instead.

The functions in this module are now thin wrappers around the core utilities.
They are kept for backward compatibility but new code should use:
    - rig_tools.core.filesystem.locked() for context manager based locking
    - rig_tools.core.filesystem.FileLock for explicit lock objects

This module will be removed in a future version.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator

# Import from core utilities
from rig_tools.core.filesystem import locked as _locked

# Emit deprecation warning when this module is imported
warnings.warn(
    "rig_tools.file_lock is deprecated. Use rig_tools.core.filesystem instead.",
    DeprecationWarning,
    stacklevel=2,
)


@contextmanager
def job_store_lock(repo_root: Path, *, timeout: float = 10.0) -> Iterator[None]:
    """
    Context manager for locking the job store.
    
    DEPRECATED: Use rig_tools.core.filesystem.locked() instead.
    
    Arguments:
        repo_root: Repository root path
        timeout: Lock timeout in seconds
    """
    warnings.warn(
        "job_store_lock is deprecated. Use rig_tools.core.filesystem.locked() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    lock_path = repo_root / ".build" / "rig" / "jobs" / ".lock"
    with _locked(lock_path, timeout=timeout):
        yield
