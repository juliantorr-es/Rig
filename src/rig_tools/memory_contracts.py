from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from rig_tools.system_pressure import sample_system_pressure
from rig_tools.state_store import StateStore


DEFAULT_MEMORY_SETTINGS = {
    "memory": {
        "max_tui_events": 500,
        "max_projection_bytes": 1_000_000,
        "max_loaded_log_bytes": 200_000,
        "high_pressure_disable_parallel_agents": True,
        "max_parallel_agents_default": 1,
    }
}


@dataclass
class MemoryContractCheck:
    check_id: str
    subsystem: str
    status: str
    detail: str
    recommendation: str = ""
    artifact_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "subsystem": self.subsystem,
            "status": self.status,
            "detail": self.detail,
            "recommendation": self.recommendation,
            "artifact_path": self.artifact_path,
        }


@dataclass
class MemoryContractReport:
    schema_version: str = "rig.memory_contract.v1"
    status: str = "pass"
    checks: list[MemoryContractCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    authoritative: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
            "warnings": self.warnings,
            "artifact_paths": self.artifact_paths,
            "authoritative": self.authoritative,
        }


def memory_settings(settings: dict[str, Any]| Optional = None) -> dict[str, Any]:
    merged = json.loads(json.dumps(DEFAULT_MEMORY_SETTINGS))
    if isinstance(settings, dict):
        mem = settings.get("memory")
        if isinstance(mem, dict):
            merged["memory"].update({k: v for k, v in mem.items() if v is not None})
    return merged["memory"]


def trim_event_tail(events: Iterable[dict[str, Any]], *, max_events: int) -> list[dict[str, Any]]:
    tail = list(events)
    if max_events <= 0:
        return []
    return tail[-max_events:]


def read_jsonl_tail(path: Path, *, max_events: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: deque[dict[str, Any]] = deque(maxlen=max_events)
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return list(events)


def projected_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except Exception:
        return 0


def describe_log_file(path: Path, *, max_loaded_bytes: int) -> dict[str, Any]:
    size = projected_bytes(path)
    if size <= max_loaded_bytes:
        try:
            return {
                "path": str(path),
                "size_bytes": size,
                "loaded": True,
                "content": path.read_text(encoding="utf-8", errors="ignore"),
            }
        except Exception as exc:
            return {"path": str(path), "size_bytes": size, "loaded": False, "error": str(exc)}
    return {
        "path": str(path),
        "size_bytes": size,
        "loaded": False,
        "content": None,
    }


def _check_projection_size(repo_root: Path, limits: dict[str, Any]) -> MemoryContractCheck:
    proj_dir = repo_root / ".build" / "rig" / "projections"
    latest = proj_dir / "latest.json"
    tui = proj_dir / "tui-snapshot.json"
    max_bytes = int(limits.get("max_projection_bytes", 1_000_000))
    paths = [p for p in [latest, tui] if p.exists()]
    biggest = max((projected_bytes(p) for p in paths), default=0)
    if biggest > max_bytes:
        return MemoryContractCheck(
            check_id="projection_size",
            subsystem="projections",
            status="warn",
            detail=f"largest_projection_bytes={biggest} limit={max_bytes}",
            recommendation="Reduce projection payloads and trim the event tail",
            artifact_path=str(latest.relative_to(repo_root)) if latest.exists() else "",
        )
    return MemoryContractCheck(
        check_id="projection_size",
        subsystem="projections",
        status="pass",
        detail=f"largest_projection_bytes={biggest} limit={max_bytes}",
        artifact_path=str(latest.relative_to(repo_root)) if latest.exists() else "",
    )


def _check_prompt_trace_storage(repo_root: Path, limits: dict[str, Any]) -> MemoryContractCheck:
    store = StateStore(repo_root)
    if not store.db_path.exists():
        return MemoryContractCheck(
            check_id="prompt_trace_storage",
            subsystem="state_store",
            status="pass",
            detail="state db missing; no traces to inspect",
        )
    cap = int(limits.get("max_loaded_log_bytes", 200_000))
    try:
        with store.connect() as conn:
            row = conn.execute("SELECT data FROM prompt_traces ORDER BY created_at DESC LIMIT 1").fetchone()
            if not row:
                return MemoryContractCheck(
                    check_id="prompt_trace_storage",
                    subsystem="state_store",
                    status="pass",
                    detail="no prompt traces found",
                )
            raw = row["data"] if isinstance(row, dict) else row[0]
            payload = json.loads(raw) if isinstance(raw, str) else {}
            bad_keys = [k for k in ("transcript", "transcript_blob", "raw_output_text", "prompt_text", "output_text") if isinstance(payload, dict) and k in payload and isinstance(payload[k], str) and len(payload[k].encode("utf-8")) > cap]
            if bad_keys:
                return MemoryContractCheck(
                    check_id="prompt_trace_storage",
                    subsystem="state_store",
                    status="fail",
                    detail=f"oversized raw trace payload keys={bad_keys}",
                    recommendation="Store transcript/log paths and short summaries instead of raw blobs",
                    artifact_path=str(store.db_path.relative_to(repo_root)),
                )
            if isinstance(payload, dict) and not any(k.endswith("_path") for k in payload.keys()):
                return MemoryContractCheck(
                    check_id="prompt_trace_storage",
                    subsystem="state_store",
                    status="warn",
                    detail="trace payload has no path fields",
                    recommendation="Record transcript paths and summaries for state-store rows",
                    artifact_path=str(store.db_path.relative_to(repo_root)),
                )
    except Exception as exc:
        return MemoryContractCheck(
            check_id="prompt_trace_storage",
            subsystem="state_store",
            status="warn",
            detail=f"trace inspection unavailable: {exc}",
            recommendation="Inspect prompt trace payload structure manually",
        )
    return MemoryContractCheck(
        check_id="prompt_trace_storage",
        subsystem="state_store",
        status="pass",
        detail="prompt trace rows are path/summaries oriented",
        artifact_path=str(store.db_path.relative_to(repo_root)),
    )


def can_launch_parallel_agents(settings: dict[str, Any]| Optional, pressure: dict[str, Any]| Optional) -> bool:
    limits = memory_settings(settings)
    if not limits.get("high_pressure_disable_parallel_agents", True):
        return True
    if not isinstance(pressure, dict):
        return False
    mem = pressure.get("memory", {})
    if isinstance(mem, dict):
        percent = mem.get("percent")
        try:
            if percent is not None and float(percent) >= 85.0:
                return False
        except Exception:
            return False
    return True


def evaluate_memory_contracts(repo_root: Path, settings: dict[str, Any]| Optional = None, pressure: dict[str, Any]| Optional = None) -> dict[str, Any]:
    limits = memory_settings(settings)
    report = MemoryContractReport()
    checks = [
        _check_projection_size(repo_root, limits),
        _check_prompt_trace_storage(repo_root, limits),
    ]
    if not can_launch_parallel_agents(settings, pressure):
        checks.append(MemoryContractCheck(
            check_id="parallel_agent_pressure",
            subsystem="loop_engine",
            status="fail",
            detail="high memory pressure blocks parallel agents",
            recommendation="Refuse new parallel agent work until memory pressure drops or the policy changes",
        ))
    report.checks = checks
    report.warnings = [c.detail for c in checks if c.status == "warn"]
    report.status = "fail" if any(c.status == "fail" for c in checks) else ("warn" if report.warnings else "pass")
    report.artifact_paths = [
        str(repo_root / ".build" / "rig" / "projections" / "latest.json"),
        str(repo_root / ".build" / "rig" / "projections" / "tui-snapshot.json"),
        str(repo_root / ".build" / "rig" / "state" / "rig.sqlite"),
    ]
    return report.to_dict()
