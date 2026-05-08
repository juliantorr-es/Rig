"""Local connector abstractions for public intake.

Connectors are read-only adapters that:
- Produce normalized PublicIntakePacket objects
- Never mutate authority state directly
- Generate PublicSyncReceipt for sync operations
- Support dry-run mode

External systems are connectors and presentation surfaces only.
Rig remains the authority.
"""

from rig.domain.connectors.base import PublicIntakeConnector, ConnectorResult
from rig.domain.connectors.google_forms import GoogleFormsIntakeAdapter
from rig.domain.connectors.google_sheets import GoogleSheetsSyncAdapter
from rig.domain.connectors.github_issues import GitHubIssueSyncAdapter

__all__ = [
    "PublicIntakeConnector",
    "ConnectorResult",
    "GoogleFormsIntakeAdapter",
    "GoogleSheetsSyncAdapter",
    "GitHubIssueSyncAdapter",
]
