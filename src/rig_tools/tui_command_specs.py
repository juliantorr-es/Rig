from __future__ import annotations

from pathlib import Path


def specs(repo_root: Path) -> dict[str, list[str]]:
    return {
        "refresh_status": ["python", "-m", "rig", "monitor", "snapshot"],
        "doctor": ["python", "-m", "rig", "doctor", "--format", "json"],
        "run": ["python", "-m", "rig", "run", "--task", "{task}", "--provider", "custom-command"],
    }
