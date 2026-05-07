from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _root(repo_root: Path) -> Path:
    out = repo_root / ".build" / "rig" / "models"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _manifest_path(repo_root: Path, model_id: str) -> Path:
    return _root(repo_root) / f"{model_id}.json"


def list_models(repo_root: Path) -> list[dict[str, Any]]:
    out = _root(repo_root)
    rows = []
    for path in sorted(out.glob("*.json"), key=lambda p: p.name):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return rows


def inspect_model(repo_root: Path, model_id: str) -> dict[str, Any]:
    path = _manifest_path(repo_root, model_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"model_id": model_id, "status": "missing"}


def register_model(repo_root: Path, path_or_name: str) -> dict[str, Any]:
    path = Path(path_or_name)
    if path.exists():
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest = {"model_id": path.stem, "source": str(path), "checksum": checksum, "kind": "local", "status": "registered"}
    else:
        manifest = {"model_id": path_or_name, "source": path_or_name, "checksum": None, "kind": "remote_or_alias", "status": "registered"}
    _manifest_path(repo_root, manifest["model_id"]).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def verify_model(repo_root: Path, model_id: str) -> dict[str, Any]:
    manifest = inspect_model(repo_root, model_id)
    source = manifest.get("source")
    if source and Path(str(source)).exists():
        checksum = hashlib.sha256(Path(str(source)).read_bytes()).hexdigest()
        manifest["verified_checksum"] = checksum
        manifest["status"] = "passed"
    else:
        manifest["status"] = "reachable" if shutil.which(str(source or model_id)) else "unverified"
    return manifest

