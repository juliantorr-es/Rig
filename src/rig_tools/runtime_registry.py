from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from rig_tools.contracts import CommandPlan, CommandSafety


TRUST_TIERS = ["blocked", "advisory", "reviewer", "planner", "executor_candidate", "validator"]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class ProviderResult:
    provider_id: str
    model_id: str
    raw_output: str
    exit_code: int
    status: str
    metadata: dict[str, Any]


class RuntimeProvider:
    def id(self) -> str: raise NotImplementedError
    def inspect(self) -> dict[str, Any]: raise NotImplementedError
    def available(self) -> bool: raise NotImplementedError
    def manifest(self) -> dict[str, Any]: raise NotImplementedError
    def invoke(self, request: dict[str, Any]) -> ProviderResult: raise NotImplementedError


class CustomCommandProvider(RuntimeProvider):
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def id(self) -> str:
        return "custom-command"

    def available(self) -> bool:
        return True

    def inspect(self) -> dict[str, Any]:
        return self.manifest()

    def manifest(self) -> dict[str, Any]:
        return {
            "schema_version": "rig.runtime_manifest.v1",
            "provider_id": self.id(),
            "kind": "custom",
            "executable": "built-in",
            "version": "1",
            "offline_capable": True,
            "supports_streaming": False,
            "supports_structured_output": True,
            "can_modify_files": False,
            "rig_allows_file_mutation": False,
            "supported_tasks": ["proposal", "decode", "inspect"],
            "trust_tier": "planner",
            "authoritative": True,
        }

    def invoke(self, request: dict[str, Any]) -> ProviderResult:
        raw = request.get("static_output") or request.get("prompt") or "{}"
        return ProviderResult(self.id(), str(request.get("model_id") or "custom-static"), str(raw), 0, "passed", {"static": True})


class GeminiCLIProvider(RuntimeProvider):
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def id(self) -> str:
        return "gemini-cli"

    def available(self) -> bool:
        return shutil.which("gemini") is not None

    def inspect(self) -> dict[str, Any]:
        return self.manifest()

    def manifest(self) -> dict[str, Any]:
        return {
            "schema_version": "rig.runtime_manifest.v1",
            "provider_id": self.id(),
            "kind": "cli",
            "executable": "gemini",
            "version": None,
            "offline_capable": False,
            "supports_streaming": True,
            "supports_structured_output": False,
            "can_modify_files": False,
            "rig_allows_file_mutation": False,
            "supported_tasks": ["proposal", "review", "decode"],
            "trust_tier": "advisory",
            "authoritative": True,
        }

    def invoke(self, request: dict[str, Any]) -> ProviderResult:
        prompt = str(request.get("prompt") or "")
        proc = subprocess.run(["gemini", "-p", prompt, "--output-format", "stream-json"], cwd=self.repo_root, text=True, capture_output=True, check=False, timeout=int(request.get("timeout_seconds") or 60))
        return ProviderResult(self.id(), str(request.get("model_id") or "gemini"), (proc.stdout or "") + (proc.stderr or ""), proc.returncode, "passed" if proc.returncode == 0 else "failed", {"structured_output": False})


def provider_for_id(repo_root: Path, provider_id: str) -> RuntimeProvider:
    if provider_id == "custom-command":
        return CustomCommandProvider(repo_root)
    if provider_id == "gemini-cli":
        return GeminiCLIProvider(repo_root)
    raise KeyError(provider_id)


def runtime_manifests(repo_root: Path) -> list[dict[str, Any]]:
    return [provider_for_id(repo_root, pid).manifest() for pid in ["custom-command", "gemini-cli"]]


def inspect_manifest(repo_root: Path, provider_id: str) -> dict[str, Any]:
    return provider_for_id(repo_root, provider_id).manifest()

