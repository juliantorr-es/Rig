from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

SCHEMA_VERSION = "rig.kanban_board.v1"

COLUMNS = ["backlog", "ready", "running", "approval", "blocked", "review", "done"]

def build_kanban_board(repo_root: Path) -> dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    tasks = _load_tasks_from_registry(repo_root)
    # Enrich tasks with artifact data
    cards = []
    for task_id, task in tasks.items():
        cards.append(_enrich_task_to_card(repo_root, task_id, task))
        
    for card in cards:
        status = card["status"].lower()
        if status in {"queued"}:
            card["column_id"] = "ready"
        elif status in {"running", "in_progress"}:
            card["column_id"] = "running"
        elif status in {"pending_approval", "needs_human_approval"}:
            card["column_id"] = "approval"
        elif status in {"blocked", "failed"}:
            card["column_id"] = "blocked"
        elif status in {"reviewable", "in_review"}:
            card["column_id"] = "review"
        elif status in {"completed", "passed", "done"}:
            card["column_id"] = "done"
        elif status in {"ready"}:
            card["column_id"] = "ready"
        else:
            card["column_id"] = "backlog"

    board = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now,
        "columns": COLUMNS,
        "cards": cards,
        "source_artifacts": [], # TODO
        "warnings": [],
        "authoritative": False,
    }
    
    _write_artifacts(repo_root, board)
    return board

def _load_tasks_from_registry(repo_root: Path) -> dict[str, dict[str, Any]]:
    registry_path = repo_root / "Docs" / "td" / "td-task-registry.yaml"
    tasks = {}
    if not registry_path.exists():
        return tasks
        
    if HAS_YAML:
        try:
            data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            for t in data.get("tasks", []):
                tasks[t["id"]] = t
        except Exception:
            pass
            
    # Fallback/Complement with basic scan
    if not tasks:
        try:
            content = registry_path.read_text(encoding="utf-8")
            task_blocks = content.split("- id:")
            for block in task_blocks[1:]:
                lines = block.split("\n")
                task_id = lines[0].strip().strip("'\"")
                title = ""
                status = "backlog"
                for line in lines:
                    if line.strip().startswith("title:"): title = line.split("title:")[1].strip().strip("'\"")
                    if line.strip().startswith("status:"): status = line.split("status:")[1].strip()
                tasks[task_id] = {"id": task_id, "title": title, "status": status}
        except Exception:
            pass
            
    return tasks

def _enrich_task_to_card(repo_root: Path, task_id: str, registry_task: dict[str, Any]) -> dict[str, Any]:
    card = {
        "card_id": f"card-{task_id}",
        "task_id": task_id,
        "title": registry_task.get("title", task_id),
        "status": registry_task.get("status", "backlog"),
        "target": registry_task.get("target"),
        "risk": registry_task.get("risk", "medium"),
        "profiles": registry_task.get("profiles", []),
        "blocked_by": registry_task.get("blocked_by", []),
        "blocks": registry_task.get("blocks", []),
        "recommended_next_action": "init",
        "warnings": [],
        "source_paths": [str(repo_root / "Docs" / "td" / "td-task-registry.yaml")],
    }
    
    # Check artifacts for status overrides/enrichment
    base = repo_root / ".build" / "rig"
    
    # Queue status
    queue_path = base / "queue" / "queue.json"
    if queue_path.exists():
        try:
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
            for item in queue.get("items", []):
                if task_id in item.get("command", ""):
                    card["latest_queue_status"] = item.get("status")
                    if item.get("status") == "running":
                        card["status"] = "running"
        except Exception:
            pass
            
    # Loop status
    loop_path = base / "loop" / "latest.json"
    if loop_path.exists():
        try:
            loop = json.loads(loop_path.read_text(encoding="utf-8"))
            if loop.get("task") == task_id:
                card["latest_loop_status"] = loop.get("status")
                if loop.get("status") == "running":
                    card["status"] = "running"
        except Exception:
            pass
            
    # Gates
    gates_dir = base / "gates"
    if gates_dir.exists():
        for p in gates_dir.glob("*.json"):
            try:
                gate = json.loads(p.read_text(encoding="utf-8"))
                if gate.get("task") == task_id:
                    card["latest_gate_status"] = gate.get("status")
                    if gate.get("status") == "pending":
                        card["status"] = "pending_approval"
            except Exception:
                continue

    # Proofs
    proof_dir = repo_root / "Docs" / "proofs"
    latest_proof = None
    if proof_dir.exists():
        matches = sorted(proof_dir.glob(f"*{task_id}*.md"), key=lambda p: p.stat().st_mtime)
        if matches:
            latest_proof = matches[-1]
            card["latest_proof_path"] = str(latest_proof.relative_to(repo_root))
            
    # Bundles
    bundle_dir = base / "bundles"
    if bundle_dir.exists():
        matches = sorted(bundle_dir.glob(f"*{task_id}*.zip"), key=lambda p: p.stat().st_mtime)
        if matches:
            card["latest_bundle_path"] = str(matches[-1].relative_to(repo_root))

    # Context Packs
    context_dir = base / "context"
    if context_dir.exists():
        matches = sorted(context_dir.glob(f"*{task_id}*.json"), key=lambda p: p.stat().st_mtime)
        if matches:
            card["latest_context_path"] = str(matches[-1].relative_to(repo_root))

    # Agent Plans
    agent_plans_dir = base / "agents" / "plans"
    if agent_plans_dir.exists():
        matches = sorted(agent_plans_dir.glob(f"*{task_id}*.json"), key=lambda p: p.stat().st_mtime)
        if matches:
            card["latest_agent_plan_path"] = str(matches[-1].relative_to(repo_root))

    # Git Status
    git_status_path = base / "git" / "status.json"
    if git_status_path.exists():
        try:
            gs = json.loads(git_status_path.read_text(encoding="utf-8"))
            if gs.get("task") == task_id:
                card["latest_git_plan"] = gs.get("plan_id")
        except Exception:
            pass
            
    # Recommended Action & Reason
    if card["status"] == "backlog":
        card["recommended_next_action"] = "context_build"
        card["recommendation_reason"] = "Task is in backlog; need to build context for planning."
    elif card["status"] == "ready":
        if not card.get("latest_context_path"):
            card["recommended_next_action"] = "context_build"
            card["recommendation_reason"] = "Task is ready but missing context pack."
        else:
            card["recommended_next_action"] = "loop_plan"
            card["recommendation_reason"] = "Context ready; proceed to loop planning."
    elif card["status"] == "pending_approval":
        card["recommended_next_action"] = "refresh_status"
        card["recommendation_reason"] = "Awaiting human decision on approval gate."
    elif card["status"] in {"reviewable", "review"}:
        card["recommended_next_action"] = "bundle_session_dry_run"
        card["recommendation_reason"] = "Implementation finished; run dry-run bundle for verification."
    elif card["status"] in {"running", "in_progress"}:
        card["recommended_next_action"] = "refresh_status"
        card["recommendation_reason"] = "Task is actively running; monitor event stream."
    elif card["status"] in {"passed", "completed", "done"}:
        card["recommended_next_action"] = "bundle_session"
        card["recommendation_reason"] = "Task completed and verified; bundle session for handoff."
    else:
        card["recommended_next_action"] = "refresh_status"
        card["recommendation_reason"] = "Check task status and artifacts."
        
    return card

def _write_artifacts(repo_root: Path, board: dict[str, Any]) -> None:
    out_dir = repo_root / ".build" / "rig" / "kanban"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    (out_dir / "latest.json").write_text(json.dumps(board, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    
    # Markdown summary
    md = [f"# Rig Kanban Board - {board['created_at']}", ""]
    for col in COLUMNS:
        col_cards = [c for c in board["cards"] if c["column_id"] == col]
        md.append(f"## {col.upper()} ({len(col_cards)})")
        for c in col_cards:
            md.append(f"- **{c['task_id']}**: {c['title']}")
        md.append("")
        
    (out_dir / "latest.md").write_text("\n".join(md) + "\n", encoding="utf-8")
