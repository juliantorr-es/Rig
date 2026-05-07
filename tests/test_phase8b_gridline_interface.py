from __future__ import annotations

import ast
import json
from pathlib import Path

from rig_tools import tui_theme, tui_layout, tui_grid
from rig import commands_tui


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def test_semantic_tokens_and_css():
    assert tui_theme.SEMANTIC_COLORS
    assert tui_theme.STATUS_TOKENS
    assert tui_theme.RIG_GLOBAL_CSS
    for key, token in tui_theme.STATUS_TOKENS.items():
        assert set(token) >= {"label", "marker", "color"}
        assert token["color"] in tui_theme.SEMANTIC_COLORS
    for klass in (
        ".rig-shell",
        ".rig-topbar",
        ".rig-sidebar",
        ".rig-main",
        ".rig-evidence-rail",
        ".rig-chat",
        ".rig-panel",
        ".rig-panel-title",
        ".rig-metric",
        ".rig-metric-title",
        ".rig-metric-value",
        ".rig-status-success",
        ".rig-status-error",
        ".rig-status-warning",
        ".rig-status-info",
        ".rig-status-muted",
        ".rig-chat-input",
        ".rig-command-preview",
    ):
        assert klass in tui_theme.RIG_GLOBAL_CSS
    assert "layout: grid" in tui_theme.RIG_GLOBAL_CSS
    assert "border-radius" not in tui_theme.RIG_GLOBAL_CSS
    assert "box-shadow" not in tui_theme.RIG_GLOBAL_CSS
    assert "drop-shadow" not in tui_theme.RIG_GLOBAL_CSS


def test_layout_primitives_exist():
    assert hasattr(tui_layout, "RigPanel")
    assert hasattr(tui_layout, "RigSidebar")
    assert hasattr(tui_layout, "RigMainColumn")
    assert hasattr(tui_layout, "RigEvidenceRail")
    assert hasattr(tui_layout, "RigMetricWidget")
    assert hasattr(tui_layout, "RigCommandInput")


def test_metric_widget_is_reactive():
    widget = tui_layout.RigMetricWidget(title="Jobs", value="3", sublines=["ok"], status="success")
    assert widget.title == "Jobs"
    assert widget.value == "3"
    assert widget.status == "success"


def test_command_input_emits_message(monkeypatch):
    submitted = {}

    class Dummy:
        value = "/status"

        def post_message(self, message):
            submitted["message"] = message

    input_widget = tui_layout.RigCommandInput()
    input_widget.value = "/status"
    monkeypatch.setattr(input_widget, "post_message", Dummy().post_message)
    input_widget.submit_command()
    assert submitted["message"].raw_text == "/status"
    assert submitted["message"].command_kind == "slash"


def test_grid_module_is_cqrs_safe():
    banned = {
        "rig.commands_",
        "rig_tools.orchestration",
        "rig_tools.provider_credentials",
        "rig_tools.cloud_providers",
        "subprocess",
    }
    for path in (Path(tui_theme.__file__), Path(tui_layout.__file__), Path(tui_grid.__file__)):
        imports = _imports(path)
        assert not any(name.startswith("rig.commands_") for name in imports)
        assert "rig_tools.orchestration" not in imports
        assert "rig_tools.provider_credentials" not in imports
        assert "rig_tools.cloud_providers" not in imports
        assert "subprocess" not in imports


def test_grid_module_exports_shell():
    assert hasattr(tui_grid, "RigDashboardGrid")
    assert hasattr(tui_grid, "compose_sidebar")
    assert hasattr(tui_grid, "compose_main")
    assert hasattr(tui_grid, "compose_evidence_rail")
    assert hasattr(tui_grid, "compose_chat")


def test_tui_window_dry_run_uses_canonical_invocation(tmp_path, monkeypatch, capsys):
    class Helpers:
        repo_root = tmp_path

    class Args:
        safe = True
        action = False
        auto_approve = False
        yolo = False
        window = False
        dry_run = True
        mode = None
        refresh = 2

    rc = commands_tui._run(Helpers(), Args())
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"][1:4] == ["-m", "rig", "tui"]


def test_tui_window_alias_dry_run(monkeypatch, tmp_path):
    captured = {}

    def fake_open_window(repo_root, dry_run, host, port, browser, allow_lan):
        captured["repo_root"] = repo_root
        captured["dry_run"] = dry_run
        captured["host"] = host
        captured["browser"] = browser
        return {"status": "dry_run"}

    monkeypatch.setattr("rig_tools.window_launcher.open_window", fake_open_window)

    class Helpers:
        repo_root = tmp_path

    class Args:
        safe = True
        action = False
        auto_approve = False
        yolo = False
        window = True
        dry_run = True
        mode = None
        refresh = 2

    assert commands_tui._run(Helpers(), Args()) == 0
    assert captured["dry_run"] is True
    assert captured["browser"] is True
