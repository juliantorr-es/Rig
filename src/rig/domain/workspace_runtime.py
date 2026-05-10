from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "rig.workspace_runtime.v1"


def _workspace_id(worktree_root: Path, lane_name: str) -> str:
    digest = hashlib.sha256(f"{worktree_root.resolve()}|{lane_name}".encode("utf-8")).hexdigest()
    return f"ws_{digest[:16]}"


@dataclass(frozen=True, slots=True)
class WorkspaceRuntime:
    repo_root: Path
    lane_name: str
    worktree_root: Path | None = None
    schema_version: str = SCHEMA_VERSION
    workspace_id: str = field(init=False)
    worktree_path: Path = field(init=False)
    rig_root: Path = field(init=False)
    replay_namespace: str = field(init=False)
    artifact_namespace: str = field(init=False)
    runtime_namespace: str = field(init=False)
    lifecycle_state: str = "planned"

    def __post_init__(self) -> None:
        root = self.worktree_root or (self.repo_root / ".rig" / "worktrees")
        object.__setattr__(self, "worktree_root", root)
        object.__setattr__(self, "workspace_id", _workspace_id(root, self.lane_name))
        object.__setattr__(self, "worktree_path", root / self.lane_name)
        object.__setattr__(self, "rig_root", self.repo_root / ".rig")
        object.__setattr__(self, "replay_namespace", f"replay/{self.workspace_id}")
        object.__setattr__(self, "artifact_namespace", f"artifacts/{self.workspace_id}")
        object.__setattr__(self, "runtime_namespace", f"runtime/{self.workspace_id}")

