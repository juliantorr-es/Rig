from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable

@dataclass
class Intent:
    schema_version: str = "rig.ui.intent.v1"
    intent_id: str = ""
    kind: str = ""
    target: Optional[Dict[str, Any]] = None
    observed_projection_revision: int = 0
    idempotency_key: Optional[str] = None
    submitted_at: str = ""
    client: Dict[str, str] = field(default_factory=lambda: {"kind": "pywebview"})

class IntentHandler:
    def __init__(self):
        self._handlers: Dict[str, Callable[[Intent], Any]] = {}

    def register(self, kind: str, handler: Callable[[Intent], Any]):
        self._handlers[kind] = handler

    def handle(self, intent: Intent) -> Any:
        handler = self._handlers.get(intent.kind)
        if not handler:
            return {"accepted": False, "reason": f"Unknown intent kind: {intent.kind}"}
        return handler(intent)
