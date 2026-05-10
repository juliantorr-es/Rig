from __future__ import annotations

from pathlib import Path

from rig.domain.workspace_runtime import WorkspaceRuntime


def test_workspace_runtime_namespaces_are_deterministic(tmp_path: Path) -> None:
    runtime = WorkspaceRuntime(repo_root=tmp_path, lane_name="lane-a")
    again = WorkspaceRuntime(repo_root=tmp_path, lane_name="lane-a")
    assert runtime.workspace_id == again.workspace_id
    assert runtime.replay_namespace.startswith("replay/")
    assert runtime.artifact_namespace.startswith("artifacts/")
    assert runtime.runtime_namespace.startswith("runtime/")

