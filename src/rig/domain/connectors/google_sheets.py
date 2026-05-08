"""Google Sheets sync adapter (stub).

This is a STUB connector - it does not actually connect to Google Sheets.
It demonstrates the connector interface and produces normalized packets.

Real implementation would require:
- Google API credentials
- OAuth flow
- Spreadsheet parsing logic

For Phase 1, this is intentionally a stub that produces sample data.
Rig remains the authority; Google Sheets is a connector only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

from rig.domain.connectors.base import BasePublicIntakeConnector, ConnectorResult
from rig.domain.public_intake import PublicIntakePacket


@dataclass(frozen=True, slots=True)
class GoogleSheetsConfig:
    """Configuration for Google Sheets connector.
    
    In a real implementation, this would include:
    - spreadsheet_id: The Google Sheet ID
    - sheet_name: Name of the sheet to read
    - service_account_json: Path to service account credentials
    
    For Phase 1 stub, these are placeholders.
    """
    spreadsheet_id: str = ""
    sheet_name: str = "Form Responses 1"


class GoogleSheetsSyncAdapter(BasePublicIntakeConnector):
    """Google Sheets sync adapter - STUB implementation.
    
    Produces normalized PublicIntakePacket objects from Google Sheets rows.
    Never mutates authority state directly.
    Supports dry-run mode.
    
    Phase 1: Returns sample stub data only.
    """
    
    connector_name: str = "google_sheets"
    
    def __init__(self, config: Optional[GoogleSheetsConfig] = None):
        self.config = config or GoogleSheetsConfig()
    
    def _normalize_row(self, row: dict[str, Any], row_num: int) -> PublicIntakePacket:
        """Normalize a Google Sheets row to a PublicIntakePacket.
        
        In real implementation, this would map sheet columns to packet fields.
        For Phase 1, this returns a stub packet.
        """
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Extract values from row with safe defaults
        # Column names are typical Google Forms -> Sheets export
        title = str(row.get("Feature Request", row.get("Title", row.get("What feature would you like?", ""))))
        description = str(row.get("Description", row.get("Tell us more", "")))
        email = str(row.get("Email", row.get("Email Address", "")))
        name = str(row.get("Name", row.get("Submitter", "")))
        funding = row.get("Funding Request", row.get("requested_funding_usd", 0))
        community = row.get("Community Request", row.get("community_requested", False))
        timestamp = str(row.get("Timestamp", now))
        
        try:
            funding_usd = int(funding) if funding else 0
        except (ValueError, TypeError):
            funding_usd = 0
        
        is_community = isinstance(community, str) and community.strip().lower() in ("yes", "true", "1") or community is True
        
        # Generate deterministic ID
        row_id = str(row.get("Row", row_num))
        source_id = f"sheet_row_{row_num}"
        
        return PublicIntakePacket(
            packet_id=f"gs-{source_id[:12]}-{uuid.uuid5(uuid.NAMESPACE_URL, source_id + timestamp).hex[:8]}",
            source="google_sheets",
            source_id=source_id,
            raw_payload=row,
            normalizes_to="",
            title=title or "Untitled Proposal",
            description=description or "",
            submitter_email=email,
            submitter_name=name,
            submitted_at=timestamp,
            tags=(),
            priority_class="standard",
            requested_funding_usd=funding_usd,
            is_community_requested=is_community,
            deduplication_key=None,
            lifecycle_state="submitted",
            sync_receipt_id=None,
            imported_at=now,
            dry_run=False,
        )
    
    def _generate_sample_rows(self, count: int = 1) -> list[dict[str, Any]]:
        """Generate sample rows for stub testing.
        
        Phase 1 only: In real implementation, this would fetch from Google Sheets API.
        """
        samples = []
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for i in range(count):
            row_offset = i * 10
            samples.append({
                "Row": i + 2,  # Row 2 is header typically
                "Timestamp": now_str,
                "Email Address": f"sheets_user{i}@example.com",
                "Name": f"Sheets User {i}",
                "What feature would you like?": f"Sheets Integration for dataset {i}",
                "Tell us more": f"Need to import CSV data from Google Sheets. Dataset {i} has {row_offset * 100} rows.",
                "Funding Request": (i + 1) * 500,
                "Community Request": "Yes" if i % 2 == 0 else "No",
                "Title": f"Sheets Feature {i}",
                "Description": f"Full description for sheets feature request {i}.",
            })
        return samples
    
    def import_packets(
        self,
        *,
        source_config: Optional[dict[str, Any]] = None,
        since: Optional[str] = None,
        dry_run: bool = True,
        limit: Optional[int] = None,
    ) -> ConnectorResult:
        """Import packets from Google Sheets.
        
        Phase 1 (stub): Generates sample packets without actual API calls.
        Dry-run mode is always supported.
        """
        from datetime import datetime, timezone
        
        start_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        effective_limit = limit or 10
        
        # Merge config
        effective_config = self.config
        if source_config:
            effective_config = GoogleSheetsConfig(
                spreadsheet_id=source_config.get("spreadsheet_id", effective_config.spreadsheet_id),
                sheet_name=source_config.get("sheet_name", effective_config.sheet_name),
            )
        
        # Phase 1: Generate sample rows
        rows = self._generate_sample_rows(count=effective_limit * 2)  # Generate extra, we'll limit
        
        # Since filter
        if since:
            rows = [r for r in rows if str(r.get("Timestamp", "")) >= since]
        
        normalized: list[PublicIntakePacket] = []
        errors: list[str] = []
        
        for idx, row in enumerate(rows[:effective_limit]):
            try:
                packet = self._normalize_row(row, row_num=idx + 2)  # +2 for header row
                normalized.append(packet)
            except Exception as e:
                row_id = row.get("Row", idx)
                errors.append(f"Failed to normalize row {row_id}: {e}")
        
        end_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        receipt = self._generate_receipt(
            operation="public_intake_import",
            dry_run=dry_run,
            packets=normalized,
            errors=errors,
            start_time=start_time,
            end_time=end_time,
        )
        
        return ConnectorResult(
            connector_name=self.connector_name,
            operation="import",
            dry_run=dry_run,
            packets=tuple(normalized),
            receipt=receipt,
            errors=tuple(errors),
        )
    
    def list_packets(
        self,
        *,
        source_config: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> tuple[PublicIntakePacket, ...]:
        """List available packets from Google Sheets.
        
        Phase 1 (stub): Generates sample packets without actual API calls.
        """
        effective_limit = limit or 5
        rows = self._generate_sample_rows(count=effective_limit)
        return tuple(self._normalize_row(r, i + 2) for i, r in enumerate(rows))
