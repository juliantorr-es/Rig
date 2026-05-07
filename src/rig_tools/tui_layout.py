from __future__ import annotations

from typing import Iterable

try:  # pragma: no cover - exercised when Textual is installed
    from textual.containers import Container
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widgets import Input, Static
except Exception:  # pragma: no cover - fallback for test/bootstrap environments without Textual
    class _Shim:
        def __init__(self, *children, **kwargs):
            self.children = children
            self.kwargs = kwargs
            self.id = kwargs.get("id")
            self.classes = kwargs.get("classes")

        def add_class(self, *_args, **_kwargs):
            return None

        def remove_class(self, *_args, **_kwargs):
            return None

        def post_message(self, _message):
            return None

    class Container(_Shim):
        pass

    class Message:
        def __init__(self, sender):
            self.sender = sender

    def reactive(default):  # type: ignore[override]
        return default

    class Static(_Shim):
        pass

    class Input(_Shim):
        def __init__(self, *children, placeholder: str = "", **kwargs):
            super().__init__(*children, **kwargs)
            self.placeholder = placeholder
            self.value = ""


class RigPanel(Container):
    def __init__(self, *children, title: str | None = None, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(*children, id=id, classes=classes)
        self.title = title or ""

    def on_mount(self) -> None:
        if self.title:
            self.add_class("rig-panel")


class RigSidebar(Container):
    pass


class RigMainColumn(Container):
    pass


class RigEvidenceRail(Container):
    pass


class RigMetricWidget(Static):
    title = reactive("")
    value = reactive("")
    sublines = reactive(())
    status = reactive("info")

    def __init__(self, *, title: str = "", value: str = "", sublines: Iterable[str] | None = None, status: str = "info", id: str | None = None) -> None:
        super().__init__(id=id, classes="rig-metric")
        self.title = title
        self.value = value
        self.sublines = tuple(sublines or ())
        self.status = status

    def watch_status(self, _old: str, new: str) -> None:
        for token in ("rig-status-success", "rig-status-error", "rig-status-warning", "rig-status-info", "rig-status-muted"):
            self.remove_class(token)
        self.add_class(f"rig-status-{new}" if new else "rig-status-info")

    def render(self) -> str:
        lines = [f"{self.title}", f"{self.value}"]
        lines.extend(self.sublines)
        return "\n".join(line for line in lines if line)


class CommandSubmitted(Message):
    def __init__(self, sender: "RigCommandInput", raw_text: str, command_kind: str, timestamp: str | None = None) -> None:
        super().__init__(sender)
        self.raw_text = raw_text
        self.command_kind = command_kind
        self.timestamp = timestamp


class RigCommandInput(Input):
    DEFAULT_CSS_CLASSES = "rig-chat-input"

    def submit_command(self) -> None:
        raw = self.value.strip()
        if not raw:
            return
        kind = "slash" if raw.startswith("/") else "natural-language"
        self.post_message(CommandSubmitted(self, raw, kind))
        self.value = ""
