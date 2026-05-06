from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from anigma_common.io import write_json_stable

IGNORED_SEGMENTS = {".build", "DerivedData", ".git", "__MACOSX"}
IGNORED_NAMES = {".DS_Store"}


@dataclass
class AffectedResult:
    command: list[str]
    mode: str
    base: str | None
    head: str | None
    changed_files: list[str]
    unknown_files: list[str]
    directly_affected_targets: list[str]
    upstream_or_dependent_targets: list[str]
    affected_risks: list[dict]
    recommended_profiles: list[str]
    recommended_validation_commands: list[str]
    target_notes: list[str]

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "mode": self.mode,
            "base": self.base,
            "head": self.head,
            "changed_files": self.changed_files,
            "unknown_files": self.unknown_files,
            "directly_affected_targets": self.directly_affected_targets,
            "upstream_or_dependent_targets": self.upstream_or_dependent_targets,
            "affected_risks": self.affected_risks,
            "recommended_profiles": self.recommended_profiles,
            "recommended_validation_commands": self.recommended_validation_commands,
            "target_notes": self.target_notes,
        }


def _repo_root(start: Path | None = None) -> Path:
    start = start or Path(__file__).resolve()
    return Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=start.parent if start.is_file() else start, text=True).strip())


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _normalize(path: str) -> str | None:
    raw = path.strip().replace("\\", "/")
    if not raw:
        return None
    p = Path(raw)
    if any(seg in IGNORED_SEGMENTS for seg in p.parts) or p.name in IGNORED_NAMES:
        return None
    if raw.startswith(".build/") or raw.startswith("DerivedData/") or raw.startswith(".git/"):
        return None
    if raw.startswith("archives/") or raw.endswith(".zip") or raw.endswith(".tar") or raw.endswith(".tgz"):
        return None
    return raw.lstrip("./")


def _git_changed_files(repo_root: Path, base: str | None, head: str | None) -> list[str]:
    if base and head:
        cmd = ["git", "diff", "--name-only", f"{base}..{head}", "--"]
    elif base:
        cmd = ["git", "diff", "--name-only", base, "--"]
    else:
        cmd = ["git", "diff", "--name-only", "HEAD", "--"]
    proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True, check=False)
    files = [_normalize(line) for line in proc.stdout.splitlines()]
    files = [f for f in files if f]
    if base is None and head is None:
        status = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=repo_root, text=True, capture_output=True, check=False)
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            normalized = _normalize(path)
            if normalized and normalized not in files:
                files.append(normalized)
    return sorted(dict.fromkeys(files))


def _load_profiles(repo_root: Path) -> list[str]:
    profiles_dir = repo_root / "Docs" / "pipeline" / "profiles"
    if not profiles_dir.exists():
        return []
    return sorted(p.stem for p in profiles_dir.glob("*.yaml"))


def _infer_targets_from_paths(files: list[str], targets_data: dict) -> tuple[list[str], list[str]]:
    targets = targets_data.get("targets", []) if isinstance(targets_data, dict) else []
    target_names = [t.get("name") for t in targets if t.get("name")]
    source_paths = {t.get("name"): str(t.get("source_paths") or "") for t in targets if t.get("name")}
    directly: list[str] = []
    unknown: list[str] = []

    for path in files:
        matched = None
        for target in target_names:
            source_path = source_paths.get(target, "")
            candidates = [
                f"anigma/Sources/{target}/",
                f"anigma/Tests/{target}/",
                f"anigma/Packages/{target}/Sources/{target}/",
                f"anigma/Packages/{target}/Tests/{target}/",
                f"{source_path.rstrip('/')}/" if source_path else "",
            ]
            if any(candidate and path.startswith(candidate) for candidate in candidates):
                matched = target
                break
            if f"/{target}/" in path or path.endswith(f"{target}.swift") or path.startswith(f"anigma/Sources/{target}") or path.startswith(f"anigma/Tests/{target}"):
                matched = target
                break
        if matched and matched not in directly:
            directly.append(matched)
        if matched is None:
            unknown.append(path)
    return sorted(directly), sorted(dict.fromkeys(unknown))


def _repo_map_direct_targets(files: list[str], repo_map: list[dict]) -> list[str]:
    direct: list[str] = []
    by_path = {item.get("path"): item.get("target") for item in repo_map if item.get("path") and item.get("target")}
    for path in files:
        target = by_path.get(path)
        if target and target not in direct:
            direct.append(target)
    return sorted(direct)


def _affected_risks_for_targets_and_files(risk_index: list[dict], files: list[str], targets: list[str]) -> list[dict]:
    changed = set(files)
    target_set = set(targets)
    risks = []
    for risk in risk_index:
        path = risk.get("path") or ""
        target = risk.get("target") or ""
        if path in changed or any(path.startswith(prefix) for prefix in changed) or target in target_set:
            risks.append(risk)
    risks.sort(key=lambda r: (r.get("severity") or "", r.get("confidence") or "", r.get("target") or "", r.get("path") or "", r.get("category") or ""))
    return risks


def _recommend_profiles(files: list[str], targets: list[str], risks: list[dict], profiles: list[str]) -> list[str]:
    files_lower = [f.lower() for f in files]
    targets_set = {t.lower() for t in targets}
    rec: list[str] = []
    def add(name: str):
        if name in profiles and name not in rec:
            rec.append(name)

    if any(p.startswith("scripts/") or p.startswith("scripts\\") for p in files_lower):
        add("local-fast")
    if any(f.startswith("docs/") or f.startswith("docs\\") for f in files_lower):
        add("local-fast")
    if "anigmadaemoncore" in targets_set or "anigmad" in targets_set:
        add("daemon-runtime")
        add("cleanup-review")
    if any(f.endswith("package.swift") for f in files_lower):
        add("backend-regularization")
    if any("mediacore" in f or f.endswith(".metal") or f.endswith(".mm") or f.endswith(".m") for f in files_lower):
        add("backend-regularization")
    if any(f.startswith("anigma/") and f.endswith(".swift") for f in files_lower):
        add("cleanup-review")
    if any(f.startswith("scripts/rig") or f.startswith("scripts/anigma_") for f in files_lower):
        add("local-fast")
    if not rec:
        add("local-fast")
    return rec


def _validation_commands(targets: list[str], profiles: list[str]) -> list[str]:
    cmds = ["python3 scripts/test_rig.py", "python3 scripts/test_swift_log_parser.py"]
    if "cleanup-review" in profiles or "daemon-runtime" in profiles:
        cmds.append("python3 scripts/anigma_pipeline.py run --profile cleanup-review --task td-cleanup-005")
    if "daemon-runtime" in profiles and "AnigmaDaemonCore" in targets:
        cmds.append("python3 scripts/rig.py swift build --target AnigmaDaemonCore")
    if any(t in {"AnigmaDaemonCore", "anigmad"} for t in targets):
        cmds.append("python3 scripts/rig.py audit executable-consolidation --mode gate --focus anigmad --baseline Docs/baselines/executable-consolidation-baseline.json")
    return cmds


def compute(repo_root: Path, *, mode: str, base: str | None = None, head: str | None = None, stdin_files: list[str] | None = None, task: str | None = None, command: list[str] | None = None) -> AffectedResult:
    repo_map = _load_json(repo_root / "Docs" / "atlas" / "repo-map.json", [])
    targets_data = _load_json(repo_root / "Docs" / "atlas" / "targets.json", {})
    risk_index = _load_json(repo_root / "Docs" / "atlas" / "risk-index.json", [])

    if stdin_files is not None:
        changed_files = sorted(dict.fromkeys([f for f in (_normalize(line) for line in stdin_files) if f]))
        mode_label = "stdin"
    else:
        changed_files = _git_changed_files(repo_root, base, head)
        mode_label = "git"

    directly_affected_targets, unknown_files = _infer_targets_from_paths(changed_files, targets_data)
    if repo_map:
        for target in _repo_map_direct_targets(changed_files, repo_map):
            if target not in directly_affected_targets:
                directly_affected_targets.append(target)
        directly_affected_targets = sorted(dict.fromkeys(directly_affected_targets))

    upstream_or_dependent_targets: list[str] = []
    risks = _affected_risks_for_targets_and_files(risk_index, changed_files, directly_affected_targets)
    profiles = _load_profiles(repo_root)
    recommended_profiles = _recommend_profiles(changed_files, directly_affected_targets, risks, profiles)
    validation_commands = _validation_commands(directly_affected_targets, recommended_profiles)

    target_notes = []
    if not directly_affected_targets and unknown_files:
        target_notes.append("No direct target inference from changed files.")
    if "Package.swift" in changed_files:
        target_notes.append("Package graph changes detected; prefer backend-regularization.")

    return AffectedResult(
        command=command or [],
        mode=mode_label,
        base=base,
        head=head,
        changed_files=changed_files,
        unknown_files=unknown_files,
        directly_affected_targets=directly_affected_targets,
        upstream_or_dependent_targets=upstream_or_dependent_targets,
        affected_risks=risks,
        recommended_profiles=recommended_profiles,
        recommended_validation_commands=validation_commands,
        target_notes=target_notes,
    )


def render_summary(result: AffectedResult, task: str | None = None) -> str:
    lines = [
        "# Rig Affected Summary",
        "",
        f"- Mode: `{result.mode}`",
        f"- Base: `{result.base or 'n/a'}`",
        f"- Head: `{result.head or 'n/a'}`",
        f"- Task: `{task or 'n/a'}`",
        "",
        "## Changed Files",
    ]
    for path in result.changed_files:
        lines.append(f"- `{path}`")
    lines.extend(["", "## Directly Affected Targets"])
    for target in result.directly_affected_targets:
        lines.append(f"- `{target}`")
    if not result.directly_affected_targets:
        lines.append("- `n/a`")
    lines.extend(["", "## Unknown Files"])
    for path in result.unknown_files:
        lines.append(f"- `{path}`")
    if not result.unknown_files:
        lines.append("- `n/a`")
    lines.extend(["", "## Recommended Profiles"])
    for profile in result.recommended_profiles:
        lines.append(f"- `{profile}`")
    if not result.recommended_profiles:
        lines.append("- `n/a`")
    lines.extend(["", "## Recommended Validation Commands"])
    for cmd in result.recommended_validation_commands:
        lines.append(f"- `{cmd}`")
    if not result.recommended_validation_commands:
        lines.append("- `n/a`")
    lines.extend(["", "## Risk Count", f"- `{len(result.affected_risks)}`"])
    return "\n".join(lines) + "\n"


def write_outputs(repo_root: Path, result: AffectedResult, task: str | None = None) -> dict[str, Path]:
    out_dir = repo_root / ".build" / "rig" / "affected"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict() | {
        "task": task,
        "changed_file_count": len(result.changed_files),
        "affected_risk_count": len(result.affected_risks),
    }
    files_json = out_dir / "files.json"
    targets_json = out_dir / "targets.json"
    risks_json = out_dir / "risks.json"
    profiles_json = out_dir / "profiles.json"
    summary_md = out_dir / "summary.md"
    write_json_stable(files_json, {
        "command": payload["command"],
        "mode": payload["mode"],
        "base": payload["base"],
        "head": payload["head"],
        "task": task,
        "changed_files": result.changed_files,
        "unknown_files": result.unknown_files,
        "changed_file_count": len(result.changed_files),
    })
    write_json_stable(targets_json, {
        "command": payload["command"],
        "mode": payload["mode"],
        "base": payload["base"],
        "head": payload["head"],
        "task": task,
        "directly_affected_targets": result.directly_affected_targets,
        "upstream_or_dependent_targets": result.upstream_or_dependent_targets,
        "unknown_files": result.unknown_files,
    })
    write_json_stable(risks_json, {
        "command": payload["command"],
        "mode": payload["mode"],
        "base": payload["base"],
        "head": payload["head"],
        "task": task,
        "affected_risk_count": len(result.affected_risks),
        "affected_risks": result.affected_risks,
        "grouped_by_target": _group_risks(result.affected_risks, "target"),
        "grouped_by_category": _group_risks(result.affected_risks, "category"),
        "grouped_by_severity": _group_risks(result.affected_risks, "severity"),
        "grouped_by_confidence": _group_risks(result.affected_risks, "confidence"),
    })
    write_json_stable(profiles_json, {
        "command": payload["command"],
        "mode": payload["mode"],
        "base": payload["base"],
        "head": payload["head"],
        "task": task,
        "recommended_profiles": result.recommended_profiles,
        "recommended_validation_commands": result.recommended_validation_commands,
        "target_notes": result.target_notes,
    })
    summary_md.write_text(render_summary(result, task=task), encoding="utf-8")
    return {
        "files_json": files_json,
        "targets_json": targets_json,
        "risks_json": risks_json,
        "profiles_json": profiles_json,
        "summary_md": summary_md,
    }


def _group_risks(risks: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for risk in risks:
        value = str(risk.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
