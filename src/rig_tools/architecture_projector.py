from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "rig.architecture_projection.v1"
COUPLING_SCHEMA_VERSION = "rig.coupling_index.v1"


def duckdb_available() -> bool:
    try:
        import duckdb  # noqa: F401
    except Exception:
        return False
    return True


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _repo_rel(repo_root: Path, path: Path | str | None) -> str | None:
    if path is None:
        return None
    p = Path(str(path))
    try:
        return str(p.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()[:16]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _signals(text: str) -> set[str]:
    out = set()
    lowered = text.lower()
    if "runtimeauthority" in lowered:
        out.add("runtimeauthority")
    if "exit(" in lowered or "fatalerror(" in lowered or "preconditionfailure(" in lowered or "abort(" in lowered:
        out.add("shutdown_and_exit")
    if "processinfo.processinfo.environment" in lowered or "commandline.arguments" in lowered or "currentdirectorypath" in lowered:
        out.add("ambient_process_read")
    if ".shared" in lowered or "singleton" in lowered or "static let" in lowered:
        out.add("singleton_global_state")
    if "socketpath" in lowered or "bind(" in lowered or "listen(" in lowered or ".sock" in lowered or ".pid" in lowered or ".lock" in lowered:
        out.add("daemon_ipc_binding")
    if "copy" in lowered or "materialization" in lowered:
        out.add("copy_flow")
    return out


def _load_repo_sources(repo_root: Path) -> dict[str, Any]:
    atlas = {}
    for name in ["repo-map.json", "targets.json", "symbols.json", "dependencies.json", "authority-map.json", "risk-index.json", "state-map.json", "data-flow-map.json", "cohesion-index.json", "copy-flow-map.json", "materialization-map.json", "buffer-lifetime-map.json", "zero-copy-readiness-index.json"]:
        path = repo_root / "Docs" / "atlas" / name
        if path.exists():
            atlas[name] = _load_json(path, {})
    indexes = {}
    for name in ["rig-run-index.json", "rig-swift-diagnostics-index.json", "rig-affected-index.json", "validator-registry-index.json", "rig-cache-metadata-index.json"]:
        path = repo_root / "Docs" / "indexes" / name
        if path.exists():
            indexes[name] = _load_json(path, [])
    return {"atlas": atlas, "indexes": indexes}


def _duckdb_read(repo_root: Path) -> dict[str, Any]:
    if not duckdb_available():
        return {"used": False, "warning": "duckdb_unavailable"}
    db = repo_root / ".build" / "rig" / "rig.duckdb"
    if not db.exists():
        return {"used": False, "warning": "duckdb_missing"}
    try:
        import duckdb

        con = duckdb.connect(str(db), read_only=True)
        runs = con.execute("select * from runs order by coalesce(finished_at,''), run_id desc limit 20").fetchall()
        cols = [c[0] for c in con.description]
        con.close()
        return {"used": True, "warning": None, "runs": [dict(zip(cols, row)) for row in runs]}
    except Exception as exc:
        return {"used": False, "warning": f"duckdb_read_failed:{exc}"}


def _target_files(repo_root: Path, target: str) -> list[Path]:
    files: list[Path] = []
    for root in [repo_root / "anigma", repo_root / "scripts"]:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".swift", ".py", ".json", ".md"}:
                text = path.as_posix()
                if target in text or target in _read_text(path):
                    files.append(path)
    return sorted(set(files), key=lambda p: p.as_posix())


def _target_evidence(repo_root: Path, target: str) -> dict[str, Any]:
    atlas = _load_repo_sources(repo_root)
    score = 0
    file_count = 0
    signals = []
    evidence_files = _target_files(repo_root, target)[:50]
    for path in evidence_files:
        file_count += 1
        text = _read_text(path)
        sig = _signals(text)
        if sig:
            signals.extend(sorted(sig))
            score += len(sig)
    return {
        "target": target,
        "file_count": file_count,
        "signals": sorted(set(signals)),
        "atlas_files": sorted(atlas["atlas"].keys()),
    }


def _projection_kind(signals: set[str]) -> str:
    if "shutdown_and_exit" in signals:
        return "move_lifecycle_to_daemon_owner"
    if "ambient_process_read" in signals:
        return "move_config_to_configuration_boundary"
    if "daemon_ipc_binding" in signals:
        return "extract_authority"
    if "singleton_global_state" in signals:
        return "replace_global_state_with_actor"
    return "defer_no_change"


def _projection_for_target(repo_root: Path, target: str) -> dict[str, Any]:
    evidence = _target_evidence(repo_root, target)
    sigs = set(evidence["signals"])
    kind = _projection_kind(sigs)
    counter = []
    if kind == "move_lifecycle_to_daemon_owner":
        counter.append("Do not move process exit into shared authority.")
    if kind == "extract_authority":
        counter.append("Avoid promoting RuntimeAuthority into a general service locator.")
    if kind == "replace_global_state_with_actor":
        counter.append("If state is immutable or test-only, defer refactor.")
    if kind == "defer_no_change":
        counter.append("Evidence insufficient for a refactor projection.")
    projection_id = f"projection.{target}.{_stable_id(target, kind, ','.join(sorted(sigs)))}"
    return {
        "schema_version": SCHEMA_VERSION,
        "projection_id": projection_id,
        "kind": kind,
        "title": f"{target} projection",
        "target": target,
        "current_shape": {"signals": sorted(sigs), "evidence_file_count": evidence["file_count"]},
        "recommended_shape": {"boundary": "explicit authority / typed lifecycle owner"},
        "evidence": {"sources": evidence["atlas_files"], "signals": sorted(sigs)},
        "coupling_effect": "reduce" if kind != "defer_no_change" else "neutral",
        "cohesion_effect": "improve" if kind != "defer_no_change" else "neutral",
        "zero_copy_effect": "unknown",
        "risk_of_tight_coupling": "high" if kind in {"extract_authority", "move_lifecycle_to_daemon_owner"} else "medium",
        "risk_of_god_object": "high" if target == "RuntimeAuthority" and kind != "defer_no_change" else "medium",
        "counterarguments": counter,
        "confidence": "medium" if sigs else "low",
        "recommended_task_type": "task-brief",
        "validation_plan": ["rig affected summary", "rig swift build", "schema validate result/event"],
        "suggested_task_brief_seed": f"Review {target} for {kind} concerns",
    }


def _coupling_record(repo_root: Path, target: str) -> dict[str, Any]:
    atlas = _load_repo_sources(repo_root)
    target_data = atlas["atlas"].get("targets.json", {})
    item = {}
    if isinstance(target_data, dict):
        items = target_data.get("targets") or []
        if isinstance(items, list):
            for entry in items:
                if isinstance(entry, dict) and entry.get("name") == target:
                    item = entry
                    break
    fan_in = int(item.get("fan_in", 0) or 0)
    fan_out = int(item.get("fan_out", 0) or 0)
    risk_count = 0
    state_count = 0
    flow_count = 0
    diagnostic_count = 0
    affected_count = 0
    risks = atlas["atlas"].get("risk-index.json", {})
    if isinstance(risks, dict):
        for v in risks.get("risks", []) or []:
            if isinstance(v, dict) and v.get("target") == target:
                risk_count += 1
    state_map = atlas["atlas"].get("state-map.json", {})
    if isinstance(state_map, dict):
        for v in state_map.get("records", []) or []:
            if isinstance(v, dict) and v.get("target") == target:
                state_count += 1
    data_flow = atlas["atlas"].get("data-flow-map.json", {})
    if isinstance(data_flow, dict):
        for v in data_flow.get("flows", []) or []:
            if isinstance(v, dict) and (v.get("target") == target or target in str(v.get("path", ""))):
                flow_count += 1
    for row in atlas["indexes"].get("rig-swift-diagnostics-index.json", []) or []:
        if isinstance(row, dict) and row.get("target") == target:
            diagnostic_count += 1
    for row in atlas["indexes"].get("rig-affected-index.json", []) or []:
        if isinstance(row, dict) and target in str(row.get("directly_affected_targets") or ""):
            affected_count += 1
    score = fan_in + fan_out + risk_count * 2 + state_count * 2 + flow_count + diagnostic_count + affected_count
    return {
        "schema_version": COUPLING_SCHEMA_VERSION,
        "target": target,
        "fan_in": fan_in,
        "fan_out": fan_out,
        "risk_count": risk_count,
        "state_count": state_count,
        "flow_count": flow_count,
        "diagnostic_count": diagnostic_count,
        "affected_count": affected_count,
        "coupling_score": score,
        "coupling_rationale": "High score driven by repeated risks/state/flow/diagnostic correlation" if score else "Insufficient evidence",
    }


def _overlap_records(repo_root: Path, target: str) -> list[dict[str, Any]]:
    records = []
    files = _target_files(repo_root, target)
    phrases = {
        "duplicate_config": ["ProcessInfo.processInfo.environment", "CommandLine.arguments", "currentDirectoryPath"],
        "duplicate_lifecycle": ["exit(", "fatalError(", "preconditionFailure("],
        "duplicate_socket_ownership": ["socketPath", "bind(", "listen("],
        "duplicate_logging": ["Logger(", "os_log", "print("],
        "duplicate_runtime_authority": ["RuntimeAuthority"],
    }
    for overlap_type, needles in phrases.items():
        hits = []
        for path in files:
            text = _read_text(path)
            if any(needle.lower() in text.lower() for needle in needles):
                hits.append(_repo_rel(repo_root, path))
        if hits:
            records.append({
                "schema_version": "rig.overlap_index.v1",
                "overlap_id": f"overlap.{target}.{overlap_type}.{_stable_id(target, overlap_type)}",
                "responsibility_phrase": overlap_type.replace("_", " "),
                "targets": [target],
                "files": hits[:20],
                "symbols": [],
                "evidence_sources": ["atlas", "source"],
                "overlap_type": overlap_type,
                "risk": "medium" if overlap_type != "duplicate_runtime_authority" else "high",
                "rationale": "Evidence of repeated responsibility signals across files",
            })
    return records


def build_projection_bundle(repo_root: Path, target: str | None = None, mode: str = "advisory", risk: str | None = None) -> dict[str, Any]:
    duck = _duckdb_read(repo_root)
    targets = [target] if target else []
    if not targets:
        atlas_targets = _load_json(repo_root / "Docs" / "atlas" / "targets.json", {})
        if isinstance(atlas_targets, dict):
            items = atlas_targets.get("targets") or []
            targets = [entry.get("name") for entry in items if isinstance(entry, dict) and entry.get("name")]
        if not targets:
            targets = ["RuntimeAuthority", "AnigmaDaemonCore"]
    projections = [_projection_for_target(repo_root, t) for t in targets]
    coupling = [_coupling_record(repo_root, t) for t in targets]
    overlaps = []
    for t in targets:
        overlaps.extend(_overlap_records(repo_root, t))
    module_move_candidates = []
    for proj in projections:
        if proj["kind"] != "defer_no_change":
            module_move_candidates.append({
                "schema_version": "rig.module_move_candidate.v1",
                "candidate_id": f"candidate.{proj['projection_id']}",
                "symbol_or_file": proj["target"],
                "current_target": proj["target"],
                "proposed_target": proj["recommended_shape"]["boundary"],
                "move_kind": proj["kind"],
                "evidence": proj["evidence"],
                "coupling_effect": proj["coupling_effect"],
                "risk": proj["risk_of_tight_coupling"],
                "validation_plan": proj["validation_plan"],
            })
    desired = [{
        "schema_version": "rig.desired_state_index.v1",
        "target": p["target"],
        "current_shape": p["current_shape"],
        "desired_shape": p["recommended_shape"],
        "blocked_by": p["counterarguments"],
        "recommended_next_projection_ids": [p["projection_id"]],
        "confidence": p["confidence"],
    } for p in projections]
    latest = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed" if projections else "partial",
        "duckdb_used": duck["used"],
        "duckdb_warning": duck["warning"],
        "projection_count": len(projections),
        "coupling_record_count": len(coupling),
        "overlap_record_count": len(overlaps),
        "module_move_candidate_count": len(module_move_candidates),
        "desired_state_record_count": len(desired),
        "top_projections": [p["projection_id"] for p in projections[:10]],
        "warnings": [duck["warning"]] if duck.get("warning") else [],
    }
    return {
        "projections": projections,
        "coupling": coupling,
        "overlaps": overlaps,
        "module_move_candidates": module_move_candidates,
        "desired": desired,
        "latest": latest,
    }


def write_projection_outputs(repo_root: Path, bundle: dict[str, Any]) -> dict[str, Path]:
    atlas_dir = repo_root / "Docs" / "atlas"
    build_dir = repo_root / ".build" / "rig" / "projections"
    atlas_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "Docs/atlas/architecture-projections.json": atlas_dir / "architecture-projections.json",
        "Docs/atlas/coupling-index.json": atlas_dir / "coupling-index.json",
        "Docs/atlas/overlap-index.json": atlas_dir / "overlap-index.json",
        "Docs/atlas/module-move-candidates.json": atlas_dir / "module-move-candidates.json",
        "Docs/atlas/desired-state-index.json": atlas_dir / "desired-state-index.json",
        ".build/rig/projections/latest.json": build_dir / "latest.json",
        ".build/rig/projections/latest.md": build_dir / "latest.md",
    }
    _write(outputs["Docs/atlas/architecture-projections.json"], bundle["projections"])
    _write(outputs["Docs/atlas/coupling-index.json"], bundle["coupling"])
    _write(outputs["Docs/atlas/overlap-index.json"], bundle["overlaps"])
    _write(outputs["Docs/atlas/module-move-candidates.json"], bundle["module_move_candidates"])
    _write(outputs["Docs/atlas/desired-state-index.json"], bundle["desired"])
    _write(outputs[".build/rig/projections/latest.json"], bundle["latest"])
    _write(outputs[".build/rig/projections/latest.md"], _render_md(bundle))
    return outputs


def _write(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _render_md(bundle: dict[str, Any]) -> str:
    latest = bundle["latest"]
    lines = [
        "# Rig Architecture Projections",
        "",
        f"- Status: `{latest['status']}`",
        f"- DuckDB used: `{latest['duckdb_used']}`",
        f"- DuckDB warning: `{latest['duckdb_warning']}`",
        "",
        "## Top Projections",
    ]
    for p in bundle["projections"][:10]:
        lines.append(f"- `{p['projection_id']}` {p['kind']} on `{p['target']}`")
    lines.append("")
    lines.append("## Coupling Hotspots")
    for c in bundle["coupling"][:10]:
        lines.append(f"- `{c['target']}` score `{c['coupling_score']}`")
    lines.append("")
    lines.append("## Overlap Risks")
    for o in bundle["overlaps"][:10]:
        lines.append(f"- `{o['overlap_id']}` {o['overlap_type']}")
    return "\n".join(lines) + "\n"

