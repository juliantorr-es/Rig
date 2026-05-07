"""
Observability and Tracing for rig_tools

Provides structured logging, performance tracing, and breadcrumb tracking
for debugging rig_tools operations.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TextIO
import threading


# =============================================================================
# Span Data Model
# =============================================================================

@dataclass
class Span:
    """Represents a traced operation."""
    span_id: str
    parent_id: str | None
    name: str
    category: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration: float | None = None
    tags: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    breadcrumbs: list[dict[str, Any]] = field(default_factory=list)
    children: list[Span] = field(default_factory=list)
    
    @property
    def is_complete(self) -> bool:
        """Check if the span has been completed."""
        return self.end_time is not None
    
    def add_tag(self, key: str, value: Any) -> None:
        """Add a tag to the span."""
        self.tags[key] = value
    
    def add_error(self, error: str | Exception) -> None:
        """Add an error to the span."""
        if isinstance(error, Exception):
            error = f"{type(error).__name__}: {error}"
        self.errors.append(error)
    
    def add_breadcrumb(self, message: str, **data: Any) -> None:
        """Add a breadcrumb (debug message) to the span."""
        self.breadcrumbs.append({
            "timestamp": time.time(),
            "message": message,
            **data,
        })
    
    def to_dict(self) -> dict[str, Any]:
        """Export span to dictionary."""
        return {
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "category": self.category,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "tags": self.tags,
            "errors": self.errors,
            "breadcrumbs": self.breadcrumbs,
            "children": [c.to_dict() for c in self.children],
        }


# =============================================================================
# Thread-Local Storage for Current Span
# =============================================================================

_thread_local = threading.local()


def _get_current_span() -> Span | None:
    """Get the current span for this thread."""
    return getattr(_thread_local, "current_span", None)


def _set_current_span(span: Span | None) -> None:
    """Set the current span for this thread."""
    _thread_local.current_span = span


# =============================================================================
# Tracer Class
# ============================================================================= 

class Tracer:
    """
    Central tracing facility for rig_tools.
    
    Provides:
    - Hierarchical span tracing
    - Performance metrics
    - Error tracking
    - Breadcrumb logging
    """
    
    def __init__(self, name: str = "rig_tools"):
        """
        Initialize the tracer.
        
        Args:
            name: Name for this tracer instance
        """
        self.name = name
        self._logger = logging.getLogger(name)
        self._root_spans: dict[str, Span] = {}
        self._span_stack: dict[int, list[Span]] = {}  # thread_id -> [span]
    
    def start_span(
        self,
        name: str,
        category: str = "",
        parent: Span | None = None,
        **tags: Any,
    ) -> Span:
        """
        Start a new span.
        
        Args:
            name: Span name/operation
            category: Span category (e.g., "ml", "git", "io")
            parent: Parent span (None = new root span)
            **tags: Initial span tags
            
        Returns:
            The new Span object
        """
        span = Span(
            span_id=uuid.uuid4().hex[:12],
            parent_id=parent.span_id if parent else None,
            name=name,
            category=category,
            start_time=time.time(),
            tags=tags,
        )
        
        # Track in span stack for this thread
        thread_id = threading.get_ident()
        if thread_id not in self._span_stack:
            self._span_stack[thread_id] = []
        
        self._span_stack[thread_id].append(span)
        
        if parent is None:
            self._root_spans[span.span_id] = span
        else:
            parent.children.append(span)
        
        # Set as current span
        _set_current_span(span)
        
        self._logger.debug(f"SPAN START: {name} [{span.span_id}] category={category}")
        
        return span
    
    def end_span(self, span: Span) -> None:
        """
        End a span.
        
        Args:
            span: The span to end
        """
        span.end_time = time.time()
        span.duration = span.end_time - span.start_time
        
        # Pop from stack if it's the current span
        thread_id = threading.get_ident()
        if thread_id in self._span_stack:
            stack = self._span_stack[thread_id]
            if stack and stack[-1].span_id == span.span_id:
                stack.pop()
                _set_current_span(stack[-1] if stack else None)
        
        self._logger.debug(
            f"SPAN END: {span.name} [{span.span_id}] "
            f"duration={span.duration:.3f}s "
            f"errors={len(span.errors)}"
        )
    
    @contextmanager
    def span(
        self,
        name: str,
        category: str = "",
        **tags: Any,
    ):
        """
        Context manager for tracing an operation.
        
        Args:
            name: Span name/operation
            category: Span category
            **tags: Initial span tags
            
        Yields:
            Span object for adding tags/errors/breadcrumbs
        """
        parent = _get_current_span()
        span = self.start_span(name, category=category, parent=parent, **tags)
        
        try:
            yield span
        except Exception as e:
            span.add_error(e)
            raise
        finally:
            self.end_span(span)
    
    def get_current_span(self) -> Span | None:
        """Get the current span for this thread."""
        return _get_current_span()
    
    def add_breadcrumb(self, message: str, **data: Any) -> None:
        """
        Add a breadcrumb to the current span.
        
        Args:
            message: Breadcrumb message
            **data: Additional breadcrumb data
        """
        span = _get_current_span()
        if span:
            span.add_breadcrumb(message, **data)
        self._logger.debug(f"BREADCRUMB: {message}")
    
    def log(self, level: str, message: str, **data: Any) -> None:
        """
        Log a message, optionally adding to current span.
        
        Args:
            level: Log level (debug, info, warning, error)
            message: Log message
            **data: Additional data
        """
        span = _get_current_span()
        if span:
            span.add_breadcrumb(message, level=level, **data)
        
        getattr(self._logger, level.lower(), self._logger.debug)(
            f"[{self.name}] {message}"
        )
    
    def get_spans(self) -> list[Span]:
        """Get all root spans."""
        return list(self._root_spans.values())
    
    def get_trace(self, span_id: str | None = None) -> dict[str, Any] | None:
        """
        Get a span tree as a dictionary.
        
        Args:
            span_id: Root span ID (None = get current span tree)
            
        Returns:
            Span tree as dictionary, or None if not found
        """
        if span_id is None:
            span = _get_current_span()
            if span is None:
                # Return all root spans
                return {
                    "spans": [s.to_dict() for s in self._root_spans.values()]
                }
            # Find the root of current span
            while span.parent_id:
                span = next(
                    (s for s in self._root_spans.values() 
                     if s.span_id == span.parent_id),
                    span
                )
            return span.to_dict()
        
        span = self._root_spans.get(span_id)
        if span is None:
            return None
        return span.to_dict()
    
    def export_traces(self, path: Path) -> Path:
        """
        Export all traces to a JSON file.
        
        Args:
            path: Output path
            
        Returns:
            The output path
        """
        from rig_tools.core.io import write_json
        
        data = {
            "exporter": self.name,
            "exported_at": time.time(),
            "spans": [s.to_dict() for s in self._root_spans.values()],
        }
        write_json(path, data)
        return path
    
    def clear(self) -> None:
        """Clear all spans."""
        self._root_spans.clear()
        self._span_stack.clear()
        _set_current_span(None)


# =============================================================================
# Global Tracer Instance
# =============================================================================

_global_tracer: Tracer | None = None
_tracer_lock = threading.Lock()


def get_tracer(name: str = "rig_tools") -> Tracer:
    """
    Get or create the global tracer instance.
    
    Args:
        name: Tracer name
        
    Returns:
        Tracer instance
    """
    global _global_tracer
    with _tracer_lock:
        if _global_tracer is None:
            _global_tracer = Tracer(name)
        return _global_tracer


def set_tracer(tracer: Tracer) -> None:
    """
    Set the global tracer instance.
    
    Args:
        tracer: Tracer instance to use
    """
    global _global_tracer
    with _tracer_lock:
        _global_tracer = tracer


# =============================================================================
# Convenience Functions
# =============================================================================

def trace(name: str, category: str = "", **tags: Any) -> Any:
    """
    Decorator for tracing a function.
    
    Args:
        name: Function name (defaults to __name__)
        category: Span category
        **tags: Initial span tags
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        name = name or func.__name__
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.span(name, category=category, **tags) as span:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.add_error(e)
                    raise
        
        return wrapper
    
    return decorator


@contextmanager
def trace_context(name: str, category: str = "", **tags: Any):
    """
    Context manager for tracing a block of code.
    
    Args:
        name: Span name
        category: Span category
        **tags: Initial span tags
        
    Yields:
        Span object
    """
    tracer = get_tracer()
    with tracer.span(name, category=category, **tags) as span:
        yield span


# Alias for context manager
span = trace_context


def add_breadcrumbs(message: str, **data: Any) -> None:
    """Add a breadcrumb to the current span."""
    get_tracer().add_breadcrumb(message, **data)


def log_event(message: str, level: str = "info", **data: Any) -> None:
    """Log an event to the current span and logger."""
    get_tracer().log(level, message, **data)
