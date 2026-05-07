from __future__ import annotations

import json
from pathlib import Path

from rig_tools import release_check
from rig import commands_release


def test_release_docs_and_scripts_exist():
    repo = Path.cwd()
    for path in [
        repo / "CHANGELOG.md",
        repo / "SECURITY.md",
        repo / "SUPPORT.md",
        repo / "CONTRIBUTING.md",
        repo / "docs" / "release" / "RELEASE_CHECKLIST.md",
        repo / "docs" / "release" / "PUBLIC_ALPHA_CRITERIA.md",
        repo / "docs" / "release" / "KNOWN_LIMITATIONS.md",
        repo / "docs" / "dev" / "rig" / "PUBLIC_COMMAND_CONTRACT.md",
        repo / "docs" / "dev" / "rig" / "public_command_contract.json",
        repo / "docs" / "dev" / "rig" / "SCAFFOLDING_INVENTORY.md",
        repo / "docs" / "dev" / "rig" / "DEBUG_BUNDLE_CONTRACT.md",
        repo / "scripts" / "release" / "smoke_install.py",
        repo / "scripts" / "release" / "check_public_commands.py",
        repo / "scripts" / "release" / "check_readme_commands.py",
        repo / "scripts" / "release" / "check_release.py",
        repo / "scripts" / "release" / "demo_first_run.sh",
        repo / ".github" / "workflows" / "test.yml",
        repo / ".github" / "workflows" / "release-check.yml",
        repo / ".github" / "workflows" / "docs.yml",
        repo / ".github" / "workflows" / "publish.yml.disabled",
    ]:
        assert path.exists()


def test_public_command_contract_matches_readme():
    readme = Path("README.md").read_text(encoding="utf-8")
    for item in ["rig init", "rig tui", "rig run --task", "rig debug bundle"]:
        assert item in readme


def test_release_readiness_json():
    report = release_check.run_release_check(Path.cwd())
    payload = report.to_dict()
    assert payload["schema_version"] == "rig.release_readiness.v2"
    assert "checks" in payload


def test_release_command_registers():
    assert hasattr(commands_release, "register")


def test_release_check_json(monkeypatch, capsys, tmp_path):
    class Helpers:
        repo_root = tmp_path

    class Report:
        status = "pass"
        def to_dict(self):
            return {"status": "pass", "checks": []}

    monkeypatch.setattr("rig_tools.release_check.run_release_check", lambda *args, **kwargs: Report())

    class Args:
        json = True

    assert commands_release._check(Helpers(), Args()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "pass"
