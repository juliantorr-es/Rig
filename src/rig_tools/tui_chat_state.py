from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TuiChatState:
    draft: str = ""
    preview: str | None = None
    history: list[str] = field(default_factory=list)
