from __future__ import annotations

from typing import Any, Dict
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.message import Message
from textual.widgets import Label, Static
from rig_tools import tui_views
from rig_tools.tui_events import bauhaus_marker_for_status

class TaskSelected(Message):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__()

class TaskCard(Static):
    """A Bauhaus-style task card for the Kanban board."""
    def __init__(self, card_data: Dict[str, Any]):
        self.card_data = card_data
        self.task_id = card_data["task_id"]
        # Use task_id in the widget ID to avoid duplicates
        super().__init__(id=f"card-{self.task_id}", classes="kanban-card")

    def compose(self) -> ComposeResult:
        # Avoid using fixed IDs like "card-title-label" which repeat across instances.
        # Access them via classes or instance references if needed.
        status = self.card_data.get("status", "idle")
        risk = self.card_data.get("risk", "low")
        marker = bauhaus_marker_for_status(status, risk)
        next_action = self.card_data.get("recommended_next_action") or "refresh_status"
        receipt = self.card_data.get("latest_proof_path") or self.card_data.get("latest_bundle_path") or "no receipt"
        
        yield Label(f"{marker} {self.task_id}", classes="card-tid")
        yield Label(self.card_data.get("title", "No Title"), classes="card-title")
        yield Static(f"status {status} · risk {risk}", classes="card-meta")
        yield Static(f"next {next_action}", classes="card-action")
        yield Static(f"receipt {receipt}", classes="card-receipt")
        
        badges = []
        if self.card_data.get("is_blocked"): badges.append("BLOCKED")
        if self.card_data.get("needs_approval"): badges.append("APPROVAL")
        if self.card_data.get("has_patches"): badges.append("PATCHES")
        
        yield Static(" ".join(badges), classes="card-badges")

    def on_mount(self) -> None:
        self.sync_visuals()

    def sync_visuals(self) -> None:
        status = str(self.card_data.get("status", "idle")).lower()
        risk = self.card_data.get("risk", "low")
        marker = bauhaus_marker_for_status(status, risk)
        next_action = self.card_data.get("recommended_next_action") or "refresh_status"
        receipt = self.card_data.get("latest_proof_path") or self.card_data.get("latest_bundle_path") or "no receipt"
        for s in ["semantic-pass", "semantic-warn", "semantic-fail", "semantic-info", "semantic-selected", "semantic-disabled"]:
            self.remove_class(s)
        self.add_class(tui_views.semantic_status_class(status))
        for r in ["high", "medium", "low"]:
            self.set_class(risk == r, f"risk-{r}")
        try:
            self.query_one(".card-tid", Label).update(f"{marker} {self.task_id}")
            self.query_one(".card-title", Label).update(self.card_data.get("title", "No Title"))
            self.query_one(".card-meta", Static).update(f"status {status} · risk {risk}")
            self.query_one(".card-action", Static).update(f"next {next_action}")
            self.query_one(".card-receipt", Static).update(f"receipt {receipt}")
        except Exception:
            pass

    def on_click(self) -> None:
        self.post_message(TaskSelected(self.task_id))

class KanbanColumn(ScrollableContainer):
    """A scrollable column in the Kanban board."""
    def __init__(self, column_id: str, title: str):
        self.column_id = column_id
        self.column_title = title
        super().__init__(id=f"col-{column_id}")

    def compose(self) -> ComposeResult:
        # Each column has a header
        yield Label(self.column_title.upper(), classes="column-header")
        # And a vertical container for cards
        yield Vertical(id=f"cards-{self.column_id}", classes="column-cards")

    def update_cards(self, cards: list[Dict[str, Any]], card_widgets: dict[str, TaskCard]):
        """Updates the cards in this column, reusing existing widgets where possible."""
        container = self.query_one(f"#cards-{self.column_id}", Vertical)
        
        # This is a bit complex for a stateless update, usually you'd rebuild or diff.
        # For now, let the app handle the high-level diffing to minimize code here.
        pass
