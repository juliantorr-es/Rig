"""
Rig Tools Core Utilities

This package provides shared utilities used across all rig_tools modules.
These are internal implementation details and should only be used by
rig_tools modules, not by the domain layer or CLI commands.

Modules:
- io: Atomic I/O operations, JSON/YAML/TOML serialization
- process: Subprocess execution with logging, retry, timeout
- filesystem: Path utilities, atomic operations, locking
- config: Settings management with validation
- tracing: Observability (spans, metrics, structured logging)
- errors: Custom exceptions and error handling patterns
"""

from rig_tools.core.io import (
    read_text,
    write_text,
    read_json,
    write_json,
    read_yaml,
    write_yaml,
    read_toml,
    write_toml,
    load_json,
    dump_json,
)

from rig_tools.core.process import (
    run,
    run_check,
    run_capture,
    run_async,
    RetryConfig,
    retry,
    TimeoutError,
)

from rig_tools.core.filesystem import (
    ensure_dir,
    atomic_write,
    atomic_move,
    temp_dir,
    list_files,
    find_files,
    glob_match,
    PathLike,
)

from rig_tools.core.tracing import (
    get_tracer,
    Tracer,
    Span,
    trace,
    trace_context,
    add_breadcrumbs,
    log_event,
    span,
)

from rig_tools.core.errors import (
    RigError,
    RigConfigError,
    RigIOError,
    RigProcessError,
    RigValidationError,
    RigTimeoutError,
    RigNotFoundError,
    RigPermissionError,
    RigStateError,
    format_exception,
    ErrorCollector,
    Result,
)

from rig_tools.core.config import (
    Config,
    ConfigDict,
    ConfigManager,
    ConfigSpec,
    ConfigSource,
    ConfigValue,
    get_config_manager,
    set_config_manager,
    get_config,
    load_config,
    save_config,
    merge_configs,
)

__all__ = [
    # IO
    "read_text", "write_text",
    "read_json", "write_json", 
    "read_yaml", "write_yaml",
    "read_toml", "write_toml",
    "load_json", "dump_json",
    # Process
    "run", "run_check", "run_capture", "run_async",
    "RetryConfig", "retry", "TimeoutError",
    # Filesystem
    "ensure_dir", "atomic_write", "atomic_move",
    "temp_dir", "list_files", "find_files", "glob_match",
    "PathLike",
    # Tracing
    "get_tracer", "Tracer", "Span", "trace", "trace_context",
    "add_breadcrumbs", "log_event", "span",
    # Errors
    "RigError", "RigConfigError", "RigIOError",
    "RigProcessError", "RigValidationError", "RigTimeoutError",
    "RigNotFoundError", "RigPermissionError", "RigStateError",
    "format_exception", "ErrorCollector", "Result",
    # Config
    "Config", "ConfigDict", "ConfigManager", "ConfigSpec",
    "ConfigSource", "ConfigValue",
    "get_config_manager", "set_config_manager", "get_config",
    "load_config", "save_config", "merge_configs",
]
