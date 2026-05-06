from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rig_tools import textual_validator

def setup(subparsers: argparse._SubParsersAction, helpers: Any) -> None:
    textual = subparsers.add_parser("textual", help="Textual TUI management and validation")
    textual_subs = textual.add_subparsers(dest="textual_cmd")

    validate = textual_subs.add_parser("validate", help="Validate Rig TUI source for Textual compatibility")
    validate.add_argument("--path", type=str, help="Specific path to validate")
    validate.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    validate.add_argument("--agent", action="store_true", help="Agent mode: JSON only, exit nonzero on fail")
    validate.set_defaults(handler=lambda args: _validate(helpers, args))

    rules = textual_subs.add_parser("rules", help="List Textual compatibility rules")
    rules.set_defaults(handler=lambda args: _rules(helpers, args))

def _validate(helpers: Any, args: argparse.Namespace) -> int:
    paths = []
    if args.path:
        paths.append(Path(args.path))
    else:
        # Defaults
        paths.append(helpers.repo_root / "scripts" / "rig_tools" / "tui_app.py")
        for p in (helpers.repo_root / "scripts" / "rig_tools").glob("*.tcss"):
            paths.append(p)
        for p in (helpers.repo_root / "scripts" / "rig_tools").glob("*.py"):
            if "CSS =" in p.read_text(encoding="utf-8", errors="ignore"):
                paths.append(p)

    result = textual_validator.run_validation(paths)
    
    if args.agent or args.format == "json":
        print(json.dumps(result, indent=2))
        return 1 if result["status"] == "fail" else 0

    # Human readable mode
    print(f"RIG TEXTUAL VALIDATOR - Status: {result['status'].upper()}")
    print("-" * 60)
    
    for issue in result["issues"]:
        print(f"ERROR: {issue['message']}")
        print(f"Path:  {issue['path']}:{issue['line']}:{issue['column']}")
        print(f"Bad:   {issue['snippet']}")
        print(f"Fix:   {issue['fix']}")
        print("-" * 60)

    for warn in result["warnings"]:
        print(f"WARN:  {warn['message']}")
        print(f"Path:  {warn['path']}:{warn['line']}")
        print("-" * 60)

    if result["status"] == "fail":
        print(f"Found {result['issue_count']} compatibility issues.")
        return 1
    
    print("No compatibility issues found.")
    return 0

def _rules(helpers: Any, args: argparse.Namespace) -> int:
    print("TEXTUAL COMPATIBILITY RULES")
    print("=" * 60)
    print("1. No browser CSS properties (font-size, display: flex, gap, etc.)")
    print("2. 'align' must have exactly two values: horizontal then vertical")
    print("   (e.g. align: center middle;)")
    print("3. No RichLog internal API access (.lines_count, .lines)")
    print("4. No direct widget internal mutation (._*)")
    return 0
