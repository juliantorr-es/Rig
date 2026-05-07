from __future__ import annotations

from pathlib import Path

from rig_tools.tui_actions import ActionRegistry
from rig_tools.tui_snapshot import load_snapshot
from rig_tools.tui_slash_commands import parse_slash_command


def test_product_tui_commands_do_not_use_scripts_wrapper(tmp_path: Path) -> None:
    registry = ActionRegistry(tmp_path)
    for action in registry.actions.values():
        assert "scripts/rig.py" not in " ".join(action.argv_template)


def test_tui_snapshot_is_read_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    snapshot = load_snapshot(repo)
    assert snapshot["queue"]["using_canonical_jobs"] is True
    assert not (repo / ".build" / "rig" / "jobs" / ".lock").exists()

