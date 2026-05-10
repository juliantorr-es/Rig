"""IntakeRegistry - Repo-scoped connector registry for public intake.

This module owns connector inventory and routing. It explicitly does NOT own:
- Connector semantics (config validation, normalization)
- Packet persistence (IntakeStore owns this)
- Sync receipts (operational evidence, future EvidenceDomain)
- Pledges (funding concern, future extraction)

Ownership (per CONTEXT.md): IntakeRegistry owns connector inventory and routing.
Authority (per CONTEXT.md): Rig owns final decisions; connectors are advisors only.

Architecture:
- Per-repo: Each repo creates its own registry instance
- Explicit inventory: _KNOWN_CONNECTORS dict is the single source of truth
- No auto-discovery: Connectors must be explicitly listed
- No decorators: Avoids import-time side effects
- Connector ownership: Connectors own their config validation and may raise on invalid config
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Type, cast

from rig.domain.connectors.base import PublicIntakeConnector
from rig.domain.connectors.github_issues import GitHubIssueSyncAdapter, GitHubIssuesConfig
from rig.domain.connectors.google_forms import GoogleFormsIntakeAdapter, GoogleFormsConfig
from rig.domain.connectors.google_sheets import GoogleSheetsSyncAdapter, GoogleSheetsConfig


# Explicit inventory: registry KNOWS what exists, but does NOT KNOW how they work.
# This is inventory knowledge, not semantic knowledge.
_KNOWN_CONNECTORS: Dict[str, Type[PublicIntakeConnector]] = {
    "google_forms": GoogleFormsIntakeAdapter,
    "google_sheets": GoogleSheetsSyncAdapter,
    "github_issues": GitHubIssueSyncAdapter,
}


class IntakeRegistry:
    """Repo-scoped connector registry. Owns inventory and routing, NOT semantics.
    
    Operational topology is explicit and deterministic.
    Connector instantiation may fail (connector owns validation).
    """

    def __init__(
        self,
        repo_root: Path,
        connectors: Optional[Dict[str, Type[PublicIntakeConnector]]] = None
    ):
        """Initialize registry for a repo.
        
        Args:
            repo_root: Path to repository root
            connectors: Optional override connector map (for testing)
        """
        self.repo_root = repo_root
        self._connectors = connectors or _KNOWN_CONNECTORS.copy()

    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "IntakeRegistry":
        """Factory: per-repo, deterministic, explicit operational lineage.
        
        This is the canonical way to get a registry.
        Returns a fully initialized registry with all known connectors.
        """
        return cls(repo_root)

    def get_connector(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> PublicIntakeConnector:
        """Get connector instance by name.
        
        Connector owns its validation — this may raise if config is invalid.
        
        Args:
            name: Connector name (e.g., "google_forms")
            config: Optional connector-specific configuration dict
            
        Returns:
            Connector instance
            
        Raises:
            ValueError: If connector name is unknown
            (Connector may raise its own errors for invalid config)
        """
        cls = self._connectors.get(name)
        if cls is None:
            available = ", ".join(sorted(self._connectors.keys()))
            raise ValueError(f"Unknown connector '{name}'. Available: {available}")
        # Cast generic dict to connector-specific config type
        # Each connector__init__ accepts its own config type as optional first arg
        # At runtime, dict is compatible; at type-check time, we cast
        if config is None:
            return cls()
        return cls(config)  # type: ignore[call-arg]

    def list_connectors(self) -> List[str]:
        """List available connector names."""
        return list(self._connectors.keys())

    def has_connector(self, name: str) -> bool:
        """Check if a connector is available."""
        return name in self._connectors
