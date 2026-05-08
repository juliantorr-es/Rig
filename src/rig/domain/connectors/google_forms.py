"""Google Forms intake adapter (stub).

This is a STUB connector - it does not actually connect to Google Forms.
It demonstrates the connector interface and produces normalized packets.

Real implementation would require:
- Google API credentials
- OAuth flow
- Actual API calls

For Phase 1, this is intentionally a stub that produces sample data.
Rig remains the authority; Google Forms is a connector only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import uuid

from rig.domain.connectors.base import BasePublicIntakeConnector, ConnectorResult
from rig.domain.public_intake import (
    PublicIntakePacket,
    FUNDING_LIFECYCLE_STATES,
)


@dataclass(frozen=True, slots=True)
class GoogleFormsConfig:
    """Configuration for Google Forms connector.
    
    In a real implementation, this would include:
    - form_id: The Google Form ID
    - service_account_json: Path to service account credentials
    - scopes: Required OAuth scopes
    
    For Phase 1 stub, these are placeholders.
    """
    form_id: str = ""
    spreadsheet_id: str = ""  # Linked spreadsheet for responses
    
    # Not implemented in Phase 1
    # service_account_path: Optional[str] = None
    # api_key: Optional[str] = None


class GoogleFormsIntakeAdapter(BasePublicIntakeConnector):
    """Google Forms intake adapter - STUB implementation.
    
    Produces normalized PublicIntakePacket objects from Google Forms responses.
    Never mutates authority state directly.
    Supports dry-run mode.
    
    Phase 1: Returns sample stub data only.
    """
    
    connector_name: str = "google_forms"
    
    def __init__(self, config: Optional[GoogleFormsConfig] = None):
        self.config = config or GoogleFormsConfig()
    
    def _normalize_response(self, response: dict[str, Any]) -> PublicIntakePacket:
        """Normalize a Google Forms response to a PublicIntakePacket.
        
        In real implementation, this would map form fields to packet fields.
        For Phase 1, this returns a stub packet.
        """
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Extract values from response with safe defaults
        title = str(response.get("title", response.get("Untitled Question", "")))
        description = str(response.get("description", response.get("Tell us more", "")))
        email = str(response.get("email", response.get("Email Address", "")))
        name = str(response.get("name", response.get("Name", "")))
        funding = response.get("funding_request", response.get("requested_funding_usd", 0))
        try:
            funding_usd = int(funding) if funding else 0
        except (ValueError, TypeError):
            funding_usd = 0
        
        # Generate deterministic IDs from response
        response_id = str(response.get("responseId", ""))
        timestamp = str(response.get("timestamp", response.get("createdAt", now)))
        
        return PublicIntakePacket(
            packet_id=f"gf-{response_id[:12]}-{uuid.uuid5(uuid.NAMESPACE_URL, response_id + timestamp).hex[:8]}",
            source="google_forms",
            source_id=response_id,
            raw_payload=response,
            normalizes_to="",
            title=title or "Untitled Proposal",
            description=description or "",
            submitter_email=email,
            submitter_name=name,
            submitted_at=timestamp or now,
            tags=(),
            priority_class="standard",
            requested_funding_usd=funding_usd,
            is_community_requested=response.get("community_requested", False),
            deduplication_key=None,
            lifecycle_state="submitted",
            sync_receipt_id=None,
            imported_at=now,
            dry_run=False,
        )
    
    def _generate_sample_responses(self, count: int = 1) -> list[dict[str, Any]]:
        """Generate sample responses for stub testing.
        
        Phase 1 only: In real implementation, this would fetch from Google Forms API.
        """
        samples = []
        for i in range(count):
            base_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            samples.append({
                "responseId": f"resp_{i:04d}",
                "timestamp": base_timestamp,
                "email": f"submitter{i}@example.com",
                "Name": f"Submitter {i}",
                "title": f"Feature Request: Add widget support {i}",
                "description": f"Please add support for widget type {i} with full customization options.",
                "requested_funding_usd": (i + 1) * 1000,
                "community_requested": i % 3 == 0,  # Every 3rd is community
                "Untitled Question": f"Widget {i} Support",
                "Tell us more": f"This would help my project significantly. I need this for production use case {i}.",
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
        """Import packets from Google Forms.
        
        Phase 1 (stub): Generates sample packets without actual API calls.
        Dry-run mode is always supported.
        """
        from datetime import datetime, timezone
        
        start_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        effective_limit = limit or 10
        
        # Merge config
        effective_config = self.config
        if source_config:
            effective_config = GoogleFormsConfig(
                form_id=source_config.get("form_id", effective_config.form_id),
                spreadsheet_id=source_config.get("spreadsheet_id", effective_config.spreadsheet_id),
            )
        
        # Phase 1: Generate sample responses
        responses = self._generate_sample_responses(count=effective_limit)
        
        # Since filter (stub: just check timestamp string)
        if since:
            responses = [r for r in responses if r.get("timestamp", "") >= since]
        
        normalized: list[PublicIntakePacket] = []
        errors: list[str] = []
        
        for resp in responses[:effective_limit]:
            try:
                packet = self._normalize_response(resp)
                normalized.append(packet)
            except Exception as e:
                errors.append(f"Failed to normalize response {resp.get('responseId', '?')}: {e}")
        
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
        """List available packets from Google Forms.
        
        Phase 1 (stub): Generates sample packets without actual API calls.
        """
        effective_limit = limit or 5
        responses = self._generate_sample_responses(count=effective_limit)
        return tuple(self._normalize_response(r) for r in responses)
