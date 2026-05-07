from __future__ import annotations

import json
from pathlib import Path

from rig_tools import release_check
from rig import commands_release


def test_release_check_json_shape(monkeypatch, capsys, tmp_path):
    class Report:
        status = "pass"

        def to_dict(self):
            return {
                "schema_version": "rig.release_readiness.v2",
                "report_id": "release-1",
                "created_at": "2026-05-06T00:00:00Z",
                "status": "pass",
                "checks": [
                    {
                        "id": "python",
                        "category": "environment",
                        "status": "pass",
                        "message": "ok",
                        "details": {},
                        "blocking": False,
                        "next_action": "",
                    }
                ],
                "warnings": [],
                "failures": [],
                "authoritative": True,
            }

    monkeypatch.setattr("rig_tools.release_check.run_release_check", lambda repo_root: Report())

    class Helpers:
        repo_root = tmp_path

    class Args:
        json = True

    assert commands_release._check(Helpers(), Args()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "rig.release_readiness.v2"
    assert payload["checks"][0]["category"] == "environment"


def test_release_check_blocks_on_fail(monkeypatch, tmp_path):
    class Report:
        status = "fail"

        def to_dict(self):
            return {"status": "fail", "checks": [], "warnings": [], "failures": []}

    monkeypatch.setattr("rig_tools.release_check.run_release_check", lambda repo_root: Report())

    class Helpers:
        repo_root = tmp_path

    class Args:
        json = False

    assert commands_release._check(Helpers(), Args()) == 1


def test_release_check_python_guard(monkeypatch, tmp_path):
    monkeypatch.setattr(release_check.sys, "version_info", (3, 13, 0))
    report = release_check.run_release_check(tmp_path)
    assert report.status == "fail"
    assert report.checks[0].id == "python"


def test_release_contract_file_exists():
    assert Path("docs/dev/rig/public_command_contract.json").exists()

