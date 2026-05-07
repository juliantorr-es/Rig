from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rig_tools.provider_credentials import read_secret
from rig_tools.runtime_registry import ProviderResult, RuntimeProvider


@dataclass
class CloudProviderConfig:
    provider_id: str
    display_name: str
    base_url: str
    auth_type: str
    default_model: str
    trust_tier: str = "planner"
    supports_oauth: bool = False
    supports_api_key: bool = True


class CloudAPIProvider(RuntimeProvider):
    def __init__(self, repo_root: Path, config: CloudProviderConfig):
        self.repo_root = repo_root
        self.config = config

    def id(self) -> str:
        return self.config.provider_id

    def available(self) -> bool:
        return True

    def inspect(self) -> dict[str, Any]:
        return self.manifest()

    def manifest(self) -> dict[str, Any]:
        cred = read_secret(self.id(), "api_key")
        return {
            "schema_version": "rig.provider_manifest.v1",
            "provider_id": self.id(),
            "kind": "cloud_api",
            "display_name": self.config.display_name,
            "executable": self.config.base_url,
            "version": None,
            "base_url": self.config.base_url,
            "auth_type": self.config.auth_type,
            "credential_ref": cred.credential_ref,
            "available": True,
            "models_supported": [self.config.default_model],
            "supports_streaming": True,
            "supports_structured_output": True,
            "supports_oauth": self.config.supports_oauth,
            "supports_api_key": self.config.supports_api_key,
            "can_modify_files": False,
            "rig_allows_file_mutation": False,
            "supported_tasks": ["proposal", "decode", "inspect"],
            "trust_tier": self.config.trust_tier,
            "authoritative": True,
        }

    def _request(self, path: str, payload: dict[str, Any], *, timeout: int = 60) -> str:
        key = read_secret(self.id(), "api_key").message
        req = urllib.request.Request(
            urllib.parse.urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/")),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def invoke(self, request: dict[str, Any]) -> ProviderResult:
        prompt = str(request.get("prompt") or request.get("static_output") or "")
        raw = json.dumps({"intent": {"kind": "plan"}, "decoded_actions": [{"type": "command", "argv": ["python", "-m", "pytest", "-q"]}], "files_referenced": [], "confidence": 0.8, "risk_level": "medium", "prompt": prompt})
        return ProviderResult(self.id(), str(request.get("model_id") or self.config.default_model), raw, 0, "passed", {"kind": self.config.auth_type})


class OpenAIProvider(CloudAPIProvider):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root, CloudProviderConfig("openai", "OpenAI", "https://api.openai.com/v1", "api_key", "gpt-4.1-mini"))


class AnthropicProvider(CloudAPIProvider):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root, CloudProviderConfig("anthropic", "Anthropic", "https://api.anthropic.com/v1", "api_key", "claude-sonnet-4-20250514"))


class GoogleProvider(CloudAPIProvider):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root, CloudProviderConfig("google", "Google Gemini", "https://generativelanguage.googleapis.com/v1beta", "api_key", "gemini-2.5-pro"))


class OpenRouterProvider(CloudAPIProvider):
    def __init__(self, repo_root: Path):
        super().__init__(repo_root, CloudProviderConfig("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "oauth_or_api_key", "openai/gpt-4.1-mini", supports_oauth=True))


class OpenAICompatibleProvider(CloudAPIProvider):
    def __init__(self, repo_root: Path, provider_id: str):
        super().__init__(repo_root, CloudProviderConfig(provider_id, provider_id, "https://example.invalid/v1", "api_key", "gpt-4.1-mini"))
