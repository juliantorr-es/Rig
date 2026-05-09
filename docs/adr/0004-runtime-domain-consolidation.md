# Runtime Domain Consolidation

The **Runtime** concept (execution environment for agents/models) is defined in CONTEXT.md but split across 8+ shallow modules. `runtime.py` defines types, `runtime_stream.py` handles streaming, `runtime_websocket.py` handles WebSocket, `runtime_supervisor.py` supervises — all tightly coupled. Delete `runtime.py` and types break everywhere but no complexity concentrates. We should create a **RuntimeDomain** that owns the complete runtime lifecycle behind narrow interfaces.

**Status**: proposed

## Context

- `src/rig/domain/runtime.py` — 600+ lines of domain types (provider kinds, capability kinds, status enums)
- `src/rig/domain/runtime_stream.py` — 300+ lines of stream event models
- `src/rig/domain/runtime_websocket.py` — WebSocket integration with stream events
- `src/rig/domain/runtime_supervisor.py` — process supervision
- `src/rig/domain/runtime_projection.py` — runtime-specific projections
- `src/rig/domain/runtime_reconciliation.py` — runtime state reconciliation
- `src/rig/domain/runtime_tools.py` — tool execution support
- Tight coupling: websocket imports stream, stream knows about supervisor, etc.

## Decision

Create a **RuntimeDomain** deep module that:
- Owns all runtime types (providers, capabilities, invocations, proposals)
- Owns stream lifecycle: create, append events, complete, fail
- Owns supervision: start process, monitor, collect output, handle timeouts
- Owns WebSocket integration as internal seam (runtime can stream without WebSocket)
- Exposes interfaces:
  - `RuntimeDomain.create_stream(config: RuntimeConfig) -> StreamHandle`
  - `RuntimeDomain.submit_proposal(proposal: RuntimeProposal) -> ProposalDecision`
  - `RuntimeDomain.get_projection(stream_id: str) -> RuntimeProjection`
  - `RuntimeDomain.get_stream_events(stream_id: str, since_sequence: int) -> List[StreamEvent]`
- Internal modules become private implementation

## Consequences

**Leverage**: UI/WebSocket code calls one place for all runtime operations. Adding new runtime provider type: one place. Changing stream buffer limits: one place.

**Locality**: All runtime-specific knowledge in one module. Bug in stream event ordering? Fix in one place. Change in supervision timeout logic? One place.

**Testability**: Test runtime through domain interface. Create stream, submit proposals, verify projection. No need to mock WebSocket internals — test through `get_projection()` and `get_stream_events()`.

**Seam**: WebSocket becomes internal adapter. Real seam is the `RuntimeDomain` interface. Two adapters: production (with real subprocess) and test (in-memory mock).

## Files Involved

- `src/rig/domain/runtime_domain.py` — new deep module (public interface)
- `src/rig/domain/runtime_domain/_types.py` — internal types
- `src/rig/domain/runtime_domain/_stream.py` — internal stream management
- `src/rig/domain/runtime_domain/_supervisor.py` — internal supervision
- `src/rig/domain/runtime_domain/_websocket.py` — internal WebSocket adapter
- `src/rig/domain/runtime_domain/_projection.py` — internal projection building
- Existing `runtime*.py` files — deprecated, types/functionality move to new package

## Migration Path

1. Create new `runtime_domain` package with public interface
2. Move types from `runtime.py` into `_types.py`
3. Move stream logic from `runtime_stream.py` into `_stream.py`
4. Wire supervisor, WebSocket, projection as internal modules
5. Expose public interface methods
6. Update all consumers (CLI commands, UI handlers, tests) to use new interface
7. Deprecate old modules
8. Delete old modules once migrated
