from __future__ import annotations

import sys
import subprocess
import json
from pathlib import Path
from typing import Optional

def register(subparsers, helpers):
    """Registers the 'os' command group."""
    parser = subparsers.add_parser("os", help="Rig OS governance commands")
    os_sub = parser.add_subparsers(dest="os_command")
    
    sentinel_parser = os_sub.add_parser("sentinel", help="Run Rig OS Sentinel validator")
    sentinel_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    sentinel_parser.set_defaults(handler=lambda args: os_sentinel(format=args.format))

def os_sentinel(format: str = "text"):
    """Runs the Rig OS Sentinel governance validator."""
    repo_root = Path(__file__).parent.parent.parent.resolve()
    sentinel_py = repo_root / "Scripts" / "rig_os_sentinel.py"
    
    if not sentinel_py.exists():
        print(f"Error: Sentinel not found at {sentinel_py}", file=sys.stderr)
        sys.exit(1)
        
    cmd = [sys.executable, str(sentinel_py), "--format", format]
    
    # We use subprocess.run here because the sentinel is the authority
    # and we want to pass through its output and exit code directly.
    result = subprocess.run(cmd, cwd=repo_root, capture_output=False)
    sys.exit(result.returncode)
