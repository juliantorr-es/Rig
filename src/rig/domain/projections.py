from dataclasses import dataclass, field
import uuid
from typing import Any, Dict, List, Optional

@dataclass
class WidgetProjection:
    type: str
    id: str
    data: Dict[str, Any]
    actions: List[str] = field(default_factory=list)

@dataclass
class IntentProjection:
    kind: str
    label: str
    enabled: bool
    target: Optional[Dict[str, Any]] = None
    disabled_reason: Optional[str] = None

@dataclass
class ProjectionLayout:
    regions: Dict[str, List[str]]

@dataclass
class ValidatorItem:
    id: str
    label: str
    state: str # 'passed', 'failed', 'missing', 'running'
    detail: Optional[str] = None

@dataclass
class ValidatorStackProjection:
    title: str
    state: Dict[str, str] # {label, severity}
    summary: str
    items: List[ValidatorItem]
    running_validator_id: Optional[str] = None  # ID of currently running validator, or None
    run_in_progress: bool = False  # True if validation run is currently in progress

@dataclass
class ReceiptProjection:
    id: str
    kind: str
    label: str
    timestamp: str
    verified: bool
    summary: str
    raw_reference: Optional[str] = None
    schema_version: str = "rig.ui.projection.v1"
    projection_revision: Optional[int] = None

@dataclass
class ChatMessage:
    role: str # 'user' or 'assistant'
    content: str
    at: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

@dataclass
class ChatProjection:
    messages: List[ChatMessage]
    composer_enabled: bool = True
    composer_placeholder: str = "Type / for commands or describe an intent..."

@dataclass
class UIProjection:
    schema_version: str = "rig.ui.projection.v1"
    projection_id: str = "local-shell"
    revision: int = 1
    generated_at: str = ""
    screen: str = "empty_workspace"
    shell: Dict[str, Any] = field(default_factory=dict)
    chat: Optional[ChatProjection] = None
    layout: ProjectionLayout = field(default_factory=lambda: ProjectionLayout({}))
    widgets: Dict[str, WidgetProjection] = field(default_factory=dict)
    intents: Dict[str, IntentProjection] = field(default_factory=dict)
