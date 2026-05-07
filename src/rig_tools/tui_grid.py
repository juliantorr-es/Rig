from __future__ import annotations

try:  # pragma: no cover - exercised when Textual is installed
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Footer, Static
except Exception:  # pragma: no cover - fallback for environments without Textual
    from rig_tools.tui_layout import Container, Static

    class Horizontal(Container):
        pass

    class Vertical(Container):
        pass

    class Footer(Static):
        pass

from rig_tools.tui_layout import RigSidebar, RigMainColumn, RigEvidenceRail, RigPanel, RigCommandInput
from rig_tools.tui_theme import RIG_GLOBAL_CSS


class RigDashboardGrid(Container):
    DEFAULT_CSS_CLASSES = "rig-shell"
    DEFAULT_CSS = RIG_GLOBAL_CSS

    def compose(self):
        with RigPanel(title="Topbar", id="rig-topbar", classes="rig-topbar"):
            yield Static("RIG", classes="rig-panel-title")
        with RigSidebar(id="rig-sidebar"):
            yield Static("Sidebar", classes="rig-panel-title")
        with RigMainColumn(id="rig-main"):
            yield Static("Main", classes="rig-panel-title")
        with RigEvidenceRail(id="rig-evidence"):
            yield Static("Evidence", classes="rig-panel-title")
        with RigPanel(id="rig-chat", classes="rig-chat"):
            yield RigCommandInput(placeholder="Type /status or a natural-language intent", id="rig-chat-input")
        yield Footer(id="rig-footer")


def compose_sidebar():
    return RigSidebar(id="rig-sidebar")


def compose_main():
    return RigMainColumn(id="rig-main")


def compose_evidence_rail():
    return RigEvidenceRail(id="rig-evidence")


def compose_chat():
    return RigPanel(id="rig-chat", classes="rig-chat")
