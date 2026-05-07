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
        assert "workspace.command_progress" in projection.widgets

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

        progress = projection.widgets["workspace.command_progress"].data
        assert progress["command"] == ""
        assert progress["phase"] == "operation.log"
        assert progress["status"] == "unknown"


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
        assert payload["widgets"]["workspace.command_progress"]["type"] == "CommandProgressCard"


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


def test_progress_event_builder_has_required_fields():
    from rig.domain.progress_events import ALLOWED_PROGRESS_PHASES, build_progress_event

    event = build_progress_event(
        operation_id="op-123",
        command="workspace.refresh_projection",
        phase="operation.started",
        status="running",
        message="Refreshing workspace projection.",
        workspace_id="ws-1",
        sequence=1,
    )

    payload = event.to_dict()
    assert payload["event_id"]
    assert payload["operation_id"] == "op-123"
    assert payload["workspace_id"] == "ws-1"
    assert payload["command"] == "workspace.refresh_projection"
    assert payload["phase"] == "operation.started"
    assert payload["status"] == "running"
    assert payload["message"] == "Refreshing workspace projection."
    assert payload["timestamp"]
    assert payload["sequence"] == 1
    assert payload["receipt_candidate"] is False
    assert payload["receipt_kind"] is None
    assert payload["evidence_refs"] == []
    assert payload["metadata"] == {}
    assert "operation.completed" in ALLOWED_PROGRESS_PHASES


def test_progress_event_envelope_shape_is_stable():
    from rig.domain.progress_events import build_progress_event

    event = build_progress_event(
        operation_id="op-456",
        command="workspace.status",
        phase="operation.completed",
        status="completed",
        message="Workspace status read complete.",
        workspace_path="/tmp/workspace",
        sequence=2,
    )
    envelope = event.to_envelope()

    assert envelope["kind"] == "progress_event"
    assert envelope["event"]["operation_id"] == "op-456"
    assert envelope["event"]["command"] == "workspace.status"
    assert envelope["event"]["phase"] == "operation.completed"
    assert envelope["event"]["workspace_path"] == "/tmp/workspace"


def test_progress_events_do_not_define_receipt_authority():
    path = Path(__file__).parent.parent / "src" / "rig" / "domain" / "progress_events.py"
    content = path.read_text(encoding="utf-8")
    assert "get_receipt_store" not in content
    assert "receipt_candidate" in content
    assert "evidence_refs" in content


def test_ui_server_refresh_emits_progress_events():
    from rig_tools.ui_server import UIServer
    from rig.domain.intent_defs import Intent

    server = UIServer(Path(__file__).parent.parent, "test-token")
    emitted = []
    server._schedule_send = lambda msg: emitted.append(msg)  # type: ignore[method-assign]

    result = server.handle_refresh(Intent(kind="rig.intent.refresh_projection", intent_id="refresh-1", observed_projection_revision=1, client={"kind": "pywebview"}))

    assert result == {"accepted": True}
    kinds = [msg["kind"] for msg in emitted]
    assert kinds.count("progress_event") >= 4
    phases = [msg["event"]["phase"] for msg in emitted if msg["kind"] == "progress_event"]
    assert "operation.started" in phases
    assert "operation.progress" in phases
    assert "operation.completed" in phases
    assert "workspace.projection.refreshed" in phases


def test_ui_server_workspace_status_emits_progress_events():
    from rig_tools.ui_server import UIServer
    from rig.domain.intent_defs import Intent

    server = UIServer(Path(__file__).parent.parent, "test-token")
    emitted = []
    server._schedule_send = lambda msg: emitted.append(msg)  # type: ignore[method-assign]

    result = server.handle_workspace_status(
        Intent(kind="rig.intent.workspace_status", intent_id="status-1", observed_projection_revision=1, client={"kind": "pywebview"})
    )

    assert result == {"accepted": True}
    phases = [msg["event"]["phase"] for msg in emitted if msg["kind"] == "progress_event"]
    assert phases == ["operation.started", "operation.progress", "operation.completed"]
    commands = {msg["event"]["command"] for msg in emitted if msg["kind"] == "progress_event"}
    assert commands == {"workspace.status"}


def test_progress_event_builder_normalizes_metadata_and_lists():
    from rig.domain.progress_events import build_progress_event

    event = build_progress_event(
        operation_id="op-789",
        command="workspace.status",
        phase="operation.progress",
        status="running",
        message="Scanning workspace root.",
        metadata={"detail": "scan"},
        evidence_refs=None,
        sequence=3,
    )

    payload = event.to_dict()
    assert payload["receipt_candidate"] is False
    assert payload["evidence_refs"] == []
    assert payload["metadata"] == {"detail": "scan"}
    assert payload["sequence"] == 3


def test_static_index_loads_module_entrypoint_and_css():
    index_path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "index.html"
    content = index_path.read_text(encoding="utf-8")
    assert 'type="module"' in content
    assert '/static/js/main.js' in content
    assert '/static/css/main.css' in content
    assert 'boot-fallback' in content
    assert 'boot-status' in content


def test_static_module_paths_exist():
    repo_root = Path(__file__).parent.parent
    for rel in [
        "src/rig_tools/static/js/main.js",
        "src/rig_tools/static/js/app/runtime.js",
        "src/rig_tools/static/js/app/boot.js",
        "src/rig_tools/static/js/app/websocket.js",
        "src/rig_tools/static/js/app/projection-store.js",
        "src/rig_tools/static/js/app/intent-dispatch.js",
        "src/rig_tools/static/js/app/render-root.js",
        "src/rig_tools/static/js/app/logging.js",
        "src/rig_tools/static/js/widgets/registry.js",
        "src/rig_tools/static/js/widgets/empty-state-card.js",
        "src/rig_tools/static/js/widgets/workspace-header.js",
        "src/rig_tools/static/js/widgets/workspace-git-state.js",
        "src/rig_tools/static/js/widgets/workspace-lane-summary.js",
        "src/rig_tools/static/css/main.css",
        "src/rig_tools/static/css/layers.css",
        "src/rig_tools/static/css/tokens.css",
        "src/rig_tools/static/css/base.css",
        "src/rig_tools/static/css/layout.css",
        "src/rig_tools/static/css/widgets.css",
        "src/rig_tools/static/css/states.css",
        "src/rig_tools/static/css/utilities.css",
    ]:
        assert (repo_root / rel).exists(), rel


def test_runtime_js_is_compatibility_shim():
    runtime_path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "app" / "runtime.js"
    content = runtime_path.read_text(encoding="utf-8")
    assert "bootRigUI" in content
    assert "connectWebSocket" not in content
    assert "createIntentDispatcher" not in content
    assert "buildWidgetRegistry" not in content


def test_widget_registry_includes_workspace_renderers():
    registry_path = Path(__file__).parent.parent / "src" / "rig_tools" / "static" / "js" / "widgets" / "registry.js"
    content = registry_path.read_text(encoding="utf-8")
    assert "WorkspaceHeader" in content
    assert "WorkspaceGitState" in content
    assert "WorkspaceLaneSummary" in content
    assert "CommandProgressCard" in content
    assert "_fallback" in content
