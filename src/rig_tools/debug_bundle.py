from __future__ import annotations

import json
import platform
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from rig.config.loader import merge_config
from rig_tools import orchestration, provider_registry, tui_views


@dataclass
class DebugBundleResult:
    bundle_path: Path | None
    manifest: dict[str, object]


def _redact_text(text: str) -> str:
    return text.replace("sk-", "<redacted>")


def _redact_value(value):
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _bundle_manifest(repo_root: Path, *, output: Path, sections: list[str], redact: bool) -> dict[str, object]:
    cfg = merge_config(repo_root)
    return {
        "schema": "rig.debug_bundle_manifest.v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_root": str(repo_root),
        "output": str(output),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "sections": sections,
        "redact": redact,
        "config": {
            "config_file": cfg.get("config_file"),
            "repo_root": cfg.get("repo_root"),
            "state_dir": cfg.get("state_dir"),
        },
    }


def build_bundle(repo_root: Path, *, output: Path | None = None, include_logs: bool = False, include_receipts: bool = False, include_context: bool = False, include_tui: bool = False, redact: bool = True, dry_run: bool = False) -> DebugBundleResult:
    repo_root = repo_root.resolve()
    output = output or (repo_root / ".build" / "rig" / "debug" / f"rig-debug-bundle-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.zip")
    sections = ["doctor", "deps", "config", "jobs", "queue", "providers"]
    if include_logs:
        sections.append("logs")
    if include_receipts:
        sections.append("receipts")
    if include_context:
        sections.append("context")
    if include_tui:
        sections.append("tui")
    manifest = _bundle_manifest(repo_root, output=output, sections=sections, redact=redact)
    if dry_run:
        return DebugBundleResult(None, manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle_manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        zf.writestr("doctor.json", json.dumps({"queue": orchestration.queue_health(repo_root), "providers": provider_registry.list_providers(repo_root)}, indent=2, sort_keys=True))
        zf.writestr("config.json", json.dumps(_redact_value(merge_config(repo_root)), indent=2, sort_keys=True))
        zf.writestr("tui_snapshot.json", json.dumps(tui_views.latest_receipt_paths(repo_root), indent=2, sort_keys=True))
        if include_tui:
            tui_state = _redact_value(json.loads((repo_root / ".build" / "rig" / "tui" / "state.json").read_text(encoding="utf-8"))) if (repo_root / ".build" / "rig" / "tui" / "state.json").exists() else {}
            zf.writestr("tui_state.json", json.dumps(tui_state, indent=2, sort_keys=True))
        if redact:
            zf.writestr("redaction.txt", _redact_text("Secrets redacted. Model weights excluded. Venv excluded."))
    return DebugBundleResult(output, manifest)
