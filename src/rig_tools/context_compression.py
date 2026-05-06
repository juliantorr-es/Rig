from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rig_tools import action_manifest, mlx_local


SCHEMA_VERSION = "rig.context_pack.v1"
DEFAULT_BUDGETS = {
    "loop-planner": 16000,
    "agent-plan": 24000,
    "review": 48000,
    "bundle-summary": 32000,
}
SECTION_ORDER = [
    "task_brief",
    "latest_status",
    "affected_summary",
    "architecture_projection",
    "embedding_hits",
    "swift_diagnostics",
    "schema_status",
    "registry_gate",
    "git_commit_plan",
    "agent_summary",
    "loop_summary",
    "proof_summary",
    "patch_summary",
    "review_questions",
]
HARD_EXCLUDES = {".git", ".venv-rig", "__pycache__", "__MACOSX", ".DS_Store"}
MAX_SECTION_BYTES = {
    "task_brief": 4000,
    "latest_status": 3000,
    "affected_summary": 3500,
    "architecture_projection": 3500,
    "embedding_hits": 3000,
    "swift_diagnostics": 3500,
    "schema_status": 2500,
    "registry_gate": 2500,
    "git_commit_plan": 2500,
    "agent_summary": 2500,
    "loop_summary": 2500,
    "proof_summary": 3500,
    "patch_summary": 4000,
    "review_questions": 2000,
}


def _repo_rel(repo_root: Path, path: Path| Optional) -> str| Optional:
    if path is None:
        return None
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_text(path: Path, limit: int| Optional = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text if limit is None else text[:limit]
    except Exception:
        return ""


def _sha256(path: Path) -> str| Optional:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def _is_hidden_or_junk(path: Path) -> bool:
    parts = set(path.parts)
    return any(part in HARD_EXCLUDES for part in parts) or path.name.endswith(".pyc") or path.name == ".DS_Store" or path.suffix == ".zip"


def _discover_paths(repo_root: Path, task: str) -> list[Path]:
    candidates: list[Path] = []
    patterns = [
        repo_root / "Docs" / "td" / "briefs",
        repo_root / ".build" / "rig" / "affected" / "summary.md",
        repo_root / ".build" / "rig" / "projections" / "latest.md",
        repo_root / ".build" / "rig" / "embeddings" / "query-results.md",
        repo_root / ".build" / "rig" / "swift-diagnostics" / "latest.md",
        repo_root / ".build" / "rig" / "schema-validation" / "latest.md",
        repo_root / ".build" / "rig" / "llm",
        repo_root / ".build" / "rig" / "agents" / "plans",
        repo_root / ".build" / "rig" / "agents" / "runs",
        repo_root / ".build" / "rig" / "loop",
        repo_root / ".build" / "rig" / "git",
        repo_root / "Docs" / "proofs",
        repo_root / "Session-bundles",
        repo_root / "Docs" / "indexes",
    ]
    for item in patterns:
        if item.is_dir():
            for child in sorted(item.rglob("*"), key=lambda p: p.as_posix()):
                if child.is_file() and task in child.as_posix():
                    candidates.append(child)
        elif item.exists() and task in item.as_posix():
            candidates.append(item)
    for fixed in [
        repo_root / ".build" / "rig" / "affected" / "summary.md",
        repo_root / ".build" / "rig" / "projections" / "latest.md",
        repo_root / ".build" / "rig" / "embeddings" / "query-results.md",
        repo_root / ".build" / "rig" / "swift-diagnostics" / "latest.md",
        repo_root / ".build" / "rig" / "schema-validation" / "latest.md",
        repo_root / ".build" / "rig" / "llm" / f"{task}-session-summary.md",
        repo_root / ".build" / "rig" / "loop" / "latest.md",
    ]:
        if fixed.exists():
            candidates.append(fixed)
    return sorted({p for p in candidates if p.exists() and p.is_file() and not _is_hidden_or_junk(p)}, key=lambda p: p.as_posix())


def _score_path(path: Path, task: str) -> int:
    score = 0
    text = path.as_posix()
    if task in text:
        score += 100
    if "brief" in text:
        score += 90
    if "summary" in text:
        score += 80
    if "projections" in text:
        score += 70
    if "affected" in text:
        score += 70
    if "diagnostics" in text or "swift" in text:
        score += 60
    if "schema-validation" in text:
        score += 55
    if "embeddings" in text:
        score += 50
    if "agents" in text:
        score += 50
    if "loop" in text:
        score += 50
    if "proofs" in text:
        score += 45
    if "git" in text:
        score += 40
    if "indexes" in text:
        score += 35
    return score


def _hash_record(repo_root: Path, path: Path) -> dict[str, Any]:
    return {"path": _repo_rel(repo_root, path), "sha256": _sha256(path), "size_bytes": path.stat().st_size}


def _section_from_text(name: str, text: str, path: Path| Optional, repo_root: Path, advisory: bool = False) -> dict[str, Any]:
    return {
        "section_type": name,
        "path": _repo_rel(repo_root, path) if path else None,
        "advisory": advisory,
        "text": text[:MAX_SECTION_BYTES.get(name, 3000)],
    }


def _first_nonempty(*values: str| Optional) -> str| Optional:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None


def _summarize_text(path: Path, text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    keep: list[str] = []
    for line in lines[: min(24, len(lines))]:
        keep.append(line)
        if sum(len(item) + 1 for item in keep) >= max_chars // 2:
            break
    tail = lines[-8:] if len(lines) > 8 else []
    out = []
    if keep:
        out.extend(keep)
    if tail and tail != keep[-len(tail):]:
        out.append("...")
        out.extend(tail)
    return "\n".join(out)[:max_chars]


def _fit_text(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= 120:
        return text[:limit]
    head = text[: max(40, limit // 2 - 20)].rstrip()
    tail = text[-max(40, limit // 2 - 20):].lstrip()
    combined = f"{head}\n...\n{tail}"
    return combined[:limit]


def _maybe_llm_summary(repo_root: Path, *, task: str, purpose: str, text: str, use_llm: bool, model: str| Optional) -> dict[str, Any]| Optional:
    if not use_llm:
        return None
    result = mlx_local.generate_summary(
        prompt="\n".join([
            "Summarize the following Rig context pack section.",
            "This is advisory only; do not invent facts.",
            "Keep citations and file paths if present.",
            "Return concise Markdown bullets.",
            "",
            text[:12000],
        ]),
        model=model or mlx_local.SUMMARY_MODEL,
        max_tokens=256,
        timeout_seconds=300,
        task=task,
        prompt_kind="context_summary",
        prompt_template_id="rig.context_pack.v1",
        context_pack_path=repo_root / ".build" / "rig" / "context" / "latest.md",
    )
    return {
        "status": result.get("status"),
        "model": result.get("model"),
        "backend": result.get("backend"),
        "output": result.get("output") or "",
        "warnings": result.get("warnings") or [],
        "limitations": ["advisory", "derived", "non_authoritative"],
    }


def _build_section(repo_root: Path, task: str, purpose: str, path: Path) -> dict[str, Any]:
    text = _read_text(path, MAX_SECTION_BYTES.get("patch_summary", 4000))
    name = "latest_status"
    rel = _repo_rel(repo_root, path) or ""
    if "briefs" in rel:
        name = "task_brief"
    elif "affected" in rel:
        name = "affected_summary"
    elif "projections" in rel:
        name = "architecture_projection"
    elif "query-results" in rel:
        name = "embedding_hits"
    elif "swift-diagnostics" in rel:
        name = "swift_diagnostics"
    elif "schema-validation" in rel:
        name = "schema_status"
    elif "/llm/" in rel:
        name = "agent_summary"
    elif "/agents/" in rel:
        name = "agent_summary"
    elif "/loop/" in rel:
        name = "loop_summary"
    elif "/git/" in rel:
        name = "git_commit_plan"
    elif "/proofs/" in rel:
        name = "proof_summary"
    elif rel.endswith(".md") and "session-review" in rel:
        name = "review_questions"
    return _section_from_text(name, _summarize_text(path, text, MAX_SECTION_BYTES.get(name, 3000)), path, repo_root)


def build_context_pack(repo_root: Path, *, task: str, purpose: str = "review", max_chars: int| Optional = None, use_llm: bool = False, model: str| Optional = None) -> dict[str, Any]:
    max_chars = int(max_chars or DEFAULT_BUDGETS.get(purpose, 32000))
    candidate_paths = _discover_paths(repo_root, task)
    selected: list[Path] = []
    omitted: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    input_artifacts = [_repo_rel(repo_root, p) for p in candidate_paths if _repo_rel(repo_root, p)]
    char_count = 0
    mandatory_sections = {"task_brief", "affected_summary", "swift_diagnostics", "schema_status"}
    for idx, path in enumerate(sorted(candidate_paths, key=lambda p: (-_score_path(p, task), p.as_posix()))):
        section = _build_section(repo_root, task, purpose, path)
        path_text = section["text"]
        remaining = max_chars - char_count
        if remaining <= 0 and section["section_type"] not in mandatory_sections:
            record = _hash_record(repo_root, path)
            omitted.append({"path": record["path"], "reason": "budget", "sha256": record["sha256"], "size_bytes": record["size_bytes"]})
            continue
        fitted = _fit_text(path_text, remaining)
        projected = char_count + len(fitted)
        record = _hash_record(repo_root, path)
        if projected > max_chars and section["section_type"] not in mandatory_sections:
            omitted.append({"path": record["path"], "reason": "budget", "sha256": record["sha256"], "size_bytes": record["size_bytes"]})
            continue
        if section["section_type"] not in mandatory_sections and remaining < 80 and len(path_text) > remaining:
            omitted.append({"path": record["path"], "reason": "budget", "sha256": record["sha256"], "size_bytes": record["size_bytes"]})
            continue
        selected.append(path)
        section["text"] = fitted
        sections.append(section)
        citations.append(record)
        if record["sha256"]:
            hashes[record["path"]] = record["sha256"]
        char_count += len(fitted)
    if not any(sec["section_type"] == "task_brief" for sec in sections):
        brief = next((p for p in candidate_paths if "briefs" in p.as_posix()), None)
        if brief:
            sec = _build_section(repo_root, task, purpose, brief)
            if sec not in sections:
                sec["text"] = _fit_text(sec["text"], max_chars - char_count)
                sections.insert(0, sec)
                selected.insert(0, brief)
                char_count += len(sec["text"])
    if not any(sec["section_type"] == "affected_summary" for sec in sections):
        affected = next((p for p in candidate_paths if "affected/summary.md" in p.as_posix()), None)
        if affected:
            sec = _build_section(repo_root, task, purpose, affected)
            if sec not in sections:
                sec["text"] = _fit_text(sec["text"], max_chars - char_count)
                sections.append(sec)
                selected.append(affected)
                char_count += len(sec["text"])
    if not any(sec["section_type"] == "swift_diagnostics" for sec in sections):
        swift = next((p for p in candidate_paths if "swift-diagnostics" in p.as_posix()), None)
        if swift:
            sec = _build_section(repo_root, task, purpose, swift)
            if sec not in sections:
                sec["text"] = _fit_text(sec["text"], max_chars - char_count)
                sections.append(sec)
                selected.append(swift)
                char_count += len(sec["text"])
    if not any(sec["section_type"] == "schema_status" for sec in sections):
        schema = next((p for p in candidate_paths if "schema-validation" in p.as_posix()), None)
        if schema:
            sec = _build_section(repo_root, task, purpose, schema)
            if sec not in sections:
                sec["text"] = _fit_text(sec["text"], max_chars - char_count)
                sections.append(sec)
                selected.append(schema)
                char_count += len(sec["text"])
    for sec in sections:
        llm = _maybe_llm_summary(repo_root, task=task, purpose=purpose, text=sec["text"], use_llm=use_llm, model=model)
        if llm:
            sec["llm_summary"] = llm
            sec["llm_summary"] = {**llm, "advisory": True}
    markdown_lines = [
        "# Rig Context Pack",
        "",
        f"- Task: `{task}`",
        f"- Purpose: `{purpose}`",
        f"- Created at: `{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}`",
        f"- Max chars: `{max_chars}`",
        f"- Char count: `{char_count}`",
        f"- Compression ratio: `{round(char_count / max(1, sum(p.stat().st_size for p in selected)), 3)}`",
        "",
        "## Selected Artifacts",
    ]
    for path in selected:
        markdown_lines.append(f"- `{_repo_rel(repo_root, path)}`")
    markdown_lines.extend(["", "## Sections"])
    for sec in sections:
        markdown_lines.extend([
            f"### {sec['section_type']}",
            f"- Path: `{sec.get('path') or 'n/a'}`",
            f"- Advisory: `{sec.get('advisory')}`",
            "",
            sec["text"].strip(),
            "",
        ])
        if sec.get("llm_summary"):
            markdown_lines.extend(["**LLM summary (advisory)**", sec["llm_summary"]["output"].strip(), ""])
    markdown_lines.extend(["## Omitted Artifacts", ""])
    if omitted:
        for item in omitted:
            markdown_lines.append(f"- `{item['path']}` reason={item['reason']} sha256={item['sha256']}")
    else:
        markdown_lines.append("- None")
    markdown_lines.extend(["", "## Review Questions", "- What is the smallest next action?", "- What evidence is still missing?", "- What is the strongest blocker?"])
    markdown = "\n".join(markdown_lines).strip() + "\n"
    pack = {
        "schema_version": SCHEMA_VERSION,
        "task": task,
        "purpose": purpose,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "max_chars": max_chars,
        "input_artifacts": input_artifacts,
        "selected_artifacts": [_repo_rel(repo_root, p) for p in selected if _repo_rel(repo_root, p)],
        "omitted_artifacts": omitted,
        "sections": sections,
        "citations": citations,
        "hashes": hashes,
        "char_count": char_count,
        "compression_ratio": round(char_count / max(1, sum(p.stat().st_size for p in selected)), 3) if selected else 0.0,
        "warnings": [],
        "authoritative": False,
        "markdown": markdown,
        "source_repo_root": str(repo_root),
    }
    if use_llm:
        pack["warnings"].append("llm_summaries_advisory")
    return pack


def write_context_pack(repo_root: Path, *, task: str, purpose: str = "review", max_chars: int| Optional = None, use_llm: bool = False, model: str| Optional = None) -> dict[str, Any]:
    pack = build_context_pack(repo_root, task=task, purpose=purpose, max_chars=max_chars, use_llm=use_llm, model=model)
    out_dir = repo_root / ".build" / "rig" / "context"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = task or "latest"
    json_path = out_dir / f"{slug}-context-pack.json"
    md_path = out_dir / f"{slug}-context-pack.md"
    latest_json = out_dir / "latest.json"
    latest_md = out_dir / "latest.md"
    json_path.write_text(json.dumps({k: v for k, v in pack.items() if k != "markdown"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(pack["markdown"], encoding="utf-8")
    latest_json.write_text(json.dumps({k: v for k, v in pack.items() if k != "markdown"}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_md.write_text(pack["markdown"], encoding="utf-8")
    action_manifest.write_action_manifest(
        repo_root,
        task=task,
        action_kind="context.build",
        command_group="context",
        command=["python", "scripts/rig.py", "context", "build", "--task", task, "--purpose", purpose],
        inputs=[{"path": str(path), "kind": "context_source"} for path in pack["input_artifacts"][:8]],
        outputs=[{"path": str(json_path), "kind": "context_pack", "status": "produced"}, {"path": str(md_path), "kind": "context_pack", "status": "produced"}],
        status="passed",
        exit_code=0,
        result_path=json_path,
    )
    pack.update({"json_path": str(json_path), "md_path": str(md_path), "latest_json_path": str(latest_json), "latest_md_path": str(latest_md)})
    return pack


def budget_for_purpose(purpose: str) -> int:
    return DEFAULT_BUDGETS.get(purpose, DEFAULT_BUDGETS["review"])
