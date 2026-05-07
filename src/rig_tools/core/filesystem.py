"""
Filesystem Utilities for rig_tools

Provides atomic file operations, directory management, and file locking.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import stat
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Iterator, TextIO

# Type alias for path-like objects
PathLike = str | Path | bytes | os.PathLike


# =============================================================================
# Directory Operations
# =============================================================================

def ensure_dir(path: PathLike) -> Path:
    """
    Ensure a directory exists, creating parent directories as needed.
    
    Args:
        path: Path to the directory
        
    Returns:
        Path to the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write(path: PathLike, content: str | bytes, *, encoding: str = "utf-8") -> None:
    """
    Write content to a file atomically.
    
    Writes to a temporary file first, then renames to the target path.
    This ensures that readers never see a partially written file.
    
    Args:
        path: Path to write to
        content: Content to write (string or bytes)
        encoding: Encoding for string content
    """
    path = Path(path)
    ensure_dir(path.parent)
    
    temp_path = path.with_suffix(path.suffix + ".tmp" + uuid.uuid4().hex[:8])
    
    try:
        if isinstance(content, str):
            temp_path.write_text(content, encoding=encoding)
        else:
            temp_path.write_bytes(content)
        # Ensure the temp file is synced to disk
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic rename
        temp_path.replace(path)
    finally:
        # Clean up temp file if it still exists
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def atomic_move(src: PathLike, dst: PathLike) -> None:
    """
    Move a file atomically.
    
    Args:
        src: Source path
        dst: Destination path
    """
    src = Path(src)
    dst = Path(dst)
    ensure_dir(dst.parent)
    src.replace(dst)


@contextmanager
def temp_dir(prefix: str = "rig_", suffix: str | None = None, dir: PathLike | None = None) -> Iterator[Path]:
    """
    Context manager for a temporary directory.
    
    Args:
        prefix: Prefix for the temp directory name
        suffix: Suffix for the temp directory name
        dir: Parent directory (default: system temp dir)
        
    Yields:
        Path to the temporary directory
    """
    with tempfile.TemporaryDirectory(prefix=prefix, suffix=suffix or "", dir=dir) as td:
        yield Path(td)


# =============================================================================
# File Operations
# =============================================================================

def list_files(path: PathLike, pattern: str | None = None, recursive: bool = False) -> list[Path]:
    """
    List files in a directory.
    
    Args:
        path: Path to the directory
        pattern: Glob pattern to filter files
        recursive: Recurse into subdirectories
        
    Returns:
        List of Path objects
    """
    path = Path(path)
    if not path.exists():
        return []
    
    if pattern:
        if recursive:
            files = list(path.rglob(pattern))
        else:
            files = list(path.glob(pattern))
    else:
        if recursive:
            files = [f for f in path.rglob("*") if f.is_file()]
        else:
            files = [f for f in path.iterdir() if f.is_file()]
    
    return files


def find_files(path: PathLike, patterns: list[str], recursive: bool = True) -> list[Path]:
    """
    Find files matching multiple patterns.
    
    Args:
        path: Path to search
        patterns: List of glob patterns
        recursive: Recurse into subdirectories
        
    Returns:
        List of Path objects matching any pattern
    """
    path = Path(path)
    results = set()
    for pattern in patterns:
        if recursive:
            results.update(path.rglob(pattern))
        else:
            results.update(path.glob(pattern))
    return sorted(results)


def glob_match(path: PathLike, patterns: list[str]) -> bool:
    """
    Check if a path matches any of the given glob patterns.
    
    Args:
        path: Path to check
        patterns: List of glob patterns
        
    Returns:
        True if the path matches any pattern
    """
    import fnmatch
    path_str = str(Path(path).resolve())
    return any(fnmatch.fnmatch(path_str, p) for p in patterns)


# =============================================================================
# File Locking
# =============================================================================

@dataclass
class FileLock:
    """File-based lock for cross-process synchronization."""
    path: Path
    _fd: int | None = None
    
    def __enter__(self) -> FileLock:
        self.acquire()
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()
    
    def acquire(self, timeout: float | None = None) -> bool:
        """
        Acquire the lock.
        
        Args:
            timeout: Maximum time to wait in seconds (None = block forever)
            
        Returns:
            True if lock was acquired
            
        Raises:
            TimeoutError: If timeout is reached
        """
        import time
        
        self.path.parent.mkdir(parents=True, exist_ok=True)
        
        start_time = time.time()
        while True:
            try:
                # Open file in write mode (creates if doesn't exist)
                self._fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR)
                # Try to acquire exclusive lock
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        raise TimeoutError(f"Could not acquire lock on {self.path} within {timeout}s")
                    time.sleep(0.1)
                else:
                    time.sleep(0.1)
            except Exception as e:
                if self._fd is not None:
                    os.close(self._fd)
                    self._fd = None
                raise
    
    def release(self) -> None:
        """Release the lock."""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                os.close(self._fd)
                self._fd = None
                # Try to remove the lock file
                try:
                    self.path.unlink()
                except Exception:
                    pass
    
    @property
    def locked(self) -> bool:
        """Check if the lock is held."""
        return self._fd is not None


def file_lock(path: PathLike, timeout: float | None = None) -> FileLock:
    """
    Create a file lock.
    
    Args:
        path: Path to the lock file
        timeout: Maximum time to wait for lock
        
    Returns:
        FileLock instance
    """
    return FileLock(Path(path), timeout=timeout)


@contextmanager
def locked(path: PathLike, timeout: float | None = None) -> Iterator[FileLock]:
    """
    Context manager for file locking.
    
    Args:
        path: Path to the lock file
        timeout: Maximum time to wait for lock
        
    Yields:
        FileLock instance
    """
    lock = FileLock(Path(path))
    try:
        lock.acquire(timeout=timeout)
        yield lock
    finally:
        lock.release()


# =============================================================================
# File System Utilities
# =============================================================================

def remove_tree(path: PathLike) -> None:
    """Remove a directory tree, including all contents."""
    import shutil
    path = Path(path)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def copy_tree(src: PathLike, dst: PathLike, overwrite: bool = False) -> None:
    """Copy a directory tree."""
    src = Path(src)
    dst = Path(dst)
    if dst.exists():
        if overwrite:
            remove_tree(dst)
        else:
            raise FileExistsError(f"Destination {dst} already exists")
    shutil.copytree(src, dst)


def symlink_tree(src: PathLike, dst: PathLike, overwrite: bool = False) -> None:
    """Create a symlink to a directory."""
    src = Path(src)
    dst = Path(dst)
    if dst.exists():
        if overwrite:
            dst.unlink()
        else:
            raise FileExistsError(f"Destination {dst} already exists")
    dst.symlink_to(src)


def file_size(path: PathLike) -> int:
    """Get the size of a file in bytes."""
    return Path(path).stat().st_size


def file_mtime(path: PathLike) -> float:
    """Get the modification time of a file."""
    return Path(path).stat().st_mtime


def is_executable(path: PathLike) -> bool:
    """Check if a file is executable."""
    path = Path(path)
    if not path.exists():
        return False
    return os.access(path, os.X_OK)


def make_executable(path: PathLike) -> None:
    """Make a file executable."""
    path = Path(path)
    if path.exists():
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
