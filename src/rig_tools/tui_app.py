from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import os
import re
import uuid
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from rich.text import Text

def short_text(value: Optional[Any], limit: int = 30, fallback: str = "unknown") -> str:
    """Safely truncates and formats optional values."""
    text = str(value) if value not in (None, "") else fallback
    return text[:limit]

def bauhaus_marker_for_status(status: str, risk: str = "low", artifact: bool = False) -> str:
    """Returns geometric Bauhaus markers for states."""
    if artifact: return "\u25c6" # ◆
    
    s = str(status).lower()
    r = str(risk).lower()
    
    if s in {"blocked", "failed"} or r == "high": return "\u25b2" # ▲
    if s in {"approval", "warning"} or r == "medium": return "\u25a0" # ■
    if s in {"running", "queued", "in_progress"}: return "\u25cf" # ●
    if s in {"passed", "done", "complete", "review"}: return "\u25ac" # ▬
    return "\u00b7" # ·

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from rig_tools import policy, system_pressure, model_manager, kanban_board, task_graph, tui_views
from rig_tools.tui_state import load_tui_state, save_tui_state, clamp_mode
from rig_tools.tui_actions import ActionRegistry, ActionDefinition, CommandPlan
from rig_tools.tui_events import render_tui_event, render_command_result, render_human_event_line, event_semantic_class, bauhaus_marker_for_status
from rig_tools.tui_board_widgets import TaskCard, KanbanColumn, TaskSelected

SETTINGS_PATH = Path(".build/rig/tui/settings.json")
STATE_PATH = Path(".build/rig/tui/state.json")

def load_tui_settings() -> dict[str, Any]:
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except: pass
    return {"schema_version": "rig.tui_settings.v1", "mode": "safe"}

def save_tui_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    settings["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def load_ui_state() -> dict[str, Any]:
    state = load_tui_state(STATE_PATH)
    runtime = load_tui_settings()
    state["mode"] = clamp_mode(str(state.get("mode") or runtime.get("mode") or "safe"))
    state.setdefault("selected_task_id", None)
    state.setdefault("auto_approve_requested", False)
    state.setdefault("auto_approve_pending", False)
    return state

@dataclass
class CommandResult:
    command_id: str
    status: str
    exit_code: int | None
    started_at: str
    finished_at: str | None
    stdout: str
    stderr: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "warnings": self.warnings,
        }

def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists(): return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None

def _latest_from_dir(root: Path, pattern: str) -> Path | None:
    if not root.exists(): return None
    paths = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime)
    return paths[-1] if paths else None

class RigDataStore:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.base = repo_root / ".build" / "rig"

    def get_snapshot(self, build_derived: bool = False) -> dict[str, Any]:
        state = _read_json(self.base / "monitor" / "state.json") or {}
        loop = _read_json(self.base / "loop" / "latest.json") or {}
        queue = _read_json(self.base / "queue" / "queue.json") or {}
        llm = _read_json(self.base / "llm" / "latest-summary.json") or {}
        git = _read_json(self.base / "git" / "status.json") or {}
        
        prompts = self.base / "prompts"
        prompt_summary = {
            "trace_count": len(list((prompts / "traces").glob("*/trace.json"))) if (prompts / "traces").exists() else 0,
            "quarantine_count": len(list((prompts / "quarantine").glob("*/trace.json"))) if (prompts / "quarantine").exists() else 0,
        }

        # Epics/tasks
        tasks = self.load_tasks_data()
        epics = [t for t in tasks if t.get("type") == "epic"]
        active_tasks = [t for t in tasks if t.get("status") in {"ready", "in_progress", "in_review"}]

        # Agents
        agent_runs_dir = self.base / "agents" / "runs"
        latest_agent_path = _latest_from_dir(agent_runs_dir, "*/agent-run.json")
        latest_agent = _read_json(latest_agent_path) if latest_agent_path else None

        # Gates
        gates_dir = self.base / "gates"
        pending_gates = []
        if gates_dir.exists():
            for p in gates_dir.glob("*.json"):
                g = _read_json(p)
                if g and g.get("status") == "pending":
                    pending_gates.append(g)

        # Auto Policy
        auto_policy = None
        policy_path = self.repo_root / "Docs" / "dev/rig/auto-policies/docs-scripts-auto.yaml"
        if policy_path.exists() and HAS_YAML:
            try:
                auto_policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Telemetry
        pressure = system_pressure.sample_system_pressure(self.repo_root)

        # Models & Agent Discovery
        models_catalog = model_manager.load_catalog(self.repo_root)
        local_models = model_manager.list_registered_models(self.repo_root)
        agent_discovery = _read_json(self.base / "agents" / "discovery" / "latest.json") or {}

        # Workspaces
        from rig_tools.workspace_manager import WorkspaceManager
        wm = WorkspaceManager(self.repo_root)
        workspaces = wm.list_workspaces()
        latest_workspace = _read_json(self.base / "workspaces" / "latest.json") or {}

        # Product
        product_report = _read_json(self.base / "product" / "latest.json") or {}

        # Kanban & Graph
        if build_derived:
            board = kanban_board.build_kanban_board(self.repo_root)
            graph = task_graph.build_task_graph(self.repo_root, board.get("cards", []))
        else:
            board = _read_json(self.base / "kanban" / "latest.json") or {"cards": []}
            graph = _read_json(self.base / "task-graph" / "latest.json") or {}

        return {
            "repo_name": self.repo_root.name,
            "state": state,
            "loop": loop,
            "queue": queue,
            "llm": llm,
            "git": git,
            "prompt_summary": prompt_summary,
            "epics": epics,
            "active_tasks": active_tasks,
            "latest_agent": latest_agent,
            "latest_agent_run_id": latest_agent_path.parent.name if latest_agent_path else None,
            "pending_gates": pending_gates,
            "auto_policy": auto_policy,
            "pressure": pressure,
            "models_catalog": models_catalog,
            "local_models": local_models,
            "agent_discovery": agent_discovery,
            "workspaces": workspaces,
            "latest_workspace": latest_workspace,
            "product_report": product_report,
            "board": board,
            "graph": graph,
        }

    def load_tasks_data(self) -> list[dict[str, Any]]:
        registry_path = self.repo_root / "Docs" / "td" / "td-task-registry.yaml"
        if not registry_path.exists(): return []
        if HAS_YAML:
            try:
                data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
                return data.get("tasks", [])
            except Exception:
                pass
        # Fallback regex parsing
        tasks = []
        try:
            content = registry_path.read_text(encoding="utf-8")
            task_blocks = content.split("- id:")
            for block in task_blocks[1:]:
                lines = block.split("\n")
                task_id = lines[0].strip().strip("'\"")
                title = ""
                status = ""
                for line in lines:
                    if line.strip().startswith("title:"): title = line.split("title:")[1].strip().strip("'\"")
                    if line.strip().startswith("status:"): status = line.split("status:")[1].strip()
                tasks.append({"id": task_id, "title": title, "status": status, "type": "task" if "type: epic" not in block else "epic"})
        except Exception:
            pass
        return tasks

class CommandRunner:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.out_dir = repo_root / ".build" / "rig" / "tui"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.out_dir / "events.jsonl"
        self.registry = ActionRegistry(repo_root)

    def write_event(self, event_type: str, **attributes: Any) -> None:
        event = {
            "schema_version": "rig.event.v1",
            "event_type": event_type,
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "run_id": "tui",
            "command_group": "tui",
            "attributes": attributes,
        }
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")

    def run_plan(self, plan: CommandPlan, timeout: int = 1800) -> CommandResult:
        if not plan.is_valid:
            return CommandResult(plan.action_id, "failed", 1, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), None, "", plan.disabled_reason or "Invalid plan")
            
        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.write_event("command_started", action_id=plan.action_id, argv=plan.argv)
        
        proc = subprocess.Popen(plan.argv, cwd=self.repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            exit_code = proc.returncode
            status = "passed" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            exit_code = None
            status = "timeout"
            
        finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result = CommandResult(plan.action_id, status, exit_code, started_at, finished_at, stdout, stderr)
        
        (self.out_dir / "latest-command.json").write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        (self.out_dir / "latest-command.stdout.log").write_text(stdout, encoding="utf-8")
        (self.out_dir / "latest-command.stderr.log").write_text(stderr, encoding="utf-8")
        self.write_event("command_finished", action_id=plan.action_id, status=status, exit_code=exit_code)
        return result

    def run_argv(self, command_id: str, argv: list[str], timeout: int = 1800) -> CommandResult:
        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.write_event("command_started", action_id=command_id, argv=argv)
        proc = subprocess.Popen(argv, cwd=self.repo_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            exit_code = proc.returncode
            status = "passed" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            exit_code = None
            status = "timeout"
        finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result = CommandResult(command_id, status, exit_code, started_at, finished_at, stdout, stderr)
        (self.out_dir / "latest-command.json").write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
        (self.out_dir / "latest-command.stdout.log").write_text(stdout, encoding="utf-8")
        (self.out_dir / "latest-command.stderr.log").write_text(stderr, encoding="utf-8")
        self.write_event("command_finished", action_id=command_id, status=status, exit_code=exit_code)
        return result

    def write_gate_decision(self, gate_id: str, decision: str, reason: str) -> None:
        gate_path = self.repo_root / ".build" / "rig" / "gates" / f"{gate_id}.json"
        if not gate_path.exists(): return
        gate = _read_json(gate_path)
        if not gate: return
        gate["status"] = decision
        gate["decision"] = decision
        gate["reason"] = reason
        gate["decided_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        gate_path.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
        self.write_event("gate_decided", gate_id=gate_id, decision=decision)

def strip_markup(text: str) -> str:
    if not isinstance(text, str): return str(text)
    return re.sub(r"\[.*?\]", "", text)

def build_app(repo_root: Path, *, mode: str = "safe", refresh_seconds: int = 2):
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical, ScrollableContainer
    from textual.widgets import Button, DataTable, Footer, Header, RichLog, Static, Label, TabbedContent, TabPane, Input
    from textual.binding import Binding
    from textual.worker import Worker, WorkerState
    from textual.screen import ModalScreen
    from textual.message import Message
    from textual.screen import Screen

    class TaskSelected(Message):
        def __init__(self, task_id: str) -> None:
            self.task_id = task_id
            super().__init__()

    class TaskCard(Static):
        def __init__(self, card_data: dict[str, Any], is_selected: bool = False):
            self.card_data = card_data
            self.is_selected = is_selected
            super().__init__(id=f"card-{card_data['task_id']}")

        def compose(self) -> ComposeResult:
            yield Label("", id="card-tid-label")
            yield Label("", id="card-title-label")
            yield Static("", id="card-badges-label")

        def on_mount(self) -> None:
            self.update_ui()

        def update_data(self, card_data: dict[str, Any], is_selected: bool):
            if self.card_data == card_data and self.is_selected == is_selected:
                return
            self.card_data = card_data
            self.is_selected = is_selected
            self.update_ui()

        def update_ui(self) -> None:
            c = self.card_data
            tid = c["task_id"]
            status = c.get("status") or "ready"
            risk = (c.get("risk") or "medium").lower()
            marker = bauhaus_marker_for_status(status, risk)
            
            try:
                self.query_one("#card-tid-label", Label).update(f"{marker} {tid}")
                self.query_one("#card-title-label", Label).update(short_text(c.get("title") or tid, 25))
                
                badges = []
                if c.get("latest_proof_path"): badges.append("\u25c6P") # ◆P
                if c.get("latest_bundle_path"): badges.append("\u25c6B") # ◆B
                if c.get("latest_loop_status") == "running": badges.append("\u25cfL") # ●L
                if c.get("latest_gate_status") == "pending": badges.append("\u25a0G") # ■G
                
                status_text = (status or "ready").upper()
                risk_text = risk.upper()
                badges_str = " ".join(badges)
                self.query_one("#card-badges-label", Static).update(f"{status_text} \u00b7 {risk_text} {badges_str}")
                
                self.set_class(self.is_selected, "selected-card")
                for r in ["high", "medium", "low"]:
                    self.set_class(risk == r, f"risk-{r}")
            except Exception:
                pass

        def on_click(self) -> None:
            self.post_message(TaskSelected(self.card_data["task_id"]))

    class KanbanColumn(ScrollableContainer):
        def __init__(self, column_id: str, title: str):
            self.column_id = column_id
            self.column_title = title
            super().__init__(id=f"col-{column_id}")

        def compose(self) -> ComposeResult:
            yield Label(self.column_title.upper(), classes="column-header")
            yield Vertical(id=f"cards-{self.column_id}")

    class ConfirmAutoApproveScreen(ModalScreen[bool]):
        def compose(self) -> ComposeResult:
            with Vertical(id="modal-confirm"):
                yield Label("CONFIRM AUTO-APPROVE MODE", classes="card-title")
                yield Static("Bounded · Receipted · No Git Mutation · No Main Worktree Patch")
                yield Static("\nPolicy: Docs/dev/rig/auto-policies/docs-scripts-auto.yaml")
                yield Static("Allowed: loop.run, agent.launch (review), patch.apply_sandbox")
                yield Static("Budgets: 60 mins | 2 agents | 3 patches | 3 jobs")
                yield Static("\nType 'RUN RIG' to confirm:")
                yield Input(id="confirm-input")
                with Horizontal():
                    yield Button("Cancel", variant="error", id="cancel")
                    yield Button("Confirm", variant="success", id="confirm")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "cancel":
                self.dismiss(False)
            elif event.button.id == "confirm":
                if self.query_one("#confirm-input", Input).value == "RUN RIG":
                    self.dismiss(True)

    class MoreCommandsScreen(ModalScreen[str]):
        def __init__(self, mode: str):
            self.app_mode = mode
            super().__init__()

        def compose(self) -> ComposeResult:
            with Vertical(id="modal-more"):
                yield Label("MORE COMMANDS", classes="card-title")
                with ScrollableContainer():
                    yield Label("Observe", classes="section-header")
                    yield Button("Monitor", id="monitor_snapshot")
                    yield Button("Prompt Status", id="prompt_status")
                    yield Button("Prompt Quarantine", id="prompt_quarantine")
                    yield Button("Agent Status", id="agent_status")
                    yield Button("Model Status", id="llm_status_mlx")
                    yield Button("Model Catalog", id="models_list")
                    
                    yield Label("Plan", classes="section-header")
                    yield Button("Build Context", id="context_build")
                    yield Button("Loop Plan", id="loop_plan")
                    yield Button("Agent Plan", id="agent_plan")
                    yield Button("Agent Dry-run", id="agent_dry_run")
                    
                    yield Label("Run", classes="section-header")
                    yield Button("Queue x3", id="queue_add_read_only_x3")
                    
                    yield Label("Validate", classes="section-header")
                    yield Button("Schema", id="schema_validate_results")
                    yield Button("Git Plan", id="git_plan_commit")
                    
                    if self.app_mode in {"action", "auto-approve"}:
                        yield Label("Action", classes="section-header")
                        yield Button("Bundle Session", id="bundle_session")
                
                with Horizontal():
                    yield Button("Close", id="close")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "close":
                self.dismiss("")
            else:
                self.dismiss(event.button.id)

    class BootstrapScreen(ModalScreen[str]):
        def compose(self) -> ComposeResult:
            with Vertical(id="modal-bootstrap"):
                yield Label("NO PROJECT DETECTED", classes="card-title")
                yield Static("Rig could not find any project markers in this folder.")
                yield Static("Would you like to start the Project Bootstrap Walkthrough?")
                with Horizontal():
                    yield Button("Start Walkthrough", id="start_bootstrap", variant="primary")
                    yield Button("Open Read-Only", id="open_readonly")
                    yield Button("Digest Anyway", id="digest_anyway")
                    yield Button("Cancel", id="cancel")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            self.dismiss(event.button.id)

    class HelpScreen(ModalScreen[None]):
        def compose(self) -> ComposeResult:
            with Vertical(id="modal-help"):
                yield Label("RIG HELP", classes="card-title")
                yield Static(
                    "\n".join(
                        [f"{key} · {label}" for key, label in tui_views.help_keybindings()]
                    ),
                    id="help-keybindings",
                )
                yield Static("All actions are routed through Rig receipts and bounded projections.", classes="help-note")
                with Horizontal():
                    yield Button("Close", id="help-close")

        def on_button_pressed(self, event: Button.Pressed) -> None:
            self.dismiss(None)

    class RigTuiApp(App):
        from textual.reactive import reactive
        
        selected_task_id = reactive("")
        current_mode = reactive("safe")
        focus_mode = reactive(False)
        tail_enabled = reactive(True)

        CSS = """
        Screen { layout: vertical; background: $surface; }
        #header { height: 3; background: $surface-darken-1; color: $text; padding: 0 1; border-bottom: solid $primary; }
        #header-brand { width: 18; text-style: bold; color: $accent; }
        #header-mode-badge { width: 24; margin: 0 1; padding: 0 1; text-align: center; text-style: bold; }
        #header-status-badges { width: 34; text-align: center; color: $text-muted; }
        #header-safe { background: $success; color: $surface; }
        #header-action { background: $warning; color: $surface; }
        #header-auto { background: $error; color: $text; }
        #header-info { width: 1fr; text-align: right; color: $text-muted; }
        /* Semantic color contract: green = pass/safe, yellow = warn/review, red = fail/blocked, blue = focus/link, dim = disabled. */
        .mode-safe { color: $success; }
        .mode-action { color: $warning; }
        .mode-auto { color: $error; }
        .status-pass, .semantic-pass { color: $success; }
        .status-warn, .semantic-warn { color: $warning; }
        .status-fail, .semantic-fail { color: $error; }
        .semantic-info { color: $primary; }
        .semantic-selected { color: $primary; text-style: bold; }
        .semantic-disabled { color: $text-muted; }
        .receipt-path { color: $primary; text-style: italic; }
        .help-note { color: $text-muted; }
        
        #pressure-strip { height: 1; background: $surface-darken-1; color: $text-muted; padding: 0 1; border-bottom: solid $primary; }
        .pressure-warn { color: $warning; text-style: bold; }
        .pressure-critical { color: $error; text-style: bold; }
        
        #body { height: 1fr; }
        TabbedContent { height: 1fr; }
        TabPane { padding: 0 1; }
        #command-center-pane, #board-pane, #workspace-pane, #swarm-pane, #health-pane, #vault-pane, #settings-pane { height: 1fr; layout: vertical; }
        #command-center-grid { height: 1fr; layout: vertical; }
        #command-center-top { height: 4; layout: vertical; border: solid $primary; padding: 0 1; }
        #command-center-actions { height: 3; }
        #command-center-actions Button, #workspace-actions Button, #health-actions Button, #vault-actions Button, #board-actions Button, #settings-actions Button { width: 24; margin-right: 1; }
        #command-center-health, #command-center-warnings, #command-center-jobs, #command-center-receipts, #board-layout-note, #board-inspector, #workspace-summary, #workspace-artifacts, #workspace-receipts, #workspace-actions-summary, #swarm-summary, #swarm-candidates, #swarm-detail, #swarm-receipts, #health-summary, #health-issues, #health-detail, #vault-summary, #vault-notes, #settings-summary { border: solid $primary; padding: 0 1; }
        #command-center-health { height: 4; }
        #command-center-warnings { height: 4; }
        #command-center-events { height: 1fr; border: solid $primary; padding: 0 1; }
        #command-center-jobs { height: 4; }
        #command-center-receipts { height: 3; }
        #command-center-next { color: $primary; text-style: bold; }
        #command-center-event-log { height: 1fr; }
        #board-shell { height: 1fr; layout: vertical; }
        #board-layout-note, #board-inspector { margin-top: 1; }
        #board-view { height: 1fr; border-bottom: solid $primary; }
        #board-view.columns { layout: horizontal; }
        #board-view.stacked { layout: vertical; }
        KanbanColumn { width: 1fr; border-right: solid $primary; background: $surface; }
        .column-header { text-style: bold; text-align: center; background: $surface-darken-1; color: $text; height: 1; margin-bottom: 0; border-bottom: solid $primary; }
        
        /* Column Specific Colors */
        #col-ready .column-header { color: $success; }
        #col-running .column-header { color: $primary; }
        #col-approval .column-header { color: $warning; }
        #col-blocked .column-header { color: $error; }
        #col-review .column-header { color: $accent; }
        
        TaskCard {
            background: $surface;
            color: $text;
            margin: 0 1;
            padding: 0 1;
            height: 3;
            border-left: tall $primary;
            border-bottom: solid $surface-darken-1;
        }
        TaskCard:hover { background: $surface-lighten-1; }
        .selected-card { background: $primary; color: $text; border-left: tall $accent; text-style: bold; }
        .selected-card Label { color: $text; }
        .selected-card Static { color: $text; }
        .card-tid { color: $primary; text-style: bold; }
        .card-title { color: $text; text-style: bold; }
        .card-meta { color: $text-muted; }
        .card-action { color: $success; }
        .card-receipt { color: $primary; }
        .card-badges { color: $warning; }
        
        .risk-high { border-left: tall $error; }
        .risk-medium { border-left: tall $warning; }
        .risk-low { border-left: tall $success; }

        #workspace-summary, #swarm-summary, #health-summary, #vault-summary, #settings-summary { height: 1fr; border: solid $primary; padding: 0 1; }
        .tape-header { text-style: bold; color: $primary; border-bottom: solid $primary; margin-bottom: 1; }
        .primary-action { color: $primary; text-style: bold; }
        .panel-title { color: $text; text-style: bold; }
        .panel-receipt { color: $primary; }
        .panel-disabled { color: $text-muted; }
        .panel-status-pass { color: $success; }
        .panel-status-warn { color: $warning; }
        .panel-status-fail { color: $error; }
        
        .section-header { text-style: italic; color: $accent; margin-top: 1; margin-bottom: 0; }
        .help-key { color: $accent; text-style: bold; }
        .help-action { color: $text; }

        #modal-help, #modal-more, #modal-confirm, #modal-bootstrap {
            background: $surface;
            border: thick $primary;
            padding: 1 2;
            width: 60;
            height: auto;
        }
        
        Button { height: 1; border: none; padding: 0 1; background: $surface-darken-1; color: $text; }
        Button:hover { background: $primary; color: $text; }
        Button.-disabled, Button:disabled { color: $text-muted; background: $surface-darken-1; }
        
        RichLog { scrollbar-size: 1 1; background: $surface; }

        #modal-confirm, #modal-more {
            padding: 2 4;
            background: $surface-darken-1;
            border: thick $primary;
            width: 60;
            height: auto;
            max-height: 80%;
            align: center middle;
        }
        #modal-help {
            padding: 2 4;
            background: $surface-darken-1;
            border: thick $primary;
            width: 58;
            height: auto;
            max-height: 80%;
            align: center middle;
        }
        #help-keybindings { height: auto; border: solid $primary; padding: 0 1; }
        #modal-more ScrollableContainer { height: 20; border: solid $primary; margin-bottom: 1; }
        #modal-more Button { width: 100%; margin-bottom: 0; }
        
        #modal-confirm Horizontal, #modal-more Horizontal {
            margin-top: 1;
            height: 3;
            align: center middle;
        }
        #modal-help Horizontal { margin-top: 1; height: 3; align: center middle; }
        #modal-confirm Button, #modal-more Button {
            width: 15;
            margin: 0 1;
        }
        """

        BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("m", "cycle_mode", "Cycle Mode"),
            Binding("s", "set_mode_safe", "Safe Mode", show=False),
            Binding("a", "set_mode_action", "Action Mode", show=False),
            Binding("y", "request_auto_approve", "Request Auto-Approve", show=False),
            Binding("tab", "focus_next", "Next Focus", show=False),
            Binding("shift+tab", "focus_previous", "Previous Focus", show=False),
            Binding("f", "toggle_focus", "Focus"),
            Binding("t", "toggle_tail", "Tail"),
        Binding("p", "show_more", "More"),
        Binding("w", "open_workspace", "Workspace"),
        Binding("v", "run_diff_review", "Review"),
        Binding("enter", "run_recommended", "Run"),
            Binding("?", "show_help", "Help", show=False),
            Binding("u", "approve_gate", "Approve", show=False),
            Binding("x", "reject_gate", "Reject", show=False),
        ]

        def __init__(self):
            super().__init__()
            self.repo_root = repo_root
            self.refresh_seconds = refresh_seconds
            self.store = RigDataStore(repo_root)
            self.runner = CommandRunner(repo_root)
            self.snapshot = self.store.get_snapshot(build_derived=True)
            self.tail_positions = {}
            self.card_widgets = {}
            self.last_snapshot_hashes = {}
            
            ui_state = load_ui_state()
            self.current_mode = clamp_mode(mode if mode != "safe" else ui_state.get("mode", "safe"))
            self.selected_task_id = str(ui_state.get("selected_task_id") or self.auto_select_task() or "")
            self.auto_approve_requested = bool(ui_state.get("auto_approve_requested", False))
            self.auto_approve_pending = bool(ui_state.get("auto_approve_pending", False))
            self.event_stream_empty = True
            self.visible_events: list[dict[str, Any]] = []
            self.max_visible_events = int((self.snapshot.get("settings") or {}).get("memory", {}).get("max_tui_events") or 500)

        def watch_current_mode(self, old_mode: str, new_mode: str) -> None:
            """React to runtime mode changes."""
            self.persist_ui_state()
            self.update_header()
            self.update_drawer()
            self.sync_action_buttons()
            self.update_settings()
            self.write_event_line(f"MODE SWITCHED: {new_mode.upper()}", style="bold white")

        def write_event_line(self, line: Union[str, Text], style: str = "") -> None:
            try:
                log = self.query_one("#event-stream", RichLog)
                if self.event_stream_empty:
                    log.clear()
                    self.event_stream_empty = False
                
                if isinstance(line, Text):
                    log.write(line)
                elif style:
                    log.write(Text(line, style=style))
                else:
                    log.write(line)
            except: pass

        def persist_ui_state(self) -> None:
            save_tui_settings({"mode": self.current_mode})
            save_tui_state(STATE_PATH, {
                "mode": self.current_mode,
                "selected_task_id": self.selected_task_id or None,
                "auto_approve_requested": getattr(self, "auto_approve_requested", False),
                "auto_approve_pending": getattr(self, "auto_approve_pending", False),
            })

        def auto_select_task(self) -> Optional[str]:
            board = self.snapshot.get("board", {})
            cards = board.get("cards", [])
            if not cards: return None
            for status in ["approval", "running", "ready", "review", "blocked"]:
                for c in cards:
                    if c.get("column_id") == status: return c["task_id"]
            return cards[0]["task_id"]

        def compose(self) -> ComposeResult:
            with Horizontal(id="header"):
                yield Static("RIG", id="header-brand")
                yield Static("", id="header-mode-badge")
                yield Static("", id="header-status-badges")
                yield Static(f"repo: {self.snapshot['repo_name']} | {time.strftime('%H:%M:%S')}", id="header-info")

            yield Static("Initializing telemetry...", id="pressure-strip")

            with Vertical(id="body"):
                with TabbedContent(initial="command-center-pane"):
                    with TabPane("Command Center", id="command-center-pane"):
                        with Vertical(id="command-center-grid"):
                            with Vertical(id="command-center-top"):
                                yield Static("", id="command-center-next")
                                yield Static("", id="command-center-health")
                                with Horizontal(id="command-center-actions"):
                                    yield Button("Run Doctor", id="doctor_run")
                                    yield Button("Open Board", id="open_board")
                                    yield Button("Open Swarm", id="open_swarm")
                                    yield Button("Open Vault", id="open_vault")
                            yield Static("", id="command-center-jobs")
                            yield Static("", id="command-center-warnings")
                            yield Static("", id="command-center-receipts")
                            yield RichLog(id="command-center-event-log", wrap=True, highlight=False)

                    with TabPane("Board", id="board-pane"):
                        with Vertical(id="board-shell"):
                            yield Static("", id="board-layout-note")
                            with Horizontal(id="board-view"):
                                for col_id in ["ready", "running", "approval", "blocked", "review"]:
                                    yield KanbanColumn(col_id, col_id)
                            with Vertical(id="board-inspector"):
                                yield Label("RIG \u00b7 TASK CONTROL", id="drawer-row1")
                                yield Label("Select a task from the board.", id="drawer-row2")
                                with Horizontal(id="drawer-actions"):
                                    yield Button("Run: (Recommended)", id="run_recommended", variant="primary")
                                    yield Button("Create Workspace", id="create_workspace_action")
                                    yield Button("Status", id="refresh_status")
                                    yield Button("Context", id="context_build")
                                    yield Button("Loop", id="loop_plan")
                                    yield Button("Queue x3", id="queue_add_read_only_x3")
                                    yield Button("Bundle", id="bundle_session_dry_run")
                                yield Label("", id="drawer-receipts")
                            with Horizontal(id="board-actions"):
                                yield Button("Open Selected Task", id="open_selected_task")
                                yield Button("Copy Receipt Path", id="copy_selected_receipt")

                    with TabPane("Workspace", id="workspace-pane"):
                        with Vertical(id="workspace-summary"):
                            yield Static("", id="workspace-selected")
                            yield Static("", id="workspace-loop")
                            yield Static("", id="workspace-artifacts")
                            yield Static("", id="workspace-actions-summary")
                            with Horizontal(id="workspace-actions"):
                                yield Button("Run Next Safe Action", id="workspace_next_safe_action")
                                yield Button("Plan Loop Dry-Run", id="workspace_loop_dry_run")
                            yield Static("", id="workspace-receipts")

                    with TabPane("Swarm", id="swarm-pane"):
                        with Vertical(id="swarm-summary"):
                            yield Static("", id="swarm-scoreboard")
                            yield Static("", id="swarm-candidates")
                            yield Static("", id="swarm-detail")
                            with Horizontal():
                                yield Button("Open Latest Scoreboard", id="open_latest_scoreboard")
                                yield Button("Open Winner", id="swarm_open_winner")
                                yield Button("Compare Candidates", id="swarm_compare_candidates")

                    with TabPane("Health", id="health-pane"):
                        with Vertical(id="health-summary"):
                            yield Static("", id="health-status")
                            yield Static("", id="health-issues")
                            yield Static("", id="health-detail")
                            with Horizontal(id="health-actions"):
                                yield Button("Run Doctor", id="doctor_run_health")
                                yield Button("Open Latest Report", id="open_latest_report")

                    with TabPane("Vault", id="vault-pane"):
                        with Vertical(id="vault-summary"):
                            yield Static("", id="vault-status")
                            yield Static("", id="vault-notes")
                            with Horizontal(id="vault-actions"):
                                yield Button("Print/Open Dashboard URI", id="vault_open_uri")

                    with TabPane("Settings", id="settings-pane"):
                        with Vertical(id="settings-summary"):
                            yield Static("", id="settings-mode")
                            yield Static("", id="settings-backend")
                            yield Static("", id="settings-memory")
                            yield Static("", id="settings-retention")
                            yield Static("", id="settings-effective")
                            with Horizontal(id="settings-actions"):
                                yield Button("Show Effective Settings", id="settings_show_effective")

            yield Footer()

        def on_mount(self) -> None:
            self.refresh_all(build_derived=True)
            self.set_interval(self.refresh_seconds, self.update_pressure_and_header)
            self.set_interval(1, self.tail_events)
            self.set_interval(10, self.refresh_heavy)
            
            from rig_tools import bootstrap_walkthrough
            state = bootstrap_walkthrough.detect_folder_state(self.repo_root)
            if state != "existing_project":
                self.push_screen(self.BootstrapScreen(), self.handle_bootstrap_result)

        def handle_bootstrap_result(self, result: str) -> None:
            if result == "start_bootstrap":
                # For MVP, we point to CLI
                self.notify("Please run 'rig bootstrap walkthrough' in your terminal.")
            elif result == "open_readonly":
                self.current_mode = "safe"
                self.notify("Opening in Read-Only (Safe) mode.")
            elif result == "digest_anyway":
                self.refresh_all(build_derived=True)
            elif result == "cancel":
                self.exit()

        def update_pressure_and_header(self) -> None:
            try:
                self.snapshot["pressure"] = system_pressure.sample_system_pressure(self.repo_root)
                self.snapshot["git"] = _read_json(self.repo_root / ".build" / "rig" / "git" / "status.json") or {}
                self.update_header()
                self.update_pressure()
            except: pass

        def refresh_heavy(self) -> None:
            self.refresh_all(build_derived=True)

        def action_refresh(self) -> None:
            self.refresh_all(build_derived=True)

        def action_cycle_mode(self) -> None:
            modes = ["safe", "action", "auto-approve"]
            idx = modes.index(self.current_mode)
            self.current_mode = modes[(idx + 1) % len(modes)]

        def action_set_mode_safe(self) -> None: self.current_mode = "safe"
        def action_set_mode_action(self) -> None: self.current_mode = "action"
        def action_request_auto_approve(self) -> None:
            self.auto_approve_requested = True
            self.auto_approve_pending = True
            self.persist_ui_state()
            self.write_event_line("AUTO-APPROVE REQUESTED · pending confirmation", style="bold warning")
            try:
                self.push_screen(ConfirmAutoApproveScreen(), self.complete_auto_approve_request)
            except Exception:
                self.write_event_line("AUTO-APPROVE REQUEST · confirmation dialog unavailable", style="bold warning")

        def complete_auto_approve_request(self, approved: bool) -> None:
            self.auto_approve_pending = False
            if approved:
                self.current_mode = "auto-approve"
                self.write_event_line("AUTO-APPROVE ENABLED", style="bold success")
            else:
                self.write_event_line("AUTO-APPROVE CANCELLED", style="bold warning")
            self.persist_ui_state()

        def set_active_tab(self, pane_id: str) -> None:
            try:
                tabs = self.query_one(TabbedContent)
                if hasattr(tabs, "active"):
                    tabs.active = pane_id
            except Exception:
                pass

        def action_open_board(self) -> None:
            self.set_active_tab("board-pane")

        def action_open_workspace(self) -> None:
            self.set_active_tab("workspace-pane")

        def action_run_diff_review(self) -> None:
            cmd = [sys.executable, str(self.repo_root / "scripts" / "rig.py"), "diff", "review"]
            self.run_worker(self.run_fixed_command(cmd, "diff_review"), thread=True)
            self.write_event_line("DIFF REVIEW · running classification", style="bold blue")

        def action_open_swarm(self) -> None:
            self.set_active_tab("swarm-pane")

        def action_open_vault(self) -> None:
            self.set_active_tab("vault-pane")
            vault = self.snapshot.get("vault") or {}
            path = vault.get("dashboard_note_path") or vault.get("latest_export_path") or vault.get("vault_path")
            if path:
                self.write_event_line(f"VAULT URI · {path}")

        def action_run_doctor(self) -> None:
            cmd = [sys.executable, str(self.repo_root / "scripts" / "rig.py"), "doctor", "--format", "json"]
            self.run_worker(self.run_fixed_command(cmd, "doctor"), thread=True)

        def action_create_workspace(self) -> None:
            tid = self.selected_task_id or "generic"
            cmd = [sys.executable, str(self.repo_root / "scripts" / "rig.py"), "workspace", "create", "--task", tid, "--mode", self.current_mode]
            self.run_worker(self.run_fixed_command(cmd, "workspace_create"), thread=True)
            self.write_event_line(f"WORKSPACE CREATE · {tid} · {self.current_mode}", style="bold blue")

        def action_show_help(self) -> None:
            self.push_screen(HelpScreen())
            self.write_event_line("HELP OPENED · q quit · ? help · tab/shift-tab focus · enter activate · r refresh · s safe · a action · m cycle mode · y request auto-approve")

        def action_open_selected_task(self) -> None:
            self.set_active_tab("board-pane")

        def action_open_latest_scoreboard(self) -> None:
            self.set_active_tab("swarm-pane")

        def action_open_latest_report(self) -> None:
            self.set_active_tab("health-pane")
            receipts = tui_views.latest_receipt_paths(self.repo_root)
            path = receipts.get("doctor") or receipts.get("audit") or receipts.get("sentinel")
            if path:
                self.write_event_line(f"LATEST REPORT · {path}")
            else:
                self.write_event_line("LATEST REPORT · unavailable", style="bold warning")

        def action_show_effective_settings(self) -> None:
            self.set_active_tab("settings-pane")

        def action_open_selected_receipt(self) -> None:
            receipts = tui_views.latest_receipt_paths(self.repo_root)
            path = next((p for p in receipts.values() if p), None)
            if path:
                self.write_event_line(f"RECEIPT PATH · {path}")
            else:
                self.write_event_line("RECEIPT PATH · unavailable", style="bold warning")

        def action_copy_selected_receipt(self) -> None:
            receipts = tui_views.latest_receipt_paths(self.repo_root)
            path = next((p for p in receipts.values() if p), None)
            if not path:
                self.write_event_line("COPY PATH · unavailable", style="bold warning")
                return
            try:
                import pyperclip  # type: ignore
                pyperclip.copy(path)
                self.write_event_line(f"COPIED · {path}", style="success")
            except Exception:
                self.write_event_line(f"COPY FAILED · clipboard unavailable · {path}", style="bold warning")

        async def run_fixed_command(self, argv: list[str], command_id: str):
            start_time = time.time()
            result = self.runner.run_argv(command_id, argv, timeout=1800)
            duration = time.time() - start_time
            self.call_from_thread(
                self.write_event_line,
                render_command_result(command_id, result.status, duration, result.stderr if result.status != "passed" else None),
            )
            self.call_from_thread(self.refresh_all, build_derived=True)

        def refresh_all(self, build_derived: bool = False) -> None:
            try:
                self.snapshot = self.store.get_snapshot(build_derived=build_derived)
                self.max_visible_events = int((self.snapshot.get("settings") or {}).get("memory", {}).get("max_tui_events") or 500)
                cards = self.snapshot.get("board", {}).get("cards", [])
                card_ids = {c["task_id"] for c in cards}
                if not self.selected_task_id or self.selected_task_id not in card_ids:
                    self.selected_task_id = self.auto_select_task() or ""
                self.persist_ui_state()
                self.update_header()
                self.update_command_center()
                self.update_drawer()
                self.update_tables()
                self.update_pressure()
                self.update_workspace()
                self.update_swarm()
                self.update_health()
                self.update_vault()
                self.update_settings()
                self.sync_action_buttons()
            except Exception as exc:
                self.write_event_line(f"Refresh error: {exc}", style="bold error")

        def update_header(self) -> None:
            if not self.is_mounted: return
            try:
                badge = self.query_one("#header-mode-badge", Static)
                badge.remove_class("header-safe", "header-action", "header-auto")
                badge.remove_class("mode-safe", "mode-action", "mode-auto")
                if self.current_mode == "auto-approve":
                    badge.add_class("header-auto")
                    badge.add_class("mode-auto")
                    badge.update(Text("AUTO-APPROVE / PENDING" if getattr(self, "auto_approve_pending", False) else "AUTO-APPROVE / BOUNDED", style="bold red"))
                elif self.current_mode == "action":
                    badge.add_class("header-action")
                    badge.add_class("mode-action")
                    badge.update(Text("ACTION MODE / GUARDED", style="bold yellow"))
                else:
                    badge.add_class("header-safe")
                    badge.add_class("mode-safe")
                    badge.update(Text("SAFE MODE / OBSERVE", style="bold green"))

                doctor_status = ((self.snapshot.get("doctor") or {}).get("status") or "unknown").upper()
                audit_status = ((self.snapshot.get("audit") or {}).get("status") or "unknown").upper()
                sentinel_status = ((self.snapshot.get("sentinel") or {}).get("status") or "unknown").upper()
                status_text = Text()
                for label, status in [("doctor", doctor_status), ("audit", audit_status), ("sentinel", sentinel_status)]:
                    style = "green bold" if status == "PASS" else "yellow bold" if status in {"WARN", "PENDING"} else "red bold" if status in {"FAIL", "BLOCKED"} else "dim"
                    status_text.append(f"{label}: ", style="dim")
                    status_text.append(status, style=style)
                    status_text.append("  ")
                self.query_one("#header-status-badges", Static).update(status_text)

                git = self.snapshot.get("git") or {}
                dirty = git.get("dirty_count", 0)
                status = "DIRTY" if dirty > 0 else "CLEAN"
                pressure = self.snapshot.get("pressure") or {}
                model = pressure.get("local_model") or {}
                backend = model.get("latest_backend") or self.snapshot.get("settings", {}).get("active_model_backend", "mlx")
                pressure_status = str(pressure.get("status") or "unknown").upper()
                from rig_tools import system_benchmark
                bench = system_benchmark.get_latest_benchmark(self.repo_root)
                bench_profile = (bench.get("recommended_profile") or {}).get("profile_id", "none") if bench else "none"
                
                info = Text()
                info.append("bench: ", style="dim")
                info.append(bench_profile, style="bold magenta" if bench_profile != "none" else "dim")
                info.append(" | repo: ", style="dim")
                info.append(str(self.snapshot["repo_name"]), style="bold")
                info.append(" | Git: ", style="dim")
                info.append(f"{status} ({dirty})", style="yellow bold" if dirty else "green bold")
                info.append(" | ", style="dim")
                info.append(time.strftime("%H:%M:%S"), style="bold")
                info.append(" | backend: ", style="dim")
                info.append(str(backend), style="cyan bold")
                info.append(" | pressure: ", style="dim")
                info.append(pressure_status, style="yellow bold" if pressure_status != "PASS" else "green bold")
                if self.last_snapshot_hashes.get("header") != hashlib.md5(info.plain.encode()).hexdigest():
                    self.last_snapshot_hashes["header"] = hashlib.md5(info.plain.encode()).hexdigest()
                    self.query_one("#header-info", Static).update(info)
            except: pass

        def update_command_center(self) -> None:
            if not self.is_mounted:
                return
            try:
                view = tui_views.render_command_center_snapshot(self.snapshot, repo_root=self.repo_root, selected_task_id=self.selected_task_id, max_events=self.max_visible_events)
                next_widget = self.query_one("#command-center-next", Static)
                next_widget.remove_class("panel-status-pass", "panel-status-warn", "panel-status-fail")
                next_widget.add_class("primary-action")
                next_widget.update(Text.assemble(("NEXT · ", "dim"), (view["next_action"], "bold blue")))

                health_text = Text()
                for idx, card in enumerate(view["health_cards"]):
                    cls = tui_views.semantic_status_class(str(card["status"]))
                    style = "green bold" if cls == "semantic-pass" else "yellow bold" if cls == "semantic-warn" else "red bold" if cls == "semantic-fail" else "blue bold"
                    health_text.append("◆ ", style=style)
                    health_text.append(f"{card['label']}: ", style="bold")
                    health_text.append(str(card["status"]).upper(), style=style)
                    health_text.append(f" · receipt {card['receipt'] or 'none'}", style="dim")
                    if idx < len(view["health_cards"]) - 1:
                        health_text.append("\n")
                self.query_one("#command-center-health", Static).update(health_text)
                queue = self.snapshot.get("queue") or {}
                loop = self.snapshot.get("loop") or {}
                swarm = self.snapshot.get("swarm") or {}
                jobs = Text()
                jobs.append("queue · ", style="dim")
                jobs.append(f"{len(queue.get('jobs') or [])} jobs", style="blue bold")
                jobs.append(" · receipt ", style="dim")
                jobs.append(str(view["receipt_paths"]["queue"] or "none"), style="blue")
                jobs.append(" | loop · ", style="dim")
                jobs.append(f"{loop.get('status', 'unknown')}", style="green bold" if str(loop.get("status", "")).lower() in {"running", "passed", "completed"} else "yellow bold" if str(loop.get("status", "")).lower() in {"blocked", "failed"} else "dim")
                jobs.append(f" · {loop.get('run_id', 'none')}", style="dim")
                jobs.append(" · receipt ", style="dim")
                jobs.append(str(view["receipt_paths"]["loop"] or "none"), style="blue")
                jobs.append(" | swarm · ", style="dim")
                jobs.append(f"{swarm.get('status', 'unknown')}", style="green bold" if str(swarm.get("status", "")).lower() in {"running", "passed"} else "yellow bold" if str(swarm.get("status", "")).lower() == "blocked" else "dim")
                jobs.append(f" · {swarm.get('swarm_id', 'none')}", style="dim")
                jobs.append(" · receipt ", style="dim")
                jobs.append(str(view["receipt_paths"]["swarm"] or "none"), style="blue")
                self.query_one("#command-center-jobs", Static).update(jobs)
                warnings = view["warnings"]
                warning_text = Text()
                if warnings:
                    for idx, warning in enumerate(warnings[:5]):
                        warning_text.append("■ ", style="yellow bold")
                        warning_text.append(warning, style="yellow")
                        if idx < min(len(warnings), 5) - 1:
                            warning_text.append("\n")
                else:
                    warning_text.append("No current warnings.", style="dim")
                self.query_one("#command-center-warnings", Static).update(warning_text)
                receipts = [f"• {label}: {path}" for label, path in view["receipt_paths"].items() if path]
                receipt_text = Text()
                if receipts:
                    for idx, receipt in enumerate(receipts):
                        receipt_text.append(receipt, style="blue")
                        if idx < len(receipts) - 1:
                            receipt_text.append("\n")
                else:
                    receipt_text.append("No receipt paths yet.", style="dim")
                self.query_one("#command-center-receipts", Static).update(receipt_text)
                log = self.query_one("#command-center-event-log", RichLog)
                log.clear()
                tail_events = tui_views.cap_event_tail(self.visible_events if self.visible_events else (self.snapshot.get("recent_events") or []), max_events=self.max_visible_events)
                for event in tail_events[-self.max_visible_events:]:
                    line = render_human_event_line(event, focus_task_id=self.selected_task_id if self.focus_mode else None)
                    if line:
                        log.write(Text(line, style={
                            "semantic-pass": "green",
                            "semantic-warn": "yellow",
                            "semantic-fail": "red bold",
                            "semantic-info": "dim",
                            "semantic-selected": "blue bold",
                            "semantic-disabled": "dim",
                        }.get(event_semantic_class(event), "dim")))
            except Exception:
                pass

        def update_pressure(self) -> None:
            if not self.is_mounted: return
            p = self.snapshot.get("pressure") or {}
            h = hashlib.md5(json.dumps(p, sort_keys=True).encode()).hexdigest()
            if self.last_snapshot_hashes.get("pressure") == h: return
            self.last_snapshot_hashes["pressure"] = h

            try:
                strip_widget = self.query_one("#pressure-strip", Static)
                if p.get("status") == "unavailable":
                    strip_widget.update("Pressure unavailable \u00b7 install psutil")
                    return

                mem = p.get("memory", {})
                cpu = p.get("cpu", {})
                model = p.get("local_model", {})
                disk = p.get("disk", {})
                mem_pct = mem.get('percent') or 0
                cpu_pct = cpu.get('percent') or 0
                disk_free = (disk.get('free_bytes') or 0) // (1024**3)
                
                marker = "\u00b7"
                strip_widget.remove_class("pressure-warn", "pressure-critical")
                if mem_pct > 90 or cpu_pct > 95:
                    marker = "\u25b2"
                    strip_widget.add_class("pressure-critical")
                elif mem_pct > 80 or cpu_pct > 80:
                    marker = "\u25a0"
                    strip_widget.add_class("pressure-warn")
                
                backend = model.get('latest_backend') or 'idle'
                strip = f"{marker} RAM {mem_pct}% \u00b7 CPU {cpu_pct}% \u00b7 DISK {disk_free}G \u00b7 MODEL {backend.upper()}"
                strip_widget.update(strip)
            except: pass

        def update_drawer(self) -> None:
            if not self.is_mounted: return
            tid = self.selected_task_id
            board = self.snapshot.get("board", {})
            card = next((c for c in board.get("cards", []) if c["task_id"] == tid), None) if tid else None
            
            h = hashlib.md5(json.dumps({"card": card, "tid": tid, "mode": self.current_mode}, sort_keys=True).encode()).hexdigest()
            if self.last_snapshot_hashes.get("drawer") == h: return
            self.last_snapshot_hashes["drawer"] = h

            try:
                if not card:
                    self.query_one("#drawer-row1", Label).update("RIG \u00b7 TASK CONTROL")
                    self.query_one("#drawer-row2", Label).update("Select a task from the board.")
                    self.query_one("#run_recommended", Button).disabled = True
                    return

                status = (card.get("status") or "ready").upper()
                risk = (card.get("risk") or "medium").upper()
                marker = bauhaus_marker_for_status(status, risk)
                target = card.get("target") or "no target"
                self.query_one("#drawer-row1", Label).update(f"{marker} {tid} \u00b7 {status} \u00b7 {risk} RISK \u00b7 {target}")
                
                rec_action = card.get("recommended_next_action", "refresh_status")
                reason = card.get("recommendation_reason", "N/A")
                self.query_one("#drawer-row2", Label).update(f"NEXT: [bold white]{rec_action.replace('_', ' ').upper()}[/] \u2014 {reason}")
                
                btn = self.query_one("#run_recommended", Button)
                btn.label = f"RUN: {rec_action.replace('_', ' ').upper()}"
                
                # Gating all buttons by mode
                for btn_id in ["run_recommended", "refresh_status", "context_build", "loop_plan", "queue_add_read_only_x3", "bundle_session_dry_run"]:
                    action_id = rec_action if btn_id == "run_recommended" else btn_id
                    plan = self.runner.registry.build_plan(action_id, tid, self.current_mode)
                    self.query_one(f"#{btn_id}", Button).disabled = not plan.is_valid

                receipts = []
                if card.get("latest_proof_path"): receipts.append(f"\u25c6 PROOF: {card.get('latest_proof_path')}")
                if card.get("latest_bundle_path"): receipts.append(f"\u25c6 BUNDLE: {card.get('latest_bundle_path')}")
                if card.get("latest_loop_status"): receipts.append(f"\u00b7 LOOP: {card.get('latest_loop_status')}")
                if card.get("latest_gate_status"): receipts.append(f"\u25a0 GATE: {card.get('latest_gate_status')}")
                self.query_one("#drawer-receipts", Label).update("   ".join(receipts) if receipts else "No receipts yet.")
            except: pass

        def update_workspace(self) -> None:
            if not self.is_mounted:
                return
            try:
                latest_ws = self.snapshot.get("latest_workspace") or {}
                ws_id = latest_ws.get("workspace_id") or "none"
                mode = latest_ws.get("mode") or "unknown"
                status = latest_ws.get("status") or "unknown"
                
                tid = self.selected_task_id or "none"
                card = next((c for c in self.snapshot.get("board", {}).get("cards", []) if c["task_id"] == self.selected_task_id), None)
                loop = self.snapshot.get("loop") or {}
                receipts = tui_views.latest_receipt_paths(self.repo_root)
                
                # Active Workspace Header
                self.query_one("#workspace-selected", Static).update(
                    Text.assemble(
                        ("Active Workspace · ", "dim"),
                        (ws_id, "bold blue"),
                        (" · ", "dim"),
                        (mode.upper(), "bold green" if mode == "safe" else "bold yellow"),
                        (" · ", "dim"),
                        (status.upper(), "bold blue" if status == "active" else "dim")
                    )
                )
                
                # Diff Review Summary
                from rig_tools import diff_review
                dr_latest_path = self.repo_root / ".build" / "rig" / "diff" / "latest.json"
                dr_latest = _read_json(dr_latest_path) if dr_latest_path.exists() else {}
                dr_status = dr_latest.get("status", "none").upper()
                dr_cls = "green bold" if dr_status == "PASS" else "yellow bold" if dr_status == "WARN" else "red bold" if dr_status == "FAIL" else "dim"
                
                self.query_one("#workspace-artifacts", Static).update(
                    Text.assemble(
                        ("Diff Review · ", "dim"),
                        (dr_status, dr_cls),
                        (" · files ", "dim"),
                        (str(dr_latest.get("counts", {}).get("files_changed", 0)), "blue"),
                        (" · risky ", "dim"),
                        (str(len(dr_latest.get("risky_paths", []))), "red" if dr_latest.get("risky_paths") else "dim"),
                    )
                )

                loop_status = str(loop.get("status", "unknown")).lower()
                self.query_one("#workspace-loop", Static).update(
                    Text.assemble(
                        ("Loop · ", "dim"),
                        (str(loop.get("status", "unknown")), "green bold" if loop_status in {"running", "passed", "completed"} else "yellow bold" if loop_status in {"blocked", "pending"} else "red bold"),
                        (" · run ", "dim"),
                        (str(loop.get("run_id", "none")), "blue"),
                        (" · stop ", "dim"),
                        (str(loop.get("stop_reason", "unknown")), "yellow" if loop.get("stop_reason") else "dim"),
                    )
                )
                artifact_lines = []
                if card:
                    for key in ["latest_proof_path", "latest_bundle_path", "latest_loop_status", "latest_gate_status"]:
                        if card.get(key):
                            artifact_lines.append(f"{key.replace('latest_', '')}: {card.get(key)}")
                artifact_lines.extend([f"{name}: {path}" for name, path in receipts.items() if path])
                if not artifact_lines:
                    artifact_lines = ["No receipts yet."]
                art_text = Text()
                for idx, line in enumerate(artifact_lines[:8]):
                    art_text.append(line, style="blue" if ":" in line else "dim")
                    if idx < min(len(artifact_lines), 8) - 1:
                        art_text.append("\n")
                self.query_one("#workspace-artifacts", Static).update(art_text)
                rec_text = Text()
                receipt_lines = [f"• {name}: {path}" for name, path in receipts.items() if path]
                if receipt_lines:
                    for idx, line in enumerate(receipt_lines):
                        rec_text.append(line, style="blue")
                        if idx < len(receipt_lines) - 1:
                            rec_text.append("\n")
                else:
                    rec_text.append("No receipt paths yet.", style="dim")
                self.query_one("#workspace-receipts", Static).update(rec_text)
                affordances = tui_views.action_affordances(self.snapshot, selected_task_id=self.selected_task_id, mode=self.current_mode)
                workspace_actions = []
                for action_id in ("workspace_next_safe_action", "workspace_loop_dry_run"):
                    afford = affordances.get(action_id, {"enabled": False, "reason": "unknown"})
                    state = "allowed" if afford.get("enabled") else "disabled"
                    reason = afford.get("reason") or ""
                    workspace_actions.append(f"• {action_id.replace('_', ' ')} · {state}{f' · {reason}' if reason else ''}")
                ws_actions = Text()
                for idx, line in enumerate(workspace_actions):
                    ws_actions.append(line, style="green" if "allowed" in line else "dim")
                    if idx < len(workspace_actions) - 1:
                        ws_actions.append("\n")
                self.query_one("#workspace-actions-summary", Static).update(ws_actions)
            except Exception:
                pass

        def update_swarm(self) -> None:
            if not self.is_mounted:
                return
            try:
                swarm = tui_views.render_swarm_snapshot(self.snapshot)
                receipts = tui_views.latest_receipt_paths(self.repo_root)
                scoreboard = Text.assemble(
                    ("Swarm · ", "dim"),
                    (str(swarm["status"]).upper(), "green bold" if str(swarm["status"]).lower() == "running" else "yellow bold" if str(swarm["status"]).lower() == "blocked" else "dim"),
                    (" · ", "dim"),
                    (swarm["swarm_id"] or "none", "blue"),
                    (" · winner ", "dim"),
                    (swarm["winner_candidate_id"] or "none", "bold blue" if swarm["winner_candidate_id"] else "dim"),
                )
                self.query_one("#swarm-scoreboard", Static).update(scoreboard)
                rows = swarm["candidate_rows"][:10]
                candidates_text = Text()
                if rows:
                    for idx, row in enumerate(rows):
                        candidate = swarm["candidates"][idx] if idx < len(swarm["candidates"]) else {}
                        color = "blue" if candidate.get("winner_class") == "semantic-selected" else "green" if candidate.get("visual_class") == "semantic-pass" else "yellow" if candidate.get("visual_class") == "semantic-warn" else "red" if candidate.get("visual_class") == "semantic-fail" else "dim"
                        candidates_text.append(row, style=color)
                        if idx < len(rows) - 1:
                            candidates_text.append("\n")
                else:
                    candidates_text.append("No swarm candidates yet.", style="dim")
                self.query_one("#swarm-candidates", Static).update(candidates_text)
                candidate_id = getattr(self, "selected_candidate_id", None) or swarm.get("winner_candidate_id")
                detail = tui_views.render_swarm_candidate_detail(self.snapshot, candidate_id)
                detail_text = Text()
                detail_items = [
                    ("Candidate · ", "dim", str(detail["candidate_id"] or "none"), "blue bold"),
                    ("Strategy · ", "dim", str(detail["strategy"] or "n/a"), "bold"),
                    ("Score · ", "dim", str(detail["score"] if detail["score"] is not None else "n/a"), "green bold" if isinstance(detail["score"], (int, float)) and detail["score"] >= 80 else "yellow bold"),
                    ("Status · ", "dim", str(detail["status"]).upper(), "green bold" if str(detail["status"]).lower() == "passed" else "yellow bold" if str(detail["status"]).lower() in {"quarantined", "failed"} else "dim"),
                    ("Failure · ", "dim", str(detail["failure_type"] or "none"), "red" if detail["failure_type"] else "dim"),
                    ("Prompt · ", "dim", str(detail["prompt_path"] or "none"), "blue"),
                    ("Raw output · ", "dim", str(detail["raw_output_path"] or "hidden by default"), "dim"),
                    ("Validation · ", "dim", str(detail["validation_path"] or "none"), "blue"),
                ]
                for idx, (label, label_style, value, value_style) in enumerate(detail_items):
                    detail_text.append(label, style=label_style)
                    detail_text.append(value, style=value_style)
                    if idx < len(detail_items) - 1:
                        detail_text.append("\n")
                self.query_one("#swarm-detail", Static).update(detail_text)
                swarm_receipts = Text()
                receipt_lines = [f"• {label}: {path}" for label, path in receipts.items() if path]
                if receipt_lines:
                    for idx, line in enumerate(receipt_lines):
                        swarm_receipts.append(line, style="blue")
                        if idx < len(receipt_lines) - 1:
                            swarm_receipts.append("\n")
                else:
                    swarm_receipts.append("No swarm receipts yet.", style="dim")
                self.query_one("#swarm-receipts", Static).update(swarm_receipts)
            except Exception:
                pass

        def update_health(self) -> None:
            if not self.is_mounted:
                return
            try:
                health = tui_views.render_health_snapshot(self.snapshot)
                sentinel = self.snapshot.get("sentinel") or {}
                doctor = self.snapshot.get("doctor") or {}
                audit = self.snapshot.get("audit") or {}
                anigma = self.snapshot.get("anigma") or {}
                self.query_one("#health-status", Static).update(
                    Text.assemble(
                        ("Sentinel: ", "dim"),
                        (str(health["sentinel"]).upper(), "green bold" if str(health["sentinel"]).lower() == "pass" else "yellow bold" if str(health["sentinel"]).lower() == "warn" else "red bold"),
                        (" · Doctor: ", "dim"),
                        (str(health["doctor"]).upper(), "green bold" if str(health["doctor"]).lower() == "pass" else "yellow bold" if str(health["doctor"]).lower() == "warn" else "red bold"),
                        (" · Audit: ", "dim"),
                        (str(health["audit"]).upper(), "green bold" if str(health["audit"]).lower() == "pass" else "yellow bold" if str(health["audit"]).lower() == "warn" else "red bold"),
                    )
                )
                issues = []
                selected_detail = None
                for name, payload in [("sentinel", sentinel), ("doctor", doctor), ("audit", audit), ("anigma", anigma)]:
                    grouped = health["groups"].get(name, [])
                    if grouped:
                        issues.append(f"{name.upper()}")
                        items = [tui_views.human_warning_label(name, item) for item in grouped]
                        issues.extend(f"• {item}" for item in items)
                        if selected_detail is None:
                            selected_detail = tui_views.render_health_detail(self.snapshot, name, grouped[0])
                issue_text = Text()
                if issues:
                    for idx, line in enumerate(issues[:10]):
                        style = "blue bold" if line.isupper() else "yellow" if line.startswith("•") else "dim"
                        issue_text.append(line, style=style)
                        if idx < min(len(issues), 10) - 1:
                            issue_text.append("\n")
                else:
                    issue_text.append("No current health issues.", style="dim")
                self.query_one("#health-issues", Static).update(issue_text)
                if selected_detail:
                    self.query_one("#health-detail", Static).update(
                        Text.assemble(
                            ("Subsystem · ", "dim"),
                            (str(selected_detail["subsystem"]), "blue bold"),
                            ("\nIssue · ", "dim"),
                            (str(selected_detail["issue"]), "yellow"),
                            ("\nRecommendation · ", "dim"),
                            (str(selected_detail["recommendation"] or "none"), "bold"),
                            ("\nArtifact · ", "dim"),
                            (str(selected_detail["artifact_path"] or "none"), "blue"),
                        )
                    )
                else:
                    self.query_one("#health-detail", Static).update("No selected warning.")
            except Exception:
                pass

        def update_vault(self) -> None:
            if not self.is_mounted:
                return
            try:
                vault = self.snapshot.get("vault") or {}
                self.query_one("#vault-status", Static).update(
                    Text.assemble(
                        ("Vault export · ", "dim"),
                        (str(vault.get("status", "unknown")).upper(), "green bold" if str(vault.get("status", "")).lower() == "pass" else "yellow bold"),
                        (" · path ", "dim"),
                        (str(vault.get("vault_path", "unknown")), "blue"),
                        (" · notes ", "dim"),
                        (str(vault.get("note_count", 0)), "bold"),
                    )
                )
                notes = []
                for key in ["dashboard_note_path", "latest_export_path", "index_path"]:
                    if vault.get(key):
                        notes.append(f"{key}: {vault.get(key)}")
                note_text = Text()
                if notes:
                    for idx, line in enumerate(notes):
                        note_text.append(line, style="blue")
                        if idx < len(notes) - 1:
                            note_text.append("\n")
                else:
                    note_text.append("No vault note paths yet.", style="dim")
                self.query_one("#vault-notes", Static).update(note_text)
            except Exception:
                pass

        def update_settings(self) -> None:
            if not self.is_mounted:
                return
            try:
                settings = self.snapshot.get("settings") or {}
                memory = settings.get("memory") or {}
                retention = settings.get("retention") or {}
                self.query_one("#settings-mode", Static).update(
                    Text.assemble(
                        ("Mode · ", "dim"),
                        (str(self.current_mode), "blue bold"),
                        (" · backend ", "dim"),
                        (str(settings.get("active_model_backend", "mlx")), "bold"),
                    )
                )
                self.query_one("#settings-backend", Static).update(
                    Text.assemble(
                        ("LLM · ", "dim"),
                        (str(settings.get("active_model_backend", "mlx")), "bold"),
                        (" · model ", "dim"),
                        (str(settings.get("active_mlx_model", "unknown")), "blue"),
                    )
                )
                self.query_one("#settings-memory", Static).update(
                    Text.assemble(
                        ("Scheduler · ", "dim"),
                        (("enabled" if settings.get("scheduler_enabled") else "disabled"), "green bold" if settings.get("scheduler_enabled") else "yellow bold"),
                        (" · vault ", "dim"),
                        (str(settings.get("vault_path", ".build/rig/vault/Rig-vault")), "blue"),
                    )
                )
                self.query_one("#settings-retention", Static).update(
                    Text.assemble(
                        ("Memory · max_tui_events ", "dim"),
                        (str(memory.get("max_tui_events", 500)), "bold"),
                        (" · max_projection_bytes ", "dim"),
                        (str(memory.get("max_projection_bytes", 1000000)), "bold"),
                        (" · max_loaded_log_bytes ", "dim"),
                        (str(memory.get("max_loaded_log_bytes", 200000)), "bold"),
                        (" · retention ephemeral ", "dim"),
                        (f"{retention.get('ephemeral_days', 7)}d", "bold"),
                        (" cache ", "dim"),
                        (f"{retention.get('cache_days', 30)}d", "bold"),
                        (" bundle ", "dim"),
                        (f"{retention.get('bundle_days', 365)}d", "bold"),
                    )
                )
                self.query_one("#settings-effective", Static).update(
                    Text.assemble(
                        ("Selected task · ", "dim"),
                        (str(self.selected_task_id or "none"), "blue bold" if self.selected_task_id else "dim"),
                        ("\nAuto-approve · ", "dim"),
                        (("requested" if self.auto_approve_requested else "off"), "yellow bold" if self.auto_approve_requested else "dim"),
                        (" · ", "dim"),
                        (("pending" if self.auto_approve_pending else "clear"), "yellow bold" if self.auto_approve_pending else "dim"),
                        ("\nPressure gate · ", "dim"),
                        (("parallel agents disabled on high pressure" if settings.get("memory", {}).get("high_pressure_disable_parallel_agents", True) else "parallel agents allowed"), "yellow" if settings.get("memory", {}).get("high_pressure_disable_parallel_agents", True) else "green"),
                    )
                )
            except Exception:
                pass

        def sync_action_buttons(self) -> None:
            if not self.is_mounted:
                return
            affordances = tui_views.action_affordances(self.snapshot, selected_task_id=self.selected_task_id, mode=self.current_mode)
            button_map = {
                "doctor_run": "doctor_run",
                "doctor_run_health": "doctor_run_health",
                "open_board": "open_board",
                "open_selected_task": "open_selected_task",
                "open_swarm": "open_swarm",
                "open_latest_scoreboard": "open_latest_scoreboard",
                "open_vault": "open_vault",
                "vault_open_uri": "vault_open_uri",
                "workspace_next_safe_action": "workspace_next_safe_action",
                "workspace_loop_dry_run": "workspace_loop_dry_run",
                "swarm_open_winner": "swarm_open_winner",
                "swarm_compare_candidates": "swarm_compare_candidates",
                "settings_show_effective": "settings_show_effective",
                "copy_selected_receipt": "copy_selected_receipt",
                "open_latest_report": "open_latest_report",
            }
            for button_id, action_id in button_map.items():
                try:
                    button = self.query_one(f"#{button_id}", Button)
                except Exception:
                    continue
                afford = affordances.get(action_id, {"enabled": True, "reason": ""})
                button.disabled = not bool(afford.get("enabled", True))

        def update_tables(self) -> None:
            if not self.is_mounted: return
            cards = self.snapshot.get("board", {}).get("cards", [])
            h = hashlib.md5(json.dumps({"c": cards, "sel": self.selected_task_id}, sort_keys=True).encode()).hexdigest()
            if self.last_snapshot_hashes.get("board") == h: return
            self.last_snapshot_hashes["board"] = h

            try:
                board_view = self.query_one("#board-view", Horizontal)
                layout_mode = tui_views.board_layout_mode(self.size.width)
                board_view.remove_class("columns", "stacked")
                board_view.add_class(layout_mode)
                self.query_one("#board-layout-note", Static).update(
                    f"Layout · {layout_mode} · selected {self.selected_task_id or 'none'} · events capped {self.max_visible_events}"
                )
                new_card_widgets = {}
                for c_data in cards:
                    tid = c_data["task_id"]
                    col_id = c_data.get("column_id", "backlog")
                    if col_id not in {"ready", "running", "approval", "blocked", "review"}: continue
                    
                    if tid in self.card_widgets:
                        card = self.card_widgets[tid]
                        card.card_data = c_data
                        card.sync_visuals()
                        card.remove_class("selected-card", "risk-high", "risk-medium", "risk-low", "semantic-pass", "semantic-warn", "semantic-fail", "semantic-info", "semantic-selected", "semantic-disabled")
                        card.add_class(tui_views.semantic_status_class(str(c_data.get("status") or "unknown")))
                        card.set_class(tid == self.selected_task_id, "selected-card")
                        card.set_class(str(c_data.get("risk") or "low").lower() == "high", "risk-high")
                        card.set_class(str(c_data.get("risk") or "low").lower() == "medium", "risk-medium")
                        card.set_class(str(c_data.get("risk") or "low").lower() == "low", "risk-low")
                        new_card_widgets[tid] = card
                    else:
                        card = TaskCard(c_data)
                        card.add_class(tui_views.semantic_status_class(str(c_data.get("status") or "unknown")))
                        card.set_class(tid == self.selected_task_id, "selected-card")
                        self.query_one(f"#cards-{col_id}", Vertical).mount(card)
                        new_card_widgets[tid] = card
                
                for tid, widget in self.card_widgets.items():
                    if tid not in new_card_widgets: widget.remove()
                self.card_widgets = new_card_widgets
                card = next((c for c in cards if c["task_id"] == self.selected_task_id), None) if self.selected_task_id else None
                board = tui_views.render_board_snapshot(self.snapshot, selected_task_id=self.selected_task_id, width=self.size.width)
                inspector = board["inspector"]
                affordances = tui_views.action_affordances(self.snapshot, selected_task_id=self.selected_task_id, mode=self.current_mode)
                action_lines: list[str] = []
                for action_id in sorted(self.runner.registry.actions.keys()):
                    plan = self.runner.registry.build_plan(action_id, self.selected_task_id, self.current_mode)
                    reason = plan.disabled_reason or affordances.get(action_id, {}).get("reason", "")
                    action_lines.append(f"{action_id}: {'allowed' if plan.is_valid else 'disabled'}{f' · {reason}' if reason else ''}")
                inspector_lines = [
                    f"Selected · {inspector['selected_task_id'] or 'none'}",
                    f"Task · {inspector['title']}",
                    f"Status · {inspector['status']} · Risk · {inspector['risk']}",
                    f"Layout · {board['layout_mode']}",
                    "Action affordances:",
                ] + action_lines[:10]
                if inspector["receipt_paths"]:
                    inspector_lines.append("Receipts:")
                    inspector_lines.extend(f"• {path}" for path in inspector["receipt_paths"])
                if card:
                    inspector_lines.append(f"Recommended · {card.get('recommended_next_action') or 'refresh_status'}")
                    if card.get("recommendation_reason"):
                        inspector_lines.append(f"Reason · {card.get('recommendation_reason')}")
                self.query_one("#board-inspector", Static).update("\n".join(inspector_lines))
                if card:
                    self.query_one("#workspace-selected", Static).update(f"Selected task · {card['task_id']}")
                else:
                    self.query_one("#workspace-selected", Static).update("Selected task · none")
            except: pass

        def on_task_selected(self, message: TaskSelected) -> None:
            self.selected_task_id = message.task_id
            self.persist_ui_state()
            self.refresh_all()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "show_more":
                self.action_show_more()
            elif event.button.id == "open_board":
                self.action_open_board()
            elif event.button.id == "open_swarm":
                self.action_open_swarm()
            elif event.button.id == "open_vault":
                self.action_open_vault()
            elif event.button.id == "open_selected_task":
                self.action_open_selected_task()
            elif event.button.id == "open_latest_scoreboard":
                self.action_open_latest_scoreboard()
            elif event.button.id == "settings_show_effective":
                self.action_show_effective_settings()
            elif event.button.id == "open_latest_report":
                self.action_open_latest_report()
            elif event.button.id == "copy_selected_receipt":
                self.action_copy_selected_receipt()
            elif event.button.id == "vault_open_uri":
                self.action_open_vault()
            elif event.button.id == "create_workspace_action":
                self.action_create_workspace()
            elif event.button.id in {"doctor_run", "doctor_run_health"}:
                self.action_run_doctor()
            elif event.button.id == "run_recommended":
                tid = self.selected_task_id
                card = next((c for c in self.snapshot.get("board", {}).get("cards", []) if c["task_id"] == tid), None)
                if card:
                    action = card.get("recommended_next_action")
                    if action: self.run_command(action)
            else:
                self.run_command(event.button.id)

        def action_show_more(self) -> None:
            self.push_screen(MoreCommandsScreen(self.current_mode), self.run_command)

        def action_run_recommended(self) -> None:
            self.on_button_pressed(Button(id="run_recommended"))

        def run_command(self, action_id: str) -> None:
            if not action_id: return
            plan = self.runner.registry.build_plan(action_id, self.selected_task_id, self.current_mode)
            if not plan.is_valid:
                self.write_event_line(f"DISABLED: {plan.disabled_reason}", style="bold warning")
                return

            self.run_worker(self.run_command_job(plan), thread=True)

        async def run_command_job(self, plan: CommandPlan):
            start_time = time.time()
            result = self.runner.run_plan(plan)
            duration = time.time() - start_time
            self.call_from_thread(self.write_event_line, render_command_result(plan.action_id, result.status, duration, result.stderr if result.status != "passed" else None))
            self.call_from_thread(self.refresh_all, build_derived=True)

        def tail_events(self) -> None:
            if not self.tail_enabled: return
            tui_events = self.repo_root / ".build" / "rig" / "tui" / "events.jsonl"
            self.tail_file_stream(tui_events)
            loop_id = (self.snapshot.get("loop") or {}).get("run_id")
            if loop_id:
                p = self.repo_root / ".build" / "rig" / "loop" / "runs" / loop_id / "events.jsonl"
                self.tail_file_stream(p)
            swarm_id = (self.snapshot.get("swarm") or {}).get("swarm_id")
            if swarm_id:
                p = self.repo_root / ".build" / "rig" / "swarm" / swarm_id / "events.jsonl"
                self.tail_file_stream(p)

        def tail_file_stream(self, path: Path) -> None:
            if not path.exists(): return
            try:
                with path.open("r", encoding="utf-8") as f:
                    path_str = str(path)
                    last_pos = self.tail_positions.get(path_str, 0)
                    f.seek(0, 2)
                    if f.tell() < last_pos: last_pos = 0
                    f.seek(last_pos)
                    lines = f.readlines()
                    for line in lines:
                        event: dict[str, Any] = {}
                        try:
                            event = json.loads(line)
                            self.visible_events.append(event)
                        except Exception:
                            pass
                        rendered = render_human_event_line(event if isinstance(event, dict) else {}, self.selected_task_id if self.focus_mode else None)
                        if rendered:
                            style = {
                                "semantic-pass": "green",
                                "semantic-warn": "yellow",
                                "semantic-fail": "red bold",
                                "semantic-info": "dim",
                                "semantic-selected": "blue bold",
                                "semantic-disabled": "dim",
                            }.get(event_semantic_class(event), "dim")
                            self.write_event_line(Text(rendered, style=style))
                    self.visible_events = self.visible_events[-self.max_visible_events:]
                    self.tail_positions[path_str] = f.tell()
            except: pass

        def action_toggle_tail(self) -> None:
            self.tail_enabled = not self.tail_enabled
            self.write_event_line(f"Tailing {'ENABLED' if self.tail_enabled else 'DISABLED'}")

        def action_toggle_focus(self) -> None:
            self.focus_mode = not self.focus_mode
            status = "ENABLED" if self.focus_mode else "DISABLED"
            self.write_event_line(f"FOCUS {status} ({self.selected_task_id})")

        def action_approve_gate(self) -> None:
            for g in self.snapshot.get("pending_gates", []):
                if g.get("task") == self.selected_task_id:
                    self.runner.write_gate_decision(g["gate_id"], "approved", "Approved via TUI")
                    self.refresh_all()
                    return

        def action_reject_gate(self) -> None:
            for g in self.snapshot.get("pending_gates", []):
                if g.get("task") == self.selected_task_id:
                    self.runner.write_gate_decision(g["gate_id"], "rejected", "Rejected via TUI")
                    self.refresh_all()
                    return

    return RigTuiApp()
