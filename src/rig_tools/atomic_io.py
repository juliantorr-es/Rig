"""
Atomic I/O operations for rig_tools.

DEPRECATED: This module is deprecated. Use rig_tools.core.io and rig_tools.core.filesystem instead.

The functions in this module are now thin wrappers around the core utilities.
They are kept for backward compatibility but new code should use:
    - rig_tools.core.io.write_json() for atomic JSON writing
    - rig_tools.core.filesystem.atomic_write() for atomic file writing
    - rig_tools.core.filesystem FileLock for locking

This module will be removed in a future version.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

# Import from core utilities
from rig_tools.core.io import write_json
from rig_tools.core.filesystem import atomic_write

# Emit deprecation warning when this module is imported
warnings.warn(
    "rig_tools.atomic_io is deprecated. Use rig_tools.core.io and rig_tools.core.filesystem instead.",
    DeprecationWarning,
    stacklevel=2,
)


def write_json_atomic(path: Path, data: Any) -> None:
    """
    Write JSON to a file atomically.
    
    DEPRECATED: Use rig_tools.core.io.write_json() instead.
    
    Arguments:
        path: Path to write to
        data: Data to serialize as JSON
    """
    warnings.warn(
        "write_json_atomic is deprecated. Use rig_tools.core.io.write_json() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    write_json(path, data)


def lock_file(path: Path, *, timeout: float = 10.0, poll_interval: float = 0.1) -> Any:
    """
    DEPRECATED: Use rig_tools.core.filesystem.locked() or FileLock instead.
    
    This function is kept for backward compatibility but should not be used in new code.
    """
    warnings.warn(
        "lock_file is deprecated. Use rig_tools.core.filesystem.locked() or FileLock instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from rig_tools.core.filesystem import locked
    return locked(path, timeout=timeout)
