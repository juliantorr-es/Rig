"""Base connector abstraction for public intake.

Connectors are read-only adapters that produce normalized packets.
They never mutate authority state directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable
import uuid

from rig.domain.public_intake import (
    PublicIntakePacket,
    PublicSyncReceipt,
    ProposalFundingState,
)


@dataclass(frozen=True, slots=True)
class ConnectorResult:
    """Result of a connector sync operation.
    
    Pure data - does not create files or persist state.
    """
    connector_name: str
    operation: str
    dry_run: bool
    packets: tuple[PublicIntakePacket, ...]
    receipt: PublicSyncReceipt
    errors: tuple[str, ...] = ()
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@runtime_checkable
class PublicIntakeConnector(Protocol):
    """Protocol for public intake connectors.
    
    Connectors MUST:
    - Produce normalized PublicIntakePacket objects
    - Never mutate authority state directly
    - Generate PublicSyncReceipt for sync operations
    - Support dry-run mode
    - Be deterministic and side-effect free
    """
    
    connector_name: str
    
    def import_packets(
        self,
        *,
        source_config: Optional[dict[str, Any]] = None,
        since: Optional[str] = None,
        dry_run: bool = True,
        limit: Optional[int] = None,
    ) -> ConnectorResult:
        """Import packets from external source.
        
        Args:
            source_config: Connector-specific configuration
            since: Only import items newer than this timestamp
            dry_run: If True, do not persist anything
            limit: Maximum number of items to import
            
        Returns:
            ConnectorResult with packets and receipt
            
        Side effects:
            NONE when dry_run=True
            May write to local intake store when dry_run=False (still advisory only)
        """
        ...
    
    def list_packets(
        self,
        *,
        source_config: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> tuple[PublicIntakePacket, ...]:
        """List available packets from external source.
        
        Read-only. Does not mutate state.
        """
        ...


class BasePublicIntakeConnector:
    """Base implementation helper for connectors.
    
    Subclasses should override import_packets and list_packets.
    """
    
    connector_name: str = "base"
    
    def _generate_receipt(
        self,
        operation: str,
        dry_run: bool,
        packets: list[PublicIntakePacket],
        errors: list[str],
        start_time: str,
        end_time: str = "",
    ) -> PublicSyncReceipt:
        """Generate a sync receipt for a connector operation."""
        return PublicSyncReceipt(
            receipt_id=f"sync-{self.connector_name}-{uuid.uuid4().hex[:8]}",
            operation=operation,
            connector=self.connector_name,
            start_time=start_time,
            end_time=end_time,
            items_processed=len(packets),
            items_created=len(packets),
            dry_run=dry_run,
            status="completed" if not errors else "failed",
            error_summary="; ".join(errors) if errors else "",
            packet_ids=tuple(p.packet_id for p in packets),
        )
    
    def import_packets(
        self,
        *,
        source_config: Optional[dict[str, Any]] = None,
        since: Optional[str] = None,
        dry_run: bool = True,
        limit: Optional[int] = None,
    ) -> ConnectorResult:
        raise NotImplementedError(f"{self.__class__.__name__}.import_packets not implemented")
    
    def list_packets(
        self,
        *,
        source_config: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> tuple[PublicIntakePacket, ...]:
        raise NotImplementedError(f"{self.__class__.__name__}.list_packets not implemented")
