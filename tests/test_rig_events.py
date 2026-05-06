#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "rig.py"


def run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=REPO_ROOT, text=True, input=input_text, capture_output=True, check=False)


def main() -> int:
    json_result = run("--json", "affected", "summary", "--task", "td-cleanup-005")
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["schema_version"] == "rig.result.v1"
    assert payload["status"] == "passed"
    assert (REPO_ROOT / ".build" / "rig" / "results" / "latest.json").exists()

    jsonl_result = run("--jsonl", "git", "status")
    assert jsonl_result.returncode == 0, jsonl_result.stderr
    lines = [line for line in jsonl_result.stdout.splitlines() if line.strip()]
    assert lines, jsonl_result.stdout
    events = [json.loads(line) for line in lines[:-1]]
    result = json.loads(lines[-1])
    assert any(evt["event_type"] == "run_started" for evt in events), events
    assert any(evt["event_type"] == "run_finished" for evt in events), events
    assert result["schema_version"] == "rig.result.v1"

    agent_result = run("--agent", "affected", "profiles", "--task", "td-cleanup-005", input_text=(REPO_ROOT / "scripts" / "fixtures" / "affected" / "docs_scripts_change.txt").read_text(encoding="utf-8"))
    assert agent_result.returncode == 0, agent_result.stderr
    agent_lines = [line for line in agent_result.stdout.splitlines() if line.strip()]
    assert json.loads(agent_lines[-1])["schema_version"] == "rig.result.v1"

    docs_profiles = run("affected", "profiles", "--task", "td-cleanup-005", "--stdin", input_text=(REPO_ROOT / "scripts" / "fixtures" / "affected" / "docs_scripts_change.txt").read_text(encoding="utf-8"))
    assert docs_profiles.returncode == 0, docs_profiles.stderr
    docs_payload = json.loads((REPO_ROOT / docs_profiles.stdout.strip().splitlines()[0]).read_text(encoding="utf-8"))
    assert "local-fast" in docs_payload["recommended_profiles"], docs_payload
    assert "daemon-runtime" not in docs_payload["recommended_profiles"], docs_payload

    daemon_profiles = run("affected", "profiles", "--task", "td-cleanup-005", "--stdin", input_text=(REPO_ROOT / "scripts" / "fixtures" / "affected" / "daemon_core_change.txt").read_text(encoding="utf-8"))
    assert daemon_profiles.returncode == 0, daemon_profiles.stderr
    daemon_payload = json.loads((REPO_ROOT / daemon_profiles.stdout.strip().splitlines()[0]).read_text(encoding="utf-8"))
    assert "daemon-runtime" in daemon_payload["recommended_profiles"], daemon_payload
    assert "cleanup-review" in daemon_payload["recommended_profiles"], daemon_payload

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
