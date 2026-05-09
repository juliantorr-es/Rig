# Public Intake Connector Seam

The **Public Intake** concept (CONTEXT.md: intake of proposals/funding from external sources) has connectors as shallow adapters. `GoogleFormsIntakeAdapter`, `GoogleSheetsSyncAdapter`, `GitHubIssueSyncAdapter` each duplicate normalization logic, and `commands_public_intake.py` instantiates them directly by string name. Delete a connector and nothing concentrates. We need a proper **seam** with a connector registry.

**Status**: proposed

## Context

- `src/rig/domain/public_intake.py` — 500+ lines: types (packets, pledges, sponsors), lifecycle states, aggregation helpers
- `src/rig/domain/connectors/base.py` — `PublicIntakeConnector` protocol
- `src/rig/domain/connectors/google_forms.py` — Google Forms adapter
- `src/rig/domain/connectors/google_sheets.py` — Google Sheets adapter  
- `src/rig/domain/connectors/github_issues.py` — GitHub Issues adapter
- `src/rig/commands_public_intake.py` — CLI glue with hardcoded connector map, store path logic
- Each connector normalizes external data to `PublicIntakePacket` independently

## Decision

Create a proper **seam** with:
- **ConnectorRegistry** module that owns connector discovery and instantiation
  - Interface: `ConnectorRegistry.get_connector(name: str, config: Optional[dict]) -> PublicIntakeConnector`
  - Interface: `ConnectorRegistry.list_connectors() -> List[str]`
  - Interface: `ConnectorRegistry.register(name: str, connector_class: Type) -> None`
- ** connectors stay as adapters** plugged into the registry
- **IntakeNormalizer** module that owns shared normalization logic
  - All connectors delegate normalization to this shared module
  - Reduces duplication across adapters
- Move store path logic and packet persistence into **IntakeStore** module (separate concern from connectors)

## Consequences

**Leverage**: One place to add new connectors. One place to configure connector defaults. Shared normalization logic reused.

**Locality**: Connector-specific code in adapters. Shared normalization in one place. Store logic in one place.

**Testability**: Test connectors through registry interface. Test normalization separately. Mock connectors for integration tests.

**Seam**: `PublicIntakeConnector` is the real seam. Two adapters per connector type (production + test mock) justifies the interface.

## Files Involved

- `src/rig/domain/intake_registry.py` — new: connector registry (seam owner)
- `src/rig/domain/intake_normalizer.py` — new: shared normalization logic
- `src/rig/domain/intake_store.py` — new: packet persistence
- `src/rig/domain/connectors/base.py` — unchanged (protocol definition)
- `src/rig/domain/connectors/*.py` — simplified: remove duplicate normalization, use `IntakeNormalizer`
- `src/rig/commands_public_intake.py` — simplified: use registry, not hardcoded map
- `src/rig/domain/public_intake.py` — types remain, normalization logic moves to `intake_normalizer.py`

## Migration Path

1. Create `IntakeNormalizer` with shared normalization logic
2. Update each connector to use normalizer
3. Create `ConnectorRegistry` with self-registration
4. Update each connector to self-register
5. Create `IntakeStore` for packet persistence
6. Update CLI commands to use registry
7. Remove hardcoded connector map from commands
8. Add test adapters for each connector type
