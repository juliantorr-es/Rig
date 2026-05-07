from __future__ import annotations

from pathlib import Path
from typing import Any

from rig_tools.cloud_providers import AnthropicProvider, GoogleProvider, OpenAICompatibleProvider, OpenAIProvider, OpenRouterProvider, CloudAPIProvider
from rig_tools.provider_credentials import keychain_available
from rig_tools.runtime_registry import CustomCommandProvider, GeminiCLIProvider, RuntimeProvider


def _providers(repo_root: Path) -> list[RuntimeProvider]:
    return [
        CustomCommandProvider(repo_root),
        GeminiCLIProvider(repo_root),
        OpenAIProvider(repo_root),
        AnthropicProvider(repo_root),
        GoogleProvider(repo_root),
        OpenRouterProvider(repo_root),
        OpenAICompatibleProvider(repo_root, "deepseek"),
        OpenAICompatibleProvider(repo_root, "zai"),
        OpenAICompatibleProvider(repo_root, "custom-openai-compatible"),
    ]


def list_providers(repo_root: Path) -> list[dict[str, Any]]:
    return [provider.manifest() for provider in _providers(repo_root)]


def inspect_provider(repo_root: Path, provider_id: str) -> dict[str, Any]:
    for provider in _providers(repo_root):
        if provider.id() == provider_id:
            manifest = provider.manifest()
            manifest["keychain_available"] = keychain_available()
            return manifest
    return {"status": "missing", "provider_id": provider_id}


def provider_for_id(repo_root: Path, provider_id: str) -> RuntimeProvider:
    for provider in _providers(repo_root):
        if provider.id() == provider_id:
            return provider
    raise KeyError(provider_id)
