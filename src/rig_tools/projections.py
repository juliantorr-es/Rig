from __future__ import annotations

import json
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from rig_tools.state_store import StateStore
from rig_tools.settings_store import SettingsStore
from rig_tools.memory_contracts import memory_settings, read_jsonl_tail, projected_bytes

class ProjectionsBuilder:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.projections_dir = self.repo_root / ".build" / "rig" / "projections"
        self.state_store = StateStore(repo_root)
        self.settings_store = SettingsStore(repo_root)
        self.schema_version = "rig.projection_manifest.v1"

    def rebuild(self, dry_run: bool = False) -> Dict[str, Any]:
        """Rebuilds all required projections."""
        now = datetime.now(timezone.utc).isoformat()
        
        manifest = {
            "schema_version": self.schema_version,
            "created_at": now,
            "status": "pass",
            "projections": [],
            "source_artifacts": [],
            "source_tables": [],
            "warnings": [],
            "authoritative": False
        }
        limits = memory_settings(self.settings_store.get_effective_settings())

        # 1. Kanban
        kanban_res = self._build_kanban(now)
        manifest["projections"].append(kanban_res["metadata"])
        if kanban_res["metadata"]["status"] == "warn":
            manifest["status"] = "warn"
            manifest["warnings"].extend(kanban_res["metadata"]["warnings"])

        # 2. Task Graph
        graph_res = self._build_task_graph(now, kanban_res["data"])
        manifest["projections"].append(graph_res["metadata"])

        # 3. Monitor
        monitor_res = self._build_monitor(now)
        manifest["projections"].append(monitor_res["metadata"])

        # 4. TUI Snapshot
        tui_res = self._build_tui_snapshot(now, kanban_res["data"], monitor_res["data"], limits)
        manifest["projections"].append(tui_res["metadata"])

        if not dry_run:
            self.projections_dir.mkdir(parents=True, exist_ok=True)
            self._write_projection("kanban.json", kanban_res["data"])
            self._write_projection("task-graph.json", graph_res["data"])
            self._write_projection("monitor.json", monitor_res["data"])
            self._write_projection("tui-snapshot.json", tui_res["data"])
            
            # Latest summary
            self._write_projection("latest.json", manifest)
            
            # Markdown summary
            md = self._generate_markdown_summary(manifest)
            (self.projections_dir / "latest.md").write_text(md, encoding="utf-8")
        
        return manifest

    def _build_kanban(self, timestamp: str) -> Dict[str, Any]:
        """Derives Kanban columns from tasks."""
        # For now, we mock some tasks if the table is empty to allow testing
        tasks = []
        try:
            with self.state_store.connect() as conn:
                res = conn.execute("SELECT * FROM tasks").fetchall()
                tasks = [dict(r) for r in res]
        except Exception:
            pass

        columns = {
            "backlog": [],
            "ready": [],
            "running": [],
            "approval": [],
            "blocked": [],
            "review": [],
            "done": []
        }
        
        for t in tasks:
            status = t.get("status", "backlog")
            if status in columns:
                columns[status].append(t)
            else:
                columns["backlog"].append(t)

        status = "pass"
        warnings = []
        if not tasks:
            status = "warn"
            warnings.append("No tasks found in state store. Kanban is empty.")

        metadata = {
            "projection_id": "kanban",
            "kind": "kanban",
            "status": status,
            "path": ".build/rig/projections/kanban.json",
            "source_count": 1,
            "record_count": len(tasks),
            "rebuilt_at": timestamp,
            "warnings": warnings,
            "authoritative": False
        }
        
        return {"metadata": metadata, "data": columns}

    def _build_task_graph(self, timestamp: str, kanban_data: Dict[str, Any]) -> Dict[str, Any]:
        """Derives task graph nodes and edges."""
        nodes = []
        for col in kanban_data.values():
            for t in col:
                nodes.append({
                    "id": t.get("task_id"),
                    "label": t.get("label"),
                    "status": t.get("status")
                })
        
        # Mock edges for now
        edges = []
        
        metadata = {
            "projection_id": "task_graph",
            "kind": "task_graph",
            "status": "pass" if nodes else "warn",
            "path": ".build/rig/projections/task-graph.json",
            "source_count": 1,
            "record_count": len(nodes),
            "rebuilt_at": timestamp,
            "warnings": [] if nodes else ["No nodes for task graph."],
            "authoritative": False
        }
        
        return {"metadata": metadata, "data": {"nodes": nodes, "edges": edges}}

    def _build_monitor(self, timestamp: str) -> Dict[str, Any]:
        """Summarizes system health and latest runs."""
        state_status = self.state_store.get_status()
        
        # Get latest action result count
        res_count = 0
        try:
            with self.state_store.connect() as conn:
                res = conn.execute("SELECT count(*) FROM action_results").fetchone()
                res_count = res[0]
        except Exception:
            pass

        data = {
            "state_store": {
                "status": state_status["status"],
                "table_count": len(state_status["tables"])
            },
            "action_results": {
                "total_count": res_count
            },
            "system": {
                "pressure": "low", # Stub
                "time": timestamp
            }
        }
        
        metadata = {
            "projection_id": "monitor",
            "kind": "monitor",
            "status": "pass",
            "path": ".build/rig/projections/monitor.json",
            "source_count": 2,
            "record_count": 3,
            "rebuilt_at": timestamp,
            "warnings": [],
            "authoritative": False
        }
        
        return {"metadata": metadata, "data": data}

    def _build_tui_snapshot(self, timestamp: str, kanban_data: Dict[str, Any], monitor_data: Dict[str, Any], limits: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregates data for the TUI read model."""
        counts = {k: len(v) for k, v in kanban_data.items()}
        events_path = self.repo_root / ".build" / "rig" / "events"
        latest_events = []
        if events_path.exists():
            event_files = sorted([p for p in events_path.glob("*.jsonl") if p.is_file()], key=lambda p: p.stat().st_mtime)
            if event_files:
                latest_events = read_jsonl_tail(event_files[-1], max_events=int(limits.get("max_tui_events", 500)))

        data = {
            "mode": "safe", # Default
            "selected_task_id": None,
            "board_counts": counts,
            "blocked_count": counts.get("blocked", 0),
            "runnable_count": counts.get("ready", 0),
            "latest_events": latest_events,
            "monitor_summary": monitor_data
        }
        
        metadata = {
            "projection_id": "tui_snapshot",
            "kind": "tui_snapshot",
            "status": "pass",
            "path": ".build/rig/projections/tui-snapshot.json",
            "source_count": 2,
            "record_count": 5,
            "rebuilt_at": timestamp,
            "warnings": [],
            "authoritative": False
        }
        
        payload_bytes = len(json.dumps(data).encode("utf-8"))
        if payload_bytes > int(limits.get("max_projection_bytes", 1000000)):
            metadata["status"] = "warn"
            metadata.setdefault("warnings", []).append(f"tui_snapshot_size_bytes={payload_bytes}")
        return {"metadata": metadata, "data": data}

    def _write_projection(self, name: str, data: Any):
        path = self.projections_dir / name
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _generate_markdown_summary(self, manifest: Dict[str, Any]) -> str:
        md = [f"# Rig OS Projections Manifest - {manifest['status'].upper()}"]
        md.append(f"Generated at: {manifest['created_at']}\n")
        
        md.append("## Projections")
        for p in manifest["projections"]:
            md.append(f"- **{p['kind'].upper()}**: {p['status'].upper()}")
            md.append(f"  - Path: `{p['path']}`")
            md.append(f"  - Records: {p['record_count']}")
        
        if manifest["warnings"]:
            md.append("\n## Warnings")
            for w in manifest["warnings"]:
                md.append(f"- {w}")
                
        return "\n".join(md)
