"""IntakeStore - Packet persistence for public intake.

This module owns packet persistence only. It explicitly does NOT handle:
- Pledges (separate funding concern, future extraction)
- Sync receipts (operational evidence, future EvidenceDomain)

Ownership (per CONTEXT.md): IntakeStore owns ingress packet persistence.
Authority (per CONTEXT.md): Rig owns final decisions; this store is advisory only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional

from rig.domain.public_intake import PublicIntakePacket


class IntakeStore:
    """repo-scoped storage for PublicIntakePacket objects.
    
    Persists packets to .build/rig/public_intake/packets.jsonl
    Advisory only - does not make external systems authoritative.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._store_path = repo_root / ".build" / "rig" / "public_intake"
        self._packets_path = self._store_path / "packets.jsonl"

    @property
    def store_path(self) -> Path:
        """Path to the intake store directory."""
        return self._store_path

    @property
    def packets_path(self) -> Path:
        """Path to the packets JSONL file."""
        return self._packets_path

    def load_packets(self, limit: Optional[int] = None) -> List[PublicIntakePacket]:
        """Load intake packets from store.
        
        Returns empty list if store doesn't exist.
        Read-only operation.
        Advisory only.
        """
        if not self._packets_path.exists():
            return []

        packets: List[PublicIntakePacket] = []
        try:
            with open(self._packets_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        packets.append(PublicIntakePacket(**data))
                    except (json.JSONDecodeError, TypeError, KeyError):
                        # Skip malformed lines
                        continue

                    if limit and len(packets) >= limit:
                        break
        except (OSError, IOError):
            pass

        return packets

    def save_packet(self, packet: PublicIntakePacket, dry_run: bool = False) -> bool:
        """Save a packet to store.
        
        If dry_run=True, does not write.
        Returns True if wrote (or would write), False otherwise.
        Advisory only - does not persist authority state.
        """
        if dry_run:
            return True

        try:
            self._store_path.mkdir(parents=True, exist_ok=True)
            with open(self._packets_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(packet.to_dict()) + "\n")
            return True
        except (OSError, IOError):
            return False

    def load_all(self) -> List[PublicIntakePacket]:
        """Load all packets with no limit. Convenience wrapper."""
        return self.load_packets(limit=None)
