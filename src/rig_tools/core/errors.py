"""
Error Handling for rig_tools

Provides custom exception hierarchy and error formatting utilities
for consistent error handling across rig_tools modules.
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass
from typing import Any, TextIO


# =============================================================================
# Exception Hierarchy
# =============================================================================

class RigError(Exception):
    """Base exception for all rig_tools errors."""
    
    def __init__(
        self,
        message: str,
        code: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.context = context or {}
    
    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        if self.context:
            parts.append(f"Context: {self.context}")
        return " | ".join(parts)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} code={self.code!r} message={self.message!r}>"


class RigConfigError(RigError):
    """Configuration error."""
    pass


class RigIOError(RigError):
    """File I/O error."""
    pass


class RigProcessError(RigError):
    """Process execution error."""
    
    def __init__(
        self,
        message: str,
        code: str | None = None,
        context: dict[str, Any] | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        returncode: int | None = None,
    ):
        super().__init__(message, code, context)
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
    
    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.returncode:
            parts.append(f"returncode={self.returncode}")
        if self.stdout:
            parts.append(f"stdout={self.stdout[:200]}...")
        if self.stderr:
            parts.append(f"stderr={self.stderr[:200]}...")
        return " | ".join(parts)


class RigValidationError(RigError):
    """Validation error."""
    
    def __init__(
        self,
        message: str,
        code: str | None = None,
        context: dict[str, Any] | None = None,
        errors: list[str] | None = None,
    ):
        super().__init__(message, code, context)
        self.errors = errors or []
    
    def __str__(self) -> str:
        if self.errors and len(self.errors) > 1:
            error_list = "\n  - ".join(self.errors)
            return f"[{self.code}] Validation failed:\n  - {error_list}"
        return super().__str__()


class RigTimeoutError(RigError):
    """Operation timeout error."""
    
    def __init__(
        self,
        message: str,
        code: str | None = None,
        context: dict[str, Any] | None = None,
        timeout: float | None = None,
    ):
        super().__init__(message, code, context)
        self.timeout = timeout
    
    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.timeout:
            parts.append(f"timeout={self.timeout}s")
        return " | ".join(parts)


class RigNotFoundError(RigError):
    """Resource not found error."""
    
    def __init__(
        self,
        message: str,
        code: str | None = None,
        context: dict[str, Any] | None = None,
        resource_type: str = "resource",
        resource_id: str | None = None,
    ):
        super().__init__(message, code, context)
        self.resource_type = resource_type
        self.resource_id = resource_id
    
    def __str__(self) -> str:
        if self.resource_id:
            return f"[{self.code}] {self.resource_type} '{self.resource_id}' not found: {self.message}"
        return f"[{self.code}] {self.resource_type} not found: {self.message}"


class RigPermissionError(RigError):
    """Permission/access error."""
    pass


class RigStateError(RigError):
    """Invalid state error."""
    pass


# =============================================================================
# Error Formatting
# =============================================================================

def format_exception(
    exc: Exception,
    include_traceback: bool = True,
    include_context: bool = True,
) -> str:
    """
    Format an exception with optional traceback and context.
    
    Args:
        exc: The exception to format
        include_traceback: Include traceback in output
        include_context: Include context dict if available
        
    Returns:
        Formatted error string
    """
    parts = []
    
    # Exception type and message
    if isinstance(exc, RigError):
        parts.append(str(exc))
        if include_context and hasattr(exc, 'context') and exc.context:
            parts.append(f"\nContext:")
            for k, v in exc.context.items():
                parts.append(f"  {k}: {v}")
    else:
        parts.append(f"{type(exc).__name__}: {exc}")
    
    # Traceback
    if include_traceback:
        tb = traceback.format_exc()
        if tb and tb.strip():
            parts.append(f"\nTraceback:")
            parts.append(tb)
    
    return "\n".join(parts)


def format_error_for_logging(
    exc: Exception,
    level: str = "error",
) -> dict[str, Any]:
    """
    Format an exception for structured logging.
    
    Args:
        exc: The exception to format
        level: Log level
        
    Returns:
        Dictionary suitable for structured logging
    """
    error_dict: dict[str, Any] = {
        "level": level,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    
    # Add RigError-specific fields
    if isinstance(exc, RigError):
        error_dict["error_code"] = exc.code
        error_dict["context"] = exc.context
    
    # Add traceback
    error_dict["traceback"] = traceback.format_exc().splitlines()
    
    return error_dict


def log_exception(
    logger: Any,
    exc: Exception,
    message: str | None = None,
    level: str = "error",
    **context: Any,
) -> None:
    """
    Log an exception with structured data.
    
    Args:
        logger: Logger instance
        exc: Exception to log
        message: Optional message to prefix
        level: Log level
        **context: Additional context data
    """
    log_data = format_error_for_logging(exc, level)
    if message:
        log_data["message"] = message
    log_data.update(context)
    
    getattr(logger, level)(format_exception(exc), extra=log_data)


# =============================================================================
# Error Collection
# =============================================================================

class ErrorCollector:
    """Collects multiple errors with context."""
    
    def __init__(self):
        self.errors: list[dict[str, Any]] = []
    
    def add(self, exc: Exception, **context: Any) -> None:
        """Add an error to the collection."""
        self.errors.append({
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "context": context,
        })
    
    def add_from_dict(self, error_dict: dict[str, Any]) -> None:
        """Add a pre-formatted error dict."""
        self.errors.append(error_dict)
    
    @property
    def count(self) -> int:
        """Number of collected errors."""
        return len(self.errors)
    
    @property
    def is_empty(self) -> bool:
        """Check if no errors have been collected."""
        return len(self.errors) == 0
    
    def raise_if_not_empty(self, message: str | None = None) -> None:
        """
        Raise RigValidationError if errors have been collected.
        
        Args:
            message: Custom message for the exception
        """
        if not self.is_empty:
            error_messages = [e.get("error_message", "Unknown error") for e in self.errors]
            raise RigValidationError(
                message or f"Collected {len(self.errors)} errors",
                code="VALIDATION_ERROR",
                errors=error_messages,
            )
    
    def get_summary(self) -> str:
        """Get a summary of collected errors."""
        if self.is_empty:
            return "No errors"
        return f"{len(self.errors)} error(s): " + ", ".join(
            e.get("error_message", "Unknown")[:50] for e in self.errors
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Export to dictionary."""
        return {
            "error_count": len(self.errors),
            "errors": self.errors,
        }


# =============================================================================
# Result Type
# =============================================================================

@dataclass
class Result:
    """Generic result type with success/error state."""
    success: bool
    value: Any = None
    error: str | None = None
    errors: list[str] | None = None
    warnings: list[str] | None = None
    
    @classmethod
    def ok(cls, value: Any = None, warnings: list[str] | None = None) -> Result:
        """Create a successful result."""
        return cls(success=True, value=value, warnings=warnings)
    
    @classmethod
    def fail(cls, error: str, errors: list[str] | None = None) -> Result:
        """Create a failed result."""
        return cls(success=False, error=error, errors=errors)
    
    def unwrap(self) -> Any:
        """Get the value or raise an exception."""
        if not self.success:
            raise RigError(self.error or "Operation failed", errors=self.errors)
        return self.value
    
    def unwrap_or(self, default: Any) -> Any:
        """Get the value or return a default."""
        if self.success:
            return self.value
        return default


T = Any  # Placeholder for generic type
