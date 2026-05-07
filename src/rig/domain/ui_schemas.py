from dataclasses import dataclass, field
from typing import Any, List, Optional, Dict

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
class UIProjection:
    schema_version: str = "rig.ui.projection.v1"
    revision: int = 1
    screen: str = "empty_workspace"
    layout: ProjectionLayout = field(default_factory=lambda: ProjectionLayout({}))
    widgets: Dict[str, WidgetProjection] = field(default_factory=dict)
    intents: Dict[str, IntentProjection] = field(default_factory=dict)
