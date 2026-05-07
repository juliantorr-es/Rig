from __future__ import annotations

from pathlib import Path
from typing import Any

from rig_tools import orchestration, provider_registry


def load_snapshot(repo_root: Path) -> dict[str, Any]:
    return {
        "jobs": orchestration.list_jobs_summary(repo_root),
        "queue": orchestration.queue_health(repo_root),
        "providers": provider_registry.list_providers(repo_root),
    }
