from __future__ import annotations

from pathlib import Path


ACTION_COMMANDS = {
    "affected_summary": ["python", "scripts/rig.py", "--json", "affected", "summary", "--task", "{task}"],
    "embeddings_query": ["python", "scripts/rig.py", "embeddings", "query", "--backend", "mlx", "{query}", "--top-k", "5"],
    "project_architecture": ["python", "scripts/rig.py", "--json", "project", "architecture", "--target", "AnigmaDaemonCore"],
    "monitor_snapshot": ["python", "scripts/rig.py", "monitor", "snapshot"],
    "schema_validate_results": ["python", "scripts/rig.py", "schema", "validate", "--family", "rig.result.v1"],
    "schema_validate_events": ["python", "scripts/rig.py", "schema", "validate", "--family", "rig.event.v1"],
    "swift_diagnostics": ["python", "scripts/rig.py", "--json", "swift", "build", "--target", "AnigmaDaemonCore"],
    "agent_plan": ["python", "scripts/rig.py", "agent", "plan", "--task", "{task}", "--backend", "mlx", "--model", "{model}"],
    "agent_dry_run": ["python", "scripts/rig.py", "agent", "launch", "--from-plan", "{agent_plan_path}", "--dry-run"],
    "bundle_session": ["python", "scripts/rig.py", "bundle", "session", "--task", "{task}"],
    "local_patch_propose": ["python", "scripts/rig.py", "patch", "propose", "--task", "{task}", "--backend", "{backend}", "--allowed-path", "Docs/dev/rig", "--allowed-path", "scripts", "--dry-run"],
    "stop": [],
}


ACTION_ORDER = [
    "affected_summary",
    "embeddings_query",
    "project_architecture",
    "monitor_snapshot",
    "schema_validate_results",
    "schema_validate_events",
    "swift_diagnostics",
    "agent_plan",
    "agent_dry_run",
    "bundle_session",
    "local_patch_propose",
    "stop",
]


def expand_command(action_id: str, *, task: str, model: str, agent_plan_path: str| Optional = None, query: str| Optional = None) -> list[str]:
    template = ACTION_COMMANDS[action_id]
    out = []
    for part in template:
        out.append(part.format(task=task, model=model, agent_plan_path=agent_plan_path or "", query=query or "RuntimeAuthority shutdown boundary"))
    return out


def latest_agent_plan_path(repo_root: Path) -> str| Optional:
    plans_dir = repo_root / ".build" / "rig" / "agents" / "plans"
    if not plans_dir.exists():
        return None
    candidates = sorted(plans_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    return str(candidates[0].relative_to(repo_root)).replace("\\", "/")
