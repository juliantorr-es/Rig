"""
Agent Discovery for Rig

Discovers available AI agents (codex, gemini, claude, etc.) on the system.

Uses rig_tools.core.process for subprocess execution.
Uses rig_tools.core.io for JSON I/O.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

# Use core utilities
from rig_tools.core import run_capture
from rig_tools.core.io import write_json


SCHEMA_VERSION = "rig.agent_discovery.v1"


def discover_agents(repo_root: Path) -> dict[str, Any]:
    """Discover available agents on the system."""
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    candidates = ["codex", "gemini", "claude", "vibe", "opencode"]
    agents = []
    
    for agent_id in candidates:
        agents.append(_probe_agent(agent_id))
        
    discovery = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now,
        "agents": agents,
        "warnings": [],
        "authoritative": False,
    }
    
    out_dir = repo_root / ".build" / "rig" / "agents" / "discovery"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "latest.json", discovery)
    
    return discovery


def _probe_agent(agent_id: str) -> dict[str, Any]:
    """Probe a single agent for capabilities."""
    executable = shutil.which(agent_id)
    found = executable is not None
    version = "unknown"
    help_status = "unavailable"
    non_interactive_supported = False
    non_interactive_modes = []
    structured_output_supported = False
    risk_level = "medium"
    enabled_by_default = True
    warnings = []

    if found:
        # Try version
        try:
            res = run_capture([agent_id, "--version"], timeout=5)
            if res.returncode == 0:
                version = res.stdout.strip()
            else:
                res = run_capture([agent_id, "version"], timeout=5)
                if res.returncode == 0:
                    version = res.stdout.strip()
        except Exception:
            pass
            
        # Try help
        try:
            res = run_capture([agent_id, "--help"], timeout=5)
            help_text = res.stdout.lower()
            if res.returncode == 0:
                help_status = "available"
                
                if agent_id == "codex":
                    if "exec" in help_text:
                        non_interactive_supported = True
                        non_interactive_modes.append("codex exec")
                elif agent_id == "gemini":
                    if "-p" in help_text or "--prompt" in help_text:
                        non_interactive_supported = True
                        non_interactive_modes.append("-p / --prompt")
                    if "--output-format" in help_text or "stream-json" in help_text:
                        structured_output_supported = True
                elif agent_id == "claude":
                    if "-p" in help_text or "--print" in help_text:
                        non_interactive_supported = True
                    if "--output-format" in help_text:
                        structured_output_supported = True
                elif agent_id == "vibe":
                    risk_level = "high"
                    enabled_by_default = False
                    if "--prompt" in help_text:
                        non_interactive_supported = True
                    if "--auto-approve" in help_text:
                        warnings.append("auto-approve mode detected")
                elif agent_id == "opencode":
                    if "run" in help_text:
                        non_interactive_supported = True
            else:
                help_status = "failed"
        except Exception as exc:
            help_status = f"error: {exc}"

    return {
        "agent_id": agent_id,
        "executable": executable,
        "found": found,
        "version": version,
        "help_status": help_status,
        "non_interactive_supported": non_interactive_supported,
        "non_interactive_modes": non_interactive_modes,
        "structured_output_supported": structured_output_supported,
        "risk_level": risk_level,
        "enabled_by_default": enabled_by_default,
        "warnings": warnings,
    }
