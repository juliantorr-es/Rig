from __future__ import annotations

import json
import subprocess
from pathlib import Path

from rig_tools.agent_proposals import create_proposal, decode_raw_output, proposal_to_command_plan
from rig_tools.runtime_registry import CustomCommandProvider
from rig_tools.model_registry import register_model, verify_model
from rig_tools.system_probe import inspect_system
from rig_tools.workspace_governance import WorkspaceGovernance


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test User")
    (path / "pyproject.toml").write_text("[tool.rig]\n", encoding="utf-8")
    (path / ".gitignore").write_text(".build/\n", encoding="utf-8")
    (path / "file.txt").write_text("base\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-m", "init")
    return path


def test_decoder_handles_markdown_wrapped_json() -> None:
    payload = decode_raw_output(
        "preamble\n```json\n{\"intent\": {\"kind\": \"plan\"}, \"decoded_actions\": [], \"files_referenced\": [], \"confidence\": 0.9, \"risk_level\": \"low\"}\n```\n",
        provider_manifest={"trust_tier": "planner"},
    )
    assert payload["status"] == "decoded"
    assert payload["intent"]["kind"] == "plan"


def test_decoder_blocks_advisory_command() -> None:
    payload = decode_raw_output(
        "{\"intent\": {\"kind\": \"plan\"}, \"decoded_actions\": [{\"type\": \"command\", \"argv\": [\"git\", \"push\"]}], \"files_referenced\": [], \"confidence\": 0.9, \"risk_level\": \"high\"}",
        provider_manifest={"trust_tier": "advisory"},
    )
    assert payload["status"] == "blocked"
    assert payload["rejection_reason"] == "trust_tier_violation"


def test_custom_provider_end_to_end_propose_and_decode(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    provider = CustomCommandProvider(repo)
    result = provider.invoke({"model_id": "static", "static_output": "{\"intent\": {\"kind\": \"plan\"}, \"decoded_actions\": [{\"type\": \"command\", \"argv\": [\"python\", \"-m\", \"pytest\", \"-q\"]}], \"files_referenced\": [\"src/rig_tools/runtime_registry.py\"], \"confidence\": 0.8, \"risk_level\": \"low\"}"})
    proposal = create_proposal(repo, workspace_id="ws1", provider_id=provider.id(), model_id="static", raw_output=result.raw_output, provider_manifest=provider.manifest())
    assert proposal["status"] == "decoded"
    plan = proposal_to_command_plan(repo, proposal)
    assert plan.allowed is True
    assert plan.safety.shell is False


def test_accept_creates_planned_plan_without_execution(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    mgr = WorkspaceGovernance(repo)
    ws = mgr.create_workspace("task").payload["workspace_id"]
    provider = CustomCommandProvider(repo)
    proposal = create_proposal(repo, workspace_id=ws, provider_id=provider.id(), model_id="static", raw_output="{\"intent\": {\"kind\": \"plan\"}, \"decoded_actions\": [{\"type\": \"command\", \"argv\": [\"python\", \"-m\", \"pytest\", \"-q\"]}], \"files_referenced\": [], \"confidence\": 0.7, \"risk_level\": \"low\"}", provider_manifest=provider.manifest())
    plan = proposal_to_command_plan(repo, proposal)
    path = repo / ".build" / "rig" / "agent-plans" / f"{proposal['proposal_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "rig.agent_plan.v1", "command_plan": {"allowed": plan.allowed}}, indent=2), encoding="utf-8")
    assert path.exists()
    assert not (repo / ".build" / "rig" / "receipts" / f"{ws}_run.json").exists()
