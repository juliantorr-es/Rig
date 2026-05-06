from __future__ import annotations

import json
import time
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "rig.task_graph.v1"

def build_task_graph(repo_root: Path, kanban_cards: list[dict[str, Any]]) -> dict[str, Any]:
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    nodes = []
    edges = []
    
    # 1. Create nodes from kanban cards
    for card in kanban_cards:
        nodes.append({
            "task_id": card["task_id"],
            "title": card["title"],
            "status": card["status"],
            "column_id": card["column_id"],
            "risk": card["risk"],
            "target": card["target"],
            "source_paths": card["source_paths"],
        })
        
        # Explicit edges from registry
        for blocker in card.get("blocked_by", []):
            edges.append({
                "from_task": blocker,
                "to_task": card["task_id"],
                "relationship": "blocks",
                "reason": "explicit dependency in registry",
                "source_path": card["source_paths"][0],
            })
            
    # 2. Infer edges from briefs/followups
    inferred_edges = _infer_edges(repo_root, kanban_cards)
    edges.extend(inferred_edges)
    
    # Remove duplicate edges
    unique_edges = []
    seen = set()
    for e in edges:
        key = (e["from_task"], e["to_task"], e["relationship"])
        if key not in seen:
            unique_edges.append(e)
            seen.add(key)
            
    # 3. Derive runnable and blocked tasks
    node_ids = {n["task_id"] for n in nodes}
    runnable = []
    blocked = []
    
    for node in nodes:
        tid = node["task_id"]
        # Hard blockers: from_task is NOT done
        blockers = [e["from_task"] for e in unique_edges if e["to_task"] == tid and e["relationship"] in {"blocks", "depends_on"}]
        
        unresolved = []
        for b in blockers:
            b_node = next((n for n in nodes if n["task_id"] == b), None)
            if b_node and b_node["column_id"] != "done":
                unresolved.append(b)
                
        is_blocked_by_gate = node["status"] == "pending_approval"
        is_blocked_by_status = node["status"] == "blocked"
        
        if unresolved or is_blocked_by_gate or is_blocked_by_status:
            blocked.append({
                "task_id": tid,
                "reasons": unresolved + (["pending approval gate"] if is_blocked_by_gate else []) + (["status blocked"] if is_blocked_by_status else [])
            })
        elif node["column_id"] in {"backlog", "ready", "review"}:
            runnable.append(tid)

    # 4. Cycle Detection (Simple DFS)
    cycles = _detect_cycles(nodes, unique_edges)

    graph = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now,
        "nodes": nodes,
        "edges": unique_edges,
        "blocked_tasks": blocked,
        "runnable_tasks": runnable,
        "cycles": cycles,
        "source_artifacts": [],
        "warnings": [],
        "authoritative": False,
    }
    
    _write_artifacts(repo_root, graph)
    return graph

def _infer_edges(repo_root: Path, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges = []
    task_ids = {c["task_id"] for c in cards}
    
    # Scan briefs
    brief_dir = repo_root / "Docs" / "td" / "briefs"
    if brief_dir.exists():
        for p in brief_dir.glob("*.md"):
            content = p.read_text(encoding="utf-8").lower()
            # Look for "blocked by <task_id>" or "depends on <task_id>"
            for tid in task_ids:
                if tid in content:
                    if f"blocked by {tid}" in content or f"depends on {tid}" in content:
                        # Extract the task ID of this brief from filename
                        current_tid = p.stem
                        if current_tid in task_ids:
                            edges.append({
                                "from_task": tid,
                                "to_task": current_tid,
                                "relationship": "depends_on",
                                "reason": f"inferred from brief {p.name}",
                                "source_path": str(p.relative_to(repo_root)),
                            })
                            
    return edges

def _detect_cycles(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[str]]:
    adj = {}
    for n in nodes:
        adj[n["task_id"]] = []
    for e in edges:
        if e["from_task"] in adj and e["to_task"] in adj:
            adj[e["from_task"]].append(e["to_task"])
            
    visited = set()
    path = []
    cycles = []
    
    def dfs(u):
        visited.add(u)
        path.append(u)
        for v in adj.get(u, []):
            if v in path:
                cycles.append(path[path.index(v):] + [v])
            elif v not in visited:
                dfs(v)
        path.pop()
        
    for n in nodes:
        if n["task_id"] not in visited:
            dfs(n["task_id"])
            
    return cycles

def _write_artifacts(repo_root: Path, graph: dict[str, Any]) -> None:
    out_dir = repo_root / ".build" / "rig" / "task-graph"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    (out_dir / "latest.json").write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    
    # Markdown
    md = [f"# Rig Task Graph - {graph['created_at']}", ""]
    md.append(f"Nodes: {len(graph['nodes'])} | Edges: {len(graph['edges'])}")
    md.append(f"Runnable: {len(graph['runnable_tasks'])} | Blocked: {len(graph['blocked_tasks'])}")
    
    md.append("\n## Runnable Tasks")
    for t in graph["runnable_tasks"]:
        md.append(f"- {t}")
        
    md.append("\n## Blocked Tasks")
    for b in graph["blocked_tasks"]:
        md.append(f"- **{b['task_id']}**: blocked by {', '.join(b['reasons'])}")
        
    (out_dir / "latest.md").write_text("\n".join(md) + "\n", encoding="utf-8")
