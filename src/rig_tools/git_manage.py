from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo_root, text=True, capture_output=True, check=False)


def inside_repo(repo_root: Path) -> bool:
    res = git(repo_root, "rev-parse", "--is-inside-work-tree")
    return res.returncode == 0 and res.stdout.strip() == "true"


def current_branch(repo_root: Path) -> str | None:
    res = git(repo_root, "rev-parse", "--abbrev-ref", "HEAD")
    return res.stdout.strip() if res.returncode == 0 else None


def current_head(repo_root: Path) -> str | None:
    res = git(repo_root, "rev-parse", "HEAD")
    return res.stdout.strip() if res.returncode == 0 else None


def porcelain_status(repo_root: Path) -> list[str]:
    res = git(repo_root, "status", "--porcelain=v1", "-z")
    if res.returncode != 0:
        return []
    return [item for item in res.stdout.split("\0") if item]


def parse_porcelain(entries: list[str]) -> dict[str, list[str] | bool]:
    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    for entry in entries:
        code = entry[:2]
        path = entry[3:].strip()
        if code == "??":
            untracked.append(path)
            continue
        if code[0] != " ":
            staged.append(path)
        if code[1] != " ":
            unstaged.append(path)
    changed = sorted(set(staged + unstaged + untracked))
    return {
        "staged_files": sorted(set(staged)),
        "unstaged_files": sorted(set(unstaged)),
        "untracked_files": sorted(set(untracked)),
        "changed_files": changed,
        "dirty": bool(entries),
    }


def classify(path: str) -> str:
    p = Path(path)
    s = path.lower()
    if s.startswith("docs/proofs/"):
        return "proofs"
    if s.startswith("docs/baselines/"):
        return "baselines"
    if s.startswith("docs/atlas/"):
        return "atlas"
    if s.startswith("docs/pipeline/") or s.startswith("docs/indexes/") or s.startswith("docs/dev/"):
        return "docs"
    if s.startswith(".build/rig/") or s.startswith(".build/anigma-") or s.startswith(".build/anigma-pipeline/") or s.startswith(".build/review-bundles/"):
        return "generated_or_build"
    if s.startswith("scripts/"):
        return "scripts"
    if s.startswith("anigma/") and p.suffix in {".swift", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".m", ".mm", ".metal"}:
        return "production_source"
    return "unknown"


def collect_status(repo_root: Path) -> dict[str, Any]:
    entries = porcelain_status(repo_root)
    parsed = parse_porcelain(entries)
    categories: dict[str, int] = {}
    for file_path in parsed["changed_files"]:
        key = classify(file_path)
        categories[key] = categories.get(key, 0) + 1
    return {
        "available": inside_repo(repo_root),
        "branch": current_branch(repo_root),
        "head": current_head(repo_root),
        "dirty": parsed["dirty"],
        "staged_files": parsed["staged_files"],
        "unstaged_files": parsed["unstaged_files"],
        "untracked_files": parsed["untracked_files"],
        "changed_files": parsed["changed_files"],
        "categories": dict(sorted(categories.items())),
        "production_source_changed": any(classify(p) == "production_source" for p in parsed["changed_files"]),
        "baseline_files_changed": [p for p in parsed["changed_files"] if classify(p) == "baselines"],
        "proof_files_changed": [p for p in parsed["changed_files"] if classify(p) == "proofs"],
    }


def latest_result(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / ".build" / "rig" / "results" / "latest.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "status": data.get("status"),
        "exit_code": data.get("exit_code"),
        "command_group": data.get("command_group"),
        "command": data.get("command"),
        "run_id": data.get("run_id"),
        "result_path": str(path.relative_to(repo_root)),
    }


def latest_schema_validation(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / ".build" / "rig" / "schema-validation" / "latest.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "status": data.get("status"),
        "report_path": str(path.relative_to(repo_root)),
    }


def latest_affected(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / ".build" / "rig" / "affected" / "summary.md"
    if not path.exists():
        return None
    return {"summary_md": str(path.relative_to(repo_root))}


def latest_swift_diagnostics(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / ".build" / "rig" / "swift-diagnostics" / "latest.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "status": data.get("status"),
        "exit_code": data.get("exit_code"),
        "target": data.get("target"),
        "latest_json": str(path.relative_to(repo_root)),
        "latest_md": str(path.with_suffix(".md").relative_to(repo_root)) if path.with_suffix(".md").exists() else None,
    }


def latest_registry_gate(repo_root: Path) -> dict[str, Any] | None:
    root = repo_root / ".build" / "anigma-diagnostics" / "tasks"
    if not root.exists():
        return None
    candidates = sorted(root.glob("*/*/*/logs/validator-registry-check.json"), key=lambda p: (p.stat().st_mtime, p.as_posix()))
    if not candidates:
        return None
    path = candidates[-1]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "status": data.get("status"),
        "exit_code": data.get("exitCode"),
        "failure_count": data.get("failureCount"),
        "warning_count": data.get("warningCount"),
        "report_path": str(path.relative_to(repo_root)),
        "log_path": str(path.with_suffix(".log").relative_to(repo_root)) if path.with_suffix(".log").exists() else None,
        "diagnostic_run_path": str(path.parent.parent.relative_to(repo_root)),
        "timestamp_or_run_id": path.parent.parent.parent.name,
    }


def latest_review_bundle(repo_root: Path) -> dict[str, Any] | None:
    root = repo_root / ".build" / "review-bundles"
    if not root.exists():
        return None
    bundles = sorted(root.glob("*.zip"), key=lambda p: (p.stat().st_mtime, p.as_posix()))
    if not bundles:
        return None
    return {"path": str(bundles[-1].relative_to(repo_root))}


def latest_proof(repo_root: Path) -> dict[str, Any] | None:
    root = repo_root / "Docs" / "proofs"
    if not root.exists():
        return None
    proofs = sorted(root.glob("*.md"), key=lambda p: (p.stat().st_mtime, p.as_posix()))
    if not proofs:
        return None
    return {"path": str(proofs[-1].relative_to(repo_root))}


def generate_commit_message(task: str, changed_files: list[str], proof: dict[str, Any] | None, registry_gate: dict[str, Any] | None, rig_result: dict[str, Any] | None, schema: dict[str, Any] | None) -> str:
    if any(Path(p).suffix == ".swift" for p in changed_files):
        prefix = "fix(daemon)"
    elif any(p.startswith("Docs/") for p in changed_files):
        prefix = "docs(rig)"
    elif any(Path(p).name.startswith("test_") or "test" in Path(p).name.lower() for p in changed_files):
        prefix = "test(rig)"
    else:
        prefix = "chore(cleanup)"
    body = [f"Task: {task}"]
    if proof:
        body.append(f"Proof: {proof.get('path')}")
    if registry_gate:
        body.append(f"Registry gate: {registry_gate.get('status')} ({registry_gate.get('report_path')})")
    if rig_result:
        body.append(f"Latest Rig result: {rig_result.get('status')} / {rig_result.get('command_group')}")
    if schema:
        body.append(f"Schema validation: {schema.get('status')}")
    return f"{prefix}: task {task}\n\n" + "\n".join(body) + "\n"


def plan_commit(repo_root: Path, task: str, allowed_paths: list[str] | None = None, *, include_untracked: bool = True) -> dict[str, Any]:
    status = collect_status(repo_root)
    allowed_paths = allowed_paths or []
    changed = status["changed_files"]
    included: list[str] = []
    excluded: list[str] = []
    for path in changed:
        if allowed_paths and not any(path == allowed or path.startswith(allowed.rstrip("/") + "/") for allowed in allowed_paths):
            excluded.append(path)
            continue
        included.append(path)
    forbidden = [path for path in included if classify(path) == "unknown"]
    baselines_changed = any(classify(path) == "baselines" for path in included)
    production_changed = any(classify(path) == "production_source" for path in included)
    proof = latest_proof(repo_root)
    registry_gate = latest_registry_gate(repo_root)
    rig_result = latest_result(repo_root)
    schema = latest_schema_validation(repo_root)
    affected = latest_affected(repo_root)
    review_bundle = latest_review_bundle(repo_root)
    commit_message = generate_commit_message(task, included, proof, registry_gate, rig_result, schema)
    blocking_reasons: list[str] = []
    scope_status = "failed" if forbidden else "passed"
    validation_status = "passed"
    if registry_gate and registry_gate.get("status") not in {None, "pass", "passed"}:
        validation_status = "failed"
    schema_status = schema.get("status") if schema else "unknown"
    if scope_status == "failed":
        blocking_reasons.append("scope has forbidden files")
    if baselines_changed:
        blocking_reasons.append("baseline changes require explicit allow flag")
    if production_changed and not proof:
        blocking_reasons.append("production source changed without proof artifact")
    if validation_status == "failed":
        blocking_reasons.append("validation failed")
    if registry_gate and registry_gate.get("status") not in {None, "pass", "passed"}:
        blocking_reasons.append("registry gate failed")
    status_value = "blocked" if blocking_reasons else ("needs_confirmation" if not included else "ready_to_commit")
    return {
        "schema_version": "rig.git_commit_plan.v1",
        "task": task,
        "generated_at": utc_now(),
        "branch": status.get("branch"),
        "head": status.get("head"),
        "dirty": status.get("dirty"),
        "staged_files": status.get("staged_files", []),
        "unstaged_files": status.get("unstaged_files", []),
        "untracked_files": status.get("untracked_files", []),
        "included_files": included,
        "excluded_files": excluded,
        "forbidden_files": forbidden,
        "scope_status": scope_status,
        "validation_status": validation_status,
        "schema_status": schema_status,
        "registry_gate_status": registry_gate.get("status") if registry_gate else "unknown",
        "known_blockers": [],
        "baselines_changed": baselines_changed,
        "production_source_changed": production_changed,
        "proof_artifact": proof,
        "review_bundle": review_bundle,
        "commit_message": commit_message,
        "blocking_reasons": blocking_reasons,
        "status": status_value,
        "latest_affected_summary": affected,
        "latest_rig_result": rig_result,
        "latest_swift_diagnostics": latest_swift_diagnostics(repo_root),
        "latest_schema_validation": schema,
        "latest_registry_gate": registry_gate,
    }


def write_plan(repo_root: Path, plan: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = repo_root / ".build" / "rig" / "git"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"commit-plan-{plan['task']}.json"
    md_path = out_dir / f"commit-plan-{plan['task']}.md"
    json_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    blocking = [f"- {reason}" for reason in plan["blocking_reasons"]] or ["- none"]
    included = [f"- `{path}`" for path in plan["included_files"]] or ["- none"]
    excluded = [f"- `{path}`" for path in plan["excluded_files"]] or ["- none"]
    lines = [
        "# Commit Plan",
        "",
        f"- Task: `{plan['task']}`",
        f"- Status: `{plan['status']}`",
        f"- Branch: `{plan['branch']}`",
        f"- Head: `{plan['head']}`",
        f"- Dirty: `{plan['dirty']}`",
        f"- Registry gate: `{plan['registry_gate_status']}`",
        f"- Validation status: `{plan['validation_status']}`",
        f"- Schema status: `{plan['schema_status']}`",
        f"- Proof: `{plan['proof_artifact']['path'] if plan.get('proof_artifact') else 'n/a'}`",
        "",
        "## Blocking Reasons",
        *blocking,
        "",
        "## Included Files",
        *included,
        "",
        "## Excluded Files",
        *excluded,
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def load_plan(plan_path: Path) -> dict[str, Any]:
    return json.loads(plan_path.read_text(encoding="utf-8"))


def stage_from_plan(repo_root: Path, plan: dict[str, Any], confirm: bool) -> subprocess.CompletedProcess[str]:
    if not confirm:
        return subprocess.CompletedProcess(["git", "add"], 5, stdout="", stderr="confirm required")
    files = plan.get("included_files", [])
    if not files:
        return subprocess.CompletedProcess(["git", "add"], 0, stdout="", stderr="")
    return subprocess.run(["git", "add", "--", *files], cwd=repo_root, text=True, capture_output=True, check=False)


def commit_from_plan(repo_root: Path, plan: dict[str, Any], confirm: bool, *, allow_head_change: bool = False) -> subprocess.CompletedProcess[str]:
    if not confirm:
        return subprocess.CompletedProcess(["git", "commit"], 5, stdout="", stderr="confirm required")
    status = collect_status(repo_root)
    if not allow_head_change and status.get("head") != plan.get("head"):
        return subprocess.CompletedProcess(["git", "commit"], 4, stdout="", stderr="HEAD changed")
    if sorted(status.get("changed_files", [])) != sorted(plan.get("included_files", [])):
        return subprocess.CompletedProcess(["git", "commit"], 4, stdout="", stderr="included file set changed")
    res = subprocess.run(["git", "commit", "-m", plan.get("commit_message", "chore(cleanup): task")], cwd=repo_root, text=True, capture_output=True, check=False)
    return res
