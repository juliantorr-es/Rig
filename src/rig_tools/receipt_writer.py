import json
import uuid
from pathlib import Path
from typing import Dict, Any, List

class ReceiptWriter:
    def __init__(self, repo_root: Path):
        self.receipt_dir = repo_root / ".build" / "rig" / "receipts"
        self.receipt_dir.mkdir(parents=True, exist_ok=True)

    def write_receipt(self, workspace_id: str, before: str, after: str, commands: List[str], status: str) -> Path:
        receipt_id = uuid.uuid4().hex[:8]
        receipt_path = self.receipt_dir / f"{workspace_id}_run.json"
        receipt = {
            "receipt_id": receipt_id,
            "workspace_id": workspace_id,
            "worktree_hash_before": before,
            "worktree_hash_after": after,
            "commands_executed": commands,
            "status": status,
            "authoritative": True
        }
        receipt_path.write_text(json.dumps(receipt, indent=2))
        return receipt_path
