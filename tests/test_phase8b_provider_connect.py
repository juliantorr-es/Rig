from __future__ import annotations

import json
from pathlib import Path

from rig_tools import context_budget, provider_registry, schema_validation
from rig_tools import provider_credentials
from rig import commands_provider

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_provider_commands_registered() -> None:
    manifests = provider_registry.list_providers(REPO_ROOT)
    provider_ids = {item["provider_id"] for item in manifests}
    assert {"openai", "anthropic", "google", "openrouter", "deepseek", "zai", "custom-openai-compatible"}.issubset(provider_ids)


def test_provider_manifest_schema_validates(tmp_path: Path) -> None:
    manifest = provider_registry.inspect_provider(REPO_ROOT, "openai")
    repo = tmp_path / "repo"
    (repo / "Docs" / "schemas").mkdir(parents=True, exist_ok=True)
    (repo / "Docs" / "schemas" / "rig.provider_manifest.v1.schema.json").write_text((REPO_ROOT / "docs" / "schemas" / "rig.provider_manifest.v1.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
    path = repo / "provider.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = schema_validation.validate_artifacts(repo, artifact_path=str(path), family="rig.provider_manifest.v1")
    assert result.status == "passed"


def test_context_packet_schema_validates(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".build" / "rig" / "workspaces").mkdir(parents=True, exist_ok=True)
    ws = {
        "workspace_id": "abc",
        "repo_root": str(repo),
        "task": "demo",
        "branch": "rig/demo",
        "base_commit": "base",
        "worktree_path": str(repo),
        "status": "planned",
        "status_history": [],
        "receipt_paths": [],
        "authoritative": True,
    }
    (repo / ".build" / "rig" / "workspaces" / "abc.json").write_text(json.dumps(ws), encoding="utf-8")
    (repo / "Docs" / "schemas").mkdir(parents=True, exist_ok=True)
    (repo / "Docs" / "schemas" / "rig.context_packet.v1.schema.json").write_text((REPO_ROOT / "docs" / "schemas" / "rig.context_packet.v1.schema.json").read_text(encoding="utf-8"), encoding="utf-8")
    packet = context_budget.build_context_packet(repo, workspace_id="abc", provider_id="openai", model_id="gpt-4.1-mini")
    packet_path = repo / ".build" / "rig" / "context" / f"{packet['packet_id']}.json"
    result = schema_validation.validate_artifacts(repo, artifact_path=str(packet_path), family="rig.context_packet.v1")
    assert result.status == "passed"


def test_provider_connect_redacts_secret(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(provider_credentials, "keychain_available", lambda: True)
    monkeypatch.setattr(provider_credentials.subprocess, "run", lambda *args, **kwargs: type("P", (), {"returncode": 0, "stderr": "", "stdout": ""})())
    result = commands_provider._connect(tmp_path, "openai", "sk-test-123")
    assert result == 0
    out = capsys.readouterr().out
    assert "sk-test-123" not in out
