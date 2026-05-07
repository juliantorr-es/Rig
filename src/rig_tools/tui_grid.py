from __future__ import annotations

"""Gridline dashboard skeleton and app helpers."""

from pathlib import Path
from typing import Any

from rig_tools.tui_layout import (
    RigChatTranscript,
    RigCommandInput,
    RigDebugBundleCard,
    RigEvidenceRail,
    RigMainColumn,
    RigMetricWidget,
    RigPanel,
    RigSidebar,
)
from rig_tools.tui_snapshot import load_snapshot
from rig_tools.tui_theme import RIG_GLOBAL_CSS

try:  # pragma: no cover - exercised when Textual is installed
    from textual.app import App
    from textual.binding import Binding
    from textual.containers import Container
    from textual.widgets import Footer, Static
except Exception:  # pragma: no cover - fallback for environments without Textual
    from rig_tools.tui_layout import Container, Static

    class App:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def run(self):
            return None

    class Binding:  # type: ignore[override]
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class Footer(Static):
        pass


class RigDashboardGrid(Container):
    """Read-only Gridline dashboard shell."""

    DEFAULT_CSS = RIG_GLOBAL_CSS

    def __init__(self, repo_root: Path, *, snapshot: dict[str, Any] | None = None, chat_enabled: bool = True, id: str | None = None):
        super().__init__(id=id)
        self.add_class("rig-shell")
        self.repo_root = repo_root
        self.snapshot = snapshot or load_snapshot(repo_root)
        self.chat_enabled = chat_enabled

    def compose(self):
        yield from self.compose_topbar()
        yield from self.compose_body()
        if self.chat_enabled:
            yield from self.compose_chat()
        yield Footer(id="rig-footer")

    def compose_topbar(self):
        with RigPanel(title="Topbar", id="rig-topbar", classes="rig-topbar"):
            yield Static("RIG", classes="rig-panel-title")
            yield Static("GRIDLINE INTERFACE", classes="rig-panel-title")
            yield Static(f"status: {self.snapshot.get('queue', {}).get('status', 'unknown')}")

    def compose_body(self):
        with Container(id="rig-body", classes="rig-body"):
            with RigSidebar(id="rig-sidebar"):
                yield Static("NAV", classes="rig-panel-title")
                yield RigMetricWidget(title="Jobs", value=str(len(self.snapshot.get("jobs", []))), status="info")
                yield RigMetricWidget(title="Workspaces", value=str(len(self.snapshot.get("workspaces", []))), status="success")
                yield RigMetricWidget(title="Providers", value=str(len(self.snapshot.get("providers", []))), status="warning")
            with RigMainColumn(id="rig-main"):
                yield Static("COMMAND CENTER", classes="rig-panel-title")
                yield Static("Jobs, workspaces, providers, and governed runs live here.")
                yield Static("The shell is read-only in window mode.", classes="rig-command-preview")
            with RigEvidenceRail(id="rig-evidence"):
                yield Static("NEXT GATE", classes="rig-panel-title")
                yield Static(self.snapshot.get("queue", {}).get("next_gate") or self.snapshot.get("queue", {}).get("status", "unknown"))
                yield RigDebugBundleCard()

    def compose_chat(self):
        with RigPanel(id="rig-chat", classes="rig-chat"):
            yield Static("CHAT / SLASH CONSOLE", classes="rig-panel-title")
            yield RigChatTranscript(id="rig-chat-transcript")
            yield RigCommandInput(placeholder="Type / for commands or describe an intent…", id="rig-chat-input")


def compose_sidebar():
    return RigSidebar(id="rig-sidebar")


def compose_main():
    return RigMainColumn(id="rig-main")


def compose_evidence_rail():
    return RigEvidenceRail(id="rig-evidence")


def compose_chat():
    return RigPanel(id="rig-chat", classes="rig-chat")


class GridlineApp(App):
    TITLE = "Rig"
    SUB_TITLE = "control"

    BINDINGS = [
        Binding("/", "focus_chat", "Chat"),
        Binding("ctrl+p", "command_palette", "Palette", show=False),
        Binding("enter", "submit", "Submit"),
        Binding("escape", "blur", "Back"),
        Binding("?", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "down", "Down"),
        Binding("k", "up", "Up"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = RIG_GLOBAL_CSS

    def __init__(self, repo_root: Path, *, chat_enabled: bool = True):
        super().__init__()
        self.repo_root = repo_root
        self.chat_enabled = chat_enabled

    def compose(self):
        yield RigDashboardGrid(self.repo_root, chat_enabled=self.chat_enabled)


def build_gridline_app(repo_root: Path, *, chat_enabled: bool = True) -> App:
    return GridlineApp(repo_root, chat_enabled=chat_enabled)
