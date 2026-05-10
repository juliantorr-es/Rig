# Governance Engine Deepening

The **Governance Engine** concept is split shallowly: `governance/engine.py` has decision logic mixed with intent evaluation, while `intents/dispatcher.py` has its own preflight and capability checks. Delete `engine.py` and the intent legality logic scatters. We should deepen `GovernanceEngine` to own ALL "is this allowed?" decisions, with `IntentDispatcher` becoming a thin adapter.

**Status**: proposed

## Context

- `src/rig/domain/governance/engine.py` — `GovernanceEngine.evaluate_action_legality()` with 112 lines of conditional logic
- `src/rig/domain/governance/decisions.py` — `GateDecision`, `DecisionReason` types
- `src/rig/domain/intents/dispatcher.py` — `IntentDispatcher` with `_preflight()` doing capability checks
- `src/rig/domain/intent_defs.py` — `Intent` type and simple `IntentHandler`
- No single seam for governance decisions — callers import `GovernanceEngine` directly or go through dispatcher

## Decision

Depen `GovernanceEngine` to own all governance:
- Absorb preflight logic from `IntentDispatcher._preflight()`
- Absorb capability checks
- Own gate evaluation with workspace state, proposal status, evidence validation
- Treat "is this allowed?" as the canonical seam for proposal lifecycle and funding-governance gating
- Expose single interface: `GovernanceEngine.evaluate(intent: Intent, context: EvaluationContext) -> GateDecision`
- `IntentDispatcher` becomes thin adapter: receives intent, calls `GovernanceEngine.evaluate()`, routes to handler if allowed

## Consequences

**Leverage**: One place for all "is X allowed?" logic. Currently `evaluate_action_legality()` (112 lines) and `_preflight()` (~25 lines) contain overlapping logic. After: single `evaluate()` method. Add new gate? One place. Change workspace activation rule? One place.

**Locality**: All governance knowledge in `governance/` package. Currently governance logic in `engine.py` (112 lines) + dispatcher preflight (25 lines) + scattered hardcoded lists. After: all in `engine.py` with clean separation from intent routing.

**Testability**: Test governance through `evaluate()` interface. Currently tests would need to mock both `GovernanceEngine` and `IntentDispatcher._preflight()`. After: mock only `GovernanceEngine.evaluate()`. Test cases: feed various `Intent` + `EvaluationContext` combinations, assert `GateDecision`.

**Seam**: `GovernanceEngine.evaluate()` is the real seam. Two adapters already exist:
- Production: `GovernanceEngine` with real workspace/proposal/evidence checks
- Test: mock engine returning predefined `GateDecision`

**Cross-cutting**: This affects `rig_tools/ui_server.py` and `rig_tools/auth_handlers.py` which currently handle intents. They will need to route through the deepened `GovernanceEngine`.

## Files Involved

### New files
- `src/rig/domain/governance/context.py` — new: `EvaluationContext` dataclass (~20 lines)

### Modified files
- `src/rig/domain/governance/engine.py` — deepened from 112 to ~180 lines: absorb preflight logic, add `evaluate(intent, context)` method
- `src/rig/domain/intents/dispatcher.py` — simplified from 455 to ~380 lines: remove `_preflight()` inlines, delegate to `GovernanceEngine`

### Unchanged files
- `src/rig/domain/governance/decisions.py` — types remain
- `src/rig/domain/intent_defs.py` — types remain

### Updated consumers
- `src/rig_tools/ui_server.py` — update to use new `GovernanceEngine.evaluate()` interface
- `src/rig_tools/auth_handlers.py` — verify no changes needed (uses types only)
- Any direct callers of `GovernanceEngine.evaluate_action_legality()` — migrate to new interface

## Migration Path

### Phase 1: Add new interface (no breaking changes)
1. Create `governance/context.py` with `EvaluationContext` dataclass
2. Add `GovernanceEngine.evaluate(intent: Intent, context: EvaluationContext) -> GateDecision` method to `engine.py`
3. Move `_preflight()` logic from dispatcher to engine as private `_check_preflight()` 

### Phase 2: Update dispatcher
4. Update `IntentDispatcher._preflight()` to call `GovernanceEngine.evaluate()` internally
5. Update `IntentDispatcher.dispatch()` to use new governance check

### Phase 3: Migrate direct callers
6. Update `rig_tools/ui_server.py` to use new interface
7. Update any other direct `evaluate_action_legality()` callers

### Phase 4: Cleanup
8. Deprecate `evaluate_action_legality()` with warning, point to `evaluate()`
9. Remove old method once all callers migrated

**Risk**: Medium. Affects intent handling flow. Test with UI server and various intent types.
