"""
Settings Store for Rig

Manages Hierarchical settings from multiple sources with proper precedence:
1. Environment variables (highest)
2. Runtime settings (JSON)
3. Project settings (TOML)
4. User settings (TOML)
5. Built-in defaults (lowest)

Uses rig_tools.core for I/O operations and config management.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

# Use core utilities for I/O and config
from rig_tools.core import get_config_manager, ConfigManager, ConfigSpec, ConfigSource
from rig_tools.core.io import read_json, write_json, read_toml, write_toml
from rig_tools.core.filesystem import ensure_dir
from rig_tools.core.config import load_config, save_config, merge_configs

# Fallback for tomlkit if not available
try:
    import tomlkit
except ImportError:
    # We'll use write_toml from core.io as fallback
    tomlkit = None

from rig_tools.state_store import StateStore


# =============================================================================
# Settings Schema and Defaults
# =============================================================================

SETTINGS_SCHEMA_VERSION = "rig.settings.v1"

# Configuration specifications for settings that have env var mappings
_SETTINGS_SPECS = [
    ConfigSpec(
        name="default_mode",
        default="safe",
        type=str,
        choices=["safe", "fast", "debug"],
        env_var="RIG_DEFAULT_MODE",
        description="Default operating mode",
    ),
    ConfigSpec(
        name="active_model_backend",
        default="mlx",
        type=str,
        choices=["mlx", "llama_cpp"],
        env_var="RIG_ACTIVE_MODEL_BACKEND",
        description="Active ML model backend",
    ),
    ConfigSpec(
        name="vault_path",
        default=".build/rig/vault/Rig-vault",
        type=str,
        env_var="RIG_VAULT_PATH",
        description="Path to credential vault",
    ),
    ConfigSpec(
        name="tui.theme",
        default="default",
        type=str,
        env_var="RIG_TUI_THEME",
        description="TUI theme",
    ),
    ConfigSpec(
        name="tui.animations",
        default=True,
        type=bool,
        env_var="RIG_TUI_NO_ANIMATIONS",
        description="Enable TUI animations",
    ),
    ConfigSpec(
        name="retention.ephemeral_days",
        default=7,
        type=int,
        env_var="RIG_RETENTION_EPHEMERAL_DAYS",
        description="Days to keep ephemeral data",
    ),
    ConfigSpec(
        name="retention.cache_days",
        default=30,
        type=int,
        env_var="RIG_RETENTION_CACHE_DAYS",
        description="Days to keep cache data",
    ),
]


def _get_defaults() -> Dict[str, Any]:
    """Returns built-in default settings."""
    return {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "default_mode": "safe",
        "active_model_backend": "mlx",
        "active_mlx_model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "active_llama_cpp_model_path": None,
        "vault_path": ".build/rig/vault/Rig-vault",
        "state_path": ".build/rig/state/rig.sqlite",
        "projection_path": ".build/rig/projections",
        "scheduler_enabled": False,
        "tui": {
            "theme": "default",
            "animations": True,
            "remember_mode": True
        },
        "retention": {
            "ephemeral_days": 7,
            "cache_days": 30,
            "projection_days": 14,
            "receipt_days": 90,
            "bundle_days": 365
        },
        "memory": {
            "max_tui_events": 500,
            "max_projection_bytes": 1000000,
            "max_loaded_log_bytes": 200000,
            "high_pressure_disable_parallel_agents": True,
            "max_parallel_agents_default": 1,
        },
        "models": {
            "cache_path": ".build/rig/models/cache",
            "huggingface_token": None,
            "default_quantization": "Q4_K_M"
        },
        "swarm": {
            "ctx_size": 8192,
            "max_parallel_agents": 1,
            "minimum_context_tokens_per_candidate": {
                "plan": 4096,
                "validator_error_classification": 4096,
                "docs_normalization_plan": 4096,
                "patch_proposal": 6144,
                "prompt_repair": 4096,
            },
        },
        "safety": {
            "allow_git_mutation": False,
            "allow_main_worktree_patch": False,
            "allow_confirmed_external_agent_launch": False,
            "require_confirmation_for_auto_approve": True
        },
        "warnings": [],
        "authoritative": False
    }


# =============================================================================
# Helper Functions
# =============================================================================

def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
    """Deep merge override dict into base dict."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def _set_nested(data: Dict[str, Any], key: str, value: Any) -> None:
    """Set a nested key in a dictionary."""
    parts = key.split(".")
    for part in parts[:-1]:
        data = data.setdefault(part, {})
    data[parts[-1]] = value


# =============================================================================
# SettingsStore Class
# =============================================================================

class SettingsStore:
    """
    Hierarchical settings management.
    
    Loads settings from multiple sources with proper precedence:
    1. Environment variables (highest)
    2. CLI arguments
    3. Runtime settings (JSON)
    4. Project settings (TOML)
    5. User settings (TOML)
    6. Built-in defaults (lowest)
    """
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.schema_version = SETTINGS_SCHEMA_VERSION
        self.state_store = StateStore(repo_root)
        
        # Paths
        self.user_config_dir = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "rig"
        self.user_settings_path = self.user_config_dir / "settings.toml"
        self.project_settings_path = self.repo_root / ".rig" / "settings.toml"
        self.runtime_settings_path = self.repo_root / ".build" / "rig" / "tui" / "settings.json"
    
    def get_defaults(self) -> Dict[str, Any]:
        """Returns built-in default settings."""
        return _get_defaults()
    
    def get_user_settings(self) -> Dict[str, Any]:
        """Loads settings from user home directory."""
        if self.user_settings_path.exists():
            try:
                return read_toml(self.user_settings_path) or {}
            except Exception:
                return {}
        return {}
    
    def get_project_settings(self) -> Dict[str, Any]:
        """Loads settings from project directory."""
        if self.project_settings_path.exists():
            try:
                return read_toml(self.project_settings_path) or {}
            except Exception:
                return {}
        return {}
    
    def get_runtime_settings(self) -> Dict[str, Any]:
        """Loads settings from runtime build directory."""
        if self.runtime_settings_path.exists():
            try:
                return read_json(self.runtime_settings_path) or {}
            except Exception:
                return {}
        return {}
    
    def get_env_overrides(self) -> Dict[str, Any]:
        """Loads settings from environment variables."""
        overrides = {}
        mapping = {
            "RIG_DEFAULT_MODE": "default_mode",
            "RIG_ACTIVE_MODEL_BACKEND": "active_model_backend",
            "RIG_VAULT_PATH": "vault_path",
            "RIG_TUI_THEME": "tui.theme",
            "RIG_TUI_NO_ANIMATIONS": "tui.animations",
            "RIG_RETENTION_EPHEMERAL_DAYS": "retention.ephemeral_days",
            "RIG_RETENTION_CACHE_DAYS": "retention.cache_days"
        }
        
        for env_key, setting_key in mapping.items():
            val = os.environ.get(env_key)
            if val is not None:
                if val.lower() in ("true", "1", "yes"):
                    val = True
                elif val.lower() in ("false", "0", "no"):
                    val = False
                elif val.isdigit():
                    val = int(val)
                
                # Special case for NO_ANIMATIONS -> animations = False
                if env_key == "RIG_TUI_NO_ANIMATIONS":
                    val = not val if isinstance(val, bool) else False
                
                _set_nested(overrides, setting_key, val)
        return overrides
    
    def get_effective_settings(self) -> Dict[str, Any]:
        """Merges all layers of settings with correct precedence."""
        settings = self.get_defaults()
        
        # Merge layers (later sources override earlier ones)
        _deep_merge(settings, self.get_user_settings())
        _deep_merge(settings, self.get_project_settings())
        _deep_merge(settings, self.get_runtime_settings())
        _deep_merge(settings, self.get_env_overrides())
        
        # Record to state store if initialized
        self._record_to_state_store(settings)
        
        return settings
    
    def set_setting(self, key: str, value: Any, layer: Literal["user", "project", "runtime"] = "project", dry_run: bool = False) -> Dict[str, Any]:
        """Updates a setting in a specific layer."""
        if layer == "user":
            path = self.user_settings_path
        elif layer == "runtime":
            path = self.runtime_settings_path
        else:
            path = self.project_settings_path
            
        if not str(path).endswith(".json"):
            data = read_toml(path) or {}
        else:
            data = self.get_runtime_settings() or {}
        
        _set_nested(data, key, value)
        
        if not dry_run:
            ensure_dir(path.parent)
            if str(path).endswith(".json"):
                write_json(path, data)
            else:
                # Prefer tomlkit for writing, fall back to manual TOML
                if tomlkit is not None:
                    path.write_text(tomlkit.dumps(data), encoding="utf-8")
                else:
                    # Fallback: try tomli_w, then manual write
                    try:
                        from tomli_w import dumps as tomli_dumps
                        path.write_text(tomli_dumps(data), encoding="utf-8")
                    except ImportError:
                        # Last resort: write as JSON (not ideal but works)
                        write_json(path.with_suffix(".json"), data)
                
        return data
    
    def init_project(self, dry_run: bool = False) -> str:
        """Initializes a project-level settings file with defaults."""
        if self.project_settings_path.exists():
            return "Project settings already exist."
        
        defaults = {
            "default_mode": "safe",
            "active_model_backend": "mlx",
            "tui": {
                "theme": "default",
                "animations": True
            },
            "safety": {
                "allow_git_mutation": False,
                "allow_main_worktree_patch": False
            },
            "memory": {
                "max_tui_events": 500,
                "max_projection_bytes": 1000000,
                "max_loaded_log_bytes": 200000,
                "high_pressure_disable_parallel_agents": True,
                "max_parallel_agents_default": 1,
            },
            "models": {
                "cache_path": ".build/rig/models/cache",
                "huggingface_token": None,
                "default_quantization": "Q4_K_M"
            },
            "swarm": {
                "ctx_size": 8192,
                "max_parallel_agents": 1,
            }
        }
        
        if not dry_run:
            ensure_dir(self.project_settings_path.parent)
            if tomlkit is not None:
                self.project_settings_path.write_text(tomlkit.dumps(defaults), encoding="utf-8")
            else:
                # Fallback: try tomli_w, then manual write
                try:
                    from tomli_w import dumps as tomli_dumps
                    self.project_settings_path.write_text(tomli_dumps(defaults), encoding="utf-8")
                except ImportError:
                    # Last resort: write as JSON (not ideal but works)
                    write_json(self.project_settings_path.with_suffix(".json"), defaults)
            
        return f"Initialized {self.project_settings_path}"
    
    def get_paths(self) -> Dict[str, str]:
        """Returns paths of all settings layers."""
        return {
            "user": str(self.user_settings_path),
            "project": str(self.project_settings_path),
            "runtime": str(self.runtime_settings_path),
            "state_db": str(self.state_store.db_path)
        }
    
    def _record_to_state_store(self, settings: Dict[str, Any]) -> None:
        """Record settings to state store for persistence."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            with self.state_store.connect() as conn:
                # Record full settings snapshot
                conn.execute(
                    """INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)""",
                    ("effective", json.dumps(settings) if isinstance(settings, dict) else str(settings), now)
                )
                
                # Record individual settings
                conn.execute(
                    """INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)""",
                    ("default_mode", settings.get("default_mode"), now)
                )
                
                conn.commit()
        except Exception:
            pass
