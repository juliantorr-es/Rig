from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CredentialResult:
    status: str
    credential_ref: str | None
    message: str


def _service_name(provider_id: str, name: str) -> str:
    return f"rig/providers/{provider_id}/{name}"


def keychain_available() -> bool:
    return subprocess.run(["which", "security"], capture_output=True, text=True, check=False).returncode == 0


def store_secret(provider_id: str, name: str, secret: str) -> CredentialResult:
    if not keychain_available():
        return CredentialResult("failed", None, "macOS Keychain unavailable")
    service = _service_name(provider_id, name)
    proc = subprocess.run(["security", "add-generic-password", "-U", "-a", provider_id, "-s", service, "-w", secret], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return CredentialResult("failed", None, proc.stderr.strip() or "failed to store secret")
    return CredentialResult("stored", f"keychain://{service}", "stored")


def read_secret(provider_id: str, name: str) -> CredentialResult:
    if not keychain_available():
        return CredentialResult("failed", None, "macOS Keychain unavailable")
    service = _service_name(provider_id, name)
    proc = subprocess.run(["security", "find-generic-password", "-a", provider_id, "-s", service, "-w"], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return CredentialResult("missing", None, proc.stderr.strip() or "missing")
    return CredentialResult("found", f"keychain://{service}", proc.stdout.strip())


def delete_secret(provider_id: str, name: str) -> CredentialResult:
    if not keychain_available():
        return CredentialResult("failed", None, "macOS Keychain unavailable")
    service = _service_name(provider_id, name)
    proc = subprocess.run(["security", "delete-generic-password", "-a", provider_id, "-s", service], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return CredentialResult("failed", None, proc.stderr.strip() or "failed to delete secret")
    return CredentialResult("deleted", f"keychain://{service}", "deleted")

