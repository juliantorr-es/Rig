"""
Configuration Management for rig_tools

Provides settings management with validation, environment variable support,
and configuration file loading.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from rig_tools.core.io import read_json, write_json, dump_json, load_json
from rig_tools.core.filesystem import ensure_dir, PathLike
from rig_tools.core.errors import RigConfigError, RigValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# Type Definitions
# =============================================================================

ConfigValue = Any
ConfigDict = dict[str, ConfigValue]


class ConfigSource(Enum):
    """Configuration value source priority."""
    DEFAULT = "default"
    ENV_VAR = "environment_variable"
    CONFIG_FILE = "config_file"
    CLI_ARG = "cli_argument"


@dataclass
class ConfigSpec:
    """
    Configuration specification for a setting.
    
    Defines how a configuration value should be parsed, validated,
    and where it can come from.
    """
    name: str
    default: ConfigValue = None
    description: str = ""
    required: bool = False
    type: type | tuple[type, ...] | None = None
    choices: list[ConfigValue] | None = None
    env_var: str | None = None
    min_value: float | int | None = None
    max_value: float | int | None = None
    
    def validate(self, value: ConfigValue) -> ConfigValue:
        """
        Validate and coerce a configuration value.
        
        Args:
            value: The value to validate
            
        Returns:
            Validated and coerced value
            
        Raises:
            RigValidationError: If validation fails
        """
        # Check required
        if self.required and value is None:
            raise RigValidationError(
                f"Required configuration '{self.name}' is missing",
                code="CONFIG_REQUIRED",
                context={"config": self.name},
            )
        
        # Type coercion
        if self.type is not None and value is not None:
            if not isinstance(value, self.type):
                try:
                    # Try to coerce to the expected type
                    if self.type == bool:
                        value = str(value).lower() in ("true", "1", "yes")
                    elif self.type in (int, float):
                        value = self.type(value)
                    elif self.type == Path:
                        value = Path(value)
                    else:
                        value = self.type(value)
                except (ValueError, TypeError) as e:
                    raise RigValidationError(
                        f"Invalid type for '{self.name}': expected {self.type.__name__}, got {type(value).__name__}",
                        code="CONFIG_TYPE_ERROR",
                        context={"config": self.name, "value": str(value)},
                    ) from e
        
        # Check choices
        if self.choices is not None and value is not None:
            if value not in self.choices:
                raise RigValidationError(
                    f"Invalid value for '{self.name}': {value!r} not in {self.choices}",
                    code="CONFIG_CHOICE_ERROR",
                    context={"config": self.name, "value": str(value), "choices": self.choices},
                )
        
        # Check numeric bounds
        if value is not None and isinstance(value, (int, float)):
            if self.min_value is not None and value < self.min_value:
                raise RigValidationError(
                    f"Value for '{self.name}' ({value}) is less than minimum ({self.min_value})",
                    code="CONFIG_MIN_VALUE",
                    context={"config": self.name, "value": value, "min": self.min_value},
                )
            if self.max_value is not None and value > self.max_value:
                raise RigValidationError(
                    f"Value for '{self.name}' ({value}) is greater than maximum ({self.max_value})",
                    code="CONFIG_MAX_VALUE",
                    context={"config": self.name, "value": value, "max": self.max_value},
                )
        
        return value


# =============================================================================
# Configuration Classes
# =============================================================================

@dataclass
class Config:
    """
    Configuration container.
    
    Holds configuration values and tracks their sources.
    Provides methods for accessing and validating configuration.
    """
    values: ConfigDict = field(default_factory=dict)
    sources: dict[str, ConfigSource] = field(default_factory=dict)
    spec: dict[str, ConfigSpec] = field(default_factory=dict)
    
    def __getitem__(self, key: str) -> ConfigValue:
        """Get a configuration value by key."""
        if key not in self.values:
            if key in self.spec:
                # Return default if not set
                return self.spec[key].default
            raise KeyError(f"Configuration key '{key}' not found")
        return self.values[key]
    
    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None:
        """Get a configuration value with optional default."""
        try:
            return self[key]
        except KeyError:
            return default
    
    def __contains__(self, key: str) -> bool:
        """Check if a configuration key exists."""
        return key in self.values or key in self.spec
    
    def __setitem__(self, key: str, value: ConfigValue) -> None:
        """Set a configuration value."""
        self.values[key] = value
    
    def set(self, key: str, value: ConfigValue, source: ConfigSource = ConfigSource.CLI_ARG) -> None:
        """Set a configuration value with source tracking."""
        self.values[key] = value
        self.sources[key] = source
    
    def to_dict(self, include_defaults: bool = False) -> ConfigDict:
        """Export configuration as dictionary."""
        result = {}
        for key in set(self.values.keys()) | set(self.spec.keys()):
            if key in self.values:
                result[key] = self.values[key]
            elif include_defaults and key in self.spec:
                result[key] = self.spec[key].default
        return result
    
    def validate(self, specs: list[ConfigSpec] | None = None) -> None:
        """
        Validate all configuration values against their specs.
        
        Args:
            specs: Optional list of specs to validate against
            
        Raises:
            RigValidationError: If validation fails
        """
        specs = specs or list(self.spec.values())
        
        for spec in specs:
            value = self.get(spec.name)
            spec.validate(value)
    
    def get_source(self, key: str) -> ConfigSource | None:
        """Get the source of a configuration value."""
        return self.sources.get(key)


@dataclass
class ConfigManager:
    """
    Central configuration manager.
    
    Manages multiple configuration sources (files, environment, CLI args)
    and provides a unified interface for accessing configuration values.
    """
    name: str = "rig"
    config_class: type[Config] = Config
    specs: list[ConfigSpec] = field(default_factory=list)
    
    _instance: Config | None = field(default=None, repr=False)
    _loaded: bool = field(default=False, repr=False)
    
    def __post_init__(self):
        """Initialize the config manager."""
        self._instance = None
        self._loaded = False
    
    def _ensure_loaded(self) -> None:
        """Load configuration if not already loaded."""
        if self._loaded:
            return
        
        self._instance = self.config_class()
        self._load_specs()
        self._load_environment()
        self._load_config_files()
        self._loaded = True
    
    def _load_specs(self) -> None:
        """Load default values from specs."""
        if self._instance is None:
            return
        
        for spec in self.specs:
            self._instance.spec[spec.name] = spec
            if spec.default is not None:
                self._instance.set(spec.name, spec.default, ConfigSource.DEFAULT)
    
    def _load_environment(self) -> None:
        """Load configuration from environment variables."""
        if self._instance is None:
            return
        
        for spec in self.specs:
            if spec.env_var and spec.env_var in os.environ:
                env_value = os.environ[spec.env_var]
                try:
                    # Parse the value
                    if spec.type == bool:
                        value = str(env_value).lower() in ("true", "1", "yes")
                    elif spec.type == Path:
                        value = Path(env_value)
                    else:
                        value = env_value
                    
                    self._instance.set(spec.name, value, ConfigSource.ENV_VAR)
                except Exception as e:
                    logger.warning(f"Failed to parse env var {spec.env_var}: {e}")
    
    def _load_config_files(self) -> None:
        """Load configuration from files."""
        # Default: try to load from ~/.config/{name}/config.json
        config_dir = Path.home() / ".config" / self.name
        config_file = config_dir / "config.json"
        
        if config_file.exists():
            try:
                config_data = read_json(config_file)
                for key, value in config_data.items():
                    self._instance.set(key, value, ConfigSource.CONFIG_FILE)
                logger.debug(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config from {config_file}: {e}")
    
    @property
    def config(self) -> Config:
        """Get the configuration instance."""
        self._ensure_loaded()
        return self._instance  # type: ignore
    
    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None:
        """Get a configuration value."""
        return self.config.get(key, default)
    
    def __getitem__(self, key: str) -> ConfigValue:
        """Get a configuration value by key."""
        return self.config[key]
    
    def __contains__(self, key: str) -> bool:
        """Check if a configuration key exists."""
        return key in self.config
    
    def set(self, key: str, value: ConfigValue) -> None:
        """Set a configuration value (CLI argument priority)."""
        self.config.set(key, value, ConfigSource.CLI_ARG)
    
    def save(self, path: PathLike | None = None) -> None:
        """
        Save current configuration to a file.
        
        Args:
            path: Path to save to (defaults to ~/.config/{name}/config.json)
        """
        config_dir = Path.home() / ".config" / self.name
        ensure_dir(config_dir)
        save_path = Path(path) if path else config_dir / "config.json"
        
        # Only save non-default values (not from CLI)
        save_data = {}
        for key, source in self.config.sources.items():
            if source in (ConfigSource.CONFIG_FILE, ConfigSource.ENV_VAR):
                save_data[key] = self.config.values.get(key)
        
        # Also include values set directly (not from defaults)
        for key, value in self.config.values.items():
            if key not in save_data:
                save_data[key] = value
        
        write_json(save_path, save_data)
        logger.debug(f"Saved configuration to {save_path}")
    
    def validate(self) -> None:
        """Validate all configuration values."""
        self.config.validate(self.specs)


# =============================================================================
# Global Configuration Management
# =============================================================================

_global_config_manager: ConfigManager | None = None


def get_config_manager(name: str = "rig") -> ConfigManager:
    """
    Get or create the global configuration manager.
    
    Args:
        name: Name for the configuration manager
        
    Returns:
        ConfigManager instance
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager(name=name)
    return _global_config_manager


def set_config_manager(manager: ConfigManager) -> None:
    """Set the global configuration manager."""
    global _global_config_manager
    _global_config_manager = manager


def get_config(key: str, default: ConfigValue | None = None) -> ConfigValue | None:
    """Get a configuration value from the global manager."""
    return get_config_manager().get(key, default)


# =============================================================================
# Convenience Functions
# =============================================================================

def load_config(file_path: PathLike) -> ConfigDict:
    """Load configuration from a JSON or YAML file."""
    path = Path(file_path)
    
    if path.suffix in (".yaml", ".yml"):
        from rig_tools.core.io import read_yaml
        return read_yaml(path) or {}
    elif path.suffix == ".toml":
        from rig_tools.core.io import read_toml
        return read_toml(path) or {}
    else:
        # Default to JSON
        return read_json(path) or {}


def save_config(file_path: PathLike, config: ConfigDict) -> None:
    """Save configuration to a JSON or YAML file."""
    path = Path(file_path)
    ensure_dir(path.parent)
    
    if path.suffix in (".yaml", ".yml"):
        from rig_tools.core.io import write_yaml
        write_yaml(path, config)
    elif path.suffix == ".toml":
        from rig_tools.core.io import write_toml
        write_toml(path, config)
    else:
        # Default to JSON
        write_json(path, config)


def merge_configs(base: ConfigDict, override: ConfigDict, deep: bool = True) -> ConfigDict:
    """
    Merge configuration dictionaries.
    
    Args:
        base: Base configuration
        override: Configuration to override values with
        deep: Whether to do deep merging of nested dicts
        
    Returns:
        Merged configuration dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if deep and key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value, deep=True)
        else:
            result[key] = value
    
    return result
