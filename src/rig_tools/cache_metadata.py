from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

SCHEMA_VERSION = "rig.cache-metadata.v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str| Optional:
    if not path.exists() or not path.is_file():
        return None
    try:
        return sha256_bytes(path.read_bytes())
    except Exception:
        return None


def sha256_tree(path: Path) -> str| Optional:
    if not path.exists():
        return None
    if path.is_file():
        return sha256_path(path)
    try:
        items = []
        for child in sorted(path.rglob("*"), key=lambda p: p.as_posix()):
            if child.is_file():
                items.append({"path": str(child.as_posix()), "sha256": sha256_path(child)})
        return sha256_bytes(json.dumps(items, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    except Exception:
        return None


def tool_version(cmd: list[str]) -> str| Optional:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        out = (proc.stdout or proc.stderr or "").strip()
        return out.splitlines()[0] if out else None
    except Exception:
        return None


def environment_fingerprint() -> dict:
    return {
        "python_version": platform.python_version(),
        "swift_version": tool_version(["swift", "--version"]),
    }


@dataclass
class CacheMetadata:
    artifact_id: str
    producer: str
    command: str
    input_files: list[dict]
    output_files: list[dict]
    cache_key: str
    status: str
    environment_fingerprint: dict
    duration_seconds: float| Optional = None
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def build_cache_key(command: str, input_files: list[dict], environment_fingerprint: dict) -> str:
    payload = {
        "command": command,
        "inputs": input_files,
        "environment_fingerprint": environment_fingerprint,
    }
    return sha256_bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def record_metadata(repo_root: Path, *, artifact_id: str, producer: str, command: str, input_paths: list[Path], output_paths: list[Path], duration_seconds: float| Optional = None) -> Path:
    out_dir = repo_root / ".build" / "rig" / "cache-metadata"
    out_dir.mkdir(parents=True, exist_ok=True)
    inputs = [{"path": str(p.relative_to(repo_root)), "sha256": sha256_tree(p)} for p in input_paths]
    outputs = [{"path": str(p.relative_to(repo_root)), "sha256": sha256_tree(p)} for p in output_paths]
    env = environment_fingerprint()
    cache_key = build_cache_key(command, inputs, env)
    status = "fresh" if all(item.get("sha256") for item in outputs) else "missing_outputs"
    payload = CacheMetadata(
        artifact_id=artifact_id,
        producer=producer,
        command=command,
        input_files=inputs,
        output_files=outputs,
        cache_key=cache_key,
        status=status,
        environment_fingerprint=env,
        duration_seconds=duration_seconds,
    ).to_dict()
    path = out_dir / f"{artifact_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
