from __future__ import annotations

import os
import json
try:
    import tomli
except Exception:  # pragma: no cover - fallback for Python 3.11+
    import tomllib as tomli

try:
    import tomlkit
except Exception:  # pragma: no cover - fallback when tomlkit is unavailable
    class _TOMLKitFallback:
        @staticmethod
        def dumps(data: Dict[str, Any]) -> str:
            lines: list[str] = []

            def render_value(value: Any) -> str:
                if isinstance(value, bool):
                    return "true" if value else "false"
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return str(value)
                if value is None:
                    return '""'
                if isinstance(value, str):
                    return json.dumps(value)
                if isinstance(value, list):
                    return "[" + ", ".join(render_value(item) for item in value) + "]"
                return json.dumps(value)

            def emit_table(prefix: str, table: Dict[str, Any]) -> None:
                scalars: Dict[str, Any] = {}
                nested: Dict[str, Dict[str, Any]] = {}
                for key, value in table.items():
                    if isinstance(value, dict):
                        nested[key] = value
                    else:
                        scalars[key] = value
                if prefix:
                    lines.append(f"[{prefix}]")
                for key, value in scalars.items():
                    lines.append(f"{key} = {render_value(value)}")
                for key, value in nested.items():
                    if lines and lines[-1] != "":
                        lines.append("")
                    emit_table(f"{prefix}.{key}" if prefix else key, value)

            emit_table("", data)
            return "\n".join(line for line in lines if line is not None) + "\n"

    tomlkit = _TOMLKitFallback()  # type: ignore[assignment]
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from rig_tools.state_store import StateStore

class SettingsStore:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.schema_version = "rig.settings.v1"
        self.state_store = StateStore(repo_root)
        
        # Paths
        self.user_config_dir = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "rig"
        self.user_settings_path = self.user_config_dir / "settings.toml"
        self.project_settings_path = self.repo_root / ".rig" / "settings.toml"
        self.runtime_settings_path = self.repo_root / ".build" / "rig" / "tui" / "settings.json"

    def get_defaults(self) -> Dict[str, Any]:
        """Returns built-in default settings."""
        return {
            "schema_version": self.schema_version,
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

    def get_user_settings(self) -> Dict[str, Any]:
        """Loads settings from user home directory."""
        return self._load_toml(self.user_settings_path)

    def get_project_settings(self) -> Dict[str, Any]:
        """Loads settings from project directory."""
        return self._load_toml(self.project_settings_path)

    def get_runtime_settings(self) -> Dict[str, Any]:
        """Loads settings from runtime build directory."""
        if self.runtime_settings_path.exists():
            try:
                return json.loads(self.runtime_settings_path.read_text(encoding="utf-8"))
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
                
                self._set_nested(overrides, setting_key, val)
        return overrides

    def get_effective_settings(self) -> Dict[str, Any]:
        """Merges all layers of settings with correct precedence."""
        settings = self.get_defaults()
        
        # Merge layers
        self._deep_merge(settings, self.get_user_settings())
        self._deep_merge(settings, self.get_project_settings())
        self._deep_merge(settings, self.get_runtime_settings())
        self._deep_merge(settings, self.get_env_overrides())
        
        # Record to state store if initialized
        self._record_to_state_store(settings)
        
        return settings

    def set_setting(self, key: str, value: Any, layer: Literal["user", "project", "runtime"] = "project", dry_run: bool = False):
        """Updates a setting in a specific layer."""
        if layer == "user":
            path = self.user_settings_path
        elif layer == "runtime":
            path = self.runtime_settings_path
        else:
            path = self.project_settings_path
            
        data = self._load_toml(path) if not str(path).endswith(".json") else self.get_runtime_settings()
        self._set_nested(data, key, value)
        
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            if str(path).endswith(".json"):
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            else:
                path.write_text(tomlkit.dumps(data), encoding="utf-8")
                
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
            self.project_settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.project_settings_path.write_text(tomlkit.dumps(defaults), encoding="utf-8")
            
        return f"Initialized {self.project_settings_path}"

    def get_paths(self) -> Dict[str, str]:
        """Returns paths of all settings layers."""
        return {
            "user": str(self.user_settings_path),
            "project": str(self.project_settings_path),
            "runtime": str(self.runtime_settings_path),
            "state_db": str(self.state_store.db_path)
        }

    def _load_toml(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            try:
                return tomli.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _set_nested(self, data: Dict[str, Any], key: str, value: Any):
        parts = key.split(".")
        for part in parts[:-1]:
            data = data.setdefault(part, {})
        data[parts[-1]] = value

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]):
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v

    def _record_to_state_store(self, settings: Dict[str, Any]):
        try:
            # Flatten some settings for SQLite table
            # key, value, updated_at
            now = datetime.now(timezone.utc).isoformat()
            with self.state_store.connect() as conn:
                # We record a snapshot of the full settings as a single key 'effective'
                # and also granular ones
                conn.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, ("effective", json.dumps(settings), now))
                
                conn.execute("""
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, ("default_mode", settings.get("default_mode"), now))
                
                conn.commit()
        except Exception:
            pass
