"""
Process Execution Utilities for rig_tools

Provides low-level subprocess execution with logging, retry logic, and timeout handling.

NOTE: This module provides low-level process utilities. For governed execution with
leases, receipts, and evidence capture, use rig.domain.execution.WorktreeExecutor instead.

The WorktreeExecutor is the domain-level execution authority and should be preferred
for all new code that needs:
- Lease-based authorization
- Receipt creation
- Output streaming
- Timeout enforcement
- Evidence capture

These utilities remain for compatibility with existing callers and should not be
used for new governed execution paths.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, TextIO

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    delay: float = 1.0
    backoff: float = 2.0  # Multiplier for exponential backoff
    max_delay: float | None = None  # Cap on delay between retries
    retry_on: tuple[type[Exception], ...] = (Exception,)  # Which exceptions to retry
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        delay = self.delay * (self.backoff ** attempt)
        if self.max_delay is not None:
            delay = min(delay, self.max_delay)
        return delay


class TimeoutError(Exception):
    """Raised when a process times out."""
    pass


# =============================================================================
# Synchronous Execution
# =============================================================================

def run(
    cmd: str | list[str],
    *,
    cwd: Path | str | None = None,
    timeout: float | None = None,
    check: bool = False,
    capture: bool = True,
    text: bool = True,
    env: dict[str, str] | None = None,
    shell: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """
    Run a command with optional timeout and error handling.
    
    Args:
        cmd: Command to run (string or list)
        cwd: Working directory
        timeout: Timeout in seconds
        check: Raise CalledProcessError on non-zero exit
        capture: Capture stdout/stderr
        text: Use text mode (string output vs bytes)
        env: Environment variables
        shell: Use shell execution
        **kwargs: Additional subprocess.run arguments
        
    Returns:
        CompletedProcess with stdout, stderr, returncode
        
    Raises:
        TimeoutError: If timeout is reached
        subprocess.CalledProcessError: If check=True and returncode != 0
    """
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    
    start_time = time.time()
    logger.debug(f"Running: {' '.join(cmd)} (cwd={cwd}, timeout={timeout})")
    
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            timeout=timeout,
            check=check,
            capture_output=capture,
            text=text,
            env=env,
            shell=shell,
            **kwargs,
        )
        duration = time.time() - start_time
        logger.debug(f"Completed in {duration:.3f}s: {' '.join(cmd)}")
        return result
    except subprocess.TimeoutExpired as e:
        duration = time.time() - start_time
        logger.warning(f"Timeout after {duration:.3f}s: {' '.join(cmd)}")
        raise TimeoutError(f"Command timed out after {duration:.1f}s: {' '.join(cmd)}") from e


def run_check(
    cmd: str | list[str],
    *,
    cwd: Path | str | None = None,
    timeout: float | None = None,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a command and raise on non-zero exit code."""
    return run(cmd, cwd=cwd, timeout=timeout, check=True, **kwargs)


def run_capture(
    cmd: str | list[str],
    *,
    cwd: Path | str | None = None,
    timeout: float | None = None,
    text: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a command and always capture output."""
    return run(cmd, cwd=cwd, timeout=timeout, capture=True, text=text, **kwargs)


# =============================================================================
# Retry Decorator
# =============================================================================

def retry(
    config: RetryConfig | None = None,
    on: tuple[type[Exception], ...] | None = None,
) -> Callable:
    """
    Decorator to retry a function on failure.
    
    Args:
        config: Retry configuration
        on: Exception types to retry (overrides config.retry_on)
        
    Returns:
        Decorated function
    """
    if config is None:
        config = RetryConfig()
    if on is not None:
        config = RetryConfig(
            max_attempts=config.max_attempts,
            delay=config.delay,
            backoff=config.backoff,
            max_delay=config.max_delay,
            retry_on=on,
        )
    
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.retry_on as e:
                    last_error = e
                    delay = config.get_delay(attempt)
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
            raise last_error
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    
    return decorator


# =============================================================================
# Asynchronous Execution
# =============================================================================

async def run_async(
    cmd: str | list[str],
    *,
    cwd: Path | str | None = None,
    timeout: float | None = None,
    capture: bool = True,
    text: bool = True,
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """
    Run a command asynchronously.
    
    Args:
        cmd: Command to run
        cwd: Working directory
        timeout: Timeout in seconds
        capture: Capture stdout/stderr
        text: Use text mode
        **kwargs: Additional arguments
        
    Returns:
        CompletedProcess
        
    Raises:
        TimeoutError: If timeout is reached
    """
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    
    start_time = time.time()
    logger.debug(f"Running async: {' '.join(cmd)}")
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
            env=kwargs.get("env"),
        )
        
        # Wait for completion with timeout
        stdout_raw, stderr_raw = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout
        )
        
        duration = time.time() - start_time
        logger.debug(f"Async completed in {duration:.3f}s: {' '.join(cmd)}")
        
        if text:
            stdout = stdout_raw.decode() if stdout_raw else ""
            stderr = stderr_raw.decode() if stderr_raw else ""
        else:
            stdout = stdout_raw
            stderr = stderr_raw
        
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    except asyncio.TimeoutError as e:
        duration = time.time() - start_time
        logger.warning(f"Async timeout after {duration:.3f}s: {' '.join(cmd)}")
        # Kill the process group
        if isinstance(cmd, list) and cmd:
            try:
                pgid = os.getpgid(proc.pid) if hasattr(proc, 'pid') else None
                if pgid:
                    os.killpg(pgid, signal.SIGKILL)
            except:
                pass
        raise TimeoutError(f"Async command timed out after {duration:.1f}s: {' '.join(cmd)}") from e


# =============================================================================
# Utility Functions
# =============================================================================

def command_exists(cmd: str) -> bool:
    """Check if a command exists on the PATH."""
    import shutil
    return shutil.which(cmd) is not None


def which(cmd: str) -> str | None:
    """Get the full path to a command."""
    import shutil
    return shutil.which(cmd)


# Fix import
import os
