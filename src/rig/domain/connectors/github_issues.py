"""GitHub Issues sync adapter (stub).

This is a STUB connector - it does not actually connect to GitHub.
It demonstrates the connector interface and produces normalized packets.

Real implementation would require:
- GitHub API credentials or token
- Repository configuration
- Actual API calls to GitHub Issues API

For Phase 1, this is intentionally a stub that produces sample data.
Rig remains the authority; GitHub is a connector only.
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
class GitHubIssuesConfig:
    """Configuration for GitHub Issues connector.
    
    In a real implementation, this would include:
    - owner: Repository owner
    - repo: Repository name
    - token: GitHub API token
    - labels: Labels to filter by
    
    For Phase 1 stub, these are placeholders.
    """
    owner: str = ""
    repo: str = ""
    # token would be sensitive, not stored in config


class GitHubIssueSyncAdapter(BasePublicIntakeConnector):
    """GitHub Issues sync adapter - STUB implementation.
    
    Produces normalized PublicIntakePacket objects from GitHub Issues.
    Never mutates authority state directly.
    Supports dry-run mode.
    
    Phase 1: Returns sample stub data only.
    """
    
    connector_name: str = "github_issues"
    
    def __init__(self, config: Optional[GitHubIssuesConfig] = None):
        self.config = config or GitHubIssuesConfig()
    
    def _normalize_issue(self, issue: dict[str, Any]) -> PublicIntakePacket:
        """Normalize a GitHub Issue to a PublicIntakePacket.
        
        In real implementation, this would map issue fields to packet fields.
        For Phase 1, this returns a stub packet.
        """
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Extract values from issue
        number = issue.get("number", 0)
        title = str(issue.get("title", ""))
        body = str(issue.get("body", ""))
        created_at = str(issue.get("created_at", now))
        updated_at = str(issue.get("updated_at", now))
        
        # Check labels for metadata
        labels = issue.get("labels", [])
        label_names = [str(l.get("name", "")) for l in labels if isinstance(l, dict)]
        
        is_community = "community" in label_names or "community-request" in label_names
        priority = "urgent" if "priority: urgent" in label_names else \
                   "high" if "priority: high" in label_names else \
                   "elevated" if "priority: elevated" in label_names else "standard"
        
        # Parse funding from body or labels
        funding_usd = 0
        for label in label_names:
            if label.startswith("funding:"):
                try:
                    funding_usd = int(label.replace("funding:", "").replace("$", "").replace(",", "").strip())
                except (ValueError, AttributeError):
                    pass
        
        # Generate deterministic ID
        source_id = f"issue_{number}"
        
        return PublicIntakePacket(
            packet_id=f"gh-{source_id[:12]}-{uuid.uuid5(uuid.NAMESPACE_URL, source_id + created_at).hex[:8]}",
            source="github_issues",
            source_id=source_id,
            raw_payload=issue,
            normalizes_to="",
            title=title or "Untitled Issue",
            description=body or "",
            submitter_email=issue.get("user", {}).get("login", ""),
            submitter_name=issue.get("user", {}).get("name", ""),
            submitted_at=created_at,
            tags=tuple(str(l) for l in label_names if l),
            priority_class=priority,
            requested_funding_usd=funding_usd,
            is_community_requested=is_community,
            deduplication_key=None,
            lifecycle_state="submitted",
            sync_receipt_id=None,
            imported_at=now,
            dry_run=False,
        )
    
    def _generate_sample_issues(self, count: int = 1) -> list[dict[str, Any]]:
        """Generate sample issues for stub testing.
        
        Phase 1 only: In real implementation, this would fetch from GitHub API.
        """
        samples = []
        now_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for i in range(count):
            priority_label = "priority: urgent" if i % 5 == 0 else \
                            "priority: high" if i % 4 == 0 else \
                            "priority: elevated" if i % 3 == 0 else None
            funding_label = f"funding: ${(i + 1) * 1000}"
            
            labels = [{"name": "enhancement"}]
            if priority_label:
                labels.append({"name": priority_label})
            labels.append({"name": funding_label})
            if i % 2 == 0:
                labels.append({"name": "community-request"})
            
            samples.append({
                "number": i + 1,
                "title": f"Add feature for use case {i}",
                "body": f"This feature would enable {i} new scenarios.\n\nRequested funding: ${(i + 1) * 1000}",
                "created_at": now_str,
                "updated_at": now_str,
                "state": "open",
                "user": {
                    "login": f"github_user{i}",
                    "name": f"GitHub User {i}",
                },
                "labels": labels,
                "url": f"https://github.com/owner/repo/issues/{i + 1}",
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
        """Import packets from GitHub Issues.
        
        Phase 1 (stub): Generates sample packets without actual API calls.
        Dry-run mode is always supported.
        """
        from datetime import datetime, timezone
        
        start_time = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        effective_limit = limit or 10
        
        # Merge config
        effective_config = self.config
        if source_config:
            effective_config = GitHubIssuesConfig(
                owner=source_config.get("owner", effective_config.owner),
                repo=source_config.get("repo", effective_config.repo),
            )
        
        # Phase 1: Generate sample issues
        issues = self._generate_sample_issues(count=effective_limit * 2)
        
        # Since filter
        if since:
            issues = [i for i in issues if str(i.get("created_at", "")) >= since]
        
        normalized: list[PublicIntakePacket] = []
        errors: list[str] = []
        
        for issue in issues[:effective_limit]:
            try:
                packet = self._normalize_issue(issue)
                normalized.append(packet)
            except Exception as e:
                issue_num = issue.get("number", "?")
                errors.append(f"Failed to normalize issue #{issue_num}: {e}")
        
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
        """List available packets from GitHub Issues.
        
        Phase 1 (stub): Generates sample packets without actual API calls.
        """
        effective_limit = limit or 5
        issues = self._generate_sample_issues(count=effective_limit)
        return tuple(self._normalize_issue(i) for i in issues)
