from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rig.domain.workspace import WorkspaceDomain


SCHEMA_VERSION = "rig.context_packet.v1"
DEFAULT_RESERVED_OUTPUT = 8000
DEFAULT_SAFETY_MARGIN = 4000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repo_root(repo_root: Path) -> Path:
    return repo_root.resolve()


def _context_dir(repo_root: Path) -> Path:
    out = _repo_root(repo_root) / ".build" / "rig" / "context"
    out.mkdir(parents=True, exist_ok=True)
    return out


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_context_packet(repo_root: Path, *, workspace_id: str, provider_id: str, model_id: str, force_repack: bool = False) -> dict[str, Any]:
    ws = WorkspaceDomain(repo_root)
    record = ws.load_workspace(workspace_id)
    if not record:
        raise FileNotFoundError(workspace_id)
    task = record.payload.get("task") or "unknown"
    review = ws.review_path(workspace_id) / "review.json"
    validation = ws.validation_result_path(workspace_id)
    candidates = [
        {"kind": "workspace", "path": record.path},
        {"kind": "review_bundle", "path": review},
        {"kind": "validation_result", "path": validation},
    ]
    included = []
    summaries = []
    raw_hashes = []
    estimated_input_tokens = 0
    for candidate in candidates:
        path = candidate["path"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        estimated_input_tokens += _estimate_tokens(text)
        included.append({"kind": candidate["kind"], "path": str(path.relative_to(repo_root)), "sha256": _sha256(text)})
        raw_hashes.append({"path": str(path.relative_to(repo_root)), "sha256": _sha256(text)})
        summaries.append({"kind": candidate["kind"], "excerpt": text[:1200]})
    context_window_tokens = 128000
    reserved_output_tokens = DEFAULT_RESERVED_OUTPUT
    usable_input_tokens = max(0, context_window_tokens - reserved_output_tokens - DEFAULT_SAFETY_MARGIN)
    packet = {
        "schema_version": SCHEMA_VERSION,
        "packet_id": uuid.uuid4().hex[:12],
        "workspace_id": workspace_id,
        "provider_id": provider_id,
        "model_id": model_id,
        "context_window_tokens": context_window_tokens,
        "reserved_output_tokens": reserved_output_tokens,
        "usable_input_tokens": usable_input_tokens,
        "estimated_input_tokens": estimated_input_tokens,
        "token_count_method": "approximate_chars_over_4",
        "token_count_confidence": "approximate",
        "included_items": included,
        "excluded_items": [],
        "summarized_items": summaries,
        "truncation_policy": "summary_then_hash",
        "packing_policy": ["task", "workspace", "review", "validation"],
        "raw_hashes": raw_hashes,
        "authoritative": True,
        "created_at": utc_now(),
    }
    if not force_repack:
        out = _context_dir(repo_root) / f"{packet['packet_id']}.json"
        out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return packet


def inspect_context_packet(repo_root: Path, packet_id: str) -> dict[str, Any]:
    path = _context_dir(repo_root) / f"{packet_id}.json"
    if not path.exists():
        return {"status": "missing", "packet_id": packet_id}
    return json.loads(path.read_text(encoding="utf-8"))


def explain_context_packet(repo_root: Path, packet_id: str) -> dict[str, Any]:
    packet = inspect_context_packet(repo_root, packet_id)
    if packet.get("status") == "missing":
        return packet
    return {
        "packet_id": packet_id,
        "workspace_id": packet.get("workspace_id"),
        "provider_id": packet.get("provider_id"),
        "model_id": packet.get("model_id"),
        "included_count": len(packet.get("included_items") or []),
        "excluded_count": len(packet.get("excluded_items") or []),
        "estimated_input_tokens": packet.get("estimated_input_tokens"),
        "usable_input_tokens": packet.get("usable_input_tokens"),
        "token_count_confidence": packet.get("token_count_confidence"),
        "truncation_policy": packet.get("truncation_policy"),
    }
