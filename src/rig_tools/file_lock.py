from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from rig_tools.atomic_io import lock_file


@contextmanager
def job_store_lock(repo_root: Path, *, timeout: float = 10.0) -> Iterator[None]:
    with lock_file(repo_root / ".build" / "rig" / "jobs" / ".lock", timeout=timeout):
        yield
