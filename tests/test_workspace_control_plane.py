from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Rig Test"], check=True, capture_output=True, text=True)
    (path / "README.md").write_text("rig\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], check=True, capture_output=True, text=True)


def _helpers(repo_root: Path):
    return SimpleNamespace(repo_root=repo_root)


def test_build_projection_includes_workspace_placeholder_widgets():
    from rig.domain.projection_builder import build_projection

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        _init_git_repo(repo_root)

        projection = build_projection(repo_root, revision=1, chat_history=None)

        assert "workspace.header" in projection.widgets
        assert "workspace.git_state" in projection.widgets
        assert "workspace.lane_summary" in projection.widgets

        header = projection.widgets["workspace.header"].data
        assert header["repo_root"] == str(repo_root)
        assert header["authority_label"].startswith("Workspace control plane")

        git_state = projection.widgets["workspace.git_state"].data
        assert git_state["branch"] == "main"
        assert git_state["dirty"] is False
        assert git_state["safe_to_commit"] is False

        lane_summary = projection.widgets["workspace.lane_summary"].data
        assert lane_summary["status"] == "not_connected"
        assert "not connected" in lane_summary["message"].lower()
        assert "rig_agent_worktree.py" in lane_summary["next_action"]


def test_workspace_commands_report_planned_control_plane():
    from rig import commands_workspace

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        _init_git_repo(repo_root)
        helpers = _helpers(repo_root)

        assert commands_workspace.status(helpers) == 0
        assert commands_workspace.lanes(helpers) == 0
        assert commands_workspace.projection(helpers) == 0
        assert commands_workspace.receipts(helpers) == 0
        assert commands_workspace.recommend(helpers) == 0


def test_workspace_status_and_lanes_are_planned_placeholders(capsys):
    from rig import commands_workspace

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        _init_git_repo(repo_root)
        helpers = _helpers(repo_root)

        commands_workspace.status(helpers)
        status_payload = json.loads(capsys.readouterr().out)
        assert status_payload["control_plane"] == "planned"
        assert status_payload["agent_lane_registry"] == "not_connected"
        assert status_payload["current_branch"] == "main"

        commands_workspace.lanes(helpers)
        lanes_payload = json.loads(capsys.readouterr().out)
        assert lanes_payload["message"].startswith("Workspace lane integration is not connected")
        assert lanes_payload["workspaces"] == []


def test_workspace_projection_command_mentions_placeholder_widget_types(capsys):
    from rig import commands_workspace

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        _init_git_repo(repo_root)
        commands_workspace.projection(_helpers(repo_root))
        out = capsys.readouterr().out
        payload = json.loads(out)

        assert payload["message"].startswith("Workspace projection is currently")
        assert "workspace.header" in payload["widgets"]
        assert payload["widgets"]["workspace.lane_summary"]["type"] == "WorkspaceLaneSummary"


def test_workspace_recommend_is_read_only(capsys):
    from rig import commands_workspace

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        _init_git_repo(repo_root)
        commands_workspace.recommend(_helpers(repo_root))
        out = capsys.readouterr().out
        payload = json.loads(out)

        assert payload["recommended_path"] == "review"
        assert payload["ready"] is False
        assert "not connected" in payload["rationale"].lower()
        assert payload["next_safe_action"].startswith("Review governed agent lane docs")
