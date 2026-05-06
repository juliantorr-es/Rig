from __future__ import annotations

import os
import re
import json
import time
from pathlib import Path
from typing import Any

# Error codes
ERR_BROWSER_PROPERTY = "textual_css_browser_property"
ERR_ALIGN_ARITY = "textual_css_invalid_align_arity"
ERR_ALIGN_VALUE = "textual_css_invalid_align_value"
ERR_RICHLOG_INTERNAL = "textual_richlog_internal_api"
ERR_RICHLOG_WRITE_KWARG = "textual_richlog_write_unsupported_keyword"
ERR_UNSAFE_GET = "python_optional_get_unsafe_use"
ERR_FAKE_TELEMETRY = "tui_fake_telemetry_value"
ERR_WIDGET_INTERNAL = "textual_widget_internal_api"

# Forbidden browser CSS properties
FORBIDDEN_PROPERTIES = {
    "font-size": "Textual terminal cells do not support per-widget browser font sizing. Remove this. Use compact layout, padding/margin, truncation, or text-style.",
    "font-style": "Textual uses text-style: italic; instead of font-style.",
    "font-weight": "Textual uses text-style: bold; instead of font-weight.",
    "line-height": "Remove; terminal rows are discrete cells.",
    "display: flex": "Use Textual containers: Horizontal, Vertical, Grid, HorizontalScroll.",
    "gap": "Use margin/padding or container layout spacing.",
    "border-radius": "Remove; not terminal-cell concepts.",
    "box-shadow": "Remove; not terminal-cell concepts.",
    "overflow-x": "Use scrollable containers or overflow: hidden/scroll.",
    "overflow-y": "Use scrollable containers or overflow: hidden/scroll.",
    "position: absolute": "Use dock: top/bottom/left/right or layout system.",
    "position: fixed": "Use dock or sticky headers/footers.",
}

# Align validation
VALID_HORIZ = {"left", "center", "right"}
VALID_VERT = {"top", "middle", "bottom"}

def validate_textual_source(path: Path) -> list[dict[str, Any]]:
    issues = []
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # 1. CSS/TCSS Scan
    if path.suffix == ".tcss" or "CSS =" in content:
        prop_regex = re.compile(r"([\w-]+)\s*:\s*([^;]+)\s*;")
        for i, line in enumerate(lines):
            if "# textual: skip" in line: continue
            line_num = i + 1
            for match in prop_regex.finditer(line):
                prop = match.group(1)
                val = match.group(2).strip()
                
                if prop in FORBIDDEN_PROPERTIES:
                    issues.append({
                        "code": ERR_BROWSER_PROPERTY,
                        "severity": "error",
                        "path": str(path),
                        "line": line_num,
                        "column": match.start() + 1,
                        "snippet": match.group(0),
                        "message": f"Forbidden browser CSS property: {prop}",
                        "why_it_fails": FORBIDDEN_PROPERTIES[prop],
                        "fix": f"Remove {prop} from your CSS.",
                        "correct_example": "/* Remove forbidden property */",
                        "source": "rig_textual_validator"
                    })
                
                # Special cases like display: flex
                full_decl = f"{prop}: {val}"
                if full_decl in FORBIDDEN_PROPERTIES:
                    issues.append({
                        "code": ERR_BROWSER_PROPERTY,
                        "severity": "error",
                        "path": str(path),
                        "line": line_num,
                        "column": match.start() + 1,
                        "snippet": match.group(0),
                        "message": f"Forbidden browser CSS declaration: {full_decl}",
                        "why_it_fails": FORBIDDEN_PROPERTIES[full_decl],
                        "fix": f"Remove {full_decl} and use Textual containers.",
                        "correct_example": "/* Use Horizontal or Vertical containers */",
                        "source": "rig_textual_validator"
                    })
                
                if prop == "align":
                    parts = val.split()
                    if len(parts) != 2:
                        issues.append({
                            "code": ERR_ALIGN_ARITY,
                            "severity": "error",
                            "path": str(path),
                            "line": line_num,
                            "column": match.start() + 1,
                            "snippet": match.group(0),
                            "message": f"Invalid Textual align declaration: {val}",
                            "why_it_fails": "Textual align expects exactly two values: horizontal then vertical.",
                            "fix": "Replace with `align: center middle;` or another valid two-value declaration.", # textual: skip
                            "correct_example": "align: center middle;", # textual: skip
                            "source": "rig_textual_validator"
                        })
                    else:
                        h, v = parts[0], parts[1]
                        if h not in VALID_HORIZ or v not in VALID_VERT:
                             issues.append({
                                "code": ERR_ALIGN_VALUE,
                                "severity": "error",
                                "path": str(path),
                                "line": line_num,
                                "column": match.start() + 1,
                                "snippet": match.group(0),
                                "message": f"Invalid Textual align values: {h} {v}",
                                "why_it_fails": "Textual align values must be (left|center|right) and (top|middle|bottom).",
                                "fix": "Ensure the first value is horizontal and the second is vertical.",
                                "correct_example": "align: center middle;", # textual: skip
                                "source": "rig_textual_validator"
                            })

    # 2. RichLog API Scan
    richlog_internals = [".lines_count", ".lines[", ".lines)", ".lines.", "len(log.lines)", "getattr(log, \"lines\""] # textual: skip
    write_kwargs_regex = re.compile(r"\.write\(.*,\s*(style|end|highlight)\s*=")
    
    for i, line in enumerate(lines):
        if "# textual: skip" in line: continue
        line_num = i + 1
        
        # Internal API
        for internal in richlog_internals:
            if internal in line:
                issues.append({
                    "code": ERR_RICHLOG_INTERNAL,
                    "severity": "error",
                    "path": str(path),
                    "line": line_num,
                    "column": line.find(internal) + 1,
                    "snippet": line.strip(),
                    "message": f"Direct access to RichLog internal API: {internal}",
                    "why_it_fails": "RichLog internals like lines_count and lines are not part of the stable public API.",
                    "fix": "Do not inspect RichLog internals. Track empty/log-line state in Rig-owned state, e.g. self.event_stream_empty.", # textual: skip
                    "source": "rig_textual_validator"
                })
        
        # Unsupported write kwargs
        # We allow style= if it's inside Text(...) but NOT as a kwarg to .write(...)
        if ".write(" in line:
            bad_kwargs = ["style=", "end=", "highlight="]
            for kw in bad_kwargs:
                if kw in line:
                    # Stricter check: is kw actually a parameter of the .write() call?
                    # We reject .write(..., style=...) but allow .write(Text(..., style=...)) # textual: skip
                    # Basic heuristic: if 'Text(' is on the same line and before the kw, skip.
                    if kw == "style=" and "Text(" in line and line.find("Text(") < line.find(kw):
                        continue

                    write_kwarg_pattern = re.compile(rf"\.write\(.*{kw}") # textual: skip
                    if write_kwarg_pattern.search(line):
                        issues.append({
                            "code": ERR_RICHLOG_WRITE_KWARG,
                            "severity": "error",
                            "path": str(path),
                            "line": line_num,
                            "column": line.find(kw) + 1,
                            "snippet": line.strip(),
                            "message": f"Unsupported keyword argument in RichLog.write: {kw}",
                            "why_it_fails": "RichLog.write in this Textual version does not accept style=, end=, or highlight=.",
                            "fix": "Pass a Rich Text object if style is needed, or just a string.",
                            "correct_example": "from rich.text import Text\nlog.write(Text(line, style=style))", # textual: skip
                            "source": "rig_textual_validator"
                        })

    # 3. Unsafe .get() slicing/subscript
    unsafe_get_regex = re.compile(r"\.get\([^\)]+\)\[[^\]]+\]|\.get\([^\)]+\)\.(strip|lower|upper|startswith|endswith|split)\(")
    for i, line in enumerate(lines):
        if "# textual: skip" in line: continue
        line_num = i + 1
        match = unsafe_get_regex.search(line)
        if match:
            issues.append({
                "code": ERR_UNSAFE_GET,
                "severity": "error",
                "path": str(path),
                "line": line_num,
                "column": match.start() + 1,
                "snippet": line.strip(),
                "message": "Unsafe slicing or method call on .get() result",
                "why_it_fails": ".get() can return None, which causes a crash when sliced or called with a method.",
                "fix": "Use `(data.get('key') or 'default')` before slicing or calling methods.",
                "correct_example": "name = (data.get('name') or 'unknown').strip()",
                "source": "rig_textual_validator"
            })

    # 4. Telemetry fake values
    telemetry_fake_regex = re.compile(r"[\"'][^\"']*(RAM|CPU)\s+None%[^\"']*[\"']|[\"'][^\"']*Disk 0G free[^\"']*[\"']")
    for i, line in enumerate(lines):
        if "# textual: skip" in line: continue
        line_num = i + 1
        match = telemetry_fake_regex.search(line)
        if match:
            issues.append({
                "code": ERR_FAKE_TELEMETRY,
                "severity": "warning",
                "path": str(path),
                "line": line_num,
                "column": match.start() + 1,
                "snippet": line.strip(),
                "message": "Suspicious telemetry fallback value",
                "why_it_fails": "Rendering 'None%' or '0G free' when telemetry is missing looks unpolished.",
                "fix": "Render 'Pressure unavailable' if metrics are missing.",
                "correct_example": "strip = 'Pressure unavailable' if metrics_missing else ...",
                "source": "rig_textual_validator"
            })

    # 5. Risky guessed internals
    risky_internals = re.compile(r"(?<!re\.compile\(r\")\._\w+|\.children\[|\.parent\.children") # textual: skip
    for i, line in enumerate(lines):
        if "# textual: skip" in line: continue
        if "__init__" in line: continue
        line_num = i + 1
        for match in risky_internals.finditer(line):
            issues.append({
                "code": ERR_WIDGET_INTERNAL,
                "severity": "warning",
                "path": str(path),
                "line": line_num,
                "column": match.start() + 1,
                "snippet": match.group(0),
                "message": f"Access to potentially private Textual internal: {match.group(0)}",
                "why_it_fails": "Accessing private members or children directly is risky across Textual versions.",
                "fix": "Use public methods (query_one, query) to find child widgets.",
                "correct_example": "self.query_one(\"#child-id\")",
                "source": "rig_textual_validator"
            })

    return issues

def run_validation(paths: list[Path]) -> dict[str, Any]:
    all_issues = []
    checked_paths = []
    for p in paths:
        if p.exists():
            checked_paths.append(str(p))
            all_issues.extend(validate_textual_source(p))
    
    errors = [i for i in all_issues if i["severity"] == "error"]
    warnings = [i for i in all_issues if i["severity"] == "warning"]
    
    return {
        "schema_version": "rig.textual_validation.v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "fail" if errors else "pass",
        "checked_paths": checked_paths,
        "issue_count": len(errors),
        "issues": errors,
        "warnings": warnings,
        "agent_repair_prompt": "Fix the Textual compatibility and null-safety errors listed in issues. Do not use browser CSS. Do not access RichLog internals. Do not pass unsupported kwargs to RichLog.write. Do not slice or call methods on .get() without fallback. Rerun validation after fixes.",
        "authoritative": True
    }
