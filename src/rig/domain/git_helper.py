import subprocess
from pathlib import Path
from typing import Dict, Any

def get_git_info(repo_root: Path) -> Dict[str, Any]:
    try:
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        branch = "unknown"
        
    try:
        head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        head = "unknown"
        
    try:
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL)
        dirty_files = [line[3:] for line in status.splitlines() if line.strip()]
    except Exception:
        dirty_files = []
        
    return {
        "branch": branch,
        "head": head,
        "dirty": len(dirty_files) > 0,
        "dirty_files": dirty_files
    }
