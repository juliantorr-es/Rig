# Public Intake Connector Seam

The **Public Intake** concept (CONTEXT.md: intake of proposals/funding from external sources) has connectors as shallow adapters. `GoogleFormsIntakeAdapter`, `GoogleSheetsSyncAdapter`, `GitHubIssueSyncAdapter` each independently normalize external data, and `commands_public_intake.py` instantiates them directly via a hardcoded dict. Delete a connector and nothing concentrates — the hardcoded map just breaks. We need a proper **seam** with a connector registry.

**Status**: superseded by ADR-0006

**Related ADRs**:
- [0003 Governance Engine Deepening](0003-governance-engine-deepening.md) — intake may feed into governance decisions
- [0006 Ingress Interpretation](0006-ingress-interpretation.md) — ingress interpretation owns packet normalization and evidence continuity
- [0007 Workspace Domain Authority](0007-workspace-domain-authority.md) — intake packets may become workspace evidence

## Context

**Connector package (`src/rig/domain/connectors/`)** — 4 files, 801 lines total:
- `base.py` — `PublicIntakeConnector` protocol, `ConnectorResult` dataclass
- `google_forms.py` — Google Forms adapter with `_normalize_response()`
- `google_sheets.py` — Google Sheets adapter with `_normalize_row()`
- `github_issues.py` — GitHub Issues adapter with `_normalize_issue()`

**CLI glue (`src/rig/commands_public_intake.py`)**:
- Lines 37-46: `_get_connector()` with hardcoded dict mapping connector names to classes
- Lines 49-71: `_intake_store_path()`, `_load_intake_packets()` — **packet** store I/O logic
- Lines 117-140: `_save_intake_packet()` — **packet** persistence
- Lines 127-157: `_load_pledges()`, `_list_pledges_store_path()` — **pledge** storage (NOT moved to IntakeStore; separate concern per CONTEXT.md)

**Normalization**: Each connector has `_normalize_*()` method with source-specific field mapping. The fallback pattern (`row.get("Title", row.get("title", ""))`) is intentionally duplicated — this is acceptable locality, not architectural debt.

**Important distinctions (per CONTEXT.md)**:
- **Public Intake Packet**: "someone proposed something" — ingress artifact, part of proposal intake lineage
- **Funding Pledge**: "someone committed resources" — separate lifecycle, governance-sensitive, eventual accounting/audit semantics
- **PublicSyncReceipt**: operational evidence describing synchronization activity, import lineage, connector execution — **NOT** part of IntakeStore

**Architectural decisions for ADR 0005 scope**:
- IntakeStore handles: **packets only**
- Pledge storage: **NOT touched**, remains future extraction candidate
- Sync receipts (`PublicSyncReceipt`): **NOT moved** to IntakeStore, stays in CLI layer (`_save_sync_receipt()`)
  - Rationale: Sync receipts are operational evidence, not ingress persistence. Future EvidenceDomain (ADR 0007) may unify receipt handling.
- This preserves conceptual separation between:
  - Ingress persistence (IntakeStore)
  - Operational evidence (future EvidenceDomain)
  - Funding state (future FundingStore/PledgeStore)

## Decision

This ADR is superseded by ADR 0006. The earlier registry seam proposal is intentionally rejected: connector inventory remains static and private, but routing is owned by ingress interpretation, not a public registry API.

### Legacy IntakeStore Design

```python
# intake_store.py
from pathlib import Path
from typing import Any, Optional, List
from rig.domain.public_intake import PublicIntakePacket

class IntakeStore:
    """Packet persistence only. Does NOT handle pledges (separate concern)."""
    
    def __init__(self, repo_root: Path):
        self._store_path = repo_root / ".build" / "rig" / "public_intake"
        self._packets_path = self._store_path / "packets.jsonl"
    
    def _store_path(self) -> Path:
        """Path to intake store directory."""
        return self._store_path
    
    def load_packets(self, limit: Optional[int] = None) -> List[PublicIntakePacket]:
        """Load intake packets from store. Returns empty list if doesn't exist."""
        # Implementation from _load_intake_packets()
        ...
    
    def save_packet(self, packet: PublicIntakePacket, dry_run: bool = False) -> bool:
        """Save a packet to store. Returns True if wrote (or would write)."""
        # Implementation from _save_intake_packet()
        ...
```

### Legacy Implementation Pattern (Rejected)

```python
# intake_registry.py
from typing import Any, Dict, Optional, Type
from pathlib import Path
from rig.domain.connectors.base import PublicIntakeConnector
from rig.domain.connectors.google_forms import GoogleFormsIntakeAdapter
from rig.domain.connectors.google_sheets import GoogleSheetsSyncAdapter
from rig.domain.connectors.github_issues import GitHubIssueSyncAdapter

# Explicit inventory: registry KNOWS what exists, but does NOT KNOW how they work
_KNOWN_CONNECTORS: Dict[str, Type[PublicIntakeConnector]] = {
    "google_forms": GoogleFormsIntakeAdapter,
    "google_sheets": GoogleSheetsSyncAdapter,
    "github_issues": GitHubIssueSyncAdapter,
}

class IntakeRegistry:
    """Repo-scoped connector registry. Owns inventory and routing, NOT semantics."""
    
    def __init__(self, repo_root: Path, connectors: Optional[Dict[str, Type[PublicIntakeConnector]]] = None):
        self.repo_root = repo_root
        self._connectors = connectors or _KNOWN_CONNECTORS.copy()
    
    @classmethod
    def from_repo_root(cls, repo_root: Path) -> "IntakeRegistry":
        """Factory: per-repo, deterministic, explicit operational lineage."""
        return cls(repo_root)
    
    def get_connector(self, name: str, config: Optional[dict[str, Any]] = None) -> PublicIntakeConnector:
        """Get connector instance. Connector owns its validation — may raise."""
        cls = self._connectors.get(name)
        if cls is None:
            available = ", ".join(sorted(self._connectors.keys()))
            raise ValueError(f"Unknown connector '{name}'. Available: {available}")
        return cls(config)
    
    def list_connectors(self) -> list[str]:
        """List available connector names."""
        return list(self._connectors.keys())
    
    def has_connector(self, name: str) -> bool:
        """Check if connector exists."""
        return name in self._connectors
```

### Architecture Principles
- **Registry owns**: connector inventory, construction routing, deterministic lookup, repo-scoped operational topology
- **Registry does NOT own**: connector semantics, config validation, normalization logic
- **Connector owns**: connector-specific semantics, config schema, validation, normalization defaults, capability interpretation
- **IntakeStore owns**: packet persistence, retrieval (packets ONLY, not pledges)
- **No IntakeNormalizer**: normalization stays connector-local (premature abstraction risk)
- **No decorators**: explicit inventory, no import-time side effects

### Owner vs Authority (per CONTEXT.md)
- **Authority**: Rig owns final decisions (governance, application, commit)
- **Ownership**: Connector owns its config validation; registry owns routing; store owns persistence

## Consequences

**Leverage**: One place to add new connectors (decorator + class). One place for store configuration. Currently: edit hardcoded dict in CLI + create file. After: create file with decorator, add to registry factory.

**Locality**: Connector-specific code in `connectors/*.py`. Store I/O in `intake_store.py`. Normalization stays connector-local. Currently: store logic scattered in CLI glue.

**Testability**: Test connectors through registry interface. Test store via `IntakeStore` directly. Mock registry to return test adapters. Currently: no mocking of connectors.

**Seam**: `PublicIntakeConnector` is a **hypothetical seam** (one adapter each: Google Forms, Google Sheets, GitHub Issues). Becomes **real seam** when test mocks are added (two adapters each).

## Files Involved

### New files
- `src/rig/domain/intake_registry.py` (~60 lines) — connector registry with explicit `_KNOWN_CONNECTORS` dict
- `src/rig/domain/intake_store.py` (~80 lines) — packet I/O

### Modified files
- `src/rig/domain/connectors/base.py` — unchanged (protocol definition)
- `src/rig/domain/connectors/google_forms.py` — unchanged ( connector logic stays local)
- `src/rig/domain/connectors/google_sheets.py` — unchanged
- `src/rig/domain/connectors/github_issues.py` — unchanged

### Simplified files
- `src/rig/commands_public_intake.py` — remove hardcoded `_get_connector()`, `_intake_store_path()`, `_load_intake_packets()`, `_save_intake_packet()`; use `IntakeRegistry` and `IntakeStore`

### Unchanged files
- `src/rig/domain/public_intake.py` — types and helper functions remain

## Migration Path

### Phase 1: Create registry and store
1. Create `intake_store.py` with `IntakeStore` class containing `_intake_store_path()`, `_load_intake_packets()`, `_save_intake_packet()` logic from `commands_public_intake.py`
2. Create `intake_registry.py` with `IntakeRegistry` class, `_KNOWN_CONNECTORS` dict, `from_repo_root()` factory, and methods `get_connector()`, `list_connectors()`, `has_connector()`

### Phase 2: Update CLI to use new modules
3. Replace `_get_connector()` in `commands_public_intake.py` with `IntakeRegistry.from_repo_root(repo_root).get_connector(name, config)`
4. Replace `_intake_store_path()`, `_load_intake_packets()`, `_save_intake_packet()` with `IntakeStore` methods
5. Remove helper functions from `commands_public_intake.py`

### Phase 3: Add test support
6. Create test mock connectors (e.g., `TestGoogleFormsAdapter` in test module)
7. For tests: `IntakeRegistry(repo_root, connectors=test_connectors)` — inject test connector map

**Risk**: Low. Small, self-contained refactor. Affects only public intake flow which is Phase 1/local-first.
