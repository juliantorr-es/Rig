from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "rig.action.v1"


@dataclass
class ActionManifestResult:
    action_id: str
    manifest_path: Path
    latest_path: Path
    manifest: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_rel(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def _tool_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": None, "git": None, "mlx": None, "mlx_lm": None}
    versions["python"] = sys.executable
    try:
        out = subprocess.run(["python3", "--version"], capture_output=True, text=True, check=False)
        versions["python"] = (out.stdout or out.stderr).strip() or versions["python"]
    except Exception:
        pass
    try:
        out = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
        versions["git"] = (out.stdout or out.stderr).strip() or None
    except Exception:
        pass
    try:
        import mlx  # type: ignore

        versions["mlx"] = getattr(mlx, "__version__", None)
    except Exception:
        pass
    try:
        import mlx_lm  # type: ignore

        versions["mlx_lm"] = getattr(mlx_lm, "__version__", None)
    except Exception:
        pass
    return versions


def _environment_fingerprint(repo_root: Path) -> dict[str, Any]:
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=False)
    branch = subprocess.run(["git", "branch", "--show-current"], cwd=repo_root, capture_output=True, text=True, check=False)
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=repo_root, capture_output=True, text=True, check=False)
    return {
        "repo_root": str(repo_root),
        "git_head": (git.stdout or git.stderr).strip() or None,
        "git_branch": (branch.stdout or branch.stderr).strip() or None,
        "git_dirty": bool((status.stdout or "").strip()),
        "python_executable": sys.executable,
    }


def _normalize_io(repo_root: Path, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        path = item.get("path")
        if isinstance(path, str):
            abs_path = Path(path)
            sha = item.get("sha256")
            if sha is None and abs_path.exists() and abs_path.is_file():
                sha = _sha256(abs_path)
            out.append({
                "path": _repo_rel(repo_root, abs_path) if abs_path.is_absolute() else path,
                "sha256": sha,
                "kind": item.get("kind"),
                "status": item.get("status"),
            })
    return out


def write_action_manifest(
    repo_root: Path,
    *,
    task: str,
    action_kind: str,
    command_group: str,
    command: list[str] | str,
    inputs: list[dict[str, Any]] | None = None,
    outputs: list[dict[str, Any]] | None = None,
    status: str = "passed",
    exit_code: int = 0,
    result_path: Path | None = None,
    event_path: Path | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    warnings: list[str] | None = None,
) -> ActionManifestResult:
    action_id = f"{task}-{action_kind}-{uuid.uuid4().hex[:10]}"
    started = started_at or utc_now()
    finished = finished_at or started
    try:
        started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        finished_dt = datetime.fromisoformat(finished.replace("Z", "+00:00"))
        duration = round((finished_dt - started_dt).total_seconds(), 3)
    except Exception:
        duration = 0.0
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "action_id": action_id,
        "task": task,
        "action_kind": action_kind,
        "command_group": command_group,
        "command": command if isinstance(command, str) else " ".join(command),
        "inputs": _normalize_io(repo_root, inputs or []),
        "outputs": _normalize_io(repo_root, outputs or []),
        "tool_versions": _tool_versions(),
        "environment_fingerprint": _environment_fingerprint(repo_root),
        "started_at": started,
        "finished_at": finished,
        "duration_seconds": duration,
        "status": status,
        "exit_code": exit_code,
        "result_path": _repo_rel(repo_root, result_path),
        "event_path": _repo_rel(repo_root, event_path),
        "warnings": sorted(set(warnings or [])),
        "authoritative": False,
    }
    out_dir = repo_root / ".build" / "rig" / "actions"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"{action_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_path = out_dir / "latest.json"
    latest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return ActionManifestResult(action_id=action_id, manifest_path=manifest_path, latest_path=latest_path, manifest=manifest)


def list_actions(repo_root: Path) -> list[dict[str, Any]]:
    out_dir = repo_root / ".build" / "rig" / "actions"
    if not out_dir.exists():
        return []
    rows = []
    for path in sorted(out_dir.glob("*.json"), key=lambda p: p.name):
        if path.name == "latest.json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows


def load_action(repo_root: Path, action_id: str) -> dict[str, Any] | None:
    path = repo_root / ".build" / "rig" / "actions" / f"{action_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None
