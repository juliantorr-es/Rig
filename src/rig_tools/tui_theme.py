from __future__ import annotations

SEMANTIC_COLORS: dict[str, str] = {
    "success": "#1E8E3E",
    "error": "#D93025",
    "warning": "#F9AB00",
    "info": "#1A73E8",
    "border": "#1A1A1A",
    "muted": "#5F6368",
    "background": "#F7F7F2",
    "surface": "#FFFFFF",
    "text": "#111111",
}

STATUS_TOKENS: dict[str, dict[str, str]] = {
    "blocked": {"label": "BLOCKED", "marker": "!", "color": "error"},
    "failed": {"label": "FAILED", "marker": "×", "color": "error"},
    "warning": {"label": "WARN", "marker": "△", "color": "warning"},
    "pending": {"label": "PENDING", "marker": "…", "color": "warning"},
    "running": {"label": "RUNNING", "marker": "▶", "color": "info"},
    "success": {"label": "OK", "marker": "✓", "color": "success"},
    "eligible": {"label": "ELIGIBLE", "marker": "◇", "color": "success"},
    "info": {"label": "INFO", "marker": "i", "color": "info"},
    "muted": {"label": "MUTED", "marker": "-", "color": "muted"},
}

_STATUS_CLASS_RULES = "\n".join(
    f".rig-status-{key} {{ color: {SEMANTIC_COLORS[value['color']]}; }}"
    for key, value in STATUS_TOKENS.items()
)
_STATUS_CLASS_ALIASES = "\n".join(
    f".rig-status-{name} {{ color: {SEMANTIC_COLORS[name]}; }}"
    for name in ("success", "error", "warning", "info", "muted")
)

RIG_GLOBAL_CSS = f"""
/* Gridline Interface global CSS */
.rig-shell {{
    layout: grid;
    grid-size: 3;
    grid-columns: 28 1fr 38;
    grid-rows: auto 1fr auto;
    background: {SEMANTIC_COLORS["background"]};
    color: {SEMANTIC_COLORS["text"]};
    border: solid {SEMANTIC_COLORS["border"]};
}}

.rig-topbar, .rig-sidebar, .rig-main, .rig-evidence-rail, .rig-chat, .rig-panel {{
    border: solid {SEMANTIC_COLORS["border"]};
    background: {SEMANTIC_COLORS["surface"]};
}}

.rig-topbar {{ grid-column: 1 / span 3; }}
.rig-sidebar {{ grid-column: 1; }}
.rig-main {{ grid-column: 2; }}
.rig-evidence-rail {{ grid-column: 3; }}
.rig-chat {{ grid-column: 1 / span 3; }}

.rig-panel-title {{
    text-style: bold;
    text-transform: uppercase;
    color: {SEMANTIC_COLORS["muted"]};
}}

.rig-metric {{
    border: solid {SEMANTIC_COLORS["border"]};
    background: {SEMANTIC_COLORS["surface"]};
    padding: 0 1;
}}

.rig-metric-title {{
    color: {SEMANTIC_COLORS["muted"]};
    text-style: bold;
}}

.rig-metric-value {{
    text-style: bold;
}}

.rig-chat-input {{
    border: solid {SEMANTIC_COLORS["border"]};
}}

.rig-command-preview {{
    color: {SEMANTIC_COLORS["info"]};
}}

{_STATUS_CLASS_RULES}
{_STATUS_CLASS_ALIASES}
"""


def gridline_css_variables() -> str:
    return "\n".join(f"--rig-{name}: {value};" for name, value in SEMANTIC_COLORS.items())
